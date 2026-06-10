"""
战术分析引擎 — 四层因果模型计算

Layer 1: 战术选择维度值 + match-relative Gap（含控球率 + 传球量）
Layer 2: 比赛走势（节奏切换、PPDA、关键事件冲击）
Layer 3: 效果判定（维度 ROI、攻防执行分）
Layer 4: 教练博弈（克制链、换人效果）

输出符合 design/战术分析板块设计-v2.md 第 8.1 节的 JSON 结构。
"""

from __future__ import annotations

from typing import Any

from src.collector.api_client import RawMatchData
from src.engine.metrics import _stat

EPS = 1e-9

# 正确的 stat key 映射
KEY_PASSES = "Total passes"
KEY_LONG = "Long Balls"
KEY_CROSSES = "Crosses"
KEY_SHOTS = "Total Shots"
KEY_TACKLES = "Tackles"
KEY_INTERCEPTIONS = "Interceptions"
KEY_FOULS = "Fouls"
KEY_HEADERS = "Successful Headers"
KEY_SHOTS_IB = "Shots insidebox"
KEY_SHOTS_OB = "Shots outsidebox"
KEY_BLOCKED = "Blocked Shots"
KEY_PASS_PCT = "Passes %"
KEY_POSSESSION = "Ball Possession"


def _safe_div(a: float, b: float) -> float:
    return a / b if b and abs(b) > EPS else 0.0


def _gap(high: float, low: float) -> float:
    if abs(high) < EPS or abs(low) < EPS:
        return 1.0
    return max(high, low) / max(min(high, low), EPS)


# ═══════════════════════════════════════════════════════════════
# Layer 1: 战术选择维度
# ═══════════════════════════════════════════════════════════════

class _TeamDim:
    """单队维度计算结果。"""
    def __init__(self, long_ball: float, cross_r: float, final_third: float,
                 forward_r: float, pps: float, ppda: float, high_press: float,
                 cs_ratio: float, possession: float, pass_vol: int, shots: int):
        self.long_ball_ratio = round(long_ball, 3)
        self.cross_ratio = round(cross_r, 3)
        self.final_third_pass_ratio = round(final_third, 3)
        self.forward_ratio = round(forward_r, 3)
        self.passes_per_shot = round(pps, 1)
        self.ppda = round(ppda, 1)
        self.high_press_ratio = round(high_press, 3)
        self.clearance_ratio = round(cs_ratio, 1)
        self.possession_pct = round(possession, 1)
        self.pass_volume = pass_vol
        self.shots_count = shots

    def to_dict(self) -> dict:
        return {
            "long_ball_ratio": self.long_ball_ratio,
            "cross_ratio": self.cross_ratio,
            "final_third_pass_ratio": self.final_third_pass_ratio,
            "forward_ratio": self.forward_ratio,
            "passes_per_shot": self.passes_per_shot,
            "ppda": self.ppda,
            "high_press_ratio": self.high_press_ratio,
            "clearance_ratio": self.clearance_ratio,
            "possession_pct": self.possession_pct,
            "pass_volume": self.pass_volume,
        }


def _compute_team_dim(raw: RawMatchData, team: str, opp: str) -> dict:
    s = raw.home_stats if team == "home" else raw.away_stats
    opp_s = raw.home_stats if opp == "home" else raw.away_stats

    passes = int(float(_stat(s, KEY_PASSES, default=1)))
    long_balls = float(_stat(s, KEY_LONG, default=0))
    crosses = float(_stat(s, KEY_CROSSES, default=0))
    shots = int(float(_stat(s, KEY_SHOTS, default=1)))
    tackles = float(_stat(s, KEY_TACKLES, default=0))
    interceptions = float(_stat(s, KEY_INTERCEPTIONS, default=0))
    fouls = float(_stat(s, KEY_FOULS, default=0))
    blocked = float(_stat(s, KEY_BLOCKED, default=0))
    opp_shots = float(_stat(opp_s, KEY_SHOTS, default=1))
    opp_passes = float(_stat(opp_s, KEY_PASSES, default=1))
    possession = float(_stat(s, KEY_POSSESSION, default=50))

    players = raw.home_players if team == "home" else raw.away_players
    final_third_pass = sum(getattr(p, "passes_final_third", 0) or 0 for p in players)
    long_balls_won = long_balls * 0.55
    forward_pass = final_third_pass + long_balls_won

    long_ball_ratio = _safe_div(long_balls, passes)
    cross_r = _safe_div(crosses, passes)
    final_third_r = _safe_div(final_third_pass, passes)
    forward_r = _safe_div(forward_pass, passes)
    pps = _safe_div(passes, max(shots, 1))
    ppda = _safe_div(opp_passes, tackles + interceptions + fouls)
    high_press = _safe_div(tackles, max(opp_passes, 1))
    cs_ratio = _safe_div(blocked, max(opp_shots, 1))

    return {
        "long_ball_ratio": round(long_ball_ratio, 3),
        "cross_ratio": round(cross_r, 3),
        "final_third_pass_ratio": round(final_third_r, 3),
        "forward_ratio": round(forward_r, 3),
        "passes_per_shot": round(pps, 1),
        "ppda": round(ppda, 1),
        "high_press_ratio": round(high_press, 3),
        "clearance_ratio": round(cs_ratio, 1),
        "possession_pct": round(possession, 1),
        "pass_volume": passes,
    }


