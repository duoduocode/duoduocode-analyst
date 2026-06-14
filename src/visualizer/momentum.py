"""
Momentum curve v3: plot actual possession + attacks trends over time
with key events annotated.
"""

from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

from src.collector.api_client import RawMatchData, TrendPoint
from src.visualizer import HOME_COLOR, AWAY_COLOR


def plot_momentum_curve_v3(
    raw: RawMatchData,
    output_path: str,
    dpi: int = 150,
) -> str:
    """Plot possession% and attacking trends from actual trends data."""

    trends = raw.trends or {}
    home_id = str(raw.home_team.id)
    away_id = str(raw.away_team.id)
    home_name = raw.home_team.name
    away_name = raw.away_team.name

    # Extract possession trends
    home_poss = _get_trend_series(trends, home_id, "45")  # possession type_id=45
    away_poss = _get_trend_series(trends, away_id, "45")

    # Extract attack trends
    home_att = _get_trend_series(trends, home_id, "43")  # attacks type_id=43
    away_att = _get_trend_series(trends, away_id, "43")

    # Extract shots trends
    home_shots = _get_trend_series(trends, home_id, "42")
    away_shots = _get_trend_series(trends, away_id, "42")

    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)
    fig.patch.set_facecolor("#1a1a2e")

    colors = [HOME_COLOR, AWAY_COLOR]

    # ---- Panel 1: Possession % ----
    ax = axes[0]
    ax.set_facecolor("#1a1a2e")
    if home_poss:
        xs, ys = zip(*home_poss)
        ax.fill_between(xs, ys, alpha=0.2, color=colors[0])
        ax.plot(xs, ys, color=colors[0], linewidth=1.5)
    if away_poss:
        xs, ys = zip(*away_poss)
        ax.fill_between(xs, ys, alpha=0.2, color=colors[1])
        ax.plot(xs, ys, color=colors[1], linewidth=1.5)
    ax.set_ylabel("控球率 %", color="white")
    ax.set_title(f"控球率走势 ({home_name} {colors[0]}) | {away_name} {colors[1]})", 
                 color="white", fontweight="bold", fontsize=11)
    ax.tick_params(colors="white")
    ax.grid(True, alpha=0.15, color="white")
    for spine in ax.spines.values():
        spine.set_color("#333")
    ax.set_ylim(0, 100)

    # ---- Panel 2: Cumulative Attacks ----
    ax = axes[1]
    ax.set_facecolor("#1a1a2e")
    if home_att:
        xs, ys = zip(*home_att)
        ax.plot(xs, ys, color=colors[0], linewidth=1.5)
    if away_att:
        xs, ys = zip(*away_att)
        ax.plot(xs, ys, color=colors[1], linewidth=1.5)
    ax.set_ylabel("累计进攻", color="white")
    ax.set_title("进攻次数累计", color="white", fontweight="bold", fontsize=11)
    ax.tick_params(colors="white")
    ax.grid(True, alpha=0.15, color="white")
    for spine in ax.spines.values():
        spine.set_color("#333")

    # ---- Panel 3: Cumulative Shots ----
    ax = axes[2]
    ax.set_facecolor("#1a1a2e")
    if home_shots:
        xs, ys = zip(*home_shots)
        ax.plot(xs, ys, color=colors[0], linewidth=1.5)
    if away_shots:
        xs, ys = zip(*away_shots)
        ax.plot(xs, ys, color=colors[1], linewidth=1.5)
    ax.set_xlabel("比赛分钟", color="white")
    ax.set_ylabel("累计射门", color="white")
    ax.set_title("射门次数累计", color="white", fontweight="bold", fontsize=11)
    ax.tick_params(colors="white")
    ax.grid(True, alpha=0.15, color="white")
    for spine in ax.spines.values():
        spine.set_color("#333")

    # ---- Annotate key events on all panels ----
    key_events = [e for e in raw.events if e.event_type in ("Goal", "Card")
                  or (e.event_type == "subst" and e.detail == "substitution")]
    for e in key_events:
        mi = e.time_elapsed or 0
        if mi <= 0:
            continue
        color = HOME_COLOR if e.team_id == raw.home_team.id else AWAY_COLOR
        icon = {"Goal": "⚽", "Card": "▴", "subst": "⇅"}.get(e.event_type, "|")
        # Only annotate on the top panel to avoid clutter
        axes[0].axvline(x=mi, color=color, linewidth=0.8, alpha=0.5, linestyle="--")
        axes[1].axvline(x=mi, color=color, linewidth=0.8, alpha=0.5, linestyle="--")
        axes[2].axvline(x=mi, color=color, linewidth=0.8, alpha=0.5, linestyle="--")

    fig.suptitle(f"比赛趋势走势 — {home_name} vs {away_name}",
                 fontsize=14, color="white", fontweight="bold", y=0.99)
    fig.tight_layout(rect=[0, 0.02, 1, 0.96])
    fig.savefig(output_path, dpi=dpi, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    return output_path


def _get_trend_series(trends: dict, team_id: int, type_id: int) -> list[tuple[float, float]]:
    """Extract (minute, value) series from trends dict."""
    team_trends = trends.get(team_id, {})
    pts = team_trends.get(type_id, [])
    if not pts:
        return []
    # Sort by minute and deduplicate
    seen = set()
    result = []
    for p in sorted(pts, key=lambda p: p.minute):
        if p.minute not in seen:
            seen.add(p.minute)
            result.append((float(p.minute), float(p.value)))
    return result
