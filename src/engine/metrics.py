from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from src.collector.api_client import (
    LineupInfo,
    MatchEvent,
    PlayerStats,
    RawMatchData,
)

EPSILON = 0.001


@dataclass
class ComputedData:
    match_id: int
    home_team: str
    away_team: str
    home_goals: int
    away_goals: int
    home_ci: float
    away_ci: float
    home_tcr: float
    away_tcr: float
    home_pe: float
    away_pe: float
    ldi_result: dict = field(default_factory=dict)
    momentum: dict = field(default_factory=dict)
    home_mvp: Optional[PlayerStats] = None
    home_hidden_mvp: Optional[PlayerStats] = None
    home_black_hole: Optional[PlayerStats] = None
    away_mvp: Optional[PlayerStats] = None
    away_hidden_mvp: Optional[PlayerStats] = None
    away_black_hole: Optional[PlayerStats] = None
    home_subs_effect: list[dict] = field(default_factory=list)
    away_subs_effect: list[dict] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    home_attack_distribution: dict = field(default_factory=lambda: {"left": 0, "center": 0, "right": 0})
    away_attack_distribution: dict = field(default_factory=lambda: {"left": 0, "center": 0, "right": 0})
    home_long_ball_ratio: float = 0.0
    away_long_ball_ratio: float = 0.0
    # PPDA (Passes Per Defensive Action) — 压迫强度指标
    home_ppda: float = 0.0
    away_ppda: float = 0.0
    ppda_segments: list[dict] = field(default_factory=list)


def compute_control_index(
    home_possession: float,
    away_possession: float,
    home_pass_accuracy: float,
    away_pass_accuracy: float,
    home_shots_insidebox: int,
    away_shots_insidebox: int,
    home_corners: int,
    away_corners: int,
    home_ball_recoveries: int,
    away_ball_recoveries: int,
) -> tuple[float, float]:
    poss_sum = home_possession + away_possession + EPSILON
    poss_norm_home = home_possession / poss_sum

    pass_sum = home_pass_accuracy + away_pass_accuracy + EPSILON
    pass_norm_home = home_pass_accuracy / pass_sum

    territory_home = home_shots_insidebox + home_corners
    territory_away = away_shots_insidebox + away_corners
    territory_norm_home = (territory_home + EPSILON) / (territory_home + territory_away + EPSILON * 2)

    rec_norm_home = (home_ball_recoveries + EPSILON) / (
        home_ball_recoveries + away_ball_recoveries + EPSILON * 2
    )

    ci_home = 100 * (
        0.35 * poss_norm_home
        + 0.25 * pass_norm_home
        + 0.25 * territory_norm_home
        + 0.15 * rec_norm_home
    )
    ci_away = 100 - ci_home
    return round(ci_home, 1), round(ci_away, 1)


def compute_threat_conversion_rate(
    xg: float,
    big_chances: int,
    total_shots: int,
    corners: int,
) -> float:
    denominator = total_shots + 0.3 * corners + 0.01
    tcr = 100 * (xg + 0.3 * big_chances) / denominator
    return round(tcr, 1)


def compute_pressing_efficiency(
    home_rec: int, home_fouls: int,
    away_rec: int, away_fouls: int,
) -> tuple[float, float]:
    raw_home = home_rec / (home_fouls + 1)
    raw_away = away_rec / (away_fouls + 1)
    total = raw_home + raw_away
    if total < EPSILON:
        return 50.0, 50.0
    pe_home = round(100 * raw_home / total, 1)
    pe_away = round(100 - pe_home, 1)
    return pe_home, pe_away


def compute_ppda(
    opponent_passes: int, tackles: int, interceptions: int, fouls: int,
) -> float:
    """PPDA = 对手传球数 / (抢断 + 拦截 + 犯规)
    数值越低 = 压迫强度越大（对手每次传球前遭遇的防守动作越多）
    < 5: 高压迫  5-10: 中等压迫  10-15: 轻度压迫  >15: 低位防守
    """
    defensive_actions = tackles + interceptions + fouls
    if defensive_actions == 0:
        return 999.0
    return round(opponent_passes / defensive_actions, 1)


