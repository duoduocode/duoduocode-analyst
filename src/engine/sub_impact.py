"""
Layer 1: Substitution Impact Analysis
For each substitution event, compare 15-min windows before & after
to quantify tactical effectiveness.
"""

from __future__ import annotations

from typing import Optional

from src.collector.api_client import RawMatchData, PlayerStats, MatchEvent


def _stat(d: dict, *keys, default=0.0):
    for k in keys:
        v = d.get(k)
        if v is not None:
            return float(v)
    return float(default)


def _safe_ratio(a: float, b: float) -> float:
    return a / b if b > 0 else 0.0


def analyze_sub_impacts(raw: RawMatchData) -> list[dict]:
    """Analyze all substitution events and produce impact assessments."""
    events = raw.events
    trends = raw.trends or {}
    home_id = str(raw.home_team.id)
    away_id = str(raw.away_team.id)

    # Find all substitution events
    sub_events = [e for e in events if e.event_type == "subst"]

    # Build player lookup
    player_map = {}
    for p in raw.home_players:
        player_map[p.name] = (p, raw.home_team.name)
    for p in raw.away_players:
        player_map[p.name] = (p, raw.away_team.name)

    results = []
    for e in sub_events:
        mi = e.time_elapsed or 0
        # SportMonks parsed: player_name = player OFF, assist_name = player ON
        player_off = e.player_name or ""
        player_on = e.assist_name or ""
        team_id = e.team_id
        pid = team_id

        # Get subbed-off player stats
        off_stats = None
        if player_off and player_off in player_map:
            off_stats, _ = player_map[player_off]

        # Get period context
        period_name = _get_period_name(e.period_id, raw)

        # Compare 15-min windows
        impact = _compare_windows(trends, pid, mi, raw)

        # Infer coach intent
        intent = _infer_intent(off_stats, raw, team_id, mi, player_on, player_off)

        results.append({
            "minute": mi,
            "minute_display": f"{mi}'" + (f"+{e.time_extra}" if e.time_extra else ""),
            "period": period_name,
            "team": raw.home_team.name if team_id == raw.home_team.id else raw.away_team.name,
            "player_on": player_on,
            "player_off": player_off,
            "player_off_position": off_stats.position if off_stats else "?",
            "player_off_rating": round(off_stats.rating, 1) if off_stats and off_stats.rating else None,
            "player_off_minutes": off_stats.minutes_played if off_stats else 0,
            "player_off_goals": off_stats.goals if off_stats else 0,
            "player_off_assists": off_stats.assists if off_stats else 0,
            "player_off_shots": off_stats.shots_total if off_stats else 0,
            "player_off_passes": off_stats.passes_total if off_stats else 0,
            "player_off_tackles": off_stats.tackles_total if off_stats else 0,
            "player_off_xg": round(off_stats.xg, 4) if off_stats and off_stats.xg else 0,
            "intent": intent,
            "control_before": impact.get("possession_before"),
            "control_after": impact.get("possession_after"),
            "shots_before": impact.get("shots_before"),
            "shots_after": impact.get("shots_after"),
            "attacks_before": impact.get("attacks_before"),
            "attacks_after": impact.get("attacks_after"),
            "effectiveness": impact.get("effectiveness", "unknown"),
            "effectiveness_score": impact.get("effectiveness_score", 0),
        })

    return results


def _get_period_name(period_id, raw: RawMatchData) -> str:
    for p in (raw.periods or []):
        if p.sort_order == period_id or getattr(p, 'id', None) == period_id:
            return p.description
    return "?"


def _compare_windows(trends: dict, pid: str, minute: int, raw: RawMatchData) -> dict:
    """Compare team stats in 15-min window before vs after substitution."""
    result = {}

    # Get trends for this participant
    team_trends = trends.get(pid, {})

    # Key type_ids to check
    key_types = {45: "possession", 43: "attacks", 42: "shots",
                 80: "passes", 106: "duels_won", 44: "dangerous_attacks"}

    for tid, name in key_types.items():
        pts = team_trends.get(tid, [])
        minute_map = {int(p.minute): float(p.value) for p in pts}

        # Before window: minute-15 to minute
        before_vals = [v for m, v in minute_map.items() if minute - 15 <= m < minute]
        # After window: minute to minute+15
        after_vals = [v for m, v in minute_map.items() if minute <= m < minute + 15]

        before_sum = sum(before_vals)
        after_sum = sum(after_vals)
        before_count = len(before_vals)
        after_count = len(after_vals)

        # For rate-based metrics (possession), use average
        # For cumulative metrics, use delta
        if name == "possession":
            before_avg = before_sum / before_count if before_count else 0
            after_avg = after_sum / after_count if after_count else 0
            result[f"{name}_before"] = round(before_avg, 1)
            result[f"{name}_after"] = round(after_avg, 1)
            result[f"{name}_change"] = round(after_avg - before_avg, 1)
        else:
            result[f"{name}_before"] = round(before_sum, 1)
            result[f"{name}_after"] = round(after_sum, 1)
            result[f"{name}_change"] = round(after_sum - before_sum, 1)

    # Compute overall effectiveness
    pos_change = result.get("possession_change", 0)
    shot_change = result.get("shots_change", 0)
    attack_change = result.get("attacks_change", 0)

    score = pos_change * 0.3 + (shot_change * 2 if shot_change > 0 else shot_change) + attack_change * 0.1
    result["effectiveness_score"] = round(score, 1)

    if score > 3:
        result["effectiveness"] = "显著有效"
    elif score > 0.5:
        result["effectiveness"] = "略有改善"
    elif score >= -0.5:
        result["effectiveness"] = "效果中性"
    elif score >= -3:
        result["effectiveness"] = "略有恶化"
    else:
        result["effectiveness"] = "效果不佳"

    return result


def _infer_intent(
    off_player: PlayerStats | None,
    raw: RawMatchData,
    team_id,
    minute: int,
    player_on: str,
    player_off: str,
) -> str:
    """Infer the coach's tactical intent behind the substitution."""
    team_name = raw.home_team.name if team_id == raw.home_team.id else raw.away_team.name
    home_goals = raw.score.home
    away_goals = raw.score.away
    our_goals = home_goals if team_id == raw.home_team.id else away_goals
    opp_goals = away_goals if team_id == raw.home_team.id else home_goals

    # Position-based inference
    pos = off_player.position if off_player else "?"

    # Score context
    if our_goals > opp_goals:
        score_context = "领先"
    elif our_goals < opp_goals:
        score_context = "落后"
    else:
        score_context = "平局"

    # Timing context
    if minute <= 30:
        time_context = "早期调整"
    elif minute <= 60:
        time_context = "中场调整"
    elif minute <= 75:
        time_context = "常规轮换"
    elif minute <= 85:
        time_context = "战术调整"
    elif minute <= 105:
        time_context = "加时轮换"
    else:
        time_context = "终场调整"

    # Combine
    if pos == "F":
        intent = f"加强进攻（换下前锋 {player_off}）" if score_context == "落后" else "锋线轮换"
    elif pos == "M":
        if score_context == "落后":
            intent = "增加中场创造性"
        elif score_context == "领先":
            intent = "加强中场防守"
        else:
            intent = "中场战术调整"
    elif pos == "D":
        if score_context == "落后":
            intent = "减少后卫、加强进攻（变阵）"
        else:
            intent = "防守端体能轮换"
    elif pos == "G":
        intent = "门将被迫换人/战术调整"
    else:
        intent = f"{time_context}，{score_context}局面下的战术换人"

    return f"{intent}（{time_context}，{score_context}）"
