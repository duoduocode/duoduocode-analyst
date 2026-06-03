from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from src.visualizer import AWAY_COLOR, HOME_COLOR, NEUTRAL_COLOR


def plot_subs_comparison(
    subs_data: list[dict],
    team_name: str,
    output_path: str,
    dpi: int = 150,
) -> str:
    if not subs_data:
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.text(0.5, 0.5, "本场无换人", ha="center", va="center", fontsize=14)
        ax.set_title(f"{team_name} 换人效果", fontsize=13, fontweight="bold")
        fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        return output_path

    labels = [f"{s.get('time', '?')}'\n↑{s.get('player_in', '?')}\n↓{s.get('player_out', '?')}" for s in subs_data]

    fig, ax = plt.subplots(figsize=(10, 4))

    x = np.arange(len(subs_data))
    width = 0.35

    pre_vals = [s.get("pre_xg_diff", 0) or 0 for s in subs_data]
    post_vals = [s.get("post_xg_diff", 0) or 0 for s in subs_data]

    bars_pre = ax.bar(x - width / 2, pre_vals, width, label="换人前 xG差",
                      color=NEUTRAL_COLOR, alpha=0.7)
    bars_post = ax.bar(x + width / 2, post_vals, width, label="换人后 xG差",
                       color=HOME_COLOR, alpha=0.8)

    ratings = [s.get("rating") for s in subs_data]
    for i, (r, pre, post) in enumerate(zip(ratings, pre_vals, post_vals)):
        if r is not None:
            ax.annotate(
                f"评分: {r}",
                (i + width / 2, max(post, 0) + 0.02),
                fontsize=8,
                ha="center",
                color=HOME_COLOR,
                fontweight="bold",
            )

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("xG差", fontsize=10)
    ax.axhline(y=0, color="gray", linewidth=0.5, linestyle="--")
    ax.legend(fontsize=9)
    ax.set_title(f"{team_name} 换人效果评估", fontsize=13, fontweight="bold")
    ax.grid(True, alpha=0.2)

    fig.tight_layout()
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return output_path
