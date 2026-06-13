"""
球员贡献对比图 — matplotlib 暗色主题，雷达居中 + LLM点评 + 紧凑对比。

布局：
┌─────────────────────────────────────┐
│           比赛标题                   │
├─────────┬──────────┬───────────────┤
│ LLM点评 │   C1-C5  │   LLM点评     │
│ (左侧)  │  五维雷达 │   (右侧)     │
├─────────┴──────────┴───────────────┤
│   球员A基本信息  |  球员B基本信息     │
├─────────────────────────────────────┤
│  C1-C5指标表格A  |  C1-C5指标表格B  │
├─────────────────────────────────────┤
│         说明脚注                     │
└─────────────────────────────────────┘

2026-06-12 v3: 雷达上移+LLM点评左右+双方信息紧凑
"""
from __future__ import annotations

import math
import os
import io
import base64
import unicodedata
import textwrap
from typing import Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import requests

from src.visualizer import HOME_COLOR, AWAY_COLOR

# ── 颜色常量 ──
BG_COLOR = "#1a1a2e"
TEXT_COLOR = "#e0e8f0"
MUTED_COLOR = "#6a7a8a"
GRID_COLOR = "#2a2a4a"
CARD_BG = "#141428"
TABLE_BORDER = "#2a2a4a"

# ── v6 C1-C5 维度标签 + 副标题（设计文档 §2 副标题） ──
DIM_LABELS = ["进攻", "推进", "控制", "防守", "对抗"]
DIM_SUBTITLES = {
    "进攻": "创造机会，转化进球",
    "推进": "构建攻势，推进阵地",
    "控制": "掌控节奏，寻找机会",
    "防守": "抢断拦截，阻止得分",
    "对抗": "积极拼抢，拿下球权",
}

# ── C1 进攻指标（type_id → 中文名，用于计算得分） ──
C1_METRICS = {
    52: ("进球", 2.5), 79: ("助攻", 2.0), 5304: ("xG", 2.0),
    111: ("点球进球", 1.5), 42: ("射门", 1.0), 86: ("射正", 1.5),
    5305: ("xGOT", 1.2), 9685: ("射门表现", 1.5), 64: ("中框", 0.8),
    580: ("创造绝佳机会", 1.5), 9706: ("创造机会", 1.0), 117: ("关键传球", 1.0),
    41: ("射偏", -0.5), 58: ("被封堵射门", -0.3), 581: ("错失绝佳机会", -1.5),
}

# ── 各维度展示指标 (type_id → 中文名) — 全部指标 ──
DIM_DISPLAY_METRICS = {
    "进攻": {
        52: "进球", 79: "助攻", 5304: "xG", 111: "点球进球",
        42: "射门", 86: "射正", 5305: "xGOT", 9685: "射门表现",
        64: "中框", 580: "创造绝佳机会", 9706: "创造机会", 117: "关键传球",
        41: "射偏", 58: "被封堵射门", 581: "错失绝佳机会",
    },
    "推进": {
        27269: "三区传球", 109: "成功过人", 108: "尝试过人",
        98: "传中", 99: "精准传中", 1533: "传中成功率",
        122: "长传", 123: "成功长传", 27270: "长传成功率",
        115: "赢得点球", 96: "被犯规", 51: "越位",
    },
    "控制": {
        80: "传球", 116: "精准传球", 1584: "传球成功率",
        120: "触球", 27272: "回传", 27273: "丢失球权", 94: "被抢断",
        119: "出场时间",
    },
    "防守": {
        101: "解围", 78: "抢断", 27267: "成功抢断", 27268: "抢断成功率",
        100: "拦截", 97: "封堵射门", 110: "被过人",
        571: "导致丢球失误", 48997: "导致射门失误", 114: "送点",
    },
    "对抗": {
        105: "总对抗", 106: "赢得对抗", 1491: "输掉对抗",
        27276: "对抗成功率", 107: "赢得空中对抗",
        27274: "空中对抗", 27266: "输掉空中对抗", 27275: "空中成功率",
        27271: "球权回收", 96: "被犯规", 56: "犯规", 84: "黄牌", 83: "红牌",
    },
}

# ═══════════════════════ 图片辅助 ═══════════════════════

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
    except Exception:
        return None


def _circle_image(img: np.ndarray, size: int = 256) -> np.ndarray:
    from PIL import Image, ImageDraw
    h, w = img.shape[:2]
    s = min(h, w)
    left = (w - s) // 2
    top = (h - s) // 2
    cropped = img[top:top + s, left:left + s]
    pil_img = Image.fromarray(
        (cropped * 255).astype(np.uint8)
        if cropped.dtype in (np.float32, np.float64)
        else cropped.astype(np.uint8)
    )
    pil_img = pil_img.resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size, size), fill=255)
    rgba = Image.new("RGBA", (size, size))
    rgba.paste(pil_img, (0, 0))
    rgba.putalpha(mask)
    return np.array(rgba) / 255.0


# ═══════════════════════ 表格宽度常量 ═══════════════════════
# 紧凑列定义 (以英寸为单位的绝对列位置，相对于 inner_x)
COL_METRIC = 0      # 指标名起始
COL_VALUE  = 1.85   # 值
COL_TEAM   = 2.35   # 队排
COL_FIELD  = 2.75   # 场排
COL_END    = 3.10   # 总宽

# ═══════════════════════ 核心绘制函数 ═══════════════════════

