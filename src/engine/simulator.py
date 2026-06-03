import math
import random
from collections import Counter


def _poisson_rvs(lam, size):
    try:
        from scipy.stats import poisson
        return list(poisson.rvs(lam, size=size))
    except ImportError:
        try:
            import numpy as np
            return list(np.random.poisson(lam, size=size))
        except ImportError:
            return _poisson_rvs_pure(lam, size)


def _poisson_rvs_pure(lam, size):
    _exp = math.exp(-lam)
    result = []
    for _ in range(size):
        k = 0
        p = 1.0
        while p > _exp:
            k += 1
            p *= random.random()
        result.append(k - 1)
    return result


def compute_luck_deviation(
    home_xg: float,
    away_xg: float,
    actual_home_goals: int,
    actual_away_goals: int,
    simulations: int = 10000,
) -> dict:
    try:
        import numpy
        pass
    except ImportError:
        simulations = min(simulations, 2000)

    home_goals_sim = _poisson_rvs(home_xg, simulations)
    away_goals_sim = _poisson_rvs(away_xg, simulations)

    score_counter = Counter()
    home_wins = 0
    draws = 0
    away_wins = 0

    for h, a in zip(home_goals_sim, away_goals_sim):
        score_counter[(h, a)] += 1
        if h > a:
            home_wins += 1
        elif h == a:
            draws += 1
        else:
            away_wins += 1

    actual_count = score_counter.get((actual_home_goals, actual_away_goals), 0)
    actual_pct = round(100 * actual_count / simulations, 2)

    top_scores = score_counter.most_common(5)
    most_likely_count = top_scores[0][1] if top_scores else 1
    most_likely_pct = round(100 * most_likely_count / simulations, 2)

    ldi = round(actual_count / max(most_likely_count, 1), 3)

    if ldi > 0.7:
        interpretation = "实力碾压，结果完全符合预期"
    elif ldi >= 0.3:
        interpretation = "正常范围，结果与数据趋势一致"
    elif ldi >= 0.1:
        interpretation = "运气成分较大，结果与数据有所背离"
    else:
        interpretation = "极度反常，典型的冷门或意外赛果"

    top3_scores = [
        {"score": f"{h}-{a}", "pct": round(100 * c / simulations, 1)}
        for (h, a), c in top_scores[:3]
    ]

    home_win_pct = round(100 * home_wins / simulations, 1)
    draw_pct = round(100 * draws / simulations, 1)
    away_win_pct = round(100 * away_wins / simulations, 1)

    return {
        "home_win_pct": home_win_pct,
        "draw_pct": draw_pct,
        "away_win_pct": away_win_pct,
        "top3_scores": top3_scores,
        "ldi": ldi,
        "interpretation": interpretation,
        "actual_pct": actual_pct,
        "most_likely_pct": most_likely_pct,
    }
