"""
统一关键事件检测模块 (Unified Key Event Detection)

根据设计文档 `design/关键事件判定方案.md`，提供四种关键事件的判定：
  - 首开纪录 (First Goal)
  - 绝平球 (Equalizer)
  - 制胜球 (Winning Goal) — 仅当分差=1
  - 绝杀 (Late Winner) — 制胜球 + 最后5分钟

同时检测超级替补 (Super Sub)、点球进球者、点球大战进球/射失。

所有调用方 (v6 / 旧版 player_insights / signals) 均通过此模块统一判定。
"""

from __future__ import annotations

from dataclasses import dataclass, field

# 点球大战事件 detail 值
PSO_GOAL = "pen_shootout_goal"
PSO_MISS = "pen_shootout_miss"


@dataclass
class KeyEventResult:
    """关键事件检测结果"""
    # 首开纪录球员列表（平局时双方各1人，分胜负时1人）
    first_goal_scorers: list[str] = field(default_factory=list)

    # 绝平球球员（平局且扳平球在最后5分钟）
    equalizer_scorer: str | None = None

    # 制胜球球员（分差=1时的致胜球）
    winning_goal_scorer: str | None = None

    # 绝杀球员（制胜球 + 最后5分钟）
    late_winner_scorer: str | None = None

    # 超级替补 {player_name: diff_minutes}
    super_sub_scorers: dict[str, int] = field(default_factory=dict)

    # 点球进球者（常规时间/加时赛点球）
    penalty_scorers: list[str] = field(default_factory=list)

    # 点球大战进球者
    pen_shootout_scorers: list[str] = field(default_factory=list)

    # 点球大战射失者
    pen_shootout_missers: list[str] = field(default_factory=list)


def _get_match_end_minute(periods: list[dict]) -> int:
    """
    根据 period 数据判断比赛结束时间。
    - sort_order <= 2: 常规时间 90 分钟
    - sort_order >= 3 且 < 5: 有加时赛，120 分钟
    - sort_order == 5: 有点球大战，足球比赛在加时结束时终止 → 120 分钟
    """
    max_sort = 0
    for pd in periods:
        so = pd.get("sort_order", 0)
        if so > max_sort:
            max_sort = so
    if max_sort >= 3:
        return 120
    return 90


def _has_extra_time(periods: list[dict]) -> bool:
    """是否存在加时赛（sort_order=3 或 4）"""
    for pd in periods:
        if pd.get("sort_order", 0) in (3, 4):
            return True
    return False


# ═══════════════════════════════════════════════════════════════
# 统一入口
# ═══════════════════════════════════════════════════════════════

def detect_key_events(
    goals: list[dict],
    subs: list[dict],
    home_team_id: int,
    away_team_id: int,
    score_home: int,
    score_away: int,
    periods: list[dict] | None = None,
) -> KeyEventResult:
    """
    统一关键事件检测。

    Args:
        goals: 进球事件列表，每个 dict 需含:
            player_name, team_id, time_elapsed (int), period_id (int),
            is_penalty (bool, 可选)
        subs: 换人事件列表，每个 dict 需含:
            player_in (换上球员名), player_out (换下球员名), minute (int)
        home_team_id: 主队 ID
        away_team_id: 客队 ID
        score_home: 主队最终比分
        score_away: 客队最终比分
        periods: period 列表 (含 sort_order)，用于判断加时。为 None 则默认 90 分钟。

    Returns:
        KeyEventResult
    """
    result = KeyEventResult()
    periods = periods or []

    # ── 分离点球大战事件 ──
    # pen_shootout 事件不参与正常进球/制胜球/绝平球判定
    regular_goals: list[dict] = []
    for g in goals:
        detail = g.get("detail", "")
        if detail == PSO_GOAL:
            result.pen_shootout_scorers.append(g.get("player_name", ""))
        elif detail == PSO_MISS:
            result.pen_shootout_missers.append(g.get("player_name", ""))
        else:
            regular_goals.append(g)

    # ── 基础信息 ──
    end_minute = _get_match_end_minute(periods)
    is_draw = score_home == score_away
    margin = abs(score_home - score_away)
    winner_is_home = score_home > score_away

    # ── 按时间排序全部正常进球 ──
    sorted_goals = sorted(regular_goals, key=lambda g: (g.get("period_id", 0), g.get("time_elapsed", 0)))

    # ═══════════════════════════════════════
    # 1. 首开纪录
    # ═══════════════════════════════════════
    if sorted_goals:
        if is_draw:
            # 平局：双方各自的首球
            seen_teams: set[int] = set()
            for g in sorted_goals:
                tid = g.get("team_id", 0)
                if tid not in seen_teams:
                    seen_teams.add(tid)
                    result.first_goal_scorers.append(g.get("player_name", ""))
        else:
            # 分胜负：获胜方的第一球
            winner_id = home_team_id if winner_is_home else away_team_id
            for g in sorted_goals:
                if g.get("team_id", 0) == winner_id:
                    result.first_goal_scorers.append(g.get("player_name", ""))
                    break

    # ═══════════════════════════════════════
    # 2. 绝平球
    #    条件：比赛平局，扳平球在最后 5 分钟
    # ═══════════════════════════════════════
    if is_draw and score_home > 0:
        h, a = 0, 0
        for g in sorted_goals:
            tid = g.get("team_id", 0)
            if tid == home_team_id:
                h += 1
            else:
                a += 1
            # 当比分被扳平时（h == a），检查时间
            if h == a:
                if g.get("time_elapsed", 0) >= end_minute - 5:
                    result.equalizer_scorer = g.get("player_name", "")

    # ═══════════════════════════════════════
    # 3. 制胜球
    #    条件：分差 == 1，胜方最后一次领先的进球
    # ═══════════════════════════════════════
    if not is_draw and margin == 1:
        h, a = 0, 0
        last_winner_goal = None
        for g in sorted_goals:
            tid = g.get("team_id", 0)
            if tid == home_team_id:
                h += 1
                if winner_is_home and h > a:
                    last_winner_goal = g
            else:
                a += 1
                if not winner_is_home and a > h:
                    last_winner_goal = g
        if last_winner_goal:
            result.winning_goal_scorer = last_winner_goal.get("player_name", "")

            # ═══════════════════════════════════════
            # 4. 绝杀 = 制胜球 + 最后 5 分钟
            # ═══════════════════════════════════════
            if last_winner_goal.get("time_elapsed", 0) >= end_minute - 5:
                result.late_winner_scorer = last_winner_goal.get("player_name", "")

    # ═══════════════════════════════════════
    # 5. 超级替补 — 上场后 5 分钟内进球
    # ═══════════════════════════════════════
    for s in subs:
        player_in = s.get("player_in", "")
        sub_minute = s.get("minute", 0) or s.get("time_elapsed", 0)
        if not player_in or sub_minute <= 0:
            continue
        pin_lower = player_in.strip().lower()
        for g in sorted_goals:
            gn = (g.get("player_name", "") or "").strip().lower()
            if gn == pin_lower:
                diff = g.get("time_elapsed", 0) - sub_minute
                if 1 <= diff <= 5:
                    result.super_sub_scorers[player_in.strip()] = diff
                    break  # 一个替补最多算一次

    # ═══════════════════════════════════════
    # 6. 点球进球者
    # ═══════════════════════════════════════
    for g in sorted_goals:
        if g.get("is_penalty", False):
            result.penalty_scorers.append(g.get("player_name", ""))

    return result