def plot_player_comparison(
    match_title: str,
    home_name: str,
    away_name: str,
    player_a: dict,
    player_b: dict,
    output_path: str,
    llm_a: str = "",
    llm_b: str = "",
    dpi: int = 150,
):
    # ── 布局参数 ──
    margin = 0.18
    header_h = 0.60
    footer_h = 0.30

    llm_w = 2.30          # 左右 LLM 文字列宽
    radar_w = 4.00        # 雷达图区域宽
    gap = 0.20            # LLM↔雷达间距
    total_w = margin + llm_w + gap + radar_w + gap + llm_w + margin

    radar_row_h = 3.00    # 雷达+LLM 行高
    info_row_h = 1.90     # 球员基本信息行高

    # 球员信息面板：左右居中对称，各宽 3.20 英寸，间距 0.50 英寸
    mid_x = total_w / 2
    info_panel_w = 3.20
    info_panel_gap = 0.50
    info_total_span = info_panel_w * 2 + info_panel_gap
    info_left_x0 = mid_x - info_total_span / 2
    info_right_x0 = mid_x + info_panel_gap / 2

    # ── 维度表格高度 ──
    def _dim_table_h(player: dict) -> float:
        h = 0.0
        for dim in DIM_LABELS:
            rows = len(player.get("dim_tables", {}).get(dim, []))
            if rows:
                h += 0.20 + 0.17 + rows * 0.18 + 0.08
        return h + 0.10

    dim_h = max(_dim_table_h(player_a), _dim_table_h(player_b), 2.0)

    # ── 图表区高度评估（快速判断哪些图存在） ──
    chart_types = [
        ("heatmap_b64",),
        ("pass_chart_b64",),
        ("dribble_chart_b64",),
    ]
    chart_rows = sum(1 for (k,) in chart_types
                     if player_a.get(k) or player_b.get(k))
    row_h_per = 2.10
    gap_per = 0.12
    label_h = 0.25
    charts_h = chart_rows * (row_h_per + gap_per) - gap_per + label_h if chart_rows else 0.0
    if charts_h > 0:
        charts_h += 0.35  # top separator margin (room for sub-title + spacing)

    total_h = header_h + radar_row_h + info_row_h + charts_h + dim_h + footer_h + margin * 2

    fig = plt.figure(figsize=(total_w, total_h), dpi=dpi)
    fig.patch.set_facecolor(BG_COLOR)

    # ═══════════════════ 标题 ═══════════════════
    title_ax = fig.add_axes([0, (total_h - header_h - margin) / total_h, 1, header_h / total_h])
    title_ax.set_xlim(0, 1); title_ax.set_ylim(0, 1); title_ax.axis("off")
    title_ax.set_facecolor(BG_COLOR)
    title_ax.text(0.5, 0.78, match_title, transform=title_ax.transAxes,
                  fontsize=14, color=TEXT_COLOR, ha="center", va="center", fontweight="bold")
    title_ax.text(0.5, 0.28, "球员贡献对比", transform=title_ax.transAxes,
                  fontsize=11, color=MUTED_COLOR, ha="center", va="center")

    # ═══════════════════ 雷达行：LLM_A │ 雷达 │ LLM_B ═══════════════════
    radar_y0 = footer_h + dim_h + charts_h + info_row_h + margin
    radar_row_ax = fig.add_axes([0, radar_y0 / total_h, 1, radar_row_h / total_h])
    radar_row_ax.set_xlim(0, total_w); radar_row_ax.set_ylim(0, radar_row_h)
    radar_row_ax.axis("off"); radar_row_ax.set_facecolor(BG_COLOR)

    # LLM 文字（左右）
    for side, llm_text, color in [("left", llm_a, HOME_COLOR), ("right", llm_b, AWAY_COLOR)]:
        if not llm_text:
            continue
        x0 = margin if side == "left" else margin + llm_w + gap + radar_w + gap
        # 标题
        radar_row_ax.text(x0 + llm_w / 2, radar_row_h - 0.25, "球员点评",
                          fontsize=12, color=color, ha="center", va="center", fontweight="bold")
        # 正文（自动换行）
        wrapped = textwrap.fill(llm_text, width=12)
        lines = wrapped.split("\n")
        line_h = 0.25
        text_y = radar_row_h - 0.68
        for li in lines[:9]:  # 最多 9 行
            radar_row_ax.text(x0 + llm_w / 2, text_y, li, fontsize=11,
                              color=MUTED_COLOR, ha="center", va="center", fontweight="bold")
            text_y -= line_h

    # 雷达图
    radar_cx = llm_w + gap + radar_w / 2 + margin
    radar_cy = radar_row_h / 2
    radar_r = min(radar_w / 2.4, radar_row_h / 2.5)
    _draw_radar(radar_row_ax, player_a, player_b,
                center=(radar_cx, radar_cy), radius=radar_r,
                home_color=HOME_COLOR, away_color=AWAY_COLOR)

    # 雷达图例（底部居中）
    leg_y = radar_cy - radar_r - 0.55
    lx1 = radar_cx - 1.6
    lx2 = radar_cx + 0.3
    # Normalize names for font compat
    def _safe_name(n):
        try:
            dn = unicodedata.normalize('NFKD', n).encode('ascii', 'ignore').decode('ascii')
            return dn if dn.strip() else n
        except Exception:
            return n
    radar_row_ax.plot([lx1, lx1 + 0.35], [leg_y, leg_y],
                      color=HOME_COLOR, linewidth=2, marker="o", markersize=4, zorder=4)
    radar_row_ax.text(lx1 + 0.42, leg_y, _safe_name(player_a["name"]), fontsize=7.5, color=HOME_COLOR,
                      va="center", fontweight="bold")
    radar_row_ax.plot([lx2, lx2 + 0.35], [leg_y, leg_y],
                      color=AWAY_COLOR, linewidth=2, linestyle="--", marker="s", markersize=4, zorder=4)
    radar_row_ax.text(lx2 + 0.42, leg_y, _safe_name(player_b["name"]), fontsize=7.5, color=AWAY_COLOR,
                      va="center", fontweight="bold")

    # ═══════════════════ 球员基本信息行（左右并排，垂直布局） ═══════════════════
    info_y0 = footer_h + dim_h + charts_h + margin
    info_ax = fig.add_axes([0, info_y0 / total_h, 1, info_row_h / total_h])
    info_ax.set_xlim(0, total_w); info_ax.set_ylim(0, info_row_h)
    info_ax.axis("off"); info_ax.set_facecolor(BG_COLOR)

    _draw_player_info_compact(info_ax, player_a, info_left_x0, 0, info_panel_w, info_row_h, HOME_COLOR)
    _draw_player_info_compact(info_ax, player_b, info_right_x0, 0, info_panel_w, info_row_h, AWAY_COLOR)

    # ═══════════════════ 比赛视觉分析（热图/传球/推进） ═══════════════════
    if charts_h > 0:
        charts_y0 = footer_h + dim_h + margin
        charts_ax = fig.add_axes([0, charts_y0 / total_h, 1, charts_h / total_h])
        charts_ax.set_xlim(0, total_w); charts_ax.set_ylim(0, charts_h)
        charts_ax.axis("off"); charts_ax.set_facecolor(BG_COLOR)
        # Subtle separator line spanning panel area
        panel_start = info_left_x0
        panel_end = info_right_x0 + info_panel_w
        charts_ax.plot([panel_start, panel_end],
                       [charts_h - 0.08, charts_h - 0.08],
                       color=TABLE_BORDER, linewidth=0.5, alpha=0.3)
        _draw_charts_row(fig, charts_ax, player_a, player_b,
                         info_left_x0, info_right_x0, info_panel_w, total_w,
                         HOME_COLOR, AWAY_COLOR)
        # Section label (centered across panels)
        panel_ctr = (info_left_x0 + info_right_x0 + info_panel_w) / 2
        charts_ax.text(panel_ctr, charts_h - 0.22, "— 比赛视觉分析 —",
                       fontsize=9, color=MUTED_COLOR, ha="center", va="bottom",
                       alpha=0.8)

    # ═══════════════════ C1-C5 维度表格 ═══════════════════
    dim_y0 = footer_h + margin
    dim_ax = fig.add_axes([0, dim_y0 / total_h, 1, dim_h / total_h])
    dim_ax.set_xlim(0, total_w); dim_ax.set_ylim(0, dim_h)
    dim_ax.axis("off"); dim_ax.set_facecolor(BG_COLOR)

    _draw_dim_table(dim_ax, player_a, info_left_x0, dim_h, info_panel_w, HOME_COLOR)
    _draw_dim_table(dim_ax, player_b, info_right_x0, dim_h, info_panel_w, AWAY_COLOR)

    # ═══════════════════ 脚注 ═══════════════════
    footer_ax = fig.add_axes([0, 0, 1, footer_h / total_h])
    footer_ax.set_xlim(0, 1); footer_ax.set_ylim(0, 1); footer_ax.axis("off")
    footer_ax.set_facecolor(BG_COLOR)
    footer_ax.text(0.5, 0.55, "* 分组按 C1-C5 贡献检测维度；队排=队内排名，场排=全场外场球员排名",
                   transform=footer_ax.transAxes, fontsize=7.5, color=MUTED_COLOR, ha="center", va="center")

    # ── 保存 ──
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight", pad_inches=0.05,
                facecolor=BG_COLOR, edgecolor="none")
    plt.close(fig)


# ═══════════════════════ 紧凑球员信息 ═══════════════════════

