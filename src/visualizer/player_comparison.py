"""
球员贡献对比图 — matplotlib 暗色主题，左右对称 + 中央雷达图。

布局：
┌─────────────────────────────────────┐
│           比赛标题                   │
├─────────┬──────────┬───────────────┤
│ 球员A   │   C1-C5  │   球员B       │
│ 头像    │  五维雷达 │   头像        │
│ 姓名#   │          │   姓名#       │
│ 时长    │          │   时长        │
│ 基本指标│          │   基本指标     │
│ C1 分组 │          │   C2 分组     │
│ ...     │          │   ...         │
├─────────┴──────────┴───────────────┤
│         说明脚注                     │
└─────────────────────────────────────┘

2026-06-10 v2: 全部指标、紧凑列、副标题、修复越界
"""
from __future__ import annotations

import math
import os
import io
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
    dpi: int = 150,
):
    # ── 预计算两侧面板高度 ──
    def _panel_h(player: dict) -> float:
        h = 0.0
        h += 1.25                                 # 头像 + 姓名 + 时长
        h += 0.08 + 3 * 0.20                       # "基本指标" 标题 + 3行
        h += 0.10                                  # gap
        for dim in DIM_LABELS:
            h += 0.22                              # 维度标题行
            h += 0.18                              # 表头
            rows = len(player.get("dim_tables", {}).get(dim, []))
            h += rows * 0.20
            h += 0.10                              # gap
        h += 0.20                                  # bottom pad
        return h

    panel_h = max(_panel_h(player_a), _panel_h(player_b), 6.0)

    # ── 全局尺寸 ──
    margin = 0.40
    left_w = 3.60        # 左侧面板宽度
    right_w = 3.60       # 右侧面板宽度
    header_h = 0.65      # 标题栏高度
    footer_h = 0.35
    gap_lr = 0.30        # 面板与雷达图间距
    total_w = margin + left_w + gap_lr + 4.5 + gap_lr + right_w + margin
    total_h = header_h + panel_h + footer_h + margin * 2

    fig = plt.figure(figsize=(total_w, total_h), dpi=dpi)
    fig.patch.set_facecolor(BG_COLOR)

    # ══════════════════════════ 标题（含队徽） ══════════════════════════
    title_ax = fig.add_axes([0, (total_h - header_h - margin) / total_h, 1, header_h / total_h])
    title_ax.set_xlim(0, 1)
    title_ax.set_ylim(0, 1)
    title_ax.axis("off")
    title_ax.set_facecolor(BG_COLOR)

    title_ax.text(0.5, 0.78, match_title, transform=title_ax.transAxes,
                  fontsize=14, color=TEXT_COLOR, ha="center", va="center", fontweight="bold")
    title_ax.text(0.5, 0.32, "球员贡献对比", transform=title_ax.transAxes,
                  fontsize=11, color=MUTED_COLOR, ha="center", va="center")

    # ══════════════════════════ 底部脚注 ══════════════════════════
    footer_ax = fig.add_axes([0, 0, 1, footer_h / total_h])
    footer_ax.set_xlim(0, 1)
    footer_ax.set_ylim(0, 1)
    footer_ax.axis("off")
    footer_ax.set_facecolor(BG_COLOR)
    footer_ax.text(0.5, 0.55, "* 分组按 C1-C5 贡献检测维度；队排=队内排名，场排=全场外场球员排名",
                   transform=footer_ax.transAxes, fontsize=7.5, color=MUTED_COLOR,
                   ha="center", va="center")

    # ══════════════════════════ 主绘图区 ══════════════════════════
    # 使用 figure-level 坐标（英寸），直接用 add_axes
    x_data = margin
    y_data = footer_h
    w_data = total_w - 2 * margin
    h_data = panel_h

    main_ax = fig.add_axes([x_data / total_w, y_data / total_h,
                            w_data / total_w, h_data / total_h])
    main_ax.set_xlim(0, w_data)
    main_ax.set_ylim(0, panel_h)
    main_ax.axis("off")
    main_ax.set_facecolor(BG_COLOR)

    # ── 两侧面板 x 范围 ──
    left_x0 = 0.0
    right_x0 = w_data - right_w

    _draw_player_panel(main_ax, player_a, left_x0, 0, left_w, panel_h)
    _draw_player_panel(main_ax, player_b, right_x0, 0, right_w, panel_h)

    # ── 雷达图区域（面板之间，上移与球员基本信息对齐） ──
    radar_x0 = left_w + gap_lr
    radar_x1 = right_x0 - gap_lr
    radar_cx = (radar_x0 + radar_x1) / 2
    # 基本信息区从 panel_h 往下约 2.0 英寸 → 雷达圆心放在 panel_h - 1.0
    radar_cy = panel_h - 1.0
    radar_r = min((radar_x1 - radar_x0) / 2.2, 1.0)

    _draw_radar(main_ax, player_a, player_b,
                center=(radar_cx, radar_cy), radius=radar_r,
                home_color=HOME_COLOR, away_color=AWAY_COLOR)

    # ── 雷达图图例（雷达下方，不重叠） ──
    legend_y = radar_cy - radar_r * 1.35
    lx1 = radar_cx - 1.5
    lx2 = radar_cx + 0.3
    main_ax.plot([lx1, lx1 + 0.40], [legend_y, legend_y],
                 color=HOME_COLOR, linewidth=2, marker="o", markersize=5, zorder=4)
    main_ax.text(lx1 + 0.48, legend_y, player_a["name"], fontsize=8, color=HOME_COLOR,
                 va="center", fontweight="bold")
    main_ax.plot([lx2, lx2 + 0.40], [legend_y, legend_y],
                 color=AWAY_COLOR, linewidth=2, linestyle="--", marker="s", markersize=5, zorder=4)
    main_ax.text(lx2 + 0.48, legend_y, player_b["name"], fontsize=8, color=AWAY_COLOR,
                 va="center", fontweight="bold")

    # ── 保存 ──
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight",
                facecolor=BG_COLOR, edgecolor="none")
    plt.close(fig)


