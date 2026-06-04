"""
Sub impact v3: multi-metric comparison of before/after substitution windows.
Shows possession%, shots, attacks, crosses changes for each substitution.
"""

from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from src.collector.api_client import RawMatchData
from src.visualizer import HOME_COLOR, AWAY_COLOR


def plot_sub_impacts_v3(
    raw: RawMatchData,
    sub_impacts: list[dict],
    output_path: str,
    dpi: int = 150,
) -> str:
    """Draw multi-metric radar + bar chart for each substitution."""
    if not sub_impacts:
        fig, ax = plt.subplots(figsize=(6, 3))
        ax.text(0.5, 0.5, "无换人数据", ha="center", va="center", fontsize=12)
        fig.savefig(output_path, dpi=dpi)
        plt.close(fig)
        return output_path

    n = len(sub_impacts)
    cols = min(3, n)
    rows = (n + cols - 1) // cols

    fig, axes = plt.subplots(rows, cols, figsize=(cols * 5, rows * 4.5),
                              squeeze=False)
    fig.patch.set_facecolor("#1a1a2e")

    metrics = [
        ("possession", "控球率"),
        ("shots", "射门"),
        ("attacks", "进攻"),
        ("dangerous_attacks", "威胁进攻"),
        ("passes", "传球"),
        ("duels_won", "赢得对抗"),
    ]
    metric_names = [m[1] for m in metrics]
    n_metrics = len(metrics)

    for idx, si in enumerate(sub_impacts):
        r, c = idx // cols, idx % cols
        ax = axes[r, c]
        ax.set_facecolor("#1a1a2e")

        team = si.get("team", "?")
        player_on = si.get("player_on", "?")
        player_off = si.get("player_off", "?")
        minute = si.get("minute_display", "?")
        color = HOME_COLOR if team == raw.home_team.name else AWAY_COLOR

        # Build before/after values
        before = []
        after = []
        for key, _ in metrics:
            b = si.get(f"{key}_before", 0) or 0
            a = si.get(f"{key}_after", 0) or 0
            before.append(b)
            after.append(a)

        # Normalize for radar display
        max_vals = [max(b, a, 0.01) for b, a in zip(before, after)]
        norm_before = [b / m for b, m in zip(before, max_vals)]
        norm_after = [a / m for a, m in zip(after, max_vals)]

        # Draw grouped bar chart
        x = np.arange(n_metrics)
        w = 0.35
        bars1 = ax.bar(x - w/2, before, w, label=f"换人前", color="#888", alpha=0.7)
        bars2 = ax.bar(x + w/2, after, w, label=f"换人后", color=color, alpha=0.8)

        for bar, val in zip(bars1, before):
            if val > 0:
                ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.3,
                        f"{val:.1f}", ha="center", va="bottom", fontsize=6, color="white")
        for bar, val in zip(bars2, after):
            if val > 0:
                ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.3,
                        f"{val:.1f}", ha="center", va="bottom", fontsize=6, color="white")

        ax.set_xticks(x)
        ax.set_xticklabels(metric_names, fontsize=7, color="white", rotation=30)
        ax.tick_params(colors="white")
        title = f"{minute} {player_on}↑ / {player_off}↓"
        ax.set_title(title, fontsize=9, color=color, fontweight="bold")
        ax.legend(fontsize=7, facecolor="#1a1a2e", edgecolor="#333", labelcolor="white",
                  loc="upper right")
        for spine in ax.spines.values():
            spine.set_color("#333")
        ax.grid(True, alpha=0.1, color="white")

    # Hide empty subplots
    for idx in range(n, rows * cols):
        r, c = idx // cols, idx % cols
        axes[r, c].set_visible(False)

    fig.suptitle("换人效果分析 — 前后窗口对比", fontsize=14, color="white",
                 fontweight="bold", y=0.99)
    fig.tight_layout(rect=[0, 0.02, 1, 0.96])
    fig.savefig(output_path, dpi=dpi, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    return output_path
