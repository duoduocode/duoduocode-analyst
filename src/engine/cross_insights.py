"""
Layer 1: Hard Facts Computation
Calculates precise numerical insights from raw match data.
LLM can reference these facts but cannot distort them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from src.collector.api_client import RawMatchData, PlayerStats, MatchEvent


# ============================================================
@dataclass
class HardFacts:
    """All computed hard facts for one match."""

    # 1. Possession efficiency
    possession_xg_ratio_home: float = 0.0
    possession_xg_ratio_away: float = 0.0

    # 2. Shot conversion curve
    shot_windows: list[dict] = field(default_factory=list)

    # 3. xG deviation
    xg_deviation_home: float = 0.0
    xg_deviation_away: float = 0.0
    xg_overperformer: str = ""

    # 4. Attacking rhythm shift (half1 vs half2)
    attack_rhythm: dict = field(default_factory=dict)

    # 5. Period dominance
    period_dominance: list[dict] = field(default_factory=list)

    # 6. Defensive decay
    defensive_decay: dict = field(default_factory=dict)

    # 7. Passing profile
    passing_profile: dict = field(default_factory=dict)

    # 8. Time pressure (last 15 min)
    time_pressure: dict = field(default_factory=dict)

    # 9. Player efficiency
    player_efficiency: dict = field(default_factory=dict)

    # 10. Substitution impacts
    sub_impacts: list[dict] = field(default_factory=list)


def _stat(d: dict, *keys, default=0.0):
    for k in keys:
        v = d.get(k)
        if v is not None:
            return float(v)
    return float(default)


def _safe_ratio(num: float, den: float) -> float:
    return num / den if den > 0 else 0.0


# ============================================================
def compute_cross_insights(raw: RawMatchData, sub_impacts: list[dict] = None) -> HardFacts:
    """Compute all 10 hard facts from raw match data."""
    h = HardFacts()

    hs = raw.home_stats
    as_ = raw.away_stats
    hpl = raw.home_players
    apl = raw.away_players
    events = raw.events

    # --- 1. Possession xG efficiency ---
    home_poss = _stat(hs, "Ball Possession", default=50.0)
    away_poss = _stat(as_, "Ball Possession", default=50.0)
    home_xg = sum(p.xg for p in hpl if p.xg)
    away_xg = sum(p.xg for p in apl if p.xg)
    h.possession_xg_ratio_home = round(_safe_ratio(home_xg, home_poss) * 100, 3)
    h.possession_xg_ratio_away = round(_safe_ratio(away_xg, away_poss) * 100, 3)

    # --- 2. Shot conversion curve (15-min windows) ---
    h.shot_windows = _build_shot_windows(events, raw)

    # --- 3. xG deviation ---
    home_goals = raw.score.home
    away_goals = raw.score.away
    h.xg_deviation_home = round(home_goals - home_xg, 3)
    h.xg_deviation_away = round(away_goals - away_xg, 3)
    h.xg_overperformer = ""
    if abs(h.xg_deviation_home) > 0.4 or abs(h.xg_deviation_away) > 0.4:
        if h.xg_deviation_home > h.xg_deviation_away:
            h.xg_overperformer = raw.home_team.name
        else:
            h.xg_overperformer = raw.away_team.name

    # --- 4. Attack rhythm shift ---
    h.attack_rhythm = _compute_rhythm_shift(raw)

    # --- 5. Period dominance ---
    h.period_dominance = _compute_period_dominance(raw)

    # --- 6. Defensive decay ---
    h.defensive_decay = _compute_defensive_decay(raw)

    # --- 7. Passing profile ---
    h.passing_profile = _compute_passing_profile(raw)

    # --- 8. Time pressure (last 15 min) ---
    h.time_pressure = _compute_time_pressure(raw)

    # --- 9. Player efficiency ---
    h.player_efficiency = _compute_player_efficiency(raw)

    # --- 10. Sub impacts ---
    h.sub_impacts = sub_impacts or []

    return h


# ============================================================
# Individual computations
# ============================================================

def _build_shot_windows(events: list[MatchEvent], raw: RawMatchData) -> list[dict]:
    """Group events into 15-minute windows and count shots/goals."""
    windows = []
    for start in range(0, 120, 15):
        end = start + 15
        shots_h = 0
        shots_a = 0
        goals_h = 0
        goals_a = 0
        for e in events:
            mi = e.time_elapsed
            if mi is None or mi < start or mi >= end:
                continue
            if e.event_type in ("Goal", "Shot"):
                if e.event_type == "Goal" and "pen_shootout" not in (e.detail or ""):
                    if e.team_id == raw.home_team.id:
                        goals_h += 1
                    elif e.team_id == raw.away_team.id:
                        goals_a += 1
        windows.append({
            "window": f"{start}-{end}'",
            "goals_home": goals_h, "goals_away": goals_a,
            "shots_home": shots_h, "shots_away": shots_a,
        })

    # Count shots from timeline
    from collections import Counter
    timeline = raw.timeline or []
    for t in timeline:
        mi = t.get("minute") or 0
        tid = t.get("type_id", 0)
        if tid not in (569, 570):  # 569=shot on target, 570=shot off target
            continue
        team_id = t.get("participant_id")
        for w in windows:
            rng = w["window"].split("-")
            lo = int(rng[0])
            hi = int(rng[1].replace("'", ""))
            if lo <= mi < hi:
                if team_id == raw.home_team.id:
                    w["shots_home"] += 1
                elif team_id == raw.away_team.id:
                    w["shots_away"] += 1

    # Remove empty trailing windows
    while windows and windows[-1]["shots_home"] == 0 and windows[-1]["shots_away"] == 0 \
            and windows[-1]["goals_home"] == 0 and windows[-1]["goals_away"] == 0:
        windows.pop()

    return windows


def _compute_rhythm_shift(raw: RawMatchData) -> dict:
    """Compare half1 vs half2 attacking rhythm using period stats."""
    periods = raw.periods or []
    h1_hs = {}
    h2_hs = {}
    h1_as = {}
    h2_as = {}
    for p in periods:
        desc = p.description
        if "1st-half" in desc:
            h1_hs = p.home_stats
            h1_as = p.away_stats
        elif "2nd-half" in desc:
            h2_hs = p.home_stats
            h2_as = p.away_stats

    result = {}
    for label, p1, p2 in [("home", h1_hs, h2_hs), ("away", h1_as, h2_as)]:
        if not p1 or not p2:
            continue
        s1 = _stat(p1, "Total Shots")
        s2 = _stat(p2, "Total Shots")
        a1_ = _stat(p1, "Attacks")
        a2_ = _stat(p2, "Attacks")
        result[f"{label}_shots_h1"] = int(s1)
        result[f"{label}_shots_h2"] = int(s2)
        result[f"{label}_shots_ratio"] = round(_safe_ratio(s2, s1), 2)
        result[f"{label}_attacks_h1"] = int(a1_)
        result[f"{label}_attacks_h2"] = int(a2_)
        result[f"{label}_attacks_ratio"] = round(_safe_ratio(a2_, a1_), 2)

    return result


def _compute_period_dominance(raw: RawMatchData) -> list[dict]:
    """Compute possession / shots / danger ratio per period."""
    periods = raw.periods or []
    result = []
    for p in periods:
        desc = p.description
        hs = p.home_stats
        as_ = p.away_stats
        if not hs or not as_:
            continue
        h_poss = _stat(hs, "Ball Possession")
        a_poss = _stat(as_, "Ball Possession")
        h_shots = _stat(hs, "Total Shots")
        a_shots = _stat(as_, "Total Shots")
        result.append({
            "period": desc,
            "home_possession": h_poss,
            "away_possession": a_poss,
            "home_shots": int(h_shots),
            "away_shots": int(a_shots),
            "dominant": raw.home_team.name if h_poss > a_poss else raw.away_team.name,
        })
    return result


def _compute_defensive_decay(raw: RawMatchData) -> dict:
    """Compute tackles+interceptions per 15-min window from trends."""
    trends = raw.trends or {}
    home_id = raw.home_team.id
    away_id = raw.away_team.id

    def _get_series(pid, type_id):
        pts = trends.get(pid, {}).get(type_id, [])
        return {int(p.minute): float(p.value) for p in pts}

    home_tackles = _get_series(home_id, 78)
    home_intercept = _get_series(home_id, 100)
    away_tackles = _get_series(away_id, 78)
    away_intercept = _get_series(away_id, 100)

    windows = []
    for start in range(0, 120, 30):
        end = start + 30
        ht = max((v for m, v in home_tackles.items() if start <= m < end), default=0)
        hi = max((v for m, v in home_intercept.items() if start <= m < end), default=0)
        at = max((v for m, v in away_tackles.items() if start <= m < end), default=0)
        ai = max((v for m, v in away_intercept.items() if start <= m < end), default=0)
        if ht + hi + at + ai == 0:
            continue
        windows.append({
            "window": f"{start}-{end}'",
            "home_defensive": ht + hi,
            "away_defensive": at + ai,
        })

    # Compute decay rate
    decay = {"windows": windows}
    if len(windows) >= 2:
        first = windows[0]
        last = windows[-1]
        if first["home_defensive"] > 0:
            decay["home_decay_pct"] = round(
                (1 - last["home_defensive"] / first["home_defensive"]) * 100, 1
            )
        if first["away_defensive"] > 0:
            decay["away_decay_pct"] = round(
                (1 - last["away_defensive"] / first["away_defensive"]) * 100, 1
            )

    return decay


def _compute_passing_profile(raw: RawMatchData) -> dict:
    """Passing style: long ball ratio, cross ratio, key pass ratio."""
    hs = raw.home_stats
    as_ = raw.away_stats
    return {
        "home_long_ball_pct": round(
            _safe_ratio(_stat(hs, "Long Balls"), _stat(hs, "Total passes")) * 100, 1
        ),
        "away_long_ball_pct": round(
            _safe_ratio(_stat(as_, "Long Balls"), _stat(as_, "Total passes")) * 100, 1
        ),
        "home_cross_pct": round(
            _safe_ratio(_stat(hs, "Crosses"), _stat(hs, "Total passes")) * 100, 1
        ),
        "away_cross_pct": round(
            _safe_ratio(_stat(as_, "Crosses"), _stat(as_, "Total passes")) * 100, 1
        ),
        "home_key_pass_pct": round(
            _safe_ratio(_stat(hs, "Key Passes"), _stat(hs, "Total passes")) * 100, 1
        ),
        "away_key_pass_pct": round(
            _safe_ratio(_stat(as_, "Key Passes"), _stat(as_, "Total passes")) * 100, 1
        ),
        "home_pass_accuracy": _stat(hs, "Passes %"),
        "away_pass_accuracy": _stat(as_, "Passes %"),
    }


def _compute_time_pressure(raw: RawMatchData) -> dict:
    """Analyze last 15 minutes of regular time + extra time pressure."""
    events = raw.events
    home_goals = raw.score.home
    away_goals = raw.score.away
    result = {"leading_team": None, "description": ""}

    # Find events in 75-90 and 105-120
    late_events = [e for e in events if
                   e.time_elapsed and (75 <= e.time_elapsed <= 90 or
                                       (e.period_id and 105 <= e.time_elapsed <= 120))]
    result["late_shots_home"] = sum(
        1 for e in late_events if e.team_id == raw.home_team.id
        and e.event_type in ("Goal", "Shot")
    )
    result["late_shots_away"] = sum(
        1 for e in late_events if e.team_id == raw.away_team.id
        and e.event_type in ("Goal", "Shot")
    )

    if home_goals > away_goals:
        result["leading_team"] = raw.home_team.name
    elif away_goals > home_goals:
        result["leading_team"] = raw.away_team.name

    return result


def _compute_player_efficiency(raw: RawMatchData) -> dict:
    """Top/bottom players by efficiency metrics."""
    all_players = []
    for p in raw.home_players + raw.away_players:
        xg = p.xg or 0
        mins = p.minutes_played or 1
        shots = p.shots_total or 0
        all_players.append({
            "name": p.name,
            "team": raw.home_team.name if p in raw.home_players else raw.away_team.name,
            "minutes": mins,
            "xg": round(xg, 4),
            "xg_per_90": round(_safe_ratio(xg, mins) * 90, 4),
            "shots": shots,
            "xg_per_shot": round(_safe_ratio(xg, shots), 4) if shots > 0 else 0,
            "goals": p.goals or 0,
        })

    # Sort by xG per 90
    by_xg90 = sorted(all_players, key=lambda x: x["xg_per_90"], reverse=True)
    by_efficiency = sorted(
        [p for p in all_players if p["xg_per_shot"] > 0],
        key=lambda x: x["xg_per_shot"], reverse=True
    )

    return {
        "top_xg90": by_xg90[:3],
        "bottom_xg90": by_xg90[-3:] if len(by_xg90) >= 3 else [],
        "top_xg_per_shot": by_efficiency[:3],
    }