def _draw_player_panel(ax, player: dict, x0: float, y_bot: float,
                       panel_w: float, panel_h: float):
    """绘制单个球员面板。坐标系: ax 内部 (0,0) 为面板左上角起点。"""
    y_top = panel_h
    color = HOME_COLOR if player["team"] == "home" else AWAY_COLOR

    # ── 面板背景 ──
    rect = mpatches.FancyBboxPatch((x0 + 0.08, y_bot + 0.08),
                                    panel_w - 0.16, y_top - y_bot - 0.16,
                                    boxstyle="round,pad=0.12", linewidth=1.0,
                                    edgecolor=TABLE_BORDER, facecolor=CARD_BG, zorder=1)
    ax.add_patch(rect)

    inner_x = x0 + 0.28
    inner_w = panel_w - 0.56
    cy = y_top - 0.40

    # ── 头像 ──
    photo_r = 0.30
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
    name_x = photo_cx + photo_r + 0.15
    num = str(player.get("number", "") or "")
    display_name = player["name"]
    ax.text(name_x, cy + 0.08, f"{display_name}  #{num}",
            fontsize=10, color=TEXT_COLOR, va="center", fontweight="bold")

    # ── 出场时间 ──
    mins = player.get("minutes", 0)
    ax.text(name_x, cy - 0.26, f"出场 {mins}'",
            fontsize=8.5, color=MUTED_COLOR, va="center")

    # ── 跑动/推进距离（有数据时展示） ──
    run_km = player.get("run_km")
    carry_km = player.get("carry_km")
    phys_texts = []
    if run_km is not None:
        phys_texts.append(f"跑动 {run_km:.1f} km")
    if carry_km is not None:
        phys_texts.append(f"推进 {carry_km:.2f} km")
    if phys_texts:
        ax.text(name_x, cy - 0.49, "  ".join(phys_texts),
                fontsize=8, color="#3fb950", va="center")

    cy -= 0.72

    # ── 基本指标（3行） ──
    label_x = inner_x + 0.05
    val_x = inner_x + 1.90
    ax.text(label_x, cy, "基本指标", fontsize=8.5, color=MUTED_COLOR, va="center",
            fontweight="bold")
    cy -= 0.22

    goals = player.get("goals", 0) or 0
    assists = player.get("assists", 0) or 0
    key_events = player.get("key_events", "") or "-"
    basic = [("进球", str(goals)), ("助攻", str(assists)), ("关键事件", key_events)]
    for lbl, val in basic:
        ax.text(label_x, cy, lbl, fontsize=8.5, color=MUTED_COLOR, va="center")
        ax.text(val_x, cy, val, fontsize=8.5, color=TEXT_COLOR, va="center",
                fontweight="bold")
        cy -= 0.20

    cy -= 0.12

    # ── 维度分组表格 ──
    dim_tables = player.get("dim_tables", {})
    for dim_label in DIM_LABELS:
        subtitle = DIM_SUBTITLES.get(dim_label, "")
        rows = dim_tables.get(dim_label, [])

        # 维度标题行（带副标题）
        ax.text(label_x, cy, dim_label, fontsize=9.5, color=color,
                va="center", fontweight="bold")
        ax.text(label_x + 0.50, cy, subtitle, fontsize=7.5, color=MUTED_COLOR,
                va="center")
        cy -= 0.24

        # 表头
        hd_metric = label_x
        hd_val = inner_x + 1.60
        hd_team = inner_x + 2.25
        hd_field = inner_x + 2.75
        for pos, txt in [(hd_metric, "指标"), (hd_val, "值"), (hd_team, "队排"), (hd_field, "场排")]:
            ax.text(pos, cy, txt, fontsize=7.5, color=MUTED_COLOR, va="center")
        cy -= 0.19

        for metric_name, value, team_rank, overall_rank, *_ in rows:
            ax.text(hd_metric, cy, metric_name, fontsize=8, color=TEXT_COLOR, va="center")
            ax.text(hd_val, cy, _fmt_val(value), fontsize=8, color=TEXT_COLOR, va="center")
            ax.text(hd_team, cy, str(team_rank), fontsize=8, color=_rank_color(team_rank),
                    va="center", fontweight="bold")
            ax.text(hd_field, cy, str(overall_rank), fontsize=8, color=_rank_color(overall_rank),
                    va="center", fontweight="bold")
            cy -= 0.20

        # 分割线 — 使用数据坐标（ax 的 y 轴）
        sep_y = cy + 0.08
        ax.plot([inner_x, inner_x + inner_w], [sep_y, sep_y],
                color=TABLE_BORDER, linewidth=0.6, alpha=0.5, zorder=1)
        cy -= 0.10


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
    }


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
