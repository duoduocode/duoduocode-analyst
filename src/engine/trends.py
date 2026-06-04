from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from src.collector.api_client import (
    FIXTURE_STAT_MAP,
    RawMatchData,
    TrendPoint,
)

TREND_TYPE_NAMES: dict[int, str] = {
    80: "passes",
    43: "attacks",
    106: "duels_won",
    45: "possession",
    98: "crosses",
    99: "accurate_crosses",
    42: "shots",
    86: "shots_on_target",
    41: "shots_off_target",
    78: "tackles",
    100: "interceptions",
    34: "corners",
    117: "key_passes",
    108: "dribbles",
    109: "successful_dribbles",
    56: "fouls",
    44: "dangerous_attacks",
    49: "shots_insidebox",
    50: "shots_outsidebox",
    65: "successful_headers",
    60: "throwins",
    53: "goal_kicks",
    55: "free_kicks",
    105: "total_duels",
    580: "big_chances",
    27271: "ball_recoveries",
}

TREND_NAME_CN: dict[str, str] = {
    "passes": "传球",
    "attacks": "进攻",
    "duels_won": "赢得对抗",
    "possession": "控球率",
    "crosses": "传中",
    "accurate_crosses": "精准传中",
    "shots": "射门",
    "shots_on_target": "射正",
    "shots_off_target": "射偏",
    "tackles": "抢断",
    "interceptions": "拦截",
    "corners": "角球",
    "key_passes": "关键传球",
    "dribbles": "过人尝试",
    "successful_dribbles": "成功过人",
    "fouls": "犯规",
    "dangerous_attacks": "威胁进攻",
    "shots_insidebox": "禁区内射门",
    "shots_outsidebox": "禁区外射门",
    "successful_headers": "成功头球",
    "throwins": "界外球",
    "goal_kicks": "球门球",
    "free_kicks": "任意球",
    "total_duels": "总对抗",
    "big_chances": "绝佳机会",
    "ball_recoveries": "球权回收",
}

WINDOW_SIZES = [5, 10, 15]


@dataclass
class TrendSeries:
    type_id: int
    type_name: str
    participant_id: int
    increments: list[float]
    cumulative: list[float]
    minutes: list[int]


@dataclass
class WindowAgg:
    window_start: int
    window_end: int
    total: float
    mean: float
    peak_minute: int
    peak_value: float


@dataclass
class SlopeEvent:
    minute: int
    direction: str
    magnitude: float
    before_slope: float
    after_slope: float


@dataclass
class TurningPoint:
    minute: int
    metric: str
    description: str
    confidence: float


@dataclass
class DuelDecay:
    player_id: int = 0
    player_name: str = ""
    early_win_rate: float = 0.0
    late_win_rate: float = 0.0
    decay: float = 0.0
    severity: str = "none"


@dataclass
class TrendAnalysis:
    home_series: dict[int, TrendSeries] = field(default_factory=dict)
    away_series: dict[int, TrendSeries] = field(default_factory=dict)
    turning_points: list[TurningPoint] = field(default_factory=list)
    rhythm_phases: list[dict] = field(default_factory=list)
    duel_decay_home: list[DuelDecay] = field(default_factory=list)
    duel_decay_away: list[DuelDecay] = field(default_factory=list)
    pressing_fade_home: float = 0.0
    pressing_fade_away: float = 0.0
    style_shift_home: dict = field(default_factory=dict)
    style_shift_away: dict = field(default_factory=dict)


def _type_name(type_id: int) -> str:
    return TREND_TYPE_NAMES.get(type_id, FIXTURE_STAT_MAP.get(type_id, f"type_{type_id}"))


def compute_increments(points: list[TrendPoint]) -> TrendSeries:
    if not points:
        return TrendSeries(type_id=0, type_name="", participant_id=0,
                           increments=[], cumulative=[], minutes=[])

    sorted_pts = sorted(points, key=lambda p: (p.period_id, p.minute))
    type_id = sorted_pts[0].__dict__.get("type_id", 0) if hasattr(sorted_pts[0], "type_id") else 0

    increments = []
    cumulative = []
    minutes = []
    prev = 0.0

    for pt in sorted_pts:
        increments.append(max(0, pt.value - prev))
        cumulative.append(pt.value)
        minutes.append(pt.minute)
        prev = pt.value

    return TrendSeries(
        type_id=type_id,
        type_name="",
        participant_id=0,
        increments=increments,
        cumulative=cumulative,
        minutes=minutes,
    )