def _draw_player_info_compact(ax, player: dict, x0: float, y_bot: float, w: float, h: float, color: str):
    """绘制球员基本信息面板：头像 + 姓名# + 出场 + 跑动/推进 + 进球/助攻/关键事件。
    参数 y_bot=面板底部 y 坐标, h=面板高度。"""
    y_top = y_bot + h

    # ── 面板背景 ──
    rect = mpatches.FancyBboxPatch((x0, y_bot + 0.06), w, h - 0.12,
                                    boxstyle="round,pad=0.08", linewidth=0.8,
                                    edgecolor=TABLE_BORDER, facecolor=CARD_BG, zorder=1)
    ax.add_patch(rect)

    inner_x = x0 + 0.10
    cy = y_top - 0.32

    # ── 头像 ──
    photo_r = 0.28
    photo_cx = inner_x + photo_r
    photo_url = player.get("photo_url", "")
    photo_img = _fetch_image(photo_url) if photo_url else None
    if photo_img is not None:
        circle = _circle_image(photo_img)
        ax.imshow(circle, extent=[photo_cx - photo_r, photo_cx + photo_r,
                                   cy - photo_r, cy + photo_r], zorder=3)
    else:
        ax.add_patch(plt.Circle((photo_cx, cy), photo_r,
                                facecolor="#3a3a5c", edgecolor=color,
                                linewidth=1.5, zorder=3))

    # ── 姓名 + 号码 ──
    name_x = photo_cx + photo_r + 0.12
    num = str(player.get("number", "") or "")
    # Normalize display name: strip accents for matplotlib font compatibility
    display_name = player["name"]
    try:
        dn = unicodedata.normalize('NFKD', display_name).encode('ascii', 'ignore').decode('ascii')
        if dn.strip():
            display_name = dn
    except Exception:
        pass
    ax.text(name_x, cy + 0.08, f"{display_name}  #{num}",
            fontsize=10, color=TEXT_COLOR, va="center", fontweight="bold")

    # ── 出场时间 ──
    mins = player.get("minutes", 0)
    ax.text(name_x, cy - 0.23, f"出场 {mins}'",
            fontsize=8.5, color=MUTED_COLOR, va="center")

    # ── 跑动/推进距离 ──
    run_km = player.get("run_km")
    carry_km = player.get("carry_km")
    phys_parts = []
    if run_km is not None:
        phys_parts.append(f"跑动 {run_km:.1f} km")
    if carry_km is not None:
        phys_parts.append(f"推进 {carry_km:.2f} km")
    if phys_parts:
        ax.text(name_x, cy - 0.44, "  ".join(phys_parts),
                fontsize=8, color="#3fb950", va="center")

    # ── 进球 / 助攻 / 关键事件 ──
    label_x = inner_x + 0.05
    cy2 = y_top - 1.15
    goals = player.get("goals", 0) or 0
    assists = player.get("assists", 0) or 0
    key_events = player.get("key_events", "") or "-"
    basic = [("进球", str(goals)), ("助攻", str(assists)), ("关键事件", key_events)]
    for lbl, val in basic:
        ax.text(label_x, cy2, lbl, fontsize=8.5, color=MUTED_COLOR, va="center")
        ax.text(label_x + 1.80, cy2, val, fontsize=8.5, color=TEXT_COLOR, va="center", fontweight="bold")
        cy2 -= 0.20


# ═══════════════════════ 维度表格 ═══════════════════════

def _draw_dim_table(ax, player: dict, x0: float, y_top: float, w: float, color: str):
    """在指定区域绘制 C1-C5 维度指标表格。"""
    # 背景
    rect = mpatches.FancyBboxPatch((x0, 0.04), w, y_top - 0.08,
                                    boxstyle="round,pad=0.10", linewidth=0.8,
                                    edgecolor=TABLE_BORDER, facecolor=CARD_BG, zorder=1)
    ax.add_patch(rect)

    inner_x = x0 + 0.14
    cy = y_top - 0.25

    dim_tables = player.get("dim_tables", {})
    for dim_label in DIM_LABELS:
        subtitle = DIM_SUBTITLES.get(dim_label, "")
        rows = dim_tables.get(dim_label, [])
        if not rows:
            continue

        # 维度标题
        ax.text(inner_x, cy, dim_label, fontsize=8.5, color=color, va="center", fontweight="bold")
        ax.text(inner_x + 0.42, cy, subtitle, fontsize=7, color=MUTED_COLOR, va="center")
        cy -= 0.20

        # 表头
        hd_val = inner_x + 2.00
        hd_team = inner_x + 2.55
        hd_field = inner_x + 2.95
        for pos, txt in [(inner_x, "指标"), (hd_val, "值"), (hd_team, "队排"), (hd_field, "场排")]:
            ax.text(pos, cy, txt, fontsize=7, color=MUTED_COLOR, va="center")
        cy -= 0.17

        for metric_name, value, team_rank, overall_rank, *_ in rows:
            ax.text(inner_x, cy, metric_name, fontsize=7.5, color=TEXT_COLOR, va="center")
            ax.text(hd_val, cy, _fmt_val(value), fontsize=7.5, color=TEXT_COLOR, va="center")
            ax.text(hd_team, cy, str(team_rank), fontsize=7.5, color=_rank_color(team_rank),
                    va="center", fontweight="bold")
            ax.text(hd_field, cy, str(overall_rank), fontsize=7.5, color=_rank_color(overall_rank),
                    va="center", fontweight="bold")
            cy -= 0.18

        sep_y = cy + 0.06
        ax.plot([inner_x, inner_x + w - 0.28], [sep_y, sep_y],
                color=TABLE_BORDER, linewidth=0.5, alpha=0.4, zorder=1)
        cy -= 0.08


def _draw_charts_row(fig, ax, player_a: dict, player_b: dict,
                     info_left_x0: float, info_right_x0: float,
                     info_panel_w: float, total_w: float,
                     home_color: str, away_color: str) -> float:
    """Draw the 3-row chart comparison area (heatmap / pass_chart / dribble_chart).

    Returns total height used (in inches), or 0.0 if no charts available.
    """
    chart_types = [
        ("heatmap_b64", "比赛热图"),
        ("pass_chart_b64", "传球分布"),
        ("dribble_chart_b64", "带球推进"),
    ]
    row_h = 2.10          # height per chart row
    label_h = 0.25         # label above each row
    gap = 0.12             # gap between rows
    chart_w = info_panel_w - 0.20  # chart display width
    # 图片 display 尺寸 (英寸)：假设原图~290×175，按高度 1.60" contain
    img_display_h = 1.45
    img_display_w = chart_w - 0.40

    # Count how many chart types have data for either player
    available_rows = []
    for key, label in chart_types:
        has_a = player_a.get(key)
        has_b = player_b.get(key)
        if has_a or has_b:
            available_rows.append((key, label, has_a, has_b))

    if not available_rows:
        return 0.0

    total_charts_h = len(available_rows) * (row_h + gap) - gap + label_h

    # Y starts from top of the area going downward
    y_cur = total_charts_h

    for key, label, has_a, has_b in available_rows:
        y_top = y_cur
        y_bot = y_top - row_h

        # Row label (centered across both panel areas)
        panel_center_x = (info_left_x0 + info_right_x0 + info_panel_w) / 2
        ax.text(panel_center_x, y_top - 0.05, label,
                fontsize=8.5, color=MUTED_COLOR, ha="center", va="bottom",
                fontweight="bold")

        # Player A chart (left panel)
        _draw_chart_card(fig, ax, has_a,
                         info_left_x0 + 0.10, y_bot + 0.18,
                         img_display_w, img_display_h,
                         home_color, "暂无数据")

        # Player B chart (right panel)
        _draw_chart_card(fig, ax, has_b,
                         info_right_x0 + 0.10, y_bot + 0.18,
                         img_display_w, img_display_h,
                         away_color, "暂无数据")

        y_cur = y_bot - gap

    return total_charts_h