def interpret_ppda(ppda: float) -> str:
    if ppda > 900:
        return "数据不足"
    if ppda < 5:
        return "高压迫 — 对手每次传球都面临密集逼抢"
    if ppda < 10:
        return "中等压迫 — 主动在中前场施加压力"
    if ppda < 15:
        return "轻度压迫 — 倾向于中位防守"
    return "低位防守 — 更注重阵型而非逼抢"


def compute_ppda_segments(
    raw: "RawMatchData",
) -> list[dict]:
    """从趋势数据计算每15分钟的PPDA片段。
    需要趋势中的 type_id: 80(传球), 78(抢断), 100(拦截), 56(犯规)
    降级：趋势数据不可用时返回空列表
    """
    if not raw.trends:
        return []

    home_id = str(raw.home_team.id)
    away_id = str(raw.away_team.id)

    # Check if we have the needed type_ids
    needed = {80, 78, 100, 56}
    home_trends = raw.trends.get(home_id, {})
    away_trends = raw.trends.get(away_id, {})

    for tid in needed:
        tid_str = str(tid)
        if tid_str not in home_trends or tid_str not in away_trends:
            return []

    # Get trend series
    from collections import defaultdict

    def get_segmented_increments(points, window_size=15):
        """Split cumulative trend points into 15-min increments."""
        if not points:
            return defaultdict(float)
        sorted_pts = sorted(points, key=lambda p: (p.period_id, p.minute))
        buckets = defaultdict(float)
        prev_val = 0.0
        prev_minute = 0

        for pt in sorted_pts:
            seg = (pt.minute // window_size) * window_size
            # Key: use the current segment's cumulative value minus prev
            if pt.minute > prev_minute:
                buckets[seg] = max(0, pt.value - prev_val)
            prev_val = pt.value
            prev_minute = pt.minute

        return buckets

    home_passes = get_segmented_increments(home_trends["80"])
    away_passes = get_segmented_increments(away_trends["80"])
    home_tackles = get_segmented_increments(home_trends["78"])
    away_tackles = get_segmented_increments(away_trends["78"])
    home_int = get_segmented_increments(home_trends["100"])
    away_int = get_segmented_increments(away_trends["100"])
    home_fouls = get_segmented_increments(home_trends["56"])
    away_fouls = get_segmented_increments(away_trends["56"])

    # PPDA per 15-min segment
    all_segments = set()
    all_segments.update(home_passes.keys(), away_passes.keys(),
                        home_tackles.keys(), away_tackles.keys())

    segments = []
    for seg in sorted(all_segments):
        # Home PPDA = 对手(Away)的传球 / 主队防守动作
        h_def = home_tackles.get(seg, 0) + home_int.get(seg, 0) + home_fouls.get(seg, 0)
        a_def = away_tackles.get(seg, 0) + away_int.get(seg, 0) + away_fouls.get(seg, 0)

        h_ppda = round(away_passes.get(seg, 0) / max(h_def, 0.1), 1)
        a_ppda = round(home_passes.get(seg, 0) / max(a_def, 0.1), 1)

        label = f"{seg}-{seg + 15}min"
        segments.append({
            "label": label,
            "home_ppda": h_ppda,
            "away_ppda": a_ppda,
        })

    return segments


def interpret_tcr(tcr: float) -> str:
    if tcr > 25:
        return "极其高效：每次进攻几乎都构成真正威胁"
    elif tcr >= 15:
        return "进攻高效：在有限机会中创造了高质量射门"
    elif tcr >= 8:
        return "正常范围：进攻效率处于联赛平均水准"
    elif tcr >= 4:
        return "效率偏低：射门不少但难以形成真正威胁"
    else:
        return "进攻乏力：几乎无法产生有质量的射门机会"


def _compute_momentum_from_events(home_events, away_events) -> dict:
    from collections import defaultdict

    def get_segment(minute: int) -> int:
        if minute <= 15:
            return 0
        elif minute <= 30:
            return 1
        elif minute <= 45:
            return 2
        elif minute <= 60:
            return 3
        elif minute <= 75:
            return 4
        else:
            return 5

    seg_labels = ["0-15", "15-30", "30-45", "45-60", "60-75", "75-90"]
    home_segments = [0.0] * 6
    away_segments = [0.0] * 6

    for ev in home_events:
        seg = get_segment(ev.time_elapsed)
        if ev.event_type == "Goal":
            home_segments[seg] += 3.0
        elif ev.event_type == "Card":
            home_segments[seg] -= 0.5

    for ev in away_events:
        seg = get_segment(ev.time_elapsed)
        if ev.event_type == "Goal":
            away_segments[seg] += 3.0
        elif ev.event_type == "Card":
            away_segments[seg] -= 0.5

    segments = []
    for i, label in enumerate(seg_labels):
        segments.append(
            {"minute_range": label, "home": round(home_segments[i], 1), "away": round(away_segments[i], 1)}
        )

    key_events = []
    for ev in home_events + away_events:
        if ev.event_type in ("Goal", "Card", "subst"):
            side = "home" if ev.team_id != ev.team_id else (
                "home" if ev == ev else "away"
            )
            key_events.append(
                {
                    "minute": ev.time_elapsed,
                    "team": ev.team_name,
                    "label": f"{ev.event_type} - {ev.player_name}",
                    "type": ev.event_type,
                }
            )

    return {"segments": segments, "key_events": key_events}


def _compute_momentum_from_stats(
    home_stats: dict, away_stats: dict, events: list[MatchEvent]
) -> dict:
    seg_labels = ["0-15", "15-30", "30-45", "45-60", "60-75", "75-90"]
    home_segments = [0.0] * 6
    away_segments = [0.0] * 6

    for i in range(6):
        frac = 1.0 / 6
        moments = ["Shots on Goal", "Total Shots", "Corner Kicks", "Big Chances Created"]
        weights = [2.0, 0.5, 1.0, 3.0]

        for m, w in zip(moments, weights):
            h_val = float(home_stats.get(m, 0)) * frac
            a_val = float(away_stats.get(m, 0)) * frac
            home_segments[i] += h_val * w
            away_segments[i] += a_val * w

    segments = []
    for i, label in enumerate(seg_labels):
        segments.append(
            {"minute_range": label, "home": round(home_segments[i], 1), "away": round(away_segments[i], 1)}
        )

    key_events = []
    for ev in events:
        if ev.event_type in ("Goal", "Card"):
            key_events.append(
                {
                    "minute": ev.time_elapsed,
                    "team": ev.team_name,
                    "player": ev.player_name,
                    "label": f"{ev.detail or ev.event_type} - {ev.player_name}",
                    "type": ev.event_type,
                }
            )
        elif ev.event_type == "subst":
            key_events.append(
                {
                    "minute": ev.time_elapsed,
                    "team": ev.team_name,
                    "player": ev.player_name,
                    "label": f"换人: {ev.player_name}",
                    "type": ev.event_type,
                }
            )

    return {"segments": segments, "key_events": key_events}


def _determine_tags(home_goals: int, away_goals: int, home_xg: float, away_xg: float,
                    home_possession: float, away_possession: float,
                    home_shots: int, away_shots: int) -> list[str]:
    tags = []
    xg_diff = abs(home_xg - away_xg)
    poss_diff = abs(home_possession - away_possession)

    low_xg_won = False
    if home_goals > away_goals and home_xg < away_xg and xg_diff > 0.5:
        low_xg_won = True
    elif away_goals > home_goals and away_xg < home_xg and xg_diff > 0.5:
        low_xg_won = True

    if low_xg_won:
        tags.append("冷门")

    if home_shots > 3 * away_shots or away_shots > 3 * home_shots:
        if poss_diff > 20:
            tags.append("碾压局")

    if home_xg > 1.5 and away_xg > 1.5:
        total_goals = home_goals + away_goals
        if total_goals >= 3:
            tags.append("对攻战")

    total_goals = home_goals + away_goals
    if total_goals >= 5:
        tags.append("进球大战")
    elif total_goals == 0:
        tags.append("闷平")

    if home_goals > 0 and away_goals > 0 and home_xg < 0.5 and away_xg < 0.5:
        tags.append("非典型高分")

    if not tags:
        if xg_diff < 0.3 and poss_diff < 10:
            tags.append("势均力敌")
        else:
            tags.append("常规局")

    return tags


def _stat(stats: dict, *keys, default=0):
    for k in keys:
        v = stats.get(k)
        if v is not None:
            return v
    return default


def compute_all(raw: RawMatchData) -> ComputedData:
    hs = raw.home_stats
    aws = raw.away_stats

    home_poss = float(_stat(hs, "Ball Possession", "Ball Possession", default=50))
    away_poss = float(_stat(aws, "Ball Possession", "Ball Possession", default=50))
    home_pass_acc = float(_stat(hs, "Passes %", "Passes %", default=75))
    away_pass_acc = float(_stat(aws, "Passes %", "Passes %", default=75))
    home_shots_ib = int(float(_stat(hs, "Shots insidebox", "Shots insidebox", default=0)))
    away_shots_ib = int(float(_stat(aws, "Shots insidebox", "Shots insidebox", default=0)))
    home_corners = int(float(_stat(hs, "Corner Kicks", "Corner Kicks", default=0)))
    away_corners = int(float(_stat(aws, "Corner Kicks", "Corner Kicks", default=0)))
    home_rec = int(float(_stat(hs, "Ball Recoveries", "Ball Recoveries", default=0)))
    away_rec = int(float(_stat(aws, "Ball Recoveries", "Ball Recoveries", default=0)))

    home_ci, away_ci = compute_control_index(
        home_poss, away_poss, home_pass_acc, away_pass_acc,
        home_shots_ib, away_shots_ib, home_corners, away_corners,
        home_rec, away_rec,
    )

    home_xg = float(_stat(hs, "Expected Goals", "expected_goals", default=0))
    away_xg = float(_stat(aws, "Expected Goals", "expected_goals", default=0))
    home_bc = int(float(_stat(hs, "Big Chances Created", "Big Chances Created", default=0)))
    away_bc = int(float(_stat(aws, "Big Chances Created", "Big Chances Created", default=0)))
    home_shots = int(float(_stat(hs, "Total Shots", "Total Shots", default=0)))
    away_shots = int(float(_stat(aws, "Total Shots", "Total Shots", default=0)))

    home_tcr = compute_threat_conversion_rate(home_xg, home_bc, home_shots, home_corners)
    away_tcr = compute_threat_conversion_rate(away_xg, away_bc, away_shots, away_corners)

    home_fouls = int(float(_stat(hs, "Fouls", "Fouls", default=0)))
    away_fouls = int(float(_stat(aws, "Fouls", "Fouls", default=0)))
    home_pe, away_pe = compute_pressing_efficiency(home_rec, home_fouls, away_rec, away_fouls)

    from src.engine.simulator import compute_luck_deviation
    ldi_result = compute_luck_deviation(
        home_xg, away_xg, raw.score.home, raw.score.away
    )

    momentum = _compute_momentum_from_stats(hs, aws, raw.events)

    from src.engine.ratings import classify_players
    home_class = classify_players(raw.home_players)
    away_class = classify_players(raw.away_players)

    home_subs, away_subs = _compute_subs_effect(raw)

    tags = _determine_tags(
        raw.score.home, raw.score.away,
        home_xg, away_xg,
        home_poss, away_poss,
        home_shots, away_shots,
    )

    home_attack_dist = {"left": 33, "center": 34, "right": 33}
    away_attack_dist = {"left": 33, "center": 34, "right": 33}

    home_total_passes = float(_stat(hs, "Total passes", "Total passes", default=1))
    away_total_passes = float(_stat(aws, "Total passes", "Total passes", default=1))
    home_long = float(_stat(hs, "Long Balls", "Long Balls", default=0))
    home_long_ratio = home_long / max(home_total_passes, 1)
    away_long = float(_stat(aws, "Long Balls", "Long Balls", default=0))
    away_long_ratio = away_long / max(away_total_passes, 1)

    # PPDA — 压迫强度
    home_tackles_stat = int(float(_stat(hs, "Tackles", "Tackles", default=0)))
    away_tackles_stat = int(float(_stat(aws, "Tackles", "Tackles", default=0)))
    home_interceptions = int(float(_stat(hs, "Interceptions", "Interceptions", default=0)))
    away_interceptions = int(float(_stat(aws, "Interceptions", "Interceptions", default=0)))
    away_pass_total = int(float(_stat(aws, "Total passes", "Total passes", default=0)))
    home_pass_total = int(float(_stat(hs, "Total passes", "Total passes", default=0)))

    home_ppda = compute_ppda(away_pass_total, home_tackles_stat, home_interceptions, home_fouls)
    away_ppda = compute_ppda(home_pass_total, away_tackles_stat, away_interceptions, away_fouls)
    ppda_segments = compute_ppda_segments(raw)

    from src.engine.ratings import compute_player_contribution

    return ComputedData(
        match_id=raw.match_id,
        home_team=raw.home_team.name,
        away_team=raw.away_team.name,
        home_goals=raw.score.home,
        away_goals=raw.score.away,
        home_ci=home_ci,
        away_ci=away_ci,
        home_tcr=home_tcr,
        away_tcr=away_tcr,
        home_pe=home_pe,
        away_pe=away_pe,
        ldi_result=ldi_result,
        momentum=momentum,
        home_mvp=home_class.get("mvp"),
        home_hidden_mvp=home_class.get("hidden_mvp"),
        home_black_hole=home_class.get("black_hole"),
        away_mvp=away_class.get("mvp"),
        away_hidden_mvp=away_class.get("hidden_mvp"),
        away_black_hole=away_class.get("black_hole"),
        home_subs_effect=home_subs,
        away_subs_effect=away_subs,
        tags=tags,
        home_attack_distribution=home_attack_dist,
        away_attack_distribution=away_attack_dist,
        home_long_ball_ratio=round(home_long_ratio, 3),
        away_long_ball_ratio=round(away_long_ratio, 3),
        home_ppda=home_ppda,
        away_ppda=away_ppda,
        ppda_segments=ppda_segments,
    )


def _compute_subs_effect(raw: RawMatchData) -> tuple[list[dict], list[dict]]:
    home_subs = []
    away_subs = []
    subs_events = [e for e in raw.events if e.event_type == "subst"]

    for ev in subs_events:
        # API-Football: player_name = 被换下的球员, assist_name = 换上的球员
        sub_info = {
            "time": ev.time_elapsed,
            "player_out": ev.player_name,
            "player_in": ev.assist_name or "",
            "team": ev.team_name,
        }
        if ev.team_id == raw.home_team.id:
            home_subs.append(sub_info)
        else:
            away_subs.append(sub_info)

    for sub in home_subs:
        sub_player = _find_sub_player(sub["player_in"], raw.home_players)
        sub["minutes_played"] = sub_player.minutes_played if sub_player else 0
        sub["rating"] = sub_player.rating if sub_player else None
        sub["effect"] = "数据不足"

    for sub in away_subs:
        sub_player = _find_sub_player(sub["player_in"], raw.away_players)
        sub["minutes_played"] = sub_player.minutes_played if sub_player else 0
        sub["rating"] = sub_player.rating if sub_player else None
        sub["effect"] = "数据不足"

    return home_subs, away_subs


def _find_sub_player(name: str, players: list[PlayerStats]) -> Optional[PlayerStats]:
    for p in players:
        if p.name == name:
            return p
    return None
