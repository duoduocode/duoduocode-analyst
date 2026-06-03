from __future__ import annotations

from src.collector.api_client import PlayerStats


def compute_player_contribution(player: PlayerStats) -> float:
    if player.minutes_played <= 0:
        return 0.0

    duel_win_rate = (
        player.duels_won / max(player.duels_total, 1)
        if player.duels_total > 0
        else 0.0
    )

    score = (
        player.goals * 30
        + player.assists * 20
        + player.shots_on * 5
        + player.passes_key * 8
        + player.tackles_total * 3
        + player.tackles_interceptions * 3
        + duel_win_rate * 10
        - player.fouls_committed * 3
    )

    return round(score, 2)


def classify_players(players: list[PlayerStats]) -> dict:
    if not players:
        return {"mvp": None, "hidden_mvp": None, "black_hole": None}

    rated = sorted(
        [p for p in players if p.rating is not None],
        key=lambda p: p.rating,
        reverse=True,
    )

    mvp = rated[0] if rated else None

    top_three_ids = {p.id for p in rated[:3]}

    scored = sorted(
        [(p, compute_player_contribution(p)) for p in players],
        key=lambda x: x[1],
        reverse=True,
    )

    hidden_mvp = None
    for p, _ in scored:
        if p.id not in top_three_ids and p.minutes_played > 30:
            hidden_mvp = p
            break

    black_hole = None
    candidates = [
        p
        for p in players
        if p.rating is not None and p.rating < 6.5 and p.minutes_played >= 60
    ]
    if candidates:
        grouped = {}
        for p in candidates:
            pos_key = p.position if p.position else "Unknown"
            grouped.setdefault(pos_key, []).append(p)
        worst_by_pos = []
        for pos_key, pos_players in grouped.items():
            worst = min(pos_players, key=lambda p: compute_player_contribution(p))
            worst_by_pos.append((worst, compute_player_contribution(worst)))
        if worst_by_pos:
            black_hole, _ = min(worst_by_pos, key=lambda x: x[1])

    return {"mvp": mvp, "hidden_mvp": hidden_mvp, "black_hole": black_hole}


def get_player_radar_values(player: PlayerStats) -> dict:
    return {
        "射门威胁": min(player.shots_on / max(player.shots_total, 1), 1.0) if player.shots_total > 0 else 0,
        "传球创造力": min(player.passes_key / 5, 1.0),
        "抢断贡献": min(player.tackles_total / 10, 1.0),
        "拦截": min(player.tackles_interceptions / 5, 1.0),
        "对抗胜率": player.duels_won / max(player.duels_total, 1) if player.duels_total > 0 else 0,
        "传球稳定性": player.passes_accuracy / 100 if player.passes_accuracy > 0 else 0,
        "控球贡献": min(player.dribbles_success / 5, 1.0),
    }


def get_team_average_radar(players: list[PlayerStats]) -> dict:
    if not players:
        return {}
    keys = ["射门威胁", "传球创造力", "抢断贡献", "拦截", "对抗胜率", "传球稳定性", "控球贡献"]
    sums = {k: 0.0 for k in keys}
    count = 0
    for p in players:
        if p.minutes_played > 15:
            vals = get_player_radar_values(p)
            for k in keys:
                sums[k] += vals[k]
            count += 1
    if count == 0:
        return {k: 0.0 for k in keys}
    return {k: round(v / count, 3) for k, v in sums.items()}
