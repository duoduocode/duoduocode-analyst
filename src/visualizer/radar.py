import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from src.visualizer import AWAY_COLOR, HOME_COLOR, HIGHLIGHT_COLOR, NEUTRAL_COLOR


def plot_player_radar(
    player_values: dict,
    comparison_values: dict,
    player_label: str,
    comparison_label: str,
    output_path: str,
    dpi: int = 150,
    is_hidden_mvp: bool = False,
) -> str:
    categories = list(player_values.keys())
    N = len(categories)

    angles = [n / float(N) * 2 * np.pi for n in range(N)]
    angles += angles[:1]

    player_vals = [player_values[c] for c in categories]
    player_vals += player_vals[:1]

    comp_vals = [comparison_values.get(c, 0) for c in categories]
    comp_vals += comp_vals[:1]

    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, fontsize=10)

    ax.set_ylim(0, 1)
    ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticklabels(["20%", "40%", "60%", "80%", "100%"], fontsize=8, color=NEUTRAL_COLOR)
    ax.yaxis.grid(True, alpha=0.3)

    player_color = HOME_COLOR
    comp_color = AWAY_COLOR

    ax.fill(angles, player_vals, alpha=0.15, color=player_color)
    ax.plot(angles, player_vals, linewidth=2, color=player_color, label=player_label, marker="o")

    ax.fill(angles, comp_vals, alpha=0.1, color=comp_color)
    ax.plot(angles, comp_vals, linewidth=2, color=comp_color, label=comparison_label, marker="s",
            linestyle="--")

    title = f"球员雷达图 - {player_label}"
    if is_hidden_mvp:
        title += " (隐性MVP)"
    ax.set_title(title, fontsize=13, fontweight="bold", pad=20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.15, 1.1), fontsize=9)

    fig.tight_layout()
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return output_path
