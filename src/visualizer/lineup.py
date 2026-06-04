"""
mplsoccer lineup visualization: draw both teams' starting 11 on a pitch.
Shows player positions, jersey numbers, names, and substitution info.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

from src.collector.api_client import RawMatchData, PlayerStats
from src.visualizer import HOME_COLOR, AWAY_COLOR


def plot_lineup(
    raw: RawMatchData,
    output_path: str,
    dpi: int = 150,
) -> str:
    """Draw both teams' lineups on a football pitch using mplsoccer."""
    try:
        from mplsoccer import Pitch
    except ImportError:
        return ""

    home_players = raw.home_players
    away_players = raw.away_players

    # Split starters and substitutes
    home_starters = [p for p in home_players if not p.is_substitute]
    home_subs = [p for p in home_players if p.is_substitute]
    away_starters = [p for p in away_players if not p.is_substitute]
    away_subs = [p for p in away_players if p.is_substitute]

    # Get substitution events
    sub_events = [e for e in raw.events if e.event_type == "subst"]

    # Create figure
    fig = plt.figure(figsize=(18, 11))
    fig.patch.set_facecolor("#1a1a2e")

    # Pitch (horizontal, left-to-right)
    ax = fig.add_axes([0.05, 0.12, 0.72, 0.78])
    pitch = Pitch(
        pitch_type="opta",
        pitch_color="#122b1e",
        line_color="#3a6b4a",
    )
    pitch.draw(ax=ax)

    # Pitch coords: x=0..PITCH_X, y=0..PITCH_Y
    PX = pitch.dim.length
    PY = pitch.dim.width

    # Positions grid: rows for each line (GK, DEF, MID, FWD)
    home_positions = _build_positions(home_starters, is_home=True, px=PX, py=PY)
    away_positions = _build_positions(away_starters, is_home=False, px=PX, py=PY)

    # Draw home players
    for p in home_starters:
        x, y = home_positions.get(p.id, (PX * 0.5, PY * 0.5))
        _draw_player(pitch, ax, x, y, p.number, p.name, HOME_COLOR, "#1a5c2a")

    # Draw away players
    for p in away_starters:
        x, y = away_positions.get(p.id, (PX * 0.5, PY * 0.5))
        _draw_player(pitch, ax, x, y, p.number, p.name, AWAY_COLOR, "#1a3a6a")

    # Title area
    stage = raw.stage_info or {}
    league_name = stage.get("name", "")
    venue_info = raw.venue_info or {}
    venue_name = venue_info.get("name", "")

    # Header
    fig.text(0.41, 0.97, f"{league_name}", ha="center", fontsize=14,
             color="white", fontweight="bold")
    fig.text(0.41, 0.94, f"{venue_name}", ha="center", fontsize=9, color="#8ab4d6")

    # Team names
    fig.text(0.13, 0.97, raw.home_team.name, ha="center", fontsize=13,
             color=HOME_COLOR, fontweight="bold")
    fig.text(0.69, 0.97, raw.away_team.name, ha="center", fontsize=13,
             color=AWAY_COLOR, fontweight="bold")

    # Formation display
    for f in (raw.formations or []):
        loc = f.get("location", "")
        fm = f.get("formation", "?")
        if loc == "home":
            fig.text(0.13, 0.94, f"阵型: {fm}", ha="center", fontsize=9, color=HOME_COLOR)
        else:
            fig.text(0.69, 0.94, f"阵型: {fm}", ha="center", fontsize=9, color=AWAY_COLOR)

    # Subs panel
    _draw_subs(fig, home_subs, away_subs, sub_events, raw)

    # Save
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(out), dpi=dpi, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    return str(out)


