"""
Lineup visualization: HTML-based lineup cards embedded in the tactical report.
Generates player cards with circular photos, jersey numbers, and names.
Uses cached player photos (output/cache/player_photos/*.png).

Output: HTML fragment string for embedding in tactical_report.html.
Also exports lineup_html as a standalone PNG via matplotlib for fallback.
"""

from __future__ import annotations

import base64
import io
import urllib.request
from pathlib import Path

from src.collector.api_client import RawMatchData, PlayerStats

# Cache directory
CACHE_DIR = Path("output/cache/player_photos")

# Colors
BG_COLOR = "#0f1923"
PITCH_COLOR = "#122b1e"
LINE_COLOR = "#3a6b4a"
HOME_COLOR = "#2ecc71"
AWAY_COLOR = "#3498db"
CARD_BG = "#1a2a36"


def _get_player_photo_base64(player_id: int, photo_url: str) -> str | None:
    """Return base64 data URI for a player photo. Uses cache."""
    if not photo_url:
        return None

    cache_path = CACHE_DIR / f"{player_id}.png"
    data = None
    if cache_path.exists():
        try:
            data = cache_path.read_bytes()
        except Exception:
            pass

    if data is None:
        try:
            req = urllib.request.Request(photo_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = resp.read()
            # Resize and re-save for consistency using PIL if available
            try:
                from PIL import Image
                img = Image.open(io.BytesIO(data)).convert("RGBA")
                img = img.resize((128, 128), Image.LANCZOS)
                bio = io.BytesIO()
                img.save(bio, format="PNG")
                data = bio.getvalue()
            except Exception:
                pass
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_bytes(data)
        except Exception:
            return None

    if data:
        return "data:image/png;base64," + base64.b64encode(data).decode("utf-8")
    return None


def _get_team_logo_base64(logo_url: str) -> str | None:
    """Return base64 data URI for a team logo."""
    if not logo_url:
        return None
    cache_key = str(abs(hash(logo_url)) % 100000)
    cache_path = CACHE_DIR / f"team_logo_{cache_key}.png"
    data = None
    if cache_path.exists():
        try:
            data = cache_path.read_bytes()
        except Exception:
            pass
    if data is None:
        try:
            req = urllib.request.Request(logo_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = resp.read()
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_bytes(data)
        except Exception:
            return None
    if data:
        return "data:image/png;base64," + base64.b64encode(data).decode("utf-8")
    return None


def _col(grid_str: str) -> int:
    try:
        return int(str(grid_str).split(":")[0])
    except (ValueError, IndexError):
        return 3


def generate_lineup_html(raw: RawMatchData) -> str:
    """Generate an HTML lineup visualization with player photos, names, numbers.

    Returns a self-contained HTML block to embed in the tactical report.
    Layout: horizontal pitch, home team on the left side, away team on the right.
    Players are positioned in rows by their 'grid' column (GK, DEF, MID, FW).
    """
    home_starters = [p for p in raw.home_players if not p.is_substitute]
    away_starters = [p for p in raw.away_players if not p.is_substitute]
    home_subs = [p for p in raw.home_players if p.is_substitute]
    away_subs = [p for p in raw.away_players if p.is_substitute]

    # Substitution events
    sub_events = [e for e in raw.events if e.event_type == "subst"]

    # Preload photos
    photo_cache: dict[int, str | None] = {}

    def _photo(p: PlayerStats) -> str | None:
        if p.id in photo_cache:
            return photo_cache[p.id]
        uri = _get_player_photo_base64(p.id, p.photo_url or "")
        photo_cache[p.id] = uri
        return uri

    # Team logos
    home_logo = _get_team_logo_base64(raw.home_team.logo_url)
    away_logo = _get_team_logo_base64(raw.away_team.logo_url)

    # Formations
    home_formation = "?"
    away_formation = "?"
    for f in (raw.formations or []):
        loc = f.get("location", "")
        fm = f.get("formation", "?")
        if loc == "home":
            home_formation = fm
        else:
            away_formation = fm

    # Header info
    stage = (raw.stage_info or {}).get("name", "")
    venue = (raw.venue_info or {}).get("name", "")

    # ═══ CSS ═══
    stripe_dark = "#0d5e1a"
    stripe_light = "#0f6e20"
    STRIPE_H = 38  # px per stripe
    PEN_H = 80     # penalty area height
    GOAL_H = 32    # goal area height
    ARC_W = 90     # penalty arc width
    ARC_H = 40     # penalty arc height
    PITCH_W = 480
    PITCH_H = 640  # overall pitch height
    MID_CIRCLE = 110  # center circle diameter
    css = f"""
<style>
.lineup-wrapper {{
    font-family: "Microsoft YaHei","PingFang SC",sans-serif;
    background: {BG_COLOR};
    border-radius: 14px;
    padding: 16px 12px 12px;
    margin: 20px 0;
    color: #e0e8f0;
    overflow: hidden;
}}
.lineup-header {{
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    margin-bottom: 10px;
    padding: 0 16px;
}}
.lineup-header .team {{
    text-align: center;
    flex: 1;
}}
.lineup-header .team img {{
    width: 44px;
    height: 44px;
    object-fit: contain;
    margin-bottom: 2px;
}}
.lineup-header .team-name {{
    font-size: 15px;
    font-weight: bold;
    color: #fff;
}}
.lineup-header .formation {{
    font-size: 13px;
    color: #8ab4d6;
    font-weight: bold;
    margin-top: 1px;
}}
.lineup-header .center-info {{
    text-align: center;
    flex: 0.6;
}}
.lineup-header .center-info .stage {{
    font-size: 13px;
    font-weight: bold;
    color: #f1c40f;
}}
.lineup-header .center-info .venue {{
    font-size: 10px;
    color: #8ab4d6;
    margin-top: 1px;
}}

.pitch-wrapper {{
    position: relative;
    margin: 4px 0;
}}
.pitch {{
    position: relative;
    width: 100%;
    max-width: {PITCH_W}px;
    margin: 0 auto;
    height: {PITCH_H}px;
    border: 3px solid rgba(255,255,255,0.55);
    border-radius: 12px;
    overflow: hidden;
    background: repeating-linear-gradient(
        0deg,
        {stripe_dark} 0px, {stripe_dark} {STRIPE_H}px,
        {stripe_light} {STRIPE_H}px, {stripe_light} {2*STRIPE_H}px
    );
    padding: 0;
}}
/* center line & circle */
.pitch::before {{
    content: "";
    position: absolute;
    top: 50%;
    left: 0; right: 0;
    height: 0;
    border-top: 2px solid rgba(255,255,255,0.45);
    z-index: 2;
}}
.pitch::after {{
    content: "";
    position: absolute;
    top: 50%; left: 50%;
    width: {MID_CIRCLE}px; height: {MID_CIRCLE}px;
    transform: translate(-50%,-50%);
    border: 2px solid rgba(255,255,255,0.45);
    border-radius: 50%;
    z-index: 2;
}}
/* center dot */
.pitch-dot {{
    position: absolute;
    top: 50%; left: 50%;
    width: 6px; height: 6px;
    transform: translate(-50%,-50%);
    background: rgba(255,255,255,0.5);
    border-radius: 50%;
    z-index: 3;
}}
/* penalty areas — top */
.pitch-pen-top {{
    position: absolute;
    top: 0;
    left: 50%;
    width: 260px;
    height: {PEN_H}px;
    transform: translateX(-50%);
    border: 2px solid rgba(255,255,255,0.45);
    border-top: none;
    z-index: 2;
    pointer-events: none;
}}
/* penalty areas — bottom */
.pitch-pen-bot {{
    position: absolute;
    bottom: 0;
    left: 50%;
    width: 260px;
    height: {PEN_H}px;
    transform: translateX(-50%);
    border: 2px solid rgba(255,255,255,0.45);
    border-bottom: none;
    z-index: 2;
    pointer-events: none;
}}
/* goal areas — top */
.pitch-goal-top {{
    position: absolute;
    top: 0;
    left: 50%;
    width: 120px;
    height: {GOAL_H}px;
    transform: translateX(-50%);
    border: 2px solid rgba(255,255,255,0.40);
    border-top: none;
    z-index: 2;
    pointer-events: none;
}}
/* goal areas — bottom */
.pitch-goal-bot {{
    position: absolute;
    bottom: 0;
    left: 50%;
    width: 120px;
    height: {GOAL_H}px;
    transform: translateX(-50%);
    border: 2px solid rgba(255,255,255,0.40);
    border-bottom: none;
    z-index: 2;
    pointer-events: none;
}}
/* penalty arcs — top (D curves downward, away from goal) */
.pitch-arc-top {{
    position: absolute;
    top: {PEN_H}px;
    left: 50%;
    width: {ARC_W}px; height: {ARC_H}px;
    transform: translateX(-50%);
    border: 1.5px solid rgba(255,255,255,0.40);
    border-top: none;
    border-radius: 0 0 {ARC_H}px {ARC_H}px;
    z-index: 2;
    pointer-events: none;
}}
/* penalty arcs — bottom (D curves upward, away from goal) */
.pitch-arc-bot {{
    position: absolute;
    bottom: {PEN_H}px;
    left: 50%;
    width: {ARC_W}px; height: {ARC_H}px;
    transform: translateX(-50%);
    border: 1.5px solid rgba(255,255,255,0.40);
    border-bottom: none;
    border-radius: {ARC_H}px {ARC_H}px 0 0;
    z-index: 2;
    pointer-events: none;
}}
/* penalty spots */
.pitch-pen-spot-top {{
    position: absolute;
    top: {PEN_H - 16}px;
    left: 50%;
    width: 5px; height: 5px;
    transform: translate(-50%,-50%);
    background: rgba(255,255,255,0.5);
    border-radius: 50%;
    z-index: 3;
}}
.pitch-pen-spot-bot {{
    position: absolute;
    bottom: {PEN_H - 16}px;
    left: 50%;
    width: 5px; height: 5px;
    transform: translate(-50%,50%);
    background: rgba(255,255,255,0.5);
    border-radius: 50%;
    z-index: 3;
}}
/* goal lines (thicker) */
.pitch-goalline-top {{
    position: absolute;
    top: 0;
    left: 50%;
    width: 50px;
    height: 0;
    transform: translateX(-50%);
    border-top: 4px solid rgba(255,255,255,0.6);
    z-index: 3;
}}
.pitch-goalline-bot {{
    position: absolute;
    bottom: 0;
    left: 50%;
    width: 50px;
    height: 0;
    transform: translateX(-50%);
    border-bottom: 4px solid rgba(255,255,255,0.6);
    z-index: 3;
}}

/* players layer — absolute positioned over pitch */
.pitch-players {{
    position: absolute;
    inset: 0;
    z-index: 5;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    padding: 0 20px 0 20px;
    pointer-events: none;
}}
.pitch-half {{
    display: flex;
    flex-direction: column;
    gap: 8px;
    flex: 1;
    pointer-events: auto;
}}
.pitch-half.top     {{ justify-content: flex-start; padding-top: 4px; }}
.pitch-half.bottom  {{ justify-content: flex-end;   padding-bottom: 4px; }}

.pitch-row {{
    display: flex;
    justify-content: center;
    gap: 16px;
    width: 100%;
}}
.pitch-row .player-card {{
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1px;
    width: 48px;
    text-align: center;
}}
.player-photo {{
    width: 38px;
    height: 38px;
    border-radius: 50%;
    object-fit: cover;
    border: 2px solid;
    background: #2a3a4a;
}}
.player-photo.home {{ border-color: {HOME_COLOR}; }}
.player-photo.away {{ border-color: {AWAY_COLOR}; }}
.player-number {{
    font-size: 11px;
    font-weight: bold;
    color: #fff;
    line-height: 1;
}}
.player-name {{
    font-size: 9px;
    color: rgba(255,255,255,0.9);
    line-height: 1.2;
    max-width: 50px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    text-shadow: 0 1px 2px rgba(0,0,0,0.7);
}}
/* formation / team label inside pitch */
.pitch-label {{
    position: absolute;
    z-index: 6;
    font-size: 12px;
    font-weight: bold;
    color: rgba(255,255,255,0.8);
    text-shadow: 0 1px 3px rgba(0,0,0,0.8);
    pointer-events: none;
    background: rgba(0,0,0,0.35);
    padding: 3px 8px;
    border-radius: 4px;
}}
.pitch-label.top    {{ top: 1px; left: 6px; }}
.pitch-label.bottom {{ bottom: 1px; left: 6px; }}

/* subs */
.lineup-subs-section {{
    display: flex;
    justify-content: space-between;
    margin-top: 12px;
    padding: 0 10px;
    gap: 12px;
}}
.subs-panel {{
    flex: 1;
    background: {CARD_BG};
    border-radius: 10px;
    padding: 8px 12px;
}}
.subs-panel h4 {{
    color: #8ab4d6;
    font-size: 12px;
    margin: 0 0 6px;
    border-bottom: 1px solid {LINE_COLOR};
    padding-bottom: 4px;
}}
.subs-panel .sub-item {{
    font-size: 11px;
    color: #a0b0c0;
    padding: 1px 0;
    line-height: 1.5;
}}
.subs-panel .sub-item.on {{ color: {HOME_COLOR}; font-weight: bold; }}
.subs-panel.away .sub-item.on {{ color: {AWAY_COLOR}; }}

.sub-summary-item {{
    font-size: 10px;
    color: #7a8a9a;
    line-height: 1.6;
}}
</style>
"""

    # ═══ HTML ═══
    H: list[str] = []
    H.append(css)
    H.append('<div class="lineup-wrapper">')

    # Header row
    H.append('<div class="lineup-header">')
    # Home team
    H.append('<div class="team">')
    if home_logo:
        H.append(f'<img src="{home_logo}" alt="{raw.home_team.name}">')
    H.append(f'<div class="team-name">{raw.home_team.name}</div>')
    H.append(f'<div class="formation">{home_formation}</div>')
    H.append('</div>')

    # Center
    H.append('<div class="center-info">')
    if stage:
        H.append(f'<div class="stage">{stage}</div>')
    if venue:
        H.append(f'<div class="venue">{venue}</div>')
    H.append('</div>')

    # Away team
    H.append('<div class="team">')
    if away_logo:
        H.append(f'<img src="{away_logo}" alt="{raw.away_team.name}">')
    H.append(f'<div class="team-name">{raw.away_team.name}</div>')
    H.append(f'<div class="formation">{away_formation}</div>')
    H.append('</div>')
    H.append('</div>')

    # Pitch area — vertical layout with pitch lines
    H.append('<div class="pitch-wrapper">')
    H.append('<div class="pitch">')

    # Pitch markings
    H.append('<div class="pitch-dot"></div>')
    H.append('<div class="pitch-pen-top"></div>')
    H.append('<div class="pitch-pen-bot"></div>')
    H.append('<div class="pitch-goal-top"></div>')
    H.append('<div class="pitch-goal-bot"></div>')
    H.append('<div class="pitch-arc-top"></div>')
    H.append('<div class="pitch-arc-bot"></div>')
    H.append('<div class="pitch-pen-spot-top"></div>')
    H.append('<div class="pitch-pen-spot-bot"></div>')
    H.append('<div class="pitch-goalline-top"></div>')
    H.append('<div class="pitch-goalline-bot"></div>')

    # Formation labels
    H.append(f'<div class="pitch-label top">{raw.away_team.name} · {away_formation}</div>')
    H.append(f'<div class="pitch-label bottom">{raw.home_team.name} · {home_formation}</div>')

    # Players layer
    H.append('<div class="pitch-players">')

    # --- Away team (top half) ---
    H.append('<div class="pitch-half top">')
    # GK near goal (top), then DEF, MID, FW near center
    for col in [1, 2, 3, 4, 5]:
        col_players = [p for p in away_starters if _col(p.grid) == col]
        if not col_players:
            continue
        H.append('<div class="pitch-row">')
        for p in col_players:
            name_short = p.name.split()[-1] if p.name else "?"
            photo_uri = _photo(p)
            H.append('<div class="player-card">')
            if photo_uri:
                H.append(f'<img class="player-photo away" src="{photo_uri}" alt="{name_short}">')
            else:
                H.append(f'<div class="player-photo away" style="display:flex;align-items:center;justify-content:center;font-size:14px;color:{AWAY_COLOR}">#{p.number}</div>')
            H.append(f'<div class="player-number">#{p.number}</div>')
            H.append(f'<div class="player-name" title="{p.name}">{name_short}</div>')
            H.append('</div>')
        H.append('</div>')
    H.append('</div>')

    # --- Home team (bottom half) ---
    H.append('<div class="pitch-half bottom">')
    # FW near center, then MID, DEF, GK last (near goal at bottom)
    for col in [5, 4, 3, 2, 1]:
        col_players = [p for p in home_starters if _col(p.grid) == col]
        if not col_players:
            continue
        H.append('<div class="pitch-row">')
        for p in col_players:
            name_short = p.name.split()[-1] if p.name else "?"
            photo_uri = _photo(p)
            H.append('<div class="player-card">')
            if photo_uri:
                H.append(f'<img class="player-photo home" src="{photo_uri}" alt="{name_short}">')
            else:
                H.append(f'<div class="player-photo home" style="display:flex;align-items:center;justify-content:center;font-size:14px;color:{HOME_COLOR}">#{p.number}</div>')
            H.append(f'<div class="player-number">#{p.number}</div>')
            H.append(f'<div class="player-name" title="{p.name}">{name_short}</div>')
            H.append('</div>')
        H.append('</div>')
    H.append('</div>')

    H.append('</div>')  # .pitch-players
    H.append('</div>')  # .pitch
    H.append('</div>')  # .pitch-wrapper

    # Subs panels
    H.append('<div class="lineup-subs-section">')

    # Home subs
    H.append('<div class="subs-panel">')
    H.append('<h4>替补席</h4>')
    for p in home_subs[:9]:
        was_on = any(e.team_id == raw.home_team.id and e.assist_name == p.name for e in sub_events)
        cls = "sub-item on" if was_on else "sub-item"
        marker = "\u2191 " if was_on else ""
        H.append(f'<div class="{cls}">{marker}#{p.number} {p.name}</div>')
    H.append('</div>')

    # Sub summary in middle
    sub_lines = []
    for e in sub_events[:6]:
        team_abbr = raw.home_team.name[:3] if e.team_id == raw.home_team.id else raw.away_team.name[:3]
        mi = e.time_elapsed or "?"
        sub_lines.append(f"{mi}\u2019 {e.assist_name} \u2191 {e.player_name} \u2193 ({team_abbr})")
    if sub_lines:
        H.append('<div style="flex:1;padding:10px 8px;text-align:center;">')
        H.append('<h4 style="color:#8ab4d6;font-size:13px;margin:0 0 8px;">换人记录</h4>')
        for line in sub_lines:
            H.append(f'<div class="sub-summary-item">{line}</div>')
        H.append('</div>')
    else:
        H.append('<div style="flex:0"></div>')

    # Away subs
    H.append('<div class="subs-panel away">')
    H.append('<h4>替补席</h4>')
    for p in away_subs[:9]:
        was_on = any(e.team_id == raw.away_team.id and e.assist_name == p.name for e in sub_events)
        cls = "sub-item on" if was_on else "sub-item"
        marker = "\u2191 " if was_on else ""
        H.append(f'<div class="{cls}">{marker}#{p.number} {p.name}</div>')
    H.append('</div>')

    H.append('</div>')  # .lineup-subs-section
    H.append('</div>')  # .lineup-wrapper

    return "\n".join(H)


def save_lineup_png(raw: RawMatchData, output_path: str) -> str:
    """Render lineup HTML to a high-resolution PNG using headless Chromium.

    Args:
        raw: RawMatchData with player/team info.
        output_path: File path for the output PNG (e.g. 'output/.../lineup.png').

    Returns:
        The output_path on success.
    """
    html = generate_lineup_html(raw)
    wrapper_css = """
    <style>
      html, body { margin:0; padding:0; width:560px; background:#0f1923; }
      body { display:flex; justify-content:center; align-items:center; min-height:100vh; }
    </style>
    """.strip()
    full_html = f"<!DOCTYPE html><html><head><meta charset='utf-8'>{wrapper_css}</head><body>{html}</body></html>"

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise ImportError("playwright is required. Install: pip install playwright && playwright install chromium")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 560, "height": 1000}, device_scale_factor=2)
        page.set_content(full_html)
        # wait for images to load
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(500)
        page.screenshot(path=str(out), full_page=True)
        browser.close()

    return str(out)


