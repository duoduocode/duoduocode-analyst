import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from mplsoccer import Pitch

from src.visualizer import (
    AWAY_COLOR,
    AWAY_COLOR_DARK,
    HOME_COLOR,
    HOME_COLOR_DARK,
    HIGHLIGHT_COLOR,
    NEUTRAL_COLOR,
)


def plot_shot_map(
    home_shots: list[dict],
    away_shots: list[dict],
    home_xg: float,
    away_xg: float,
    home_name: str,
    away_name: str,
    output_path: str,
    dpi: int = 150,
) -> str:
    pitch = Pitch(pitch_type="statsbomb", pitch_color="grass", line_color="white", stripe=True)
    fig, ax = pitch.draw(figsize=(12, 8))

    for shot in home_shots:
        x = shot.get("x", 50)
        y = shot.get("y", 50)
        xg_val = shot.get("xg", 0.05)
        is_goal = shot.get("goal", False)
        size = max(30, xg_val * 500)

        color = HOME_COLOR_DARK if is_goal else HOME_COLOR
        edgecolor = "white" if is_goal else HOME_COLOR_DARK

        pitch.scatter(
            120 - x, y,
            s=size,
            c=color,
            edgecolor=edgecolor,
            linewidth=0.8,
            alpha=0.85,
            ax=ax,
            zorder=3,
        )
        if is_goal:
            player = shot.get("player", "")
            minute = shot.get("minute", "")
            label = f"{player} {minute}'"
            ax.annotate(
                label,
                (120 - x, y),
                fontsize=7,
                color="white",
                fontweight="bold",
                ha="center",
                va="bottom",
                xytext=(0, 8),
                textcoords="offset points",
                bbox=dict(boxstyle="round,pad=0.2", facecolor="black", alpha=0.7),
            )

    for shot in away_shots:
        x = shot.get("x", 50)
        y = shot.get("y", 50)
        xg_val = shot.get("xg", 0.05)
        is_goal = shot.get("goal", False)
        size = max(30, xg_val * 500)

        color = AWAY_COLOR_DARK if is_goal else AWAY_COLOR
        edgecolor = "white" if is_goal else AWAY_COLOR_DARK

        pitch.scatter(
            x, y,
            s=size,
            c=color,
            edgecolor=edgecolor,
            linewidth=0.8,
            alpha=0.85,
            ax=ax,
            marker="s",
            zorder=3,
        )
        if is_goal:
            player = shot.get("player", "")
            minute = shot.get("minute", "")
            label = f"{player} {minute}'"
            ax.annotate(
                label,
                (x, y),
                fontsize=7,
                color="white",
                fontweight="bold",
                ha="center",
                va="bottom",
                xytext=(0, 8),
                textcoords="offset points",
                bbox=dict(boxstyle="round,pad=0.2", facecolor="black", alpha=0.7),
            )

    from matplotlib.lines import Line2D

    legend_elements = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor=HOME_COLOR_DARK,
               markersize=10, label=f"{home_name} 进球"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=HOME_COLOR,
               markeredgecolor=HOME_COLOR_DARK, markeredgewidth=1,
               markersize=10, label=f"{home_name} 射偏"),
        Line2D([0], [0], marker="s", color="w", markerfacecolor=AWAY_COLOR_DARK,
               markersize=10, label=f"{away_name} 进球"),
        Line2D([0], [0], marker="s", color="w", markerfacecolor=AWAY_COLOR,
               markeredgecolor=AWAY_COLOR_DARK, markeredgewidth=1,
               markersize=10, label=f"{away_name} 射偏"),
    ]
    ax.legend(handles=legend_elements, loc="lower left", fontsize=9, framealpha=0.9)

    ax.set_title(
        f"{home_name} vs {away_name}  射门分布 | xG {home_xg} - {away_xg}",
        fontsize=14,
        fontweight="bold",
        pad=15,
    )

    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return output_path


def build_shot_data_from_players(players, team_id: int) -> list[dict]:
    shots = []
    for p in players:
        if p.shots_total > 0:
            for i in range(p.shots_total):
                is_goal = i < p.goals
                shots.append({
                    "x": np.random.randint(90, 115) if p.position == "F" else np.random.randint(70, 100),
                    "y": np.random.randint(20, 60),
                    "xg": 0.3 if is_goal else np.random.uniform(0.02, 0.2),
                    "goal": is_goal,
                    "player": p.name,
                    "minute": np.random.randint(1, 90),
                })
    return shots