def window_aggregate(series: TrendSeries, window_size: int) -> list[WindowAgg]:
    result = []
    inc = series.increments
    mins = series.minutes
    n = len(inc)
    if n == 0 or window_size <= 0:
        return result

    for i in range(n - window_size + 1):
        chunk = inc[i:i + window_size]
        chunk_mins = mins[i:i + window_size]
        total = sum(chunk)
        mean = total / window_size
        peak = max(chunk)
        peak_idx = chunk.index(peak)
        result.append(WindowAgg(
            window_start=mins[i],
            window_end=chunk_mins[-1],
            total=total,
            mean=mean,
            peak_minute=chunk_mins[peak_idx],
            peak_value=peak,
        ))
    return result


def detect_slope_changes(series: TrendSeries, window_size: int = 10,
                         threshold: float = 0.30) -> list[SlopeEvent]:
    events = []
    inc = series.increments
    mins = series.minutes
    n = len(inc)
    if n < 2 * window_size:
        return events

    prev_sum = sum(inc[:window_size])
    prev_count = window_size

    for i in range(window_size, n - window_size + 1):
        cur_sum = sum(inc[i:i + window_size])
        cur_count = window_size
        prev_avg = prev_sum / prev_count if prev_count else 0
        cur_avg = cur_sum / cur_count if cur_count else 0

        if prev_avg > 0 and cur_avg > 0:
            change = (cur_avg - prev_avg) / max(prev_avg, 0.1)
        elif cur_avg > 0:
            change = 1.0
        elif prev_avg > 0:
            change = -1.0
        else:
            change = 0.0

        if abs(change) >= threshold:
            direction = "accelerating" if change > 0 else "decelerating"
            events.append(SlopeEvent(
                minute=mins[i],
                direction=direction,
                magnitude=abs(change),
                before_slope=round(prev_avg, 2),
                after_slope=round(cur_avg, 2),
            ))

        prev_sum += inc[i] - inc[i - window_size]
        prev_count = window_size

    return _deduplicate_slopes(events, min_gap=5)


def _deduplicate_slopes(events: list[SlopeEvent], min_gap: int = 5) -> list[SlopeEvent]:
    if not events:
        return events
    merged = [events[0]]
    for e in events[1:]:
        if e.minute - merged[-1].minute < min_gap:
            if e.magnitude > merged[-1].magnitude:
                merged[-1] = e
        else:
            merged.append(e)
    return merged


TREND_DIVERGENCE_CONFIGS = [
    {"type_ids": [80], "name": "传球节奏", "window": 10, "threshold": 15},
    {"type_ids": [43], "name": "进攻频次", "window": 10, "threshold": 15},
    {"type_ids": [106], "name": "对抗优势", "window": 10, "threshold": 12},
    {"type_ids": [42, 86], "name": "射门压制", "window": 10, "threshold": 8},
    {"type_ids": [34], "name": "角球", "window": 15, "threshold": 4},
    {"type_ids": [98, 99], "name": "传中活跃度", "window": 10, "threshold": 10},
    {"type_ids": [78, 100], "name": "防守强度", "window": 10, "threshold": 10},
    {"type_ids": [44], "name": "威胁进攻密度", "window": 10, "threshold": 12},
    {"type_ids": [56], "name": "犯规节奏", "window": 10, "threshold": 8},
    {"type_ids": [27271], "name": "球权回收", "window": 10, "threshold": 10},
]


def detect_turning_points(trends: dict, home_id: int, away_id: int,
                          window_size: int = 10) -> list[TurningPoint]:
    points = []

    for config in TREND_DIVERGENCE_CONFIGS:
        type_ids = config["type_ids"]
        metric_name = config["name"]
        threshold = config["threshold"]
        w = config["window"]

        home_inc = _merged_increments(trends, home_id, type_ids)
        away_inc = _merged_increments(trends, away_id, type_ids)

        min_len = min(len(home_inc), len(away_inc))
        if min_len < w:
            continue

        for i in range(min_len - w + 1):
            h_sum = sum(home_inc[i:i + w])
            a_sum = sum(away_inc[i:i + w])
            total = h_sum + a_sum
            if total < threshold * 0.5:
                continue
            gap = abs(h_sum - a_sum)
            if gap >= threshold:
                dominant = "主队" if h_sum > a_sum else "客队"
                points.append(TurningPoint(
                    minute=i + w,
                    metric=metric_name,
                    description=f"第{i}-{i+w}分钟区间{metric_name}{dominant}明显占优",
                    confidence=min(gap / threshold, 1.0),
                ))

    return _deduplicate_turning_points(points, min_gap=8)