def compute_tactical_raw(raw: RawMatchData) -> dict:
    """计算球队维度原始值。"""
    home_dims = _compute_team_dim(raw, "home", "away")
    away_dims = _compute_team_dim(raw, "away", "home")

    dim_keys = ["long_ball_ratio", "cross_ratio", "final_third_pass_ratio",
                "forward_ratio", "passes_per_shot", "ppda",
                "high_press_ratio", "clearance_ratio",
                "possession_pct", "pass_volume"]

    home_rel = {}
    away_rel = {}
    for k in dim_keys:
        g = _gap(home_dims[k], away_dims[k])
        gk = k.replace("_ratio", "_gap").replace("_per_shot", "").replace("_pct", "").replace("_volume", "")
        if not gk.endswith("_gap"):
            gk = gk + "_gap"
        home_rel[gk] = round(g, 2)
        away_rel[gk] = round(g, 2)

    return {
        "home": {"tactical_raw": home_dims, "match_relative": home_rel},
        "away": {"tactical_raw": away_dims, "match_relative": away_rel},
    }


# ═══════════════════════════════════════════════════════════════
# Layer 2: 比赛走势
# ═══════════════════════════════════════════════════════════════

def _calc_shot_segments(raw: RawMatchData) -> dict:
    """6 个 15 分钟窗口射门统计。从 timeline 数据读取（type_id 569=射正, 570=射偏）。
    自动过滤非正赛时段（加时赛/点球大战）的事件。
    同时计算窗口级 xG 和 xGOT（团队均摊法）。
    """
    tl = raw.timeline if isinstance(raw.timeline, list) else []
    from collections import Counter
    pid_counts = Counter(
        (e.get("period_id", 0) if isinstance(e, dict) else getattr(e, "period_id", 0))
        for e in tl
    )
    top_pids = {pid for pid, _ in pid_counts.most_common(2)} if len(pid_counts) >= 2 else set(pid_counts)

    windows = [(0, 15), (15, 30), (30, 45), (45, 60), (60, 75), (75, 999)]
    h_total = [0] * 6
    h_on = [0] * 6
    h_off = [0] * 6
    a_total = [0] * 6
    a_on = [0] * 6
    a_off = [0] * 6
    home_id = raw.home_team.id
    away_id = raw.away_team.id
    for e in tl:
        ti = e.get("type_id", 0) if isinstance(e, dict) else getattr(e, "type_id", 0)
        if ti not in (569, 570):
            continue
        pid = e.get("period_id", 0) if isinstance(e, dict) else getattr(e, "period_id", 0)
        if pid not in top_pids:
            continue
        minute = e.get("minute", 0) if isinstance(e, dict) else getattr(e, "minute", 0)
        idx = -1
        for i, (lo, hi) in enumerate(windows):
            if lo <= minute < hi:
                idx = i
                break
        if idx < 0:
            continue
        tid = e.get("participant_id", 0) if isinstance(e, dict) else getattr(e, "participant_id", 0)
        is_on = (ti == 569)
        if tid == home_id:
            h_total[idx] += 1
            if is_on:
                h_on[idx] += 1
            else:
                h_off[idx] += 1
        elif tid == away_id:
            a_total[idx] += 1
            if is_on:
                a_on[idx] += 1
            else:
                a_off[idx] += 1

    # 团队级 xG / xGOT per shot
    h_xg = sum(getattr(p, "xg", 0) or 0 for p in raw.home_players)
    a_xg = sum(getattr(p, "xg", 0) or 0 for p in raw.away_players)
    h_xgot = sum(getattr(p, "xgot", 0) or 0 for p in raw.home_players)
    a_xgot = sum(getattr(p, "xgot", 0) or 0 for p in raw.away_players)
    h_shots_on_total = sum(getattr(p, "shots_on", 0) or 0 for p in raw.home_players)
    a_shots_on_total = sum(getattr(p, "shots_on", 0) or 0 for p in raw.away_players)

    # 回退：当 timeline 不含射门事件时（如 CSL 数据），从 stats 取总量并均摊到窗口
    if sum(h_total) == 0 and sum(a_total) == 0:
        h_total_shots = int(_stat(raw.home_stats, KEY_SHOTS, default=0))
        a_total_shots = int(_stat(raw.away_stats, KEY_SHOTS, default=0))
        h_on_shots = int(_stat(raw.home_stats, "Shots on Goal", default=0))
        a_on_shots = int(_stat(raw.away_stats, "Shots on Goal", default=0))
        # Also try player-aggregated data if available
        if h_total_shots == 0:
            h_total_shots = h_shots_on_total  # fallback
        if a_total_shots == 0:
            a_total_shots = a_shots_on_total
        # Distribute evenly across 6 windows
        if h_total_shots > 0:
            base = h_total_shots // 6
            rem = h_total_shots % 6
            for i in range(6):
                h_total[i] = base + (1 if i < rem else 0)
            h_on_shots = min(h_on_shots, h_total_shots)
            base_on = h_on_shots // 6
            rem_on = h_on_shots % 6
            for i in range(6):
                h_on[i] = base_on + (1 if i < rem_on else 0)
            h_off = [h_total[i] - h_on[i] for i in range(6)]
        if a_total_shots > 0:
            base = a_total_shots // 6
            rem = a_total_shots % 6
            for i in range(6):
                a_total[i] = base + (1 if i < rem else 0)
            a_on_shots = min(a_on_shots, a_total_shots)
            base_on = a_on_shots // 6
            rem_on = a_on_shots % 6
            for i in range(6):
                a_on[i] = base_on + (1 if i < rem_on else 0)
            a_off = [a_total[i] - a_on[i] for i in range(6)]

    h_xg_per = h_xg / max(sum(h_total), 1)
    a_xg_per = a_xg / max(sum(a_total), 1)
    h_xgot_per = h_xgot / max(h_shots_on_total, 1)
    a_xgot_per = a_xgot / max(a_shots_on_total, 1)

    h_xg_w = [round(h_total[i] * h_xg_per, 3) for i in range(6)]
    a_xg_w = [round(a_total[i] * a_xg_per, 3) for i in range(6)]
    h_xgot_w = [round(h_on[i] * h_xgot_per, 3) for i in range(6)]
    a_xgot_w = [round(a_on[i] * a_xgot_per, 3) for i in range(6)]

    return {
        "home": h_total,
        "away": a_total,
        "home_on": h_on,
        "away_on": a_on,
        "home_off": h_off,
        "away_off": a_off,
        "home_xg": h_xg_w,
        "away_xg": a_xg_w,
        "home_xgot": h_xgot_w,
        "away_xgot": a_xgot_w,
        "home_xg_total": round(h_xg, 3),
        "away_xg_total": round(a_xg, 3),
        "home_xgot_total": round(h_xgot, 3),
        "away_xgot_total": round(a_xgot, 3),
    }


