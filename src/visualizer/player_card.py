"""
Player Contribution Card — Dashboard layout (v4).
Normal y-axis (0=bottom), all positions computed top-down.
Top-left: [photo] name  [badge] team | Tags bar | Detector card grid.
Rankings: team + overall, no denominator/#. Footnote bottom-left.
"""
from __future__ import annotations

import os
import io

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import requests

from src.visualizer import HOME_COLOR, HOME_COLOR_DARK

DETECTOR_TAGS = {
    "D1": "推进引擎", "D2": "防守铁闸", "D3": "缠斗高手",
    "D4": "节拍器", "D5": "全能战士", "D6": "关键先生",
    "D7": "高效输出", "D8": "多面手", "D9": "串联枢纽",
    "D10": "射门质量高", "D13": "终结者",
}

PANEL_W = 9.6
MARGIN = 0.25
HEADER_H = 0.40
TAGS_H = 0.28
GRID_TOP_GAP = 0.10
CARD_PAD = 0.10
TITLE_H = 0.20
COL_HEAD_H = 0.18
METRIC_ROW_H = 0.16
FOOTNOTE_H = 0.12
PHOTO_R = 0.16
BADGE_R = 0.12


# ── Image helpers ──

def _fetch_image(url: str) -> np.ndarray | None:
    if not url:
        return None
    try:
        session = requests.Session()
        session.trust_env = False
        resp = session.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
        resp.raise_for_status()
        img = plt.imread(io.BytesIO(resp.content))
        if img.ndim == 2:
            img = np.stack([img] * 3, axis=-1)
        if img.shape[-1] == 4:
            img = img[..., :3]
        return img
    except Exception as e:
        print(f"  [WARN] _fetch_image failed for {url[:60]}: {e}")
        return None


def _circle_image(img: np.ndarray) -> np.ndarray:
    """Crop to circle with alpha. Handles both float32(0-1) and uint8(0-255)."""
    h, w = img.shape[:2]
    size = min(h, w)
    cy, cx = h // 2, w // 2
    y1, y2 = cy - size // 2, cy + size // 2
    x1, x2 = cx - size // 2, cx + size // 2
    cropped = img[y1:y2, x1:x2].copy()
    # Normalize to uint8 0-255
    if cropped.dtype == np.float32 or cropped.dtype == np.float64:
        cropped = (cropped * 255).clip(0, 255)
    cropped = cropped.astype(np.uint8)
    yy, xx = np.ogrid[:size, :size]
    dist = np.sqrt((yy - size / 2 + 0.5) ** 2 + (xx - size / 2 + 0.5) ** 2)
    mask = dist <= size / 2
    rgba = np.zeros((size, size, 4), dtype=np.uint8)
    if cropped.ndim == 3 and cropped.shape[2] >= 3:
        rgba[:, :, :3] = cropped[:, :, :3]
    else:
        rgba[:, :, :3] = cropped
    rgba[:, :, 3] = (mask * 255).astype(np.uint8)
    return rgba


def _format_val(v) -> str:
    if isinstance(v, float):
        if abs(v) >= 100:
            return str(int(v))
        elif abs(v) >= 10:
            return f"{v:.1f}"
        elif abs(v) < 1 and v != 0:
            return f"{v:.3f}"
        else:
            return f"{v:.2f}"
    return str(v)


def build_detector_sections(
    results_by_detector: dict,
    top3_per_detector: dict,
    player_name: str,
    team_name: str,
    max_metrics: int = 5,
) -> list[dict]:
    sections = []
    for dname in ["D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9", "D10", "D13"]:
        info = top3_per_detector.get(dname)
        if not info:
            continue
        team_top3 = info.get("team_results", {}).get(team_name, [])
        if not any(r.get("name") == player_name for r in team_top3):
            continue
        raw_results = results_by_detector.get(dname, {}).get(team_name, [])
        player_result = next((r for r in raw_results if r.name == player_name), None)
        if player_result is None:
            continue

        metrics = []
        event_labels = []
        evidence = player_result.evidence
        if evidence:
            # Extract event bonus labels (事件加成) — display as tags, not metrics
            ev_bonus = evidence.get("事件加成")
            if isinstance(ev_bonus, list):
                event_labels = ev_bonus
            elif isinstance(ev_bonus, str) and ev_bonus:
                event_labels = [s.strip() for s in ev_bonus.split(",") if s.strip()]

            def sort_key(item):
                _, v = item
                if isinstance(v, dict):
                    return abs(v.get("contrib", v.get("raw", 0)))
                return abs(float(v)) if isinstance(v, (int, float)) else 0

            sorted_ev = sorted(
                ((k, v) for k, v in evidence.items() if k not in ("事件加成", "关键标签")),
                key=sort_key, reverse=True)

            full_team_dict = results_by_detector.get(dname, {})
            all_players_list = []
            for _t, _rlist in full_team_dict.items():
                for _r in _rlist:
                    all_players_list.append(_r)
            all_players_list.sort(key=lambda _r: -_r.score)
            overall_map = {_p.name: _i + 1 for _i, _p in enumerate(all_players_list)}
            team_map = {_p.name: _i + 1 for _i, _p in enumerate(raw_results)}

            for key, val in sorted_ev[:max_metrics]:
                raw_val = val.get("raw", val) if isinstance(val, dict) else val
                tr = team_map.get(player_name, 1)
                otr = overall_map.get(player_name, 1)
                if dname == "D5":
                    if key == "进攻z":
                        key = "进攻贡献"
                    elif key == "防守z":
                        key = "防守贡献"
                metrics.append((key, raw_val, tr, otr))

        sections.append({
            "tag": DETECTOR_TAGS.get(dname, dname),
            "score": round(player_result.score, 2),
            "metrics": metrics,
            "event_labels": event_labels,
        })
    return sections


