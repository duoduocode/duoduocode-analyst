"""
球员人物特稿候选筛选器

根据检测器结果、关键事件、球员数据计算"文章价值分"，筛出候选名单。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PlayerCandidate:
    """球员人物特稿候选。"""
    name: str
    team: str
    position: str          # G/D/M/F or 门将/后卫/中场/前锋
    minutes: int
    rating: float
    tags: list[str] = field(default_factory=list)       # 检测器标签
    events: list[str] = field(default_factory=list)      # 关键事件描述
    key_stats: str = ""                                   # 核心数据汇总
    summary: str = ""                                     # LLM 60-80字点评
    news: list[str] = field(default_factory=list)        # 近期新闻摘要
    feature_score: float = 0.0                            # 文章价值分
    is_substitute: bool = False                           # 是否为替补登场


def select_candidates(
    players_data: list[dict],
    detector_results,
    key_events_result,
    raw_events: list,
    summaries: dict[str, str],
    max_candidates: int = 8,
) -> list[PlayerCandidate]:
    """
    从双方球员中筛出人物特稿候选。

    Args:
        players_data: 球员基础信息 [{"name":..., "team":..., "position":..., ...}, ...]
        detector_results: run_all_detectors() 返回的 AllDetectorResults
        key_events_result: detect_key_events() 返回的 KeyEventResult
        raw_events: 原始事件列表
        summaries: {player_name: 60-80字点评}
        max_candidates: 最多返回人数

    Returns: 按 feature_score 降序排列的候选列表
    """
    from src.engine.player_insights import DETECTOR_TAGS

    _DETECTOR_ATTRS = {
        "D1": "D1_progression", "D2": "D2_pressing", "D3": "D3_gravity",
        "D4": "D4_tempo", "D5": "D5_twoway", "D6": "D6_timing",
        "D7": "D7_efficiency", "D8": "D8_role_deviation", "D9": "D9_connector",
        "D13": "D13_prowess",
    }

    # Build detector top-3 sets per team and overall
    team_top3 = {}  # team_name -> {dname: set(player_name)}
    overall_top3 = {}  # dname -> set(player_name)

    for dname, attr in _DETECTOR_ATTRS.items():
        d = getattr(detector_results, attr, None)
        if d is None:
            continue
        overall_set = set()
        if isinstance(d, dict):
            for team, rlist in d.items():
                for r in rlist[:3]:
                    overall_set.add(r.name)
                    team_top3.setdefault(team, {}).setdefault(dname, set()).add(r.name)
        elif isinstance(d, list):
            for r in d[:3]:
                overall_set.add(r.name)
        overall_top3[dname] = overall_set

    # Build event info per player
    player_events = {}  # player_name -> list[str]
    for ev in raw_events:
        pname = ev.get("player_name", "")
        etype = ev.get("event_type", ev.get("type", ""))
        detail = ev.get("detail", "")
        minute = ev.get("minute", ev.get("time_elapsed", "?"))

        if etype in ("Goal", "goal", "goal_penalty"):
            label = f"{minute}' 进球"
        elif etype in ("Card", "yellowcard", "redcard"):
            label = f"{minute}' {'红牌' if 'red' in detail else '黄牌'}"
        elif etype in ("subst", "substitution"):
            continue
        else:
            continue

        if pname:
            player_events.setdefault(pname, []).append(label)

    # Event-driven flags
    ke = key_events_result
    first_goal_set = set(ke.first_goal_scorers)
    equalizer_set = {ke.equalizer_scorer} if ke.equalizer_scorer else set()
    winner_set = {ke.winning_goal_scorer} if ke.winning_goal_scorer else set()
    late_winner_set = {ke.late_winner_scorer} if ke.late_winner_scorer else set()
    super_sub_set = set(ke.super_sub_scorers.keys())
    pen_scorers_set = set(ke.penalty_scorers)
    pso_scorers_set = set(ke.pen_shootout_scorers)
    pso_missers_set = set(ke.pen_shootout_missers)

    candidates = []
    for p in players_data:
        pname = p.get("name", "")
        if not pname:
            continue
        minutes = p.get("minutes", 0)
        if minutes <= 0:
            continue

        # Compute feature score
        score = 0.0
        is_mvp = p.get("man_of_match", False) or p.get("captain_and_mom", False)
        if is_mvp:
            score += 3.0

        # Key events
        event_count = 0
        ev = player_events.get(pname, [])
        event_count += len(ev)
        if pname in first_goal_set:
            event_count += 1
        if pname in equalizer_set:
            event_count += 1
        if pname in winner_set:
            event_count += 1
        if pname in late_winner_set:
            event_count += 1
        if pname in super_sub_set:
            event_count += 1
        score += 2.0 * event_count

        # Top3 detector tags
        team = p.get("team", "")
        tag_count = 0
        p_tags = []
        for dname in _DETECTOR_ATTRS:
            if pname in overall_top3.get(dname, set()):
                tag_count += 1
                p_tags.append(DETECTOR_TAGS.get(dname, dname))
        score += 1.5 * tag_count

        # Super sub bonus
        if pname in super_sub_set:
            score += 1.0
            p_tags.append("超级替补")

        # Controversy / turning point
        controversy = 0
        for ev in raw_events:
            if ev.get("player_name") != pname:
                continue
            detail = ev.get("detail", "")
            if "red" in detail:
                controversy += 1
            if "missed_penalty" in detail:
                controversy += 1
            if "owngoal" in detail:
                controversy += 1
        has_error = p.get("error_lead_to_goal", 0) or 0
        if has_error > 0:
            controversy += 1
        if controversy > 0:
            score += 1.0

        # GK special: saves heroic
        position = p.get("position", "?")
        if position in ("G", "门将"):
            saves = p.get("saves", 0) or 0
            saves_ib = p.get("saves_inside_box", 0) or 0
            if saves >= 5 or saves_ib >= 3:
                score += 2.0
                p_tags.append("门神")

        # Build key stats string
        stats_parts = []
        if p.get("goals"):
            stats_parts.append(f"进球{p['goals']}")
        if p.get("assists"):
            stats_parts.append(f"助攻{p['assists']}")
        if p.get("shots_total"):
            stats_parts.append(f"射门{p['shots_total']}/{p.get('shots_on', 0)}")
        if p.get("xg") and p.get("xg") > 0:
            stats_parts.append(f"xG {p['xg']:.2f}")
        if p.get("passes_accuracy") and p.get("passes_accuracy") > 0:
            stats_parts.append(f"传球成功率{p['passes_accuracy']:.0f}%")
        if p.get("passes_key"):
            stats_parts.append(f"关键传球{p['passes_key']}")
        if p.get("passes_total"):
            stats_parts.append(f"传球{p['passes_total']}")
        if tag_count >= 2 and not stats_parts:
            stats_parts.append("多维度队内前3")
        key_stats = "，".join(stats_parts) if stats_parts else "无特殊数据"

        candidates.append(PlayerCandidate(
            name=pname,
            team=team,
            position=position,
            minutes=minutes,
            rating=round(p.get("rating", 0) or 0, 1),
            tags=p_tags,
            events=player_events.get(pname, []),
            key_stats=key_stats,
            summary=summaries.get(pname, ""),
            news=[],  # 新闻在后续阶段填充
            feature_score=score,
            is_substitute=p.get("is_substitute", False),
        ))

    candidates.sort(key=lambda c: -c.feature_score)
    return candidates[:max_candidates]
