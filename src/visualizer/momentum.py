import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from src.visualizer import AWAY_COLOR, HOME_COLOR


def plot_momentum_curve(
    segments: list[dict],
    key_events: list[dict],
    home_name: str,
    away_name: str,
    output_path: str,
    dpi: int = 150,
) -> str:
    fig, ax = plt.subplots(figsize=(12, 5))

    times = [7.5, 22.5, 37.5, 52.5, 67.5, 82.5]
    home_vals = [s["home"] for s in segments]
    away_vals = [s["away"] for s in segments]

    home_vals = np.array(home_vals, dtype=float)
    away_vals = np.array(away_vals, dtype=float)

    ax.fill_between(
        times,
        home_vals,
        0,
        alpha=0.3,
        color=HOME_COLOR,
        label=f"{home_name} 动量",
    )
    ax.plot(times, home_vals, color=HOME_COLOR, linewidth=2, marker="o", markersize=6)

    ax.fill_between(
        times,
        away_vals * -1,
        0,
        alpha=0.3,
        color=AWAY_COLOR,
        label=f"{away_name} 动量",
    )
    ax.plot(times, away_vals * -1, color=AWAY_COLOR, linewidth=2, marker="s", markersize=6)

    y_max = max(max(home_vals), max(away_vals)) * 1.4
    y_max = max(y_max, 1)

    for ev in key_events:
        minute = ev.get("minute", 0)
        ev_type = ev.get("type", "")
        label = ev.get("label", "")
        team = ev.get("team", "")

        y_pos = y_max * 0.9 if team == home_name else -y_max * 0.9

        marker = "▼" if ev_type == "Goal" else ("◆" if ev_type == "Card" else "○")
        color = HOME_COLOR if team == home_name else AWAY_COLOR

        ax.annotate(
            f"{marker} {label}",
            (minute, y_pos),
            fontsize=7,
            color=color,
            fontweight="bold",
            ha="center",
            va="center",
            bbox=dict(boxstyle="round,pad=0.2", facecolor="white", alpha=0.8, edgecolor=color),
        )

    ax.axhline(y=0, color="gray", linewidth=0.5, linestyle="--")
    ax.set_xlim(0, 90)
    ax.set_ylim(-y_max, y_max)
    ax.set_xlabel("比赛时间 (分钟)", fontsize=10)
    ax.set_ylabel("动量分", fontsize=10)
    ax.legend(loc="upper left", fontsize=9)
    ax.set_title(
        f"比赛动量走势 - {home_name} vs {away_name}",
        fontsize=14,
        fontweight="bold",
    )
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return output_path