def _draw_chart_card(fig, ax, b64_data, x: float, y: float, w: float, h: float,
                     color: str, placeholder: str):
    """Draw a single chart card with border. b64_data can be None (placeholder)."""
    # Card background
    card = mpatches.FancyBboxPatch((x, y), w, h,
                                    boxstyle="round,pad=0.06", linewidth=0.8,
                                    edgecolor=color, facecolor=CARD_BG,
                                    alpha=0.6, zorder=2)
    ax.add_patch(card)

    if b64_data:
        try:
            # Parse base64 data URI
            header, encoded = b64_data.split(",", 1)
            img_bytes = base64.b64decode(encoded)
            import matplotlib.image as mpimg
            from io import BytesIO
            img_arr = mpimg.imread(BytesIO(img_bytes))
            pad = 0.08
            ax.imshow(img_arr, extent=[x + pad, x + w - pad, y + pad, y + h - pad],
                      aspect='auto', zorder=3, interpolation='bilinear')
        except Exception:
            pass
    else:
        ax.text(x + w / 2, y + h / 2, placeholder,
                fontsize=9, color=MUTED_COLOR, ha="center", va="center",
                alpha=0.7, fontstyle="italic")


def _draw_radar(ax, player_a: dict, player_b: dict,
                center: tuple, radius: float,
                home_color: str, away_color: str):
    """绘制 C1-C5 五维双色雷达图。"""
    n = len(DIM_LABELS)
    cx, cy = center

    angles = [math.pi / 2 - 2 * math.pi * i / n for i in range(n)]
    angles_closed = angles + [angles[0]]

    scores_a = [player_a["dim_scores"].get(d, 0) for d in DIM_LABELS]
    scores_b = [player_b["dim_scores"].get(d, 0) for d in DIM_LABELS]

    all_vals = scores_a + scores_b
    amin = min(all_vals)
    amax = max(all_vals)
    if amax - amin < 0.001:
        amax = amin + 1.0

    def _norm(v):
        return max(0.05, (v - amin) / (amax - amin) * 0.85 + 0.05)

    na = [_norm(v) for v in scores_a] + [_norm(scores_a[0])]
    nb = [_norm(v) for v in scores_b] + [_norm(scores_b[0])]

    # 网格
    for level in [0.25, 0.50, 0.75, 1.0]:
        r = radius * level
        pts = [(cx + r * math.cos(a), cy + r * math.sin(a)) for a in angles]
        pts.append(pts[0])
        xs, ys = zip(*pts)
        ax.plot(xs, ys, color=GRID_COLOR, linewidth=0.5, alpha=0.5, zorder=1)

    # 轴线
    for a in angles:
        ax.plot([cx, cx + radius * math.cos(a)], [cy, cy + radius * math.sin(a)],
                color=GRID_COLOR, linewidth=0.5, alpha=0.4, zorder=1)

    # 球员 A（实线圆点）
    a_pts = [(cx + radius * na[i] * math.cos(angles_closed[i]),
              cy + radius * na[i] * math.sin(angles_closed[i]))
             for i in range(len(angles_closed))]
    axs, ays = zip(*a_pts)
    ax.fill(axs, ays, alpha=0.12, color=home_color, zorder=2)
    ax.plot(axs, ays, color=home_color, linewidth=2.0, zorder=3, marker="o", markersize=5)

    # 球员 B（虚线方块）
    b_pts = [(cx + radius * nb[i] * math.cos(angles_closed[i]),
              cy + radius * nb[i] * math.sin(angles_closed[i]))
             for i in range(len(angles_closed))]
    bxs, bys = zip(*b_pts)
    ax.fill(bxs, bys, alpha=0.12, color=away_color, zorder=2)
    ax.plot(bxs, bys, color=away_color, linewidth=2.0, zorder=3,
            linestyle="--", marker="s", markersize=5)

    # 维度标签（外侧）
    for i, a in enumerate(angles):
        lr = radius * 1.18
        lx = cx + lr * math.cos(a)
        ly = cy + lr * math.sin(a)
        ax.text(lx, ly, DIM_LABELS[i], fontsize=9, color=TEXT_COLOR,
                ha="center", va="center", fontweight="bold")


# ═══════════════════════ 工具函数 ═══════════════════════

def _fmt_val(v) -> str:
    if v is None:
        return "-"
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


def _rank_color(rank: int) -> str:
    if rank <= 1:
        return "#f1c40f"  # gold
    elif rank <= 3:
        return TEXT_COLOR
    else:
        return MUTED_COLOR


# ═══════════════════════ 数据构建 ═══════════════════════

def build_player_comparison_data(
    player_data_list: list,        # 该队 PlayerData 列表
    detector_results: dict,        # {"D1": {team: [DetectorResult]}, ...}
    key_event_info: dict,          # {player_name: "制胜球,..."}
    player_name: str,
    player_team: str,
    all_players: list,             # 全场 PlayerData 列表
    run_km: float = None,          # 跑动距离 (km)
    carry_km: float = None,        # 带球推进距离 (km)
    llm_summary: str = "",         # LLM 分析点评
    heatmap_b64: str = None,
    pass_chart_b64: str = None,
    dribble_chart_b64: str = None,
):
    pd = next((p for p in player_data_list if p.name == player_name), None)
    if pd is None:
        return None

    number = ""
    minutes = 0
    photo_url = ""
    ap = next((p for p in all_players if p.name == player_name), None)
    if ap:
        number = str(getattr(ap, "number", "") or "")
        minutes = int(ap.sv(119) or 0)
        photo_url = getattr(ap, "photo_url", "") or ""

    goals = int(pd.sv(52))
    assists = int(pd.sv(79))
    key_events = key_event_info.get(player_name, "")

    # ── C1-C5 维度得分 ──
    dim_scores = {}
    # C1: 加权 z-score
    c1_scores = _compute_zscore_weighted(player_data_list, C1_METRICS)
    for i, p in enumerate(player_data_list):
        if p.name == player_name:
            dim_scores["进攻"] = round(c1_scores[i], 2)
            break

    detector_dim_map = {"推进": "D1", "防守": "D2", "对抗": "D3", "控制": "D4"}
    for dim_label, dname in detector_dim_map.items():
        team_results = detector_results.get(dname, {}).get(player_team, [])
        r = next((r for r in team_results if r.name == player_name), None)
        dim_scores[dim_label] = round(r.score if r else 0, 2)

    # ── 全部指标表格（不再按排名过滤） ──
    dim_tables = {}
    for dim_label in DIM_LABELS:
        metrics = DIM_DISPLAY_METRICS.get(dim_label, {})
        rows = []
        for type_id, metric_name in metrics.items():
            if type_id == 119:
                continue  # 出场时间单独展示，不放表格
            val = pd.sv(type_id)
            if val is None:
                continue

            # 队内排名
            team_vals = [(p.sv(type_id), p.name) for p in player_data_list]
            team_vals.sort(key=lambda x: -(x[0] or 0))
            team_rank = next((i + 1 for i, (_, n) in enumerate(team_vals) if n == player_name), 999)

            # 全场排名
            all_vals = [(p.sv(type_id), p.name) for p in all_players]
            all_vals.sort(key=lambda x: -(x[0] or 0))
            overall_rank = next((i + 1 for i, (_, n) in enumerate(all_vals) if n == player_name), 999)

            rows.append((metric_name, val, team_rank, overall_rank, type_id))

        if rows:
            # 按 DIM_DISPLAY_METRICS 中定义的 type_id 顺序排序（两侧一致）
            dim_metric_order = {tid: i for i, tid in enumerate(metrics.keys())}
            rows.sort(key=lambda x: dim_metric_order.get(x[4], 999))
            dim_tables[dim_label] = rows

    return {
        "name": player_name,
        "number": number,
        "minutes": minutes,
        "photo_url": photo_url,
        "goals": goals,
        "assists": assists,
        "key_events": key_events,
        "team": "home" if any(p.name == player_name
                              for p in all_players if p.team_name == player_team and "home" in str(type(p)).lower())
                else "away",  # fallback
        "dim_scores": dim_scores,
        "dim_tables": dim_tables,
        "run_km": run_km,
        "carry_km": carry_km,
        "llm_summary": llm_summary,
        "heatmap_b64": heatmap_b64,
        "pass_chart_b64": pass_chart_b64,
        "dribble_chart_b64": dribble_chart_b64,
    }