def plot_player_card(
    player_name: str,
    photo_url: str,
    team_name: str,
    team_logo_url: str,
    position: str,
    sections: list[dict],
    output_path: str,
    accent_override: str = "",
    dpi: int = 200,
    jersey_number: str = "",
    minutes: int = 0,
):
    n_sections = len(sections)
    if n_sections == 0:
        return

    ncols = 3 if n_sections > 2 else 2
    nrows = (n_sections + ncols - 1) // ncols

    usable_w = PANEL_W - 2 * MARGIN
    gap = 0.10
    card_w = (usable_w - (ncols - 1) * gap) / ncols

    max_m = max((len(s["metrics"]) for s in sections), default=0)
    card_body_h = TITLE_H + COL_HEAD_H + max_m * METRIC_ROW_H
    card_h = card_body_h + 2 * CARD_PAD
    grid_h = nrows * card_h + (nrows - 1) * gap
    total_h = MARGIN + HEADER_H + TAGS_H + GRID_TOP_GAP + grid_h + MARGIN + FOOTNOTE_H

    accent = accent_override or HOME_COLOR
    accent_dark = HOME_COLOR_DARK
    bg_color = "#0f0f1a"

    fig, ax = plt.subplots(figsize=(PANEL_W, total_h), dpi=dpi)
    ax.set_xlim(0, PANEL_W)
    ax.set_ylim(0, total_h)           # normal: y=0 at bottom
    ax.axis("off")
    fig.patch.set_facecolor(bg_color)

    # helper: y from top
    def _yt(offset_from_top: float) -> float:
        return total_h - offset_from_top

    # Fetch images
    photo_img = _fetch_image(photo_url)
    badge_img = _fetch_image(team_logo_url)
    if photo_img is not None:
        circle_img = _circle_image(photo_img)

    # ═══════════════════════════════
    # HEADER
    # ═══════════════════════════════
    top_offset = MARGIN + HEADER_H / 2
    hy = _yt(top_offset)

    # Photo (circle)
    photo_cx = MARGIN + PHOTO_R + 0.08
    if photo_img is not None:
        ax.imshow(circle_img,
                  extent=[photo_cx - PHOTO_R, photo_cx + PHOTO_R,
                          hy - PHOTO_R, hy + PHOTO_R],
                  zorder=5)
    else:
        ax.add_patch(plt.Circle((photo_cx, hy), PHOTO_R,
                                facecolor="#3a3a5c", edgecolor=accent, linewidth=1.5))

    # ── Player name + jersey + minutes ──
    name_x = photo_cx + PHOTO_R + 0.10
    display_name = player_name
    if jersey_number:
        display_name += f"  #{jersey_number}"
    if minutes > 0:
        display_name += f"  {minutes}'"
    ax.text(name_x, hy, display_name, fontsize=9, color="white",
            fontweight="bold", ha="left", va="center")



    # ═══════════════════════════════
    # TAGS BAR
    # ═══════════════════════════════
    tag_yt = _yt(MARGIN + HEADER_H + TAGS_H / 2)
    tag_x = MARGIN + 0.05
    tag_h = 0.14
    evt_h = 0.11
    for sec in sections:
        tag_text = sec["tag"]
        tag_w = max(len(tag_text) * 0.14, 0.30)
        ax.add_patch(plt.Rectangle(
            (tag_x, tag_yt - tag_h / 2), tag_w, tag_h,
            facecolor=accent, alpha=0.85, edgecolor=accent_dark, linewidth=0.5, zorder=3))
        ax.text(tag_x + tag_w / 2, tag_yt, tag_text, fontsize=6.5, color="white",
                ha="center", va="center", fontweight="bold")
        tag_x += tag_w + 0.04

        # Event bonus labels (制胜球, 绝杀 etc.) — border-only small tags
        evt_labels = sec.get("event_labels", [])
        for evt_text in evt_labels:
            evt_w = max(len(evt_text) * 0.12, 0.22)
            ax.add_patch(plt.Rectangle(
                (tag_x, tag_yt - evt_h / 2), evt_w, evt_h,
                facecolor="none", edgecolor=accent, alpha=0.7, linewidth=0.6, zorder=3))
            ax.text(tag_x + evt_w / 2, tag_yt, evt_text, fontsize=5.0, color=accent,
                    ha="center", va="center", fontweight="bold")
            tag_x += evt_w + 0.03
        tag_x += 0.04

    # ═══════════════════════════════
    # DETECTOR CARDS
    # ═══════════════════════════════
    grid_top_offset = MARGIN + HEADER_H + TAGS_H + GRID_TOP_GAP

    for si, sec in enumerate(sections):
        row = si // ncols
        col = si % ncols
        cx = MARGIN + col * (card_w + gap)
        ctop = grid_top_offset + row * (card_h + gap)
        cy = _yt(ctop) - card_h  # card bottom-left y

        # card bg
        ax.add_patch(plt.Rectangle(
            (cx, cy), card_w, card_h,
            facecolor="#1a1a2e", edgecolor="#2a2a4a", linewidth=0.5, zorder=1))

        # title
        ty = cy + card_h - CARD_PAD - TITLE_H / 2
        ax.text(cx + CARD_PAD, ty, sec["tag"], fontsize=6.5, color=accent,
                fontweight="bold", ha="left", va="center")
        ax.text(cx + card_w - CARD_PAD, ty, f"{sec['score']:.2f}",
                fontsize=5.5, color="#8899aa", ha="right", va="center")

        sep_y = cy + card_h - CARD_PAD - TITLE_H
        ax.plot([cx + CARD_PAD, cx + card_w - CARD_PAD], [sep_y, sep_y],
                color=accent, alpha=0.2, linewidth=0.5)

        # column headers
        chdr_y = sep_y - COL_HEAD_H / 2
        inner_w = card_w - 2 * CARD_PAD
        cols_x = [
            cx + CARD_PAD,
            cx + CARD_PAD + inner_w * 0.44,
            cx + CARD_PAD + inner_w * 0.66,
            cx + CARD_PAD + inner_w * 0.80,
        ]
        col_ws = [inner_w * 0.44, inner_w * 0.22, inner_w * 0.14, inner_w * 0.20]
        col_centers = [cols_x[i] + col_ws[i] / 2 for i in range(4)]

        for i, hdr in enumerate(["指标", "值", "队", "场"]):
            ax.text(col_centers[i], chdr_y, hdr, fontsize=5.0,
                    color="#556677", ha="center", va="center")

        # metric rows
        row_bottom = sep_y - COL_HEAD_H
        for mi, (mname, mval, tr, otr) in enumerate(sec["metrics"]):
            ry = row_bottom - (mi + 0.5) * METRIC_ROW_H
            ax.text(cols_x[0] + 0.02, ry, mname, fontsize=5.5,
                    color="#ccd6e0", ha="left", va="center")
            ax.text(col_centers[1], ry, _format_val(mval),
                    fontsize=5.5, color="white", ha="center", va="center", fontweight="bold")
            ax.text(col_centers[2], ry, str(tr),
                    fontsize=5.5, color="#aabbcc", ha="center", va="center")
            ax.text(col_centers[3], ry, str(otr),
                    fontsize=5.5, color="#aabbcc", ha="center", va="center")
            if mi < len(sec["metrics"]) - 1:
                div_y = ry - METRIC_ROW_H / 2
                ax.plot([cx + CARD_PAD, cx + card_w - CARD_PAD], [div_y, div_y],
                        color="#ffffff", alpha=0.04, linewidth=0.5)

    # ═══════════════════════════════
    # FOOTER: footnote (left) + badge + team (right)
    # ═══════════════════════════════
    fny = MARGIN + FOOTNOTE_H / 2
    ax.text(MARGIN + 0.05, fny, "队: 队内排名    场: 对阵双方排名",
            fontsize=4.5, color="#445566", ha="left", va="center")

    # Badge + team name — bottom-right
    badge_cx = PANEL_W - MARGIN - BADGE_R - 0.05
    if badge_img is not None:
        ax.imshow(badge_img,
                  extent=[badge_cx - BADGE_R, badge_cx + BADGE_R,
                          fny - BADGE_R, fny + BADGE_R],
                  zorder=5)
    team_x = badge_cx - BADGE_R - 0.05
    ax.text(team_x, fny, team_name, fontsize=6.5, color="#ccd6e0",
            fontweight="bold", ha="right", va="center")

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    fig.savefig(output_path, dpi=dpi, facecolor=bg_color,
                edgecolor="none", bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    return output_path