def _calc_ppda_full(raw: RawMatchData) -> dict:
    """全场 PPDA（不虚假均分到窗口）。"""
    def _ppda(team: str, opp: str) -> dict:
        s = raw.home_stats if team == "home" else raw.away_stats
        opp_s = raw.home_stats if opp == "home" else raw.away_stats
        tk = float(_stat(s, KEY_TACKLES, default=0))
        intercept = float(_stat(s, KEY_INTERCEPTIONS, default=0))
        fl = float(_stat(s, KEY_FOULS, default=0))
        opp_p = float(_stat(opp_s, KEY_PASSES, default=1))
        ppda = round(opp_p / max(tk + intercept + fl, 1), 1)
        return {
            "full_match": ppda,
            "note": "全场均值；事件数据不支持逐窗口细分",
        }
    return {
        "home": _ppda("home", "away"),
        "away": _ppda("away", "home"),
    }


def _calc_possession_trend(raw: RawMatchData) -> dict:
    """控球率趋势。从 trends type_id=45 取逐分钟控球数据，聚合为 6 个 15 分钟窗口。"""
    trends = raw.trends or {}
    home_id = str(raw.home_team.id)
    away_id = str(raw.away_team.id)

    def _get_type_45(team_id: str) -> list:
        inner = trends.get(team_id, {})
        pts = inner.get("45", [])
        if not isinstance(pts, list):
            return []
        return pts

    home_points_raw = _get_type_45(home_id)
    away_points_raw = _get_type_45(away_id)

    # 如果任一队无数据，回退到 stats 全场控球率
    if not home_points_raw and not away_points_raw:
        hs = raw.home_stats
        aw = raw.away_stats
        h_pct = float(_stat(hs, KEY_POSSESSION, default=50))
        a_pct = float(_stat(aw, KEY_POSSESSION, default=50))
        return {"home": [h_pct] * 6, "away": [a_pct] * 6}

    # 聚合到 6 个 15 分钟窗口
    windows = [(0, 15), (15, 30), (30, 45), (45, 60), (60, 75), (75, 90)]

    def _agg(points: list, windows: list) -> list:
        vals = []
        for start, end in windows:
            w_vals = [p.value for p in points if start <= p.minute < end]
            vals.append(round(sum(w_vals) / len(w_vals), 1) if w_vals else 50.0)
        return vals

    home_trend = _agg(home_points_raw, windows)
    away_trend = _agg(away_points_raw, windows)

    return {"home": home_trend, "away": away_trend}


