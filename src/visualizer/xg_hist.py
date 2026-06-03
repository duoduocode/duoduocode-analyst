import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from src.visualizer import AWAY_COLOR, HOME_COLOR, HIGHLIGHT_COLOR, NEUTRAL_COLOR

SCORE_MAP = {
    (0, 0): 0, (1, 0): 1, (0, 1): 2, (1, 1): 3,
    (2, 0): 4, (0, 2): 5, (2, 1): 6, (1, 2): 7,
    (2, 2): 8, (3, 0): 9, (0, 3): 10, (3, 1): 11,
    (1, 3): 12, (3, 2): 13, (2, 3): 14, (3, 3): 15,
}


def plot_xg_histogram(
    simulation_results: dict,
    actual_home: int,
    actual_away: int,
    home_name: str,
    away_name: str,
    output_path: str,
    dpi: int = 150,
) -> str:
    top3 = simulation_results.get("top3_scores", [])
    if not top3:
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.text(0.5, 0.5, "模拟数据不足", ha="center", va="center", fontsize=14)
        fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        return output_path

    scores = []
    freqs = []
    for s in top3:
        score_str = s["score"]
        pct = s["pct"]
        parts = score_str.split("-")
        h, a = int(parts[0]), int(parts[1])
        idx = SCORE_MAP.get((h, a), len(SCORE_MAP))
        scores.append(idx)
        freqs.append(pct)

    fig, ax = plt.subplots(figsize=(10, 5))

    bars = ax.bar(range(len(top3)), freqs, color=AWAY_COLOR, alpha=0.7, edgecolor="white")

    actual_idx = SCORE_MAP.get((actual_home, actual_away))
    if actual_idx is not None and actual_idx < len(top3):
        bars[actual_idx].set_color(HIGHLIGHT_COLOR)
        bars[actual_idx].set_alpha(0.9)

    ax.set_xticks(range(len(top3)))
    ax.set_xticklabels([s["score"] for s in top3], fontsize=10)
    ax.set_ylabel("出现频率 (%)", fontsize=10)
    ax.set_xlabel("模拟比分", fontsize=10)

    home_win = simulation_results.get("home_win_pct", 0)
    draw = simulation_results.get("draw_pct", 0)
    away_win = simulation_results.get("away_win_pct", 0)
    ldi = simulation_results.get("ldi", 0)
    interp = simulation_results.get("interpretation", "")

    text_str = (
        f"模拟10000次结果:\n"
        f"{home_name}胜: {home_win}% | 平: {draw}% | {away_name}胜: {away_win}%\n"
        f"运气偏离指数 LDI: {ldi} → {interp}\n"
        f"实际比分: {actual_home}-{actual_away} (红色高亮)"
    )
    ax.text(
        0.98, 0.95, text_str,
        transform=ax.transAxes,
        fontsize=10,
        verticalalignment="top",
        horizontalalignment="right",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="white", alpha=0.9),
    )

    ax.set_title(
        f"xG 模拟分布 - {home_name} vs {away_name}",
        fontsize=14,
        fontweight="bold",
    )
    ax.grid(True, alpha=0.2, axis="y")

    fig.tight_layout()
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return output_path
