import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from mplsoccer import Pitch

from src.visualizer import AWAY_COLOR


def plot_pass_network(
    players: list,
    player_stats: list,
    formation: str,
    team_name: str,
    output_path: str,
    dpi: int = 150,
) -> str:
    pitch = Pitch(pitch_type="statsbomb", pitch_color="grass", line_color="white", stripe=True)
    fig, ax = pitch.draw(figsize=(10, 7))

    if not players or not player_stats:
        ax.set_title(f"{team_name} 传球网络 | 阵型 {formation}", fontsize=14, fontweight="bold")
        fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        return output_path

    stat_map = {ps.id: ps for ps in player_stats}

    formation_parts = formation.split("-") if formation else []
    if len(formation_parts) >= 3:
        try:
            def_line = int(formation_parts[-1])
            mid_line = int(formation_parts[-2])
            fwd_line = int(formation_parts[-3])
        except (ValueError, IndexError):
            def_line, mid_line, fwd_line = 4, 3, 3
    else:
        def_line, mid_line, fwd_line = 4, 3, 3

    def place_line(count: int, x: float, y_range: tuple) -> list:
        positions = []
        if count == 1:
            positions = [(x, (y_range[0] + y_range[1]) / 2)]
        else:
            step = (y_range[1] - y_range[0]) / (count + 1)
            for i in range(count):
                positions.append((x, y_range[0] + step * (i + 1)))
        return positions

    def_xy = place_line(def_line, 5, (20, 60))
    mid_xy = place_line(mid_line, 40, (15, 65))
    fwd_xy = place_line(fwd_line, 65, (20, 60))

    all_positions = def_xy + mid_xy + fwd_xy

    positioned = []
    for i, lu_player in enumerate(players):
        if i < len(all_positions):
            x, y = all_positions[i]
            positioned.append((lu_player, x, y))
        else:
            positioned.append((lu_player, 30, 30))

    node_sizes = []
    node_labels = []
    for lu_player, x, y in positioned:
        ps = stat_map.get(lu_player.id)
        passes = ps.passes_total if ps and ps.passes_total > 0 else 3
        size = max(50, min(300, passes * 2))
        node_sizes.append(size)
        node_labels.append(f"{lu_player.name}\n({passes})")

    for (p1, x1, y1), (p2, x2, y2) in zip(positioned, positioned[1:]):
        ps1 = stat_map.get(p1.id)
        ps2 = stat_map.get(p2.id)
        p1_total = ps1.passes_total if ps1 else 3
        p2_total = ps2.passes_total if ps2 else 3
        line_width = max(0.5, min(5, (p1_total + p2_total) / 30))
        pitch.lines(
            x1, y1, x2, y2,
            color=AWAY_COLOR,
            lw=line_width,
            ax=ax,
            alpha=0.4,
            zorder=1,
        )

    for (lu_player, x, y), size in zip(positioned, node_sizes):
        ps = stat_map.get(lu_player.id)
        key_p = ps.passes_key if ps and ps.passes_key > 0 else 0

        pitch.scatter(
            x, y,
            s=size,
            c="white",
            edgecolor=AWAY_COLOR,
            linewidth=1.5,
            ax=ax,
            zorder=3,
        )
        ax.annotate(
            lu_player.name,
            (x, y),
            fontsize=6,
            color="white",
            ha="center",
            va="center",
            fontweight="bold",
            zorder=4,
        )
        if key_p > 0:
            ax.annotate(
                f"★{key_p}",
                (x, y - 3),
                fontsize=6,
                color="yellow",
                ha="center",
                va="top",
                fontweight="bold",
            )

    ax.set_title(
        f"{team_name} 传球网络 | 阵型 {formation}",
        fontsize=14,
        fontweight="bold",
    )

    fig.tight_layout()
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return output_path