def _calc_rhythm(raw: RawMatchData, possession_trend: dict) -> dict:
    """节奏主导权切换判定。"""
    home_trend = possession_trend.get("home", [])
    away_trend = possession_trend.get("away", [])

    segments = []
    current_dom = None
    dom_count = 0
    for i in range(len(home_trend)):
        diff = home_trend[i] - away_trend[i]
        if diff > 10:
            new_dom = "home"
        elif diff < -10:
            new_dom = "away"
        else:
            new_dom = None

        if new_dom == current_dom:
            dom_count += 1
        else:
            if current_dom is not None and dom_count >= 2:
                segments.append(current_dom)
            current_dom = new_dom
            dom_count = 1

    if current_dom is not None and dom_count >= 2:
        segments.append(current_dom)

    switches = 0
    prev = None
    for d in segments:
        if d != prev:
            switches += 1
            prev = d
    swings = max(0, switches - 1)

    if any(d is not None for d in segments):
        if swings >= 4:
            verdict = "volatile"
        elif swings >= 2:
            verdict = "stabilized"
        else:
            verdict = "one_sided"
    else:
        verdict = "stalemate"

    return {"swings": swings, "verdict": verdict}


def _calc_key_event_impacts(raw: RawMatchData) -> list[dict]:
    """关键事件冲击检测。"""
    impacts = []
    events = raw.events

    for ev in events:
        mi = ev.time_elapsed

        # 进球
        if ev.event_type == "Goal" and ev.detail not in ("pen_shootout_goal", "pen_shootout_miss"):
            t = "home" if ev.team_id == raw.home_team.id else "away"
            tname = raw.home_team.name if t == "home" else raw.away_team.name
            type_label = "点球破门" if ev.detail == "goal_penalty" else "进球"
            impacts.append({
                "minute": mi, "event_type": type_label,
                "team": t, "team_name": tname,
                "context": f"{tname} {ev.player_name} 第 {mi} 分钟{type_label}",
            })

        # 红牌
        if ev.event_type == "Card" and ev.detail in ("redcard", "yellowredcard"):
            t = "home" if ev.team_id == raw.home_team.id else "away"
            impacts.append({
                "minute": mi, "event_type": "红牌", "team": t,
                "context": f"{ev.player_name} 第 {mi} 分钟被罚下",
            })

        # 乌龙球
        if ev.event_type == "Goal" and ev.detail == "owngoal":
            t = "home" if ev.team_id == raw.home_team.id else "away"
            impacts.append({
                "minute": mi, "event_type": "乌龙球", "team": t,
                "context": f"第 {mi} 分钟乌龙球",
            })

    return impacts