def _build_positions(players: list[PlayerStats], is_home: bool, px: float, py: float) -> dict:
    """Assign pitch coordinates to players based on grid field.
    Vertical pitch: home goal bottom (y=0), away goal top (y=100).
    x = horizontal (0..100), y = vertical (0..100)."""
    result = {}
    for p in players:
        grid = p.grid or ""
        if ":" in str(grid):
            parts = str(grid).split(":")
            col = int(parts[0])
            row = int(parts[1])
        else:
            col, row = 3, 3

        # Map column to vertical position (y): 1=GK near own goal, 5=FWD near opponent goal
        y_map = {1: 0.03, 2: 0.22, 3: 0.42, 4: 0.62, 5: 0.82}
        y = py * y_map.get(col, 0.5)
        if not is_home:
            y = py - y  # Away attacks bottom

        # Map row to x: spread the players laterally
        n_col = sum(1 for pp in players if _col(pp.grid) == col)
        idx_in_col = sum(1 for pp in players if _col(pp.grid) == col and pp.id < p.id)
        x_range = px * 0.75
        x_start = px * 0.125
        spacing = x_range / max(n_col + 1, 1)
        x = x_start + spacing * (idx_in_col + 1)

        result[p.id] = (x, y)
    return result


def _col(grid_str: str) -> int:
    try:
        return int(str(grid_str).split(":")[0])
    except (ValueError, IndexError):
        return 3


def _draw_player(pitch, ax, x: float, y: float, number: int, name: str,
                 color: str, dark_color: str):
    """Draw a player dot with number and name."""
    # Player dot
    pitch.scatter(x, y, ax=ax, s=220, c=color, edgecolors="white",
                  linewidth=1.5, zorder=5, alpha=0.9)

    # Jersey number (to the right of player dot)
    pitch.annotate(str(number), xy=(x + 1.5, y), ax=ax,
                   ha="left", va="center", fontsize=7, color="white",
                   fontweight="bold", zorder=6)

    # Player name (below)
    name_short = name.split()[-1] if name else "?"
    pitch.annotate(name_short, xy=(x, y - 2.5), ax=ax,
                   ha="center", va="top", fontsize=5.5, color="#cccccc", zorder=4)


def _draw_subs(fig, home_subs, away_subs, sub_events, raw):
    """Draw substitute lists on the sides."""
    y_start = 0.85
    y_step = 0.022

    # Header panels
    fig.text(0.005, 0.92, "≡ 替补席", fontsize=9, color=HOME_COLOR, fontweight="bold")
    fig.text(0.965, 0.92, "≡ 替补席", fontsize=9, color=AWAY_COLOR, fontweight="bold",
             ha="right")

    for i, p in enumerate(home_subs[:9]):
        if i * y_step >= 0.7:
            break
        y = y_start - i * y_step
        was_sub_on = any(e.team_id == raw.home_team.id and e.assist_name == p.name
                        for e in sub_events)
        marker = "↑" if was_sub_on else " "
        fig.text(0.005, y, f"{marker} #{p.number} {p.name[:14]}",
                 fontsize=6, color="#cccccc" if not was_sub_on else HOME_COLOR)

    for i, p in enumerate(away_subs[:9]):
        if i * y_step >= 0.7:
            break
        y = y_start - i * y_step
        was_sub_on = any(e.team_id == raw.away_team.id and e.assist_name == p.name
                        for e in sub_events)
        marker = "↑" if was_sub_on else " "
        fig.text(0.965, y, f"{marker} #{p.number} {p.name[:14]}",
                 fontsize=6, color="#cccccc" if not was_sub_on else AWAY_COLOR,
                 ha="right")

    # Substitution summary below
    sub_lines = []
    for e in sub_events[:6]:
        team_abbr = raw.home_team.name[:3] if e.team_id == raw.home_team.id else raw.away_team.name[:3]
        color = HOME_COLOR if e.team_id == raw.home_team.id else AWAY_COLOR
        mi = e.time_elapsed or "?"
        sub_lines.append((color, f"{mi}' {e.assist_name} ↑ {e.player_name} ↓"))

    fig.text(0.04, 0.06, "换人记录", fontsize=8, color="white", fontweight="bold")
    for i, (color, line) in enumerate(sub_lines):
        fig.text(0.04, 0.04 - i * 0.015, line, fontsize=6, color=color)