# ═══════════════════════ v4 双图布局 ═══════════════════════


def plot_player_comparison_summary(
    match_title: str,
    home_name: str,
    away_name: str,
    player_a: dict,
    player_b: dict,
    output_path: str,
    llm_a: str = "",
    llm_b: str = "",
    comparison_summary: str = "",
    dpi: int = 150,
):
    """球员对比汇总图 — 标题→对比总结→卡片+雷达+LLM→Player Map。

    布局（v5）：
    ┌────────────────────────────────────────────┐
    │           match_title / 球员贡献对比         │
    ├────────────────────────────────────────────┤
    │        💬 对比总结 (gold bar)                │
    ├────────┬─────────────────┬─────────────────┤
    │ 卡片 A │  C1-C5 雷达      │  卡片 B          │
    │ LLM-A  │                 │  LLM-B           │
    ├────────┴─────────────────┴─────────────────┤
    │           — Player Map 对比 —               │
    │  ┌──────────────┐ ┌──────────────┐         │
    │  │   热图 A     │ │   热图 B     │         │
    │  └──────────────┘ └──────────────┘         │
    │  ┌──────────────┐ ┌──────────────┐         │
    │  │   传球 A     │ │   传球 B     │         │
    │  └──────────────┘ └──────────────┘         │
    │  ┌──────────────┐ ┌──────────────┐         │
    │  │   推进 A     │ │   推进 B     │         │
    │  └──────────────┘ └──────────────┘         │
    └────────────────────────────────────────────┘
    """
    margin = 0.15
    header_h = 0.55
    footer_h = 0.25

    # 面板宽度
    panel_w = 2.60
    radar_w = 3.20
    inner_gap = 0.10
    total_w = margin + panel_w + inner_gap + radar_w + inner_gap + panel_w + margin

    # ── 各区域高度 ──
    card_h = 1.85               # 球员基本信息卡片
    llm_h = 1.15                # 球员叙事
    gap_between = 0.08          # 卡片与LLM之间间距
    main_bottom_pad = 0.06      # 底部留白防止边框被切
    main_row_h = card_h + gap_between + llm_h + main_bottom_pad

    cmp_summary_h = 0.42        # 对比总结（标题下方）
    title_cmp_gap = 0.04        # 标题与对比总结间距
    cmp_main_gap = 0.10         # 对比总结与主行间距

    # 图表区 — 全区宽，每行缩小到合理尺寸
    chart_row_h = 1.70          # 每行图表高度
    chart_label_h = 0.28        # Player Map 标签
    charts_gap = 0.06           # 图表行间距
    main_charts_gap = 0.10      # 主行与Player Map间距（防止遮挡雷达）

    chart_types = [
        ("heatmap_b64", "热图"),
        ("pass_chart_b64", "传球"),
        ("dribble_chart_b64", "推进"),
    ]
    available_charts = [(k, lb) for k, lb in chart_types
                        if player_a.get(k) or player_b.get(k)]
    n_chart_rows = len(available_charts)
    charts_total_h = (chart_label_h + n_chart_rows * chart_row_h
                      + max(0, n_chart_rows - 1) * charts_gap) if n_chart_rows else 0

    total_h = (header_h + title_cmp_gap + cmp_summary_h + cmp_main_gap
               + main_row_h + main_charts_gap
               + charts_total_h + footer_h + margin * 2)

    fig = plt.figure(figsize=(total_w, total_h), dpi=dpi)
    fig.patch.set_facecolor(BG_COLOR)

    # ═══════════════════ 标题 ═══════════════════
    title_y0 = (footer_h + charts_total_h + main_charts_gap
                + main_row_h + cmp_main_gap
                + cmp_summary_h + title_cmp_gap + margin)
    title_ax = fig.add_axes([0, title_y0 / total_h, 1, header_h / total_h])
    title_ax.set_xlim(0, 1); title_ax.set_ylim(0, 1); title_ax.axis("off")
    title_ax.set_facecolor(BG_COLOR)
    title_ax.text(0.5, 0.75, match_title, transform=title_ax.transAxes,
                  fontsize=14, color=TEXT_COLOR, ha="center", va="center", fontweight="bold")
    title_ax.text(0.5, 0.25, "球员贡献对比", transform=title_ax.transAxes,
                  fontsize=11, color=MUTED_COLOR, ha="center", va="center")

    # ═══════════════════ 对比总结（标题下方，主行上方） ═══════════════════
    cmp_y0 = (footer_h + charts_total_h + main_charts_gap
              + main_row_h + cmp_main_gap + margin)
    cmp_ax = fig.add_axes([0, cmp_y0 / total_h, 1, cmp_summary_h / total_h])
    cmp_ax.set_xlim(0, total_w); cmp_ax.set_ylim(0, cmp_summary_h)
    cmp_ax.axis("off"); cmp_ax.set_facecolor(BG_COLOR)

    if comparison_summary:
        bar_x0 = margin
        bar_w = total_w - margin * 2
        rect = mpatches.FancyBboxPatch(
            (bar_x0 + 0.05, 0.06), bar_w - 0.10, cmp_summary_h - 0.12,
            boxstyle="round,pad=0.08", linewidth=0.8,
            edgecolor="#f1c40f", facecolor="#1e1e08", zorder=1, alpha=0.7)
        cmp_ax.add_patch(rect)
        cmp_ax.text(total_w / 2, cmp_summary_h / 2, comparison_summary,
                    fontsize=10.5, color="#f1c40f", ha="center", va="center",
                    fontweight="bold")
    else:
        cmp_ax.text(total_w / 2, cmp_summary_h / 2, "— 对比总结 —",
                    fontsize=8.5, color=MUTED_COLOR, ha="center", va="center", alpha=0.5)

    # ═══════════════════ 主行：卡片A + 雷达 + 卡片B ═══════════════════
    main_y0 = footer_h + charts_total_h + main_charts_gap + margin
    main_ax = fig.add_axes([0, main_y0 / total_h, 1, main_row_h / total_h])
    main_ax.set_xlim(0, total_w); main_ax.set_ylim(0, main_row_h)
    main_ax.axis("off"); main_ax.set_facecolor(BG_COLOR)

    left_x0 = margin
    _draw_player_info_card(main_ax, player_a, left_x0,
                           llm_h + gap_between + main_bottom_pad,
                           panel_w, card_h, HOME_COLOR)
    _draw_llm_narrative(main_ax, llm_a, left_x0, main_bottom_pad,
                        panel_w, llm_h, HOME_COLOR, "球员点评")

    right_x0 = margin + panel_w + inner_gap + radar_w + inner_gap
    _draw_player_info_card(main_ax, player_b, right_x0,
                           llm_h + gap_between + main_bottom_pad,
                           panel_w, card_h, AWAY_COLOR)
    _draw_llm_narrative(main_ax, llm_b, right_x0, main_bottom_pad,
                        panel_w, llm_h, AWAY_COLOR, "球员点评")

    # 雷达图 — 居中
    radar_cx = margin + panel_w + inner_gap + radar_w / 2
    radar_cy = main_row_h / 2
    radar_r = min(radar_w / 2.3, main_row_h / 2.6)
    _draw_radar(main_ax, player_a, player_b,
                center=(radar_cx, radar_cy), radius=radar_r,
                home_color=HOME_COLOR, away_color=AWAY_COLOR)

    # 雷达图例（底部居中）
    leg_y = radar_cy - radar_r - 0.35
    lx1 = radar_cx - 1.2
    lx2 = radar_cx + 0.3
    def _safe_name(n):
        try:
            dn = unicodedata.normalize('NFKD', n).encode('ascii', 'ignore').decode('ascii')
            return dn if dn.strip() else n
        except Exception:
            return n
    main_ax.plot([lx1, lx1 + 0.28], [leg_y, leg_y],
                 color=HOME_COLOR, linewidth=2, marker="o", markersize=4, zorder=4)
    main_ax.text(lx1 + 0.34, leg_y, _safe_name(player_a["name"]), fontsize=7,
                 color=HOME_COLOR, va="center", fontweight="bold")
    main_ax.plot([lx2, lx2 + 0.28], [leg_y, leg_y],
                 color=AWAY_COLOR, linewidth=2, linestyle="--", marker="s", markersize=4, zorder=4)
    main_ax.text(lx2 + 0.34, leg_y, _safe_name(player_b["name"]), fontsize=7,
                 color=AWAY_COLOR, va="center", fontweight="bold")

    # ═══════════════════ Player Map 对比 ═══════════════════
    if n_chart_rows > 0:
        charts_y0 = footer_h + margin
        charts_ax = fig.add_axes([0, charts_y0 / total_h, 1, charts_total_h / total_h])
        charts_ax.set_xlim(0, total_w); charts_ax.set_ylim(0, charts_total_h)
        charts_ax.axis("off"); charts_ax.set_facecolor(BG_COLOR)

        # 分区标签
        charts_ax.text(total_w / 2, charts_total_h - 0.06, "— Player Map 对比 —",
                       fontsize=8.5, color=MUTED_COLOR, ha="center", va="bottom", alpha=0.7)

        _draw_charts_fullwidth(fig, charts_ax, player_a, player_b,
                               available_charts, total_w, charts_total_h,
                               chart_label_h, chart_row_h, charts_gap,
                               HOME_COLOR, AWAY_COLOR)

    # ═══════════════════ 脚注 ═══════════════════
    footer_ax = fig.add_axes([0, 0, 1, footer_h / total_h])
    footer_ax.set_xlim(0, 1); footer_ax.set_ylim(0, 1); footer_ax.axis("off")
    footer_ax.set_facecolor(BG_COLOR)
    footer_ax.text(0.5, 0.50, "* C1-C5 贡献维度雷达图 | 详见下方详细数据对比图",
                   transform=footer_ax.transAxes, fontsize=7, color=MUTED_COLOR,
                   ha="center", va="center")

    # ── 保存 ──
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight", pad_inches=0.05,
                facecolor=BG_COLOR, edgecolor="none")
    plt.close(fig)