def _calc_event_impact_windows(raw: RawMatchData, window_minutes: int = 10) -> list[dict]:
    """进球前后窗口对比：控球率变化 + xG密度变化。

    对每个正赛进球（排除点球大战），对比进球前/后 10 分钟窗口的：
    - 双方平均控球率（从 trends type_id=45 逐分钟数据取均值）
    - 射门数 & 近似 xG（窗口射门 * 全场每射 xG）
    """
    trends = raw.trends or {}
    home_id = str(raw.home_team.id)
    away_id = str(raw.away_team.id)
    timeline = raw.timeline if isinstance(raw.timeline, list) else []

    # 获取逐分钟控球率
    def _get_poss_points(team_id: str) -> list:
        inner = trends.get(team_id, {})
        pts = inner.get("45", [])
        return [(p.minute, p.value) for p in pts] if isinstance(pts, list) else []

    home_poss = _get_poss_points(home_id)
    away_poss = _get_poss_points(away_id)

    # 全场 xG 和射门总数（用于近似）
    h_xg = sum(getattr(p, "xg", 0) or 0 for p in raw.home_players)
    a_xg = sum(getattr(p, "xg", 0) or 0 for p in raw.away_players)
    h_shots = sum(getattr(p, "shots_total", 0) or 0 for p in raw.home_players)
    a_shots = sum(getattr(p, "shots_total", 0) or 0 for p in raw.away_players)
    h_xg_per_shot = h_xg / max(h_shots, 1)
    a_xg_per_shot = a_xg / max(a_shots, 1)

    # 从 timeline 统计某时间窗口内的射门数
    def _shots_in_window(team_pid: int, start: float, end: float) -> int:
        count = 0
        for e in timeline:
            if e.get("type_id") not in (569, 570):
                continue
            if e.get("participant_id") != team_pid:
                continue
            m = e.get("minute", 0)
            if start <= m < end:
                count += 1
        return count

    # 控球率在一个时间窗口的平均值
    def _avg_poss(points: list, start: float, end: float) -> float:
        vals = [v for m, v in points if start <= m < end]
        return round(sum(vals) / len(vals), 1) if vals else 50.0

    # 只处理正赛进球
    impacts = []
    for ev in raw.events:
        if ev.event_type != "Goal":
            continue
        if ev.detail in ("pen_shootout_goal", "pen_shootout_miss"):
            continue
        mi = ev.time_elapsed
        target_team = "home" if ev.team_id == raw.home_team.id else "away"
        target_pid = raw.home_team.id if target_team == "home" else raw.away_team.id
        opp_pid = raw.away_team.id if target_team == "home" else raw.home_team.id

        before_start = max(0, mi - window_minutes)
        before_end = mi
        after_start = mi
        after_end = min(120, mi + window_minutes)

        # 进球方/对方控球率
        target_poss_before = _avg_poss(home_poss if target_team == "home" else away_poss, before_start, before_end)
        target_poss_after = _avg_poss(home_poss if target_team == "home" else away_poss, after_start, after_end)
        opp_poss_before = _avg_poss(away_poss if target_team == "home" else home_poss, before_start, before_end)
        opp_poss_after = _avg_poss(away_poss if target_team == "home" else home_poss, after_start, after_end)

        # 进球方射门 & xG 近似
        shots_before = _shots_in_window(target_pid, before_start, before_end)
        shots_after = _shots_in_window(target_pid, after_start, after_end)
        xg_per = h_xg_per_shot if target_team == "home" else a_xg_per_shot
        xg_before = round(shots_before * xg_per, 3)
        xg_after = round(shots_after * xg_per, 3)

        # 对方射门 & xG 近似
        opp_shots_before = _shots_in_window(opp_pid, before_start, before_end)
        opp_shots_after = _shots_in_window(opp_pid, after_start, after_end)
        opp_xg_per = a_xg_per_shot if target_team == "home" else h_xg_per_shot
        opp_xg_before = round(opp_shots_before * opp_xg_per, 3)
        opp_xg_after = round(opp_shots_after * opp_xg_per, 3)

        is_penalty = ev.detail == "goal_penalty"

        impacts.append({
            "minute": mi,
            "event_type": "点球破门" if is_penalty else "进球",
            "team": target_team,
            "player": ev.player_name,
            "window_before": f"{before_start}-{before_end}'",
            "window_after": f"{after_start}-{after_end}'",
            "possession": {
                "goal_team": {"before": target_poss_before, "after": target_poss_after},
                "opponent": {"before": opp_poss_before, "after": opp_poss_after},
            },
            "shots": {
                "goal_team": {"before": shots_before, "after": shots_after},
                "opponent": {"before": opp_shots_before, "after": opp_shots_after},
            },
            "xg_approx": {
                "goal_team": {"before": xg_before, "after": xg_after},
                "opponent": {"before": opp_xg_before, "after": opp_xg_after},
            },
        })

    return impacts


def compute_match_flow(raw: RawMatchData) -> dict:
    shot_segments = _calc_shot_segments(raw)
    ppda = _calc_ppda_full(raw)
    possession_trend = _calc_possession_trend(raw)
    rhythm = _calc_rhythm(raw, possession_trend)
    key_event_impacts = _calc_key_event_impacts(raw)
    event_impact_windows = _calc_event_impact_windows(raw)

    return {
        "rhythm": rhythm,
        "ppda": ppda,
        "shot_segments": shot_segments,
        "possession_trend": possession_trend,
        "key_event_impacts": key_event_impacts,
        "event_impact_windows": event_impact_windows,
    }


