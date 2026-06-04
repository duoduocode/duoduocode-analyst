"""
Efficiency paradox visualization: bar chart comparing xG vs actual goals,
shots vs SOT, and conversion efficiency for both teams.
"""

from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from src.collector.api_client import RawMatchData
from src.visualizer import HOME_COLOR, AWAY_COLOR


def plot_efficiency_comparison(
    raw: RawMatchData,
    output_path: str,
    dpi: int = 150,
) -> str:
    """Bar chart comparing attacking efficiency metrics."""
    hs = raw.home_stats
    aws = raw.away_stats

    home_xg = sum(p.xg for p in raw.home_players)
    away_xg = sum(p.xg for p in raw.away_players)
    home_goals = raw.score.home
    away_goals = raw.score.away
    home_shots = int(float(hs.get("Total Shots", 0)))
    away_shots = int(float(aws.get("Total Shots", 0)))
    home_sot = int(float(hs.get("Shots on Goal", 0)))
    away_sot = int(float(aws.get("Shots on Goal", 0)))
    home_big = int(float(hs.get("Big Chances Created", 0)))
    away_big = int(float(aws.get("Big Chances Created", 0)))

    home_conv = home_goals / home_shots * 100 if home_shots > 0 else 0
    away_conv = away_goals / away_shots * 100 if away_shots > 0 else 0
    home_sot_pct = home_sot / home_shots * 100 if home_shots > 0 else 0
    away_sot_pct = away_sot / away_shots * 100 if away_shots > 0 else 0

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    fig.patch.set_facecolor("#1a1a2e")

    categories = ["xG", "Goals", "Shots", "SOT", "Big Chances"]

    # ---- Chart 1: xG vs Actual Goals ----
    ax = axes[0, 0]
    ax.set_facecolor("#1a1a2e")
    x = np.arange(2)
    w = 0.35
    bars1 = ax.bar(x - w/2, [home_xg, away_xg], w, label="xG",
                   color=HOME_COLOR, alpha=0.7)
    bars2 = ax.bar(x + w/2, [home_goals, away_goals], w, label="实际进球",
                   color=AWAY_COLOR, alpha=0.7)
    ax.set_xticks(x)
    ax.set_xticklabels([raw.home_team.name, raw.away_team.name], color="white", fontsize=9)
    ax.set_ylabel("数值", color="white")
    ax.set_title("xG vs 实际进球", color="white", fontweight="bold")
    ax.legend(fontsize=8, facecolor="#1a1a2e", edgecolor="#333", labelcolor="white")
    ax.tick_params(colors="white")
    for spine in ax.spines.values():
        spine.set_color("#333")
    # Add value labels
    for bar in bars1 + bars2:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., h + 0.02, f"{h:.2f}",
                ha="center", va="bottom", fontsize=8, color="white")

    # ---- Chart 2: Shots vs SOT ----
    ax = axes[0, 1]
    ax.set_facecolor("#1a1a2e")
    bars1 = ax.bar(x - w/2, [home_shots, away_shots], w, label="总射门",
                   color=HOME_COLOR, alpha=0.7)
    bars2 = ax.bar(x + w/2, [home_sot, away_sot], w, label="射正",
                   color="#ff5555", alpha=0.7)
    ax.set_xticks(x)
    ax.set_xticklabels([raw.home_team.name, raw.away_team.name], color="white", fontsize=9)
    ax.set_title("射门 vs 射正", color="white", fontweight="bold")
    ax.legend(fontsize=8, facecolor="#1a1a2e", edgecolor="#333", labelcolor="white")
    ax.tick_params(colors="white")
    for spine in ax.spines.values():
        spine.set_color("#333")
    for bar in bars1 + bars2:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., h + 0.3, f"{int(h)}",
                ha="center", va="bottom", fontsize=8, color="white")

    # ---- Chart 3: Conversion rate % ----
    ax = axes[1, 0]
    ax.set_facecolor("#1a1a2e")
    bars = ax.bar(x, [home_conv, away_conv], w * 2,
                  color=[HOME_COLOR, AWAY_COLOR], alpha=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels([raw.home_team.name, raw.away_team.name], color="white", fontsize=9)
    ax.set_ylabel("%", color="white")
    ax.set_title("射门转化率 %", color="white", fontweight="bold")
    ax.tick_params(colors="white")
    for spine in ax.spines.values():
        spine.set_color("#333")
    for bar in bars:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., h + 0.1, f"{h:.1f}%",
                ha="center", va="bottom", fontsize=9, color="white", fontweight="bold")

    # ---- Chart 4: SOT accuracy + Big Chance conversion ----
    ax = axes[1, 1]
    ax.set_facecolor("#1a1a2e")
    bars1 = ax.bar(x - w/2, [home_sot_pct, away_sot_pct], w, label="射正率%",
                   color=HOME_COLOR, alpha=0.7)
    bars2 = ax.bar(x + w/2, [home_big, away_big], w, label="绝佳机会",
                   color="#ffaa00", alpha=0.7)
    ax.set_xticks(x)
    ax.set_xticklabels([raw.home_team.name, raw.away_team.name], color="white", fontsize=9)
    ax.set_title("射正率% & 绝佳机会", color="white", fontweight="bold")
    ax.legend(fontsize=8, facecolor="#1a1a2e", edgecolor="#333", labelcolor="white")
    ax.tick_params(colors="white")
    for spine in ax.spines.values():
        spine.set_color("#333")
    for bar in bars1:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., h + 0.3, f"{h:.1f}%",
                ha="center", va="bottom", fontsize=8, color="white")
    for bar in bars2:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., h + 0.05, f"{int(h)}",
                ha="center", va="bottom", fontsize=8, color="white")

    fig.suptitle("进攻效率对比", fontsize=14, color="white", fontweight="bold", y=0.98)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(output_path, dpi=dpi, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    return output_path