# ═══════════════════════════════════════════════
# Legacy matplotlib function (no longer primary)
# ═══════════════════════════════════════════════

def plot_lineup(raw: RawMatchData, output_path: str, dpi: int = 150) -> str:
    """Legacy matplotlib lineup — kept for backwards compatibility.
    Use generate_lineup_html() instead for better visual results."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import numpy as np
    from matplotlib.offsetbox import OffsetImage, AnnotationBbox

    home_starters = [p for p in raw.home_players if not p.is_substitute]
    sub_events = [e for e in raw.events if e.event_type == "subst"]

    fig = plt.figure(figsize=(24, 14))
    fig.patch.set_facecolor("#1a1a2e")
    ax = fig.add_axes([0.04, 0.08, 0.76, 0.84])

    PX, PY = 105.0, 68.0
    ax.set_xlim(-3, PX + 3)
    ax.set_ylim(-3, PY + 3)
    ax.set_aspect("equal")
    ax.set_facecolor("#122b1e")
    ax.axis("off")

    line_kw = dict(edgecolor="#3a6b4a", facecolor="none", linewidth=1.5)
    ax.add_patch(mpatches.Rectangle((0, 0), PX, PY, **line_kw))
    ax.plot([PX / 2, PX / 2], [0, PY], color="#3a6b4a", linewidth=1.5)
    ax.add_patch(mpatches.Arc((PX / 2, PY / 2), 18.3, 18.3, angle=0, **line_kw))
    ax.add_patch(mpatches.Circle((PX / 2, PY / 2), 0.8, fc="#3a6b4a"))
    pen_x1, pen_y1 = 0, PY / 2 - 20.15
    pen_w, pen_h = 16.5, 40.3
    ax.add_patch(mpatches.Rectangle((pen_x1, pen_y1), pen_w, pen_h, **line_kw))
    ax.add_patch(mpatches.Rectangle((PX - pen_w, pen_y1), pen_w, pen_h, **line_kw))
    goal_y1 = PY / 2 - 9.15
    goal_w, goal_h = 5.5, 18.3
    ax.add_patch(mpatches.Rectangle((0, goal_y1), goal_w, goal_h, **line_kw))
    ax.add_patch(mpatches.Rectangle((PX - goal_w, goal_y1), goal_w, goal_h, **line_kw))
    ax.plot([0, 0], [PY / 2 - 3.66, PY / 2 + 3.66], color="white", linewidth=3)
    ax.plot([PX, PX], [PY / 2 - 3.66, PY / 2 + 3.66], color="white", linewidth=3)
    ax.add_patch(mpatches.Circle((PX / 2, PY / 2), 0.3, fc="#3a6b4a"))
    ax.add_patch(mpatches.Circle((11, PY / 2), 0.3, fc="#3a6b4a"))
    ax.add_patch(mpatches.Circle((PX - 11, PY / 2), 0.3, fc="#3a6b4a"))
    for cx, cy in [(0, 0), (0, PY), (PX, 0), (PX, PY)]:
        angle = {0: 0, PY: 270, PX: 90, PX + PY: 180}.get(cx + cy, 0) if cx == 0 and cy == 0 else \
                (270 if cx == 0 and cy == PY else (90 if cx == PX and cy == 0 else 180))
        if cx == 0 and cy == 0: angle = 0
        elif cx == 0 and cy == PY: angle = 270
        elif cx == PX and cy == 0: angle = 90
        else: angle = 180
        ax.add_patch(mpatches.Arc((cx, cy), 2, 2, angle=angle, theta1=0, theta2=90, **line_kw))

    # Compute positions
    def _compute_pos(players, is_home):
        result = {}
        for p in players:
            grid = p.grid or ""
            if ":" in str(grid):
                col = int(str(grid).split(":")[0])
            else:
                col = 3
            x_map = {1: 0.04, 2: 0.18, 3: 0.36, 4: 0.56, 5: 0.80}
            x = PX * x_map.get(col, 0.5)
            if not is_home:
                x = PX - x
            n_col = sum(1 for pp in players if _col(pp.grid) == col)
            idx = sum(1 for pp in players if _col(pp.grid) == col and pp.id < p.id)
            y_range = PY * 0.74
            y_start = PY * 0.13
            spacing = y_range / max(n_col + 1, 1)
            y = y_start + spacing * (idx + 1)
            result[p.id] = (x, y)
        return result

    home_pos = _compute_pos(home_starters, True)
    away_starters_list = [p for p in raw.away_players if not p.is_substitute]
    away_pos = _compute_pos(away_starters_list, False)

    PHOTO_SZ = 5.0
    photo_cache = {}

    def _load_photo(p):
        if p.id in photo_cache:
            return photo_cache[p.id]
        uri = _get_player_photo_base64(p.id, p.photo_url or "")
        if uri:
            try:
                header, b64data = uri.split(",", 1)
                raw_data = base64.b64decode(b64data)
                img = Image.open(io.BytesIO(raw_data)).convert("RGBA")
                arr = np.array(img)
                # make circular
                h, w = arr.shape[:2]
                size = min(h, w)
                yy, xx = np.ogrid[:size, :size]
                center = (size - 1) / 2.0
                mask = (xx - center) ** 2 + (yy - center) ** 2 <= center ** 2
                rgba = np.zeros((size, size, 4), dtype=np.uint8)
                if arr.shape[2] >= 3:
                    rgba[:, :, :3] = arr[:size, :size, :3]
                else:
                    rgba[:, :, 0] = arr[:size, :size, 0]
                    rgba[:, :, 1] = arr[:size, :size, 0]
                    rgba[:, :, 2] = arr[:size, :size, 0]
                alpha = mask.astype(np.uint8) * 255
                if arr.shape[2] >= 4:
                    alpha = np.minimum(alpha, arr[:size, :size, 3])
                rgba[:, :, 3] = alpha
                photo_cache[p.id] = rgba
                return rgba
            except Exception:
                pass
        photo_cache[p.id] = None
        return None

    from PIL import Image

    for p in home_starters:
        x, y = home_pos.get(p.id, (PX * 0.5, PY * 0.5))
        photo = _load_photo(p)
        if photo is not None:
            h, w = photo.shape[:2]
            imagebox = OffsetImage(photo, zoom=PHOTO_SZ * 2 / max(h, w) * 0.9)
            ab = AnnotationBbox(imagebox, (x, y), frameon=False, box_alignment=(0.5, 0.5), pad=0, zorder=10)
            ax.add_artist(ab)
        else:
            ax.scatter(x, y, s=300, c=HOME_COLOR, edgecolors="white", linewidth=2, zorder=5)
        name_short = p.name.split()[-1] if p.name else "?"
        ax.text(x, y - PHOTO_SZ - 0.3, name_short, ha="center", va="top",
                fontsize=10, color="white", fontweight="bold", zorder=4)
        ax.text(x, y + PHOTO_SZ + 0.6, f"#{p.number}", ha="center", va="bottom",
                fontsize=9, color="#cccccc", zorder=4)

    for p in away_starters_list:
        x, y = away_pos.get(p.id, (PX * 0.5, PY * 0.5))
        photo = _load_photo(p)
        if photo is not None:
            h, w = photo.shape[:2]
            imagebox = OffsetImage(photo, zoom=PHOTO_SZ * 2 / max(h, w) * 0.9)
            ab = AnnotationBbox(imagebox, (x, y), frameon=False, box_alignment=(0.5, 0.5), pad=0, zorder=10)
            ax.add_artist(ab)
        else:
            ax.scatter(x, y, s=300, c=AWAY_COLOR, edgecolors="white", linewidth=2, zorder=5)
        name_short = p.name.split()[-1] if p.name else "?"
        ax.text(x, y - PHOTO_SZ - 0.3, name_short, ha="center", va="top",
                fontsize=10, color="white", fontweight="bold", zorder=4)
        ax.text(x, y + PHOTO_SZ + 0.6, f"#{p.number}", ha="center", va="bottom",
                fontsize=9, color="#cccccc", zorder=4)

    # Midfield label
    ax.text(PX * 0.5, PY * 0.5, "\u2014 \u4e2d\u573a\u7ebf \u2014", ha="center", va="center",
            fontsize=10, color="#4a6a50", alpha=0.5)

    # Header text
    stage = (raw.stage_info or {}).get("name", "")
    venue = (raw.venue_info or {}).get("name", "")
    fig.text(0.44, 0.97, stage, ha="center", fontsize=13, color="white", fontweight="bold")
    fig.text(0.44, 0.94, venue, ha="center", fontsize=9, color="#8ab4d6")

    home_formation = away_formation = "?"
    for f in (raw.formations or []):
        if f.get("location") == "home": home_formation = f.get("formation", "?")
        else: away_formation = f.get("formation", "?")

    fig.text(0.08, 0.97, raw.home_team.name, ha="center", fontsize=13, color=HOME_COLOR, fontweight="bold")
    fig.text(0.08, 0.94, home_formation, ha="center", fontsize=10, color=HOME_COLOR)
    fig.text(0.80, 0.97, raw.away_team.name, ha="center", fontsize=13, color=AWAY_COLOR, fontweight="bold")
    fig.text(0.80, 0.94, away_formation, ha="center", fontsize=10, color=AWAY_COLOR)

    # Subs on right panel
    _draw_subs_side(fig, raw, sub_events)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(out), dpi=dpi, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    return str(out)


def _draw_subs_side(fig, raw, sub_events):
    """Draw sub panels on the right side of the legacy matplotlib figure."""
    home_subs = [p for p in raw.home_players if p.is_substitute]
    away_subs = [p for p in raw.away_players if p.is_substitute]
    # Left column: home subs
    for i, p in enumerate(home_subs[:9]):
        if i > 20: break
        was_on = any(e.team_id == raw.home_team.id and e.assist_name == p.name for e in sub_events)
        marker = "\u2191" if was_on else " "
        fig.text(0.825, 0.80 - i * 0.028, f"{marker} #{p.number} {p.name[:14]}",
                 fontsize=7, color=HOME_COLOR if was_on else "#6a7a8a")
    fig.text(0.825, 0.84, "替补席", fontsize=10, color=HOME_COLOR, fontweight="bold")
    for i, p in enumerate(away_subs[:9]):
        if i > 20: break
        was_on = any(e.team_id == raw.away_team.id and e.assist_name == p.name for e in sub_events)
        marker = "\u2191" if was_on else " "
        fig.text(0.91, 0.80 - i * 0.028, f"{marker} #{p.number} {p.name[:14]}",
                 fontsize=7, color=AWAY_COLOR if was_on else "#6a7a8a")
    fig.text(0.91, 0.84, "替补席", fontsize=10, color=AWAY_COLOR, fontweight="bold")