# ═══════════════════════════════════════════════════════════════
# Layer 3: 效果判定 — 维度 ROI
# ═══════════════════════════════════════════════════════════════

def _execution_dim_score(dim_name: str, input_gap: float, raw: RawMatchData, team: str) -> dict:
    s = raw.home_stats if team == "home" else raw.away_stats
    opp_s = raw.away_stats if team == "home" else raw.home_stats
    players = raw.home_players if team == "home" else raw.away_players
    opp_players = raw.away_players if team == "home" else raw.home_players

    roi_value = 0.0
    score = 0.0
    iw = min(input_gap / 1.5, 2.0)

    passes = float(_stat(s, KEY_PASSES, default=1))
    shots = float(_stat(s, KEY_SHOTS, default=1))
    xg = sum(getattr(p, "xg", 0) or 0 for p in players)
    shots_ib = float(_stat(s, KEY_SHOTS_IB, default=0))
    opp_pass_pct = float(_stat(opp_s, KEY_PASS_PCT, default=80))
    opp_shots = float(_stat(opp_s, KEY_SHOTS, default=1))

    if dim_name == "possession":
        roi_value = _safe_div(xg, passes) * 1000
        if roi_value > 2.5:
            score = min(iw * 1.0, 2.0)
        elif roi_value > 1.0:
            score = iw * 0.5
        else:
            score = -iw * 1.0

    elif dim_name == "long_ball":
        long_balls = float(_stat(s, KEY_LONG, default=1))
        opp_long = float(_stat(opp_s, KEY_LONG, default=1))
        opp_xg = sum(getattr(p, "xg", 0) or 0 for p in opp_players)
        roi_value = _safe_div(xg, max(long_balls, 1))
        opp_roi = _safe_div(opp_xg, max(opp_long, 1))
        if roi_value > opp_roi * 1.5:
            score = iw * 1.0
        elif roi_value > opp_roi:
            score = iw * 0.3
        else:
            score = -iw * 0.8

    elif dim_name == "crossing":
        crosses = float(_stat(s, KEY_CROSSES, default=1))
        headers = float(_stat(s, KEY_HEADERS, default=0))
        roi_value = _safe_div(headers, crosses) * 100
        if roi_value > 25:
            score = iw * 1.0
        elif roi_value > 15:
            score = iw * 0.5
        else:
            score = -iw * 0.8

    elif dim_name == "penetration":
        roi_value = _safe_div(shots_ib, max(shots, 1)) * 100
        if roi_value > 55:
            score = iw * 1.0
        elif roi_value > 40:
            score = iw * 0.4
        else:
            score = -iw * 1.0

    elif dim_name == "directness":
        goals = float(raw.score.home if team == "home" else raw.score.away)
        roi_value = _safe_div(goals, max(xg, 0.01))
        if 0.8 <= roi_value <= 1.5:
            score = iw * 1.0
        elif roi_value > 1.5:
            score = iw * 0.5
        else:
            score = -iw * 0.8

    elif dim_name == "press_intensity":
        roi_value = opp_pass_pct
        if roi_value < 75:
            score = iw * 1.0
        elif roi_value < 82:
            score = iw * 0.3
        else:
            score = -iw * 1.0

    elif dim_name == "high_press":
        tackles = float(_stat(s, KEY_TACKLES, default=1))
        roi_value = _safe_div(shots, max(tackles, 1))
        if roi_value > 1.5:
            score = iw * 1.0
        elif roi_value > 0.8:
            score = iw * 0.4
        else:
            score = -iw * 0.8

    elif dim_name == "deep_block":
        opp_xg = sum(getattr(p, "xg", 0) or 0 for p in opp_players)
        roi_value = _safe_div(opp_xg, max(opp_shots, 1))
        if roi_value < 0.08:
            score = iw * 1.0
        elif roi_value < 0.15:
            score = iw * 0.4
        else:
            score = -iw * 1.0

    elif dim_name == "interception":
        interceptions = float(_stat(s, KEY_INTERCEPTIONS, default=1))
        opp_passes = float(_stat(opp_s, KEY_PASSES, default=1))
        roi_value = _safe_div(interceptions, opp_passes) * 100
        if roi_value > 3:
            score = iw * 1.0
        elif roi_value > 1.5:
            score = iw * 0.4
        else:
            score = -iw * 0.5

    score = round(score, 2)
    roi_value = round(roi_value, 3)

    return {"dim": dim_name, "input_gap": round(input_gap, 2), "roi_value": roi_value, "score": score}