def plot_player_comparison_detail(
    match_title: str,
    player_a: dict,
    player_b: dict,
    output_path: str,
    dpi: int = 150,
):
    """球员详细数据对比图 — 双方 C1-C5 维度指标表格并排。

    布局：
    ┌───────────────────────────────────────────────┐
    │            match_title / 贡献维度详细对比      │
    ├──────────────────┬───────┬────────────────────┤
    │  ● Name A #10    │       │  ● Name B #7       │
    ├──────────────────┼───────┼────────────────────┤
    │  C1-C5 指标表 A  │       │  C1-C5 指标表 B    │
    ├──────────────────┴───────┴────────────────────┤
    │              队排/场排说明                     │
    └───────────────────────────────────────────────┘
    """
    margin = 0.18
    header_h = 0.55
    player_head_h = 0.55
    footer_h = 0.30

    panel_w = 3.20
    center_gap = 0.40
    total_w = margin + panel_w + center_gap + panel_w + margin

    # ── 维度表格高度 ──
    def _dim_table_h(player: dict) -> float:
        h = 0.0
        for dim in DIM_LABELS:
            rows = len(player.get("dim_tables", {}).get(dim, []))
            if rows:
                h += 0.20 + 0.17 + rows * 0.18 + 0.08
        return h + 0.10

    dim_h = max(_dim_table_h(player_a), _dim_table_h(player_b), 2.0)

    total_h = header_h + player_head_h + dim_h + footer_h + margin * 2

    fig = plt.figure(figsize=(total_w, total_h), dpi=dpi)
    fig.patch.set_facecolor(BG_COLOR)

    # ═══════════════════ 标题 ═══════════════════
    title_ax = fig.add_axes([0, (total_h - header_h - margin) / total_h, 1, header_h / total_h])
    title_ax.set_xlim(0, 1); title_ax.set_ylim(0, 1); title_ax.axis("off")
    title_ax.set_facecolor(BG_COLOR)
    title_ax.text(0.5, 0.75, match_title, transform=title_ax.transAxes,
                  fontsize=14, color=TEXT_COLOR, ha="center", va="center", fontweight="bold")
    title_ax.text(0.5, 0.25, "贡献维度详细对比", transform=title_ax.transAxes,
                  fontsize=11, color=MUTED_COLOR, ha="center", va="center")

    # ═══════════════════ 球员头部行 ═══════════════════
    head_y0 = footer_h + dim_h + margin
    head_ax = fig.add_axes([0, head_y0 / total_h, 1, player_head_h / total_h])
    head_ax.set_xlim(0, total_w); head_ax.set_ylim(0, player_head_h)
    head_ax.axis("off"); head_ax.set_facecolor(BG_COLOR)

    left_x0 = margin
    right_x0 = margin + panel_w + center_gap
    _draw_player_head(head_ax, player_a, left_x0, panel_w, player_head_h, HOME_COLOR)
    _draw_player_head(head_ax, player_b, right_x0, panel_w, player_head_h, AWAY_COLOR)

    # 中间分隔线
    divider_x = margin + panel_w + center_gap / 2
    head_ax.plot([divider_x, divider_x], [0.08, player_head_h - 0.08],
                 color=TABLE_BORDER, linewidth=0.5, alpha=0.4)

    # ═══════════════════ 维度表格 ═══════════════════
    dim_ax = fig.add_axes([0, (footer_h + margin) / total_h, 1, dim_h / total_h])
    dim_ax.set_xlim(0, total_w); dim_ax.set_ylim(0, dim_h)
    dim_ax.axis("off"); dim_ax.set_facecolor(BG_COLOR)

    _draw_dim_table_detail(dim_ax, player_a, left_x0, dim_h, panel_w, HOME_COLOR)
    _draw_dim_table_detail(dim_ax, player_b, right_x0, dim_h, panel_w, AWAY_COLOR)

    # 中间分隔线延续
    dim_ax.plot([divider_x, divider_x], [0.04, dim_h - 0.04],
                color=TABLE_BORDER, linewidth=0.5, alpha=0.4)

    # ═══════════════════ 脚注 ═══════════════════
    footer_ax = fig.add_axes([0, 0, 1, footer_h / total_h])
    footer_ax.set_xlim(0, 1); footer_ax.set_ylim(0, 1); footer_ax.axis("off")
    footer_ax.set_facecolor(BG_COLOR)
    footer_ax.text(0.5, 0.55, "* 队排 = 队内同位置排名 | 场排 = 全场外场球员排名",
                   transform=footer_ax.transAxes, fontsize=7.5, color=MUTED_COLOR,
                   ha="center", va="center")

    # ── 保存 ──
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight", pad_inches=0.05,
                facecolor=BG_COLOR, edgecolor="none")
    plt.close(fig)