def _merged_increments(trends: dict, participant_id: int, type_ids: list[int]) -> list[float]:
    team_trends = trends.get(participant_id, {})
    merged = []
    for tid in type_ids:
        pts = team_trends.get(tid, [])
        if pts:
            series = compute_increments(pts)
            merged = _merge_series(merged, series.increments)
    return merged


def _merge_series(a: list[float], b: list[float]) -> list[float]:
    if not a:
        return b[:]
    if not b:
        return a[:]
    result = []
    max_len = max(len(a), len(b))
    for i in range(max_len):
        va = a[i] if i < len(a) else 0
        vb = b[i] if i < len(b) else 0
        result.append(va + vb)
    return result


def _deduplicate_turning_points(points: list[TurningPoint], min_gap: int = 8) -> list[TurningPoint]:
    if not points:
        return points
    sorted_pts = sorted(points, key=lambda p: p.confidence, reverse=True)
    kept = []
    used_minutes = set()
    for tp in sorted_pts:
        if any(abs(tp.minute - m) < min_gap for m in used_minutes):
            continue
        kept.append(tp)
        used_minutes.add(tp.minute)
    return sorted(kept, key=lambda p: p.minute)


def compute_duel_decay(trends: dict, participant_id: int,
                       players: list, half_duration: int = 45) -> list[DuelDecay]:
    team_trends = trends.get(participant_id, {})
    duels_pts = team_trends.get(106, [])
    if not duels_pts:
        return []

    series = compute_increments(duels_pts)
    mid = len(series.increments) // 2
    if mid < 5:
        return []

    early = series.increments[:mid]
    late = series.increments[mid:]

    early_rate = sum(early) / max(len(early), 1)
    late_rate = sum(late) / max(len(late), 1)
    decay = (early_rate - late_rate) / max(early_rate, 0.1)
    decay = max(0, decay)

    result = []
    severity = "none"
    if decay > 0.40:
        severity = "severe"
    elif decay > 0.20:
        severity = "moderate"
    elif decay > 0.05:
        severity = "mild"

    result.append(DuelDecay(
        player_id=0,
        player_name="全队",
        early_win_rate=round(early_rate, 2),
        late_win_rate=round(late_rate, 2),
        decay=round(decay, 3),
        severity=severity,
    ))

    return result


def compute_pressing_fade(trends: dict, home_id: int, away_id: int) -> tuple[float, float]:
    def _fade(pid: int) -> float:
        team_trends = trends.get(pid, {})
        rec_pts = team_trends.get(27271, [])  # ball recoveries
        fouls_pts = team_trends.get(56, [])

        if not rec_pts and not fouls_pts:
            return 0.0

        if rec_pts:
            series = compute_increments(rec_pts)
            rec_inc = series.increments
        else:
            rec_inc = [0] * len(fouls_pts)

        if fouls_pts:
            foul_series = compute_increments(fouls_pts)
            foul_inc = foul_series.increments
        else:
            foul_inc = [1] * len(rec_inc)

        n = min(len(rec_inc), len(foul_inc))
        if n < 20:
            return 0.0

        split = n // 2
        early_pe = sum(rec_inc[:split]) / max(sum(foul_inc[:split]), 1)
        late_pe = sum(rec_inc[split:]) / max(sum(foul_inc[split:]), 1)
        if early_pe <= 0:
            return 0.0
        return round((early_pe - late_pe) / early_pe, 3)

    return _fade(home_id), _fade(away_id)