def _verdict_from_score(score: float, triggered_count: int) -> str:
    if triggered_count <= 1 and abs(score) < 0.5:
        return "undetermined"
    return "effective" if score > 0 else "fail"


def _is_high_dim(dim_name: str, team: str, tactical_data: dict) -> bool:
    td = tactical_data[team]
    other = tactical_data["away" if team == "home" else "home"]
    rs = td["tactical_raw"]
    ro = other["tactical_raw"]
    key_map = {
        "possession": "passes_per_shot", "long_ball": "long_ball_ratio",
        "crossing": "cross_ratio", "penetration": "final_third_pass_ratio",
        "directness": "forward_ratio",
    }
    dk = key_map.get(dim_name)
    if not dk:
        return True
    vs = rs.get(dk, 0)
    vo = ro.get(dk, 0)
    if dim_name == "possession":
        return vs < vo
    return vs > vo


def _is_high_def_dim(dim_name: str, team: str, tactical_data: dict) -> bool:
    td = tactical_data[team]
    other = tactical_data["away" if team == "home" else "home"]
    rs = td["tactical_raw"]
    ro = other["tactical_raw"]
    if dim_name in ("press_intensity", "interception"):
        return rs["ppda"] < ro["ppda"]
    if dim_name == "high_press":
        return rs["high_press_ratio"] > ro["high_press_ratio"]
    if dim_name == "deep_block":
        return rs["clearance_ratio"] > ro["clearance_ratio"]
    return True


def compute_execution(raw: RawMatchData, tactical_data: dict) -> dict:
    """评估所有维度的投入产出效果 — 不再过滤「高维」，所有维度均纳入评估。"""
    off_dims = {
        "possession": "passes_gap", "long_ball": "long_ball_gap",
        "crossing": "cross_gap", "penetration": "final_third_pass_gap",
        "directness": "forward_gap",
    }
    def_dims = {
        "press_intensity": "ppda_gap", "high_press": "high_press_gap",
        "deep_block": "clearance_gap", "interception": "ppda_gap",
    }

    result = {}
    for team in ("home", "away"):
        rel = tactical_data[team]["match_relative"]

        a_dims = []
        for dn, gk in off_dims.items():
            gv = rel.get(gk, 1.0)
            if abs(gv - 1.0) > 0.05:
                a_dims.append(_execution_dim_score(dn, gv, raw, team))

        d_dims = []
        for dn, gk in def_dims.items():
            gv = rel.get(gk, 1.0)
            if abs(gv - 1.0) > 0.05:
                d_dims.append(_execution_dim_score(dn, gv, raw, team))

        at = round(sum(d["score"] for d in a_dims), 1)
        dt = round(sum(d["score"] for d in d_dims), 1)

        result[team] = {
            "attack": {"dimensions": a_dims, "total_score": at,
                       "verdict": _verdict_from_score(at, len(a_dims))},
            "defense": {"dimensions": d_dims, "total_score": dt,
                        "verdict": _verdict_from_score(dt, len(d_dims))},
        }

    return result


# ═══════════════════════════════════════════════════════════════
# Layer 4: 教练博弈
# ═══════════════════════════════════════════════════════════════

def _get_dim_score(dimensions: list[dict], dim_name: str) -> float:
    for d in dimensions:
        if d["dim"] == dim_name:
            return d["score"]
    return 0.0