# ═══════════════════════ 新辅助函数 ═══════════════════════


def _draw_player_info_card(ax, player: dict, x0: float, y_bot: float,
                           w: float, h: float, color: str):
    """绘制球员基本信息卡片：头像 + 姓名# + 出场 + 进球/助攻/跑动/推进。"""
    y_top = y_bot + h

    # 面板背景
    rect = mpatches.FancyBboxPatch((x0, y_bot + 0.04), w, h - 0.08,
                                    boxstyle="round,pad=0.08", linewidth=0.8,
                                    edgecolor=TABLE_BORDER, facecolor=CARD_BG, zorder=1)
    ax.add_patch(rect)

    inner_x = x0 + 0.10
    cy = y_top - 0.32

    # 头像
    photo_r = 0.28
    photo_cx = inner_x + photo_r
    photo_url = player.get("photo_url", "")
    photo_img = _fetch_image(photo_url) if photo_url else None
    if photo_img is not None:
        circle = _circle_image(photo_img)
        ax.imshow(circle, extent=[photo_cx - photo_r, photo_cx + photo_r,
                                   cy - photo_r, cy + photo_r], zorder=3)
    else:
        ax.add_patch(plt.Circle((photo_cx, cy), photo_r,
                                facecolor="#3a3a5c", edgecolor=color,
                                linewidth=1.5, zorder=3))

    # 姓名 + 号码
    name_x = photo_cx + photo_r + 0.12
    num = str(player.get("number", "") or "")
    display_name = player["name"]
    try:
        dn = unicodedata.normalize('NFKD', display_name).encode('ascii', 'ignore').decode('ascii')
        if dn.strip():
            display_name = dn
    except Exception:
        pass
    ax.text(name_x, cy + 0.08, f"{display_name}  #{num}",
            fontsize=10, color=TEXT_COLOR, va="center", fontweight="bold")

    # 出场时间
    mins = player.get("minutes", 0)
    ax.text(name_x, cy - 0.23, f"出场 {mins}'",
            fontsize=8.5, color=MUTED_COLOR, va="center")

    # 跑动/推进
    run_km = player.get("run_km")
    carry_km = player.get("carry_km")
    phys_parts = []
    if run_km is not None:
        phys_parts.append(f"跑动 {run_km:.1f} km")
    if carry_km is not None:
        phys_parts.append(f"推进 {carry_km:.2f} km")
    if phys_parts:
        ax.text(name_x, cy - 0.44, "  ".join(phys_parts),
                fontsize=8, color="#3fb950", va="center")

    # 进球 / 助攻 / 关键事件
    label_x = inner_x + 0.05
    cy2 = y_top - 1.15
    goals = player.get("goals", 0) or 0
    assists = player.get("assists", 0) or 0
    key_events = player.get("key_events", "") or "-"
    basic = [("进球", str(goals)), ("助攻", str(assists)), ("关键事件", key_events)]
    for lbl, val in basic:
        ax.text(label_x, cy2, lbl, fontsize=8.5, color=MUTED_COLOR, va="center")
        ax.text(label_x + 1.80, cy2, val, fontsize=8.5, color=TEXT_COLOR, va="center",
                fontweight="bold")
        cy2 -= 0.20


def _draw_llm_narrative(ax, text: str, x0: float, y_bot: float,
                        w: float, h: float, color: str, title: str):
    """在卡片下方绘制 LLM 叙事文字，左对齐。"""
    if not text:
        return

    # 背景
    rect = mpatches.FancyBboxPatch((x0, y_bot + 0.04), w, h - 0.08,
                                    boxstyle="round,pad=0.06", linewidth=0.5,
                                    edgecolor=color, facecolor=CARD_BG, zorder=1, alpha=0.5)
    ax.add_patch(rect)

    # 标题 — 居中
    ax.text(x0 + w / 2, y_bot + h - 0.16, title,
            fontsize=8.5, color=color, ha="center", va="center", fontweight="bold")

    # 正文 — 左对齐
    wrapped = textwrap.fill(text, width=18)
    lines = wrapped.split("\n")
    line_h = 0.17
    text_x = x0 + 0.10
    text_y = y_bot + h - 0.38
    max_lines = 6
    for li in lines[:max_lines]:
        ax.text(text_x, text_y, li, fontsize=7,
                color=MUTED_COLOR, ha="left", va="center")
        text_y -= line_h


def _draw_player_head(ax, player: dict, x0: float, w: float, h: float, color: str):
    """绘制详细对比图顶部的球员头部（小头像+姓名+号码）。"""
    center_x = x0 + w / 2
    cy = h / 2

    # 小头像
    photo_r = 0.18
    photo_cx = x0 + photo_r + 0.08
    photo_url = player.get("photo_url", "")
    photo_img = _fetch_image(photo_url) if photo_url else None
    if photo_img is not None:
        circle = _circle_image(photo_img, size=128)
        ax.imshow(circle, extent=[photo_cx - photo_r, photo_cx + photo_r,
                                   cy - photo_r, cy + photo_r], zorder=3)
    else:
        ax.add_patch(plt.Circle((photo_cx, cy), photo_r,
                                facecolor="#3a3a5c", edgecolor=color,
                                linewidth=1.5, zorder=3))

    # 姓名 + 号码
    name_x = photo_cx + photo_r + 0.10
    num = str(player.get("number", "") or "")
    display_name = player["name"]
    try:
        dn = unicodedata.normalize('NFKD', display_name).encode('ascii', 'ignore').decode('ascii')
        if dn.strip():
            display_name = dn
    except Exception:
        pass
    ax.text(name_x, cy, f"{display_name}  #{num}",
            fontsize=9.5, color=TEXT_COLOR, va="center", fontweight="bold")


def _draw_dim_table_detail(ax, player: dict, x0: float, y_top: float, w: float, color: str):
    """绘制详细对比中的 C1-C5 维度指标表格（仅显示队排前 3 的关键指标）。"""
    # 背景
    rect = mpatches.FancyBboxPatch((x0, 0.04), w, y_top - 0.08,
                                    boxstyle="round,pad=0.10", linewidth=0.8,
                                    edgecolor=TABLE_BORDER, facecolor=CARD_BG, zorder=1)
    ax.add_patch(rect)

    inner_x = x0 + 0.12
    cy = y_top - 0.22

    dim_tables = player.get("dim_tables", {})
    for dim_label in DIM_LABELS:
        subtitle = DIM_SUBTITLES.get(dim_label, "")
        rows = dim_tables.get(dim_label, [])
        if not rows:
            continue

        # 维度标题
        ax.text(inner_x, cy, dim_label, fontsize=8.5, color=color, va="center", fontweight="bold")
        ax.text(inner_x + 0.40, cy, subtitle, fontsize=6.5, color=MUTED_COLOR, va="center")
        cy -= 0.20

        # 表头
        hd_val = inner_x + 1.85
        hd_team = inner_x + 2.35
        hd_field = inner_x + 2.70
        for pos, txt in [(inner_x, "指标"), (hd_val, "值"), (hd_team, "队排"), (hd_field, "场排")]:
            ax.text(pos, cy, txt, fontsize=6.5, color=MUTED_COLOR, va="center")
        cy -= 0.17

        for metric_name, value, team_rank, overall_rank, *_ in rows:
            ax.text(inner_x, cy, metric_name, fontsize=7, color=TEXT_COLOR, va="center")
            ax.text(hd_val, cy, _fmt_val(value), fontsize=7, color=TEXT_COLOR, va="center")
            ax.text(hd_team, cy, str(team_rank), fontsize=7, color=_rank_color(team_rank),
                    va="center", fontweight="bold")
            ax.text(hd_field, cy, str(overall_rank), fontsize=7, color=_rank_color(overall_rank),
                    va="center", fontweight="bold")
            cy -= 0.18

        sep_y = cy + 0.06
        ax.plot([inner_x, inner_x + w - 0.24], [sep_y, sep_y],
                color=TABLE_BORDER, linewidth=0.5, alpha=0.4, zorder=1)
        cy -= 0.08