def compute_style_shift(trends: dict, participant_id: int) -> dict:
    team_trends = trends.get(participant_id, {})
    short_pts = team_trends.get(63, [])
    long_pts = team_trends.get(62, [])

    if not short_pts or not long_pts:
        crosses_pts = team_trends.get(98, [])
        attacks_pts = team_trends.get(43, [])
        if crosses_pts and attacks_pts:
            cross_inc = compute_increments(crosses_pts).increments
            attack_inc = compute_increments(attacks_pts).increments
            n = min(len(cross_inc), len(attack_inc))
            if n < 20:
                return {"shift_detected": False, "direction": "stable", "magnitude": 0.0}
            split = n // 2
            early_ratio = sum(cross_inc[:split]) / max(sum(attack_inc[:split]), 1)
            late_ratio = sum(cross_inc[split:]) / max(sum(attack_inc[split:]), 1)
            if early_ratio <= 0:
                return {"shift_detected": False, "direction": "stable", "magnitude": 0.0}
            change = (late_ratio - early_ratio) / early_ratio
            direction = "more_direct" if change > 0.15 else ("more_possessional" if change < -0.15 else "stable")
            return {
                "shift_detected": abs(change) > 0.15,
                "direction": direction,
                "magnitude": round(abs(change), 3),
                "metric": "cross_per_attack",
            }
        return {"shift_detected": False, "direction": "stable", "magnitude": 0.0}

    short_inc = compute_increments(short_pts).increments
    long_inc = compute_increments(long_pts).increments
    n = min(len(short_inc), len(long_inc))
    if n < 20:
        return {"shift_detected": False, "direction": "stable", "magnitude": 0.0}

    split = n // 2
    early_ratio = sum(long_inc[:split]) / max(sum(short_inc[:split]), 1)
    late_ratio = sum(long_inc[split:]) / max(sum(short_inc[split:]), 1)
    if early_ratio <= 0:
        return {"shift_detected": False, "direction": "stable", "magnitude": 0.0}
    change = (late_ratio - early_ratio) / early_ratio
    direction = "more_direct" if change > 0.15 else ("more_possessional" if change < -0.15 else "stable")
    return {
        "shift_detected": abs(change) > 0.15,
        "direction": direction,
        "magnitude": round(abs(change), 3),
        "metric": "long_vs_short_pass",
    }


def compute_rhythm_phases(trends: dict, home_id: int, away_id: int) -> list[dict]:
    home_trends = trends.get(home_id, {})
    away_trends = trends.get(away_id, {})

    h_attack_pts = home_trends.get(44, []) or home_trends.get(43, [])
    a_attack_pts = away_trends.get(44, []) or away_trends.get(43, [])

    if not h_attack_pts or not a_attack_pts:
        return []

    h_series = compute_increments(h_attack_pts)
    a_series = compute_increments(a_attack_pts)

    n = min(len(h_series.increments), len(a_series.increments))
    if n < 15:
        return []

    phases = []
    phase_window = 15
    prev_dominant = None

    for i in range(0, n - phase_window + 1, 5):
        h_chunk = sum(h_series.increments[i:i + phase_window])
        a_chunk = sum(a_series.increments[i:i + phase_window])
        diff = h_chunk - a_chunk

        if abs(diff) < 3:
            dominant = "balanced"
        elif diff > 0:
            dominant = "home"
        else:
            dominant = "away"

        if dominant != prev_dominant or not phases:
            phases.append({
                "start_minute": h_series.minutes[i],
                "end_minute": h_series.minutes[min(i + phase_window - 1, n - 1)],
                "dominant": dominant,
                "home_intensity": round(h_chunk, 1),
                "away_intensity": round(a_chunk, 1),
            })
        else:
            phases[-1]["end_minute"] = h_series.minutes[min(i + phase_window - 1, n - 1)]
            phases[-1]["home_intensity"] = round(phases[-1]["home_intensity"] + h_chunk, 1)
            phases[-1]["away_intensity"] = round(phases[-1]["away_intensity"] + a_chunk, 1)

        prev_dominant = dominant

    return phases


def analyze_trends(raw: RawMatchData) -> TrendAnalysis:
    trends = raw.trends
    home_id = raw.home_team.id
    away_id = raw.away_team.id

    home_series = {}
    away_series = {}

    for participant_id, type_dict in trends.items():
        for type_id, points in type_dict.items():
            if not points:
                continue
            series = compute_increments(points)
            series.type_id = type_id
            series.type_name = _type_name(type_id)
            series.participant_id = participant_id
            if participant_id == home_id:
                home_series[type_id] = series
            elif participant_id == away_id:
                away_series[type_id] = series

    turning_points = detect_turning_points(trends, home_id, away_id)

    rhythm_phases = compute_rhythm_phases(trends, home_id, away_id)

    duel_decay_home = compute_duel_decay(trends, home_id, raw.home_players)
    duel_decay_away = compute_duel_decay(trends, away_id, raw.away_players)

    fade_h, fade_a = compute_pressing_fade(trends, home_id, away_id)

    style_h = compute_style_shift(trends, home_id)
    style_a = compute_style_shift(trends, away_id)

    return TrendAnalysis(
        home_series=home_series,
        away_series=away_series,
        turning_points=turning_points,
        rhythm_phases=rhythm_phases,
        duel_decay_home=duel_decay_home,
        duel_decay_away=duel_decay_away,
        pressing_fade_home=fade_h,
        pressing_fade_away=fade_a,
        style_shift_home=style_h,
        style_shift_away=style_a,
    )