def compute_coaching(raw: RawMatchData, tactical_data: dict, execution: dict) -> dict:
    hr = tactical_data["home"]["tactical_raw"]
    ar = tactical_data["away"]["tactical_raw"]

    h_poss = hr["possession_pct"]
    a_poss = ar["possession_pct"]
    h_long = hr["long_ball_ratio"]
    a_long = ar["long_ball_ratio"]
    h_fwd = hr["forward_ratio"]
    a_fwd = ar["forward_ratio"]
    h_pass = hr["pass_volume"]
    a_pass = ar["pass_volume"]

    # ── 风格碰撞判定 ──
    # 优先级：控球差距 > 长传 vs 压迫 > 镜像/混合
    poss_gap = abs(h_poss - a_poss)
    if poss_gap >= 30:
        # 控球悬殊：高控球方 + 低控球方的反击特征
        if h_poss > a_poss and a_long > h_long * 1.5 and a_fwd > h_fwd * 1.5:
            clash = "possession_vs_counter"
        elif a_poss > h_poss and h_long > a_long * 1.5 and h_fwd > a_fwd * 1.5:
            clash = "possession_vs_counter"
        elif h_pass > a_pass * 2.5 or a_pass > h_pass * 2.5:
            clash = "possession_vs_counter"
        else:
            clash = "possession_dominant"
    elif h_long > a_long * 1.5 and hr["ppda"] > ar["ppda"] * 1.5:
        clash = "long_ball_vs_press"
    elif a_long > h_long * 1.5 and ar["ppda"] > hr["ppda"] * 1.5:
        clash = "long_ball_vs_press"
    elif h_long > a_long * 1.3 and a_long > 0.05:
        clash = "direct_duel"
    elif a_long > h_long * 1.3 and h_long > 0.05:
        clash = "direct_duel"
    elif abs(h_long - a_long) < 0.02 and abs(h_fwd - a_fwd) < 0.05:
        clash = "mirror_match"
    else:
        clash = "mixed_styles"

    # 克制对
    pairs = []

    # 渗透 vs 蹲坑
    if hr["final_third_pass_ratio"] > ar["final_third_pass_ratio"] * 1.3:
        if ar["clearance_ratio"] > hr["clearance_ratio"] * 1.3:
            s = _get_dim_score(execution["home"]["attack"]["dimensions"], "penetration")
            pairs.append({"off_dim": "penetration", "def_dim": "deep_block",
                          "off_team": "home", "result": 2 if s > 0 else -2})
    if ar["final_third_pass_ratio"] > hr["final_third_pass_ratio"] * 1.3:
        if hr["clearance_ratio"] > ar["clearance_ratio"] * 1.3:
            s = _get_dim_score(execution["away"]["attack"]["dimensions"], "penetration")
            pairs.append({"off_dim": "penetration", "def_dim": "deep_block",
                          "off_team": "away", "result": 2 if s > 0 else -2})

    # 长传 vs 压迫
    if hr["long_ball_ratio"] > ar["long_ball_ratio"] * 1.3:
        if ar["ppda"] < hr["ppda"] * 0.7:
            s = _get_dim_score(execution["home"]["attack"]["dimensions"], "long_ball")
            pairs.append({"off_dim": "long_ball", "def_dim": "press_intensity",
                          "off_team": "home", "result": 2 if s > 0 else -2})
    if ar["long_ball_ratio"] > hr["long_ball_ratio"] * 1.3:
        if hr["ppda"] < ar["ppda"] * 0.7:
            s = _get_dim_score(execution["away"]["attack"]["dimensions"], "long_ball")
            pairs.append({"off_dim": "long_ball", "def_dim": "press_intensity",
                          "off_team": "away", "result": 2 if s > 0 else -2})

    # 控球 vs 压迫
    if hr["passes_per_shot"] < ar["passes_per_shot"] * 0.7:
        if ar["ppda"] < hr["ppda"] * 0.7:
            s = _get_dim_score(execution["home"]["attack"]["dimensions"], "possession")
            pairs.append({"off_dim": "possession", "def_dim": "press_intensity",
                          "off_team": "home", "result": 2 if s > 0 else -2})
    if ar["passes_per_shot"] < hr["passes_per_shot"] * 0.7:
        if hr["ppda"] < ar["ppda"] * 0.7:
            s = _get_dim_score(execution["away"]["attack"]["dimensions"], "possession")
            pairs.append({"off_dim": "possession", "def_dim": "press_intensity",
                          "off_team": "away", "result": 2 if s > 0 else -2})

    mh = sum(p["result"] for p in pairs if p["off_team"] == "home")
    ma = sum(p["result"] for p in pairs if p["off_team"] == "away")

    return {
        "style_clash": clash,
        "tactical_mismatch": {"home": mh, "away": ma},
        "mismatch_pairs": pairs,
        "sub_effectiveness": {
            "home": {"score_change": 0, "verdict": "neutral"},
            "away": {"score_change": 0, "verdict": "neutral"},
        },
    }


# ═══════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════

def compute_tactical_analysis(raw: RawMatchData) -> dict:
    tactical_data = compute_tactical_raw(raw)
    match_flow = compute_match_flow(raw)
    execution = compute_execution(raw, tactical_data)
    coaching = compute_coaching(raw, tactical_data, execution)

    return {
        "home": {
            "tactical_raw": tactical_data["home"]["tactical_raw"],
            "match_relative": tactical_data["home"]["match_relative"],
            "execution": execution["home"],
        },
        "away": {
            "tactical_raw": tactical_data["away"]["tactical_raw"],
            "match_relative": tactical_data["away"]["match_relative"],
            "execution": execution["away"],
        },
        "match_flow": match_flow,
        "coaching": coaching,
    }