def _draw_charts_fullwidth(fig, ax, player_a: dict, player_b: dict,
                           available_charts: list, total_w: float,
                           charts_total_h: float, label_h: float,
                           row_h: float, gap: float,
                           home_color: str, away_color: str):
    """全区宽图表 — A 左半区 / B 右半区，以页面中线为界各占一半。"""
    margin = 0.15
    mid = total_w / 2
    half_gap = 0.08

    half_w = (total_w - margin * 2 - half_gap * 2) / 2

    # 显示名
    def _dname(p):
        n = p.get("name", "?")
        try:
            dn = unicodedata.normalize('NFKD', n).encode('ascii', 'ignore').decode('ascii')
            return dn if dn.strip() else n
        except Exception:
            return n
    name_a = _dname(player_a)
    name_b = _dname(player_b)

    y_top = charts_total_h - label_h
    for ri, (key, label) in enumerate(available_charts):
        has_a = player_a.get(key)
        has_b = player_b.get(key)

        y_bot = y_top - label_h - (ri + 1) * row_h - ri * gap
        avail_h = row_h - 0.16

        # Player A — 左半区
        left_cx = margin + half_w / 2
        _draw_chart_card_v2(fig, ax, has_a,
                            margin + 0.06, y_bot + 0.08,
                            half_w - 0.12, avail_h, home_color)
        ax.text(left_cx, y_bot + row_h - 0.04,
                f"{name_a} {label}", fontsize=7.5, color=HOME_COLOR,
                ha="center", va="bottom", fontweight="bold")

        # Player B — 右半区
        right_cx = mid + half_gap + half_w / 2
        _draw_chart_card_v2(fig, ax, has_b,
                            mid + half_gap + 0.06, y_bot + 0.08,
                            half_w - 0.12, avail_h, away_color)
        ax.text(right_cx, y_bot + row_h - 0.04,
                f"{name_b} {label}", fontsize=7.5, color=AWAY_COLOR,
                ha="center", va="bottom", fontweight="bold")


def _draw_charts_grid_v2(fig, ax, player_a: dict, player_b: dict,
                         panel_w: float, inner_gap: float, radar_w: float,
                         margin: float, total_w: float, charts_h: float,
                         home_color: str, away_color: str):
    """3 组×2 列横排图表，保持原始宽高比。

    charts_h = 2.00 — 每行图表约 1.65" 高（减去标签占位）。
    """
    chart_types = [
        ("heatmap_b64", "热图"),
        ("pass_chart_b64", "传球"),
        ("dribble_chart_b64", "推进"),
    ]

    available = []
    for key, label in chart_types:
        has_a = player_a.get(key)
        has_b = player_b.get(key)
        if has_a or has_b:
            available.append((key, label, has_a, has_b))

    if not available:
        return

    n_cols = len(available)
    y_bot = 0.06
    label_top = 0.22
    y_top = charts_h - label_top
    avail_h = y_top - y_bot

    # 左右面板区域
    left_start = margin
    left_end = margin + panel_w
    right_start = margin + panel_w + inner_gap + radar_w + inner_gap
    right_end = right_start + panel_w

    # 每个格子宽度
    col_w = (panel_w - 0.20) / n_cols
    # 图片最大尺寸：保持约 1.4:1 或原始比例，不超过格子
    img_max_w = col_w - 0.12
    img_max_h = avail_h - 0.10

    for ci, (key, label, has_a, has_b) in enumerate(available):
        # Player A — 左侧格子
        col_x_a = left_start + 0.10 + ci * col_w
        _draw_chart_card_v2(fig, ax, has_a, col_x_a, y_bot,
                            col_w - 0.12, img_max_h, home_color)

        ax.text(col_x_a + (col_w - 0.12) / 2, y_top + 0.05,
                f"{label} A", fontsize=7, color=HOME_COLOR,
                ha="center", va="bottom", fontweight="bold")

        # Player B — 右侧对应格子
        col_x_b = right_start + 0.10 + ci * col_w
        _draw_chart_card_v2(fig, ax, has_b, col_x_b, y_bot,
                            col_w - 0.12, img_max_h, away_color)

        ax.text(col_x_b + (col_w - 0.12) / 2, y_top + 0.05,
                f"{label} B", fontsize=7, color=AWAY_COLOR,
                ha="center", va="bottom", fontweight="bold")


def _draw_chart_card_v2(fig, ax, b64_data, x: float, y: float,
                        w: float, h: float, color: str):
    """Draw a single chart card — 保持图像原始宽高比居中。"""
    # 卡片背景
    card = mpatches.FancyBboxPatch((x, y), w, h,
                                    boxstyle="round,pad=0.05", linewidth=0.8,
                                    edgecolor=color, facecolor=CARD_BG,
                                    alpha=0.5, zorder=2)
    ax.add_patch(card)

    if b64_data:
        try:
            header, encoded = b64_data.split(",", 1)
            img_bytes = base64.b64decode(encoded)
            import matplotlib.image as mpimg
            from io import BytesIO
            img_arr = mpimg.imread(BytesIO(img_bytes))
            ih, iw = img_arr.shape[:2]
            if ih > 0 and iw > 0:
                aspect = iw / ih
                pad = 0.04
                avail_w = w - pad * 2
                avail_h = h - pad * 2
                if avail_w / avail_h > aspect:
                    # 高度受限
                    draw_h = avail_h
                    draw_w = draw_h * aspect
                else:
                    # 宽度受限
                    draw_w = avail_w
                    draw_h = draw_w / aspect
                draw_cx = x + w / 2
                draw_cy = y + h / 2
                ax.imshow(img_arr,
                          extent=[draw_cx - draw_w / 2, draw_cx + draw_w / 2,
                                  draw_cy - draw_h / 2, draw_cy + draw_h / 2],
                          zorder=3, interpolation='bilinear')
        except Exception:
            ax.text(x + w / 2, y + h / 2, "加载失败", fontsize=7,
                    color=MUTED_COLOR, ha="center", va="center", alpha=0.7)
    else:
        ax.text(x + w / 2, y + h / 2, "暂无数据", fontsize=7,
                color=MUTED_COLOR, ha="center", va="center", alpha=0.7)


def _compute_zscore_weighted(players: list, metric_defs: dict) -> list[float]:
    n = len(players)
    if n < 2:
        return [0.0] * n
    weights = []
    z_lists = []
    for type_id, (_, w) in metric_defs.items():
        vals = [float(p.sv(type_id) or 0) for p in players]
        mean = np.mean(vals)
        std = np.std(vals)
        if std < 1e-8:
            z_lists.append([0.0] * n)
        else:
            z_lists.append([(v - mean) / std for v in vals])
        weights.append(w)
    combined = [0.0] * n
    for i in range(n):
        combined[i] = sum(z_lists[j][i] * weights[j] for j in range(len(weights)))
    return combined
