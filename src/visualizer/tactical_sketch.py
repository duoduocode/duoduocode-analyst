"""
战术速写图生成模块 (v5 — 多色球员 + 头像 + 球衣号)

从球员空间行为数据提取结构化信息，在真实球场背景上标注：
  - 每个球员独立颜色，多热区以同色虚线圆标注
  - 球员头像 + 球衣号码
  - 进攻偏重区域高亮

纯 matplotlib 实现，不依赖 mplsoccer。
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Arc
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
import numpy as np

from src.utils.player_names import to_chinese as _cn

# ── 配色 ──
BG = "#0d1824"
PITCH_GREEN = "#1a3a2a"
PITCH_LINE = "#3a5a4a"
TEXT = "#d8dce6"
MUTED = "#6b7a90"
GOLD = "#f1c40f"
HOME_ZONE = "#55efc4"
AWAY_ZONE = "#74b9ff"

# 8 人配色方案
_PLAYER_COLORS = [
    "#55efc4",  # mint
    "#74b9ff",  # sky
    "#f1c40f",  # gold
    "#e74c3c",  # red
    "#a29bfe",  # lavender
    "#fd79a8",  # pink
    "#fdcb6e",  # peach
    "#00b894",  # green
]

_UNICODE_FIX = {
    "\u00d8": "O", "\u00f8": "o", "\u00ef": "i", "\u00ed": "i",
    "\u00e9": "e", "\u00e8": "e", "\u00f3": "o", "\u00fc": "u",
    "\u00f6": "o", "\u00e5": "a", "\u00c5": "A",
}

_PHOTO_CACHE_DIR = Path("output/cache/player_photos")
_PHOTO_SIZE = 28  # photo size in data coords (pitch units)

# ── 18 区 → 球场坐标映射 ──
_ZONE_COORDS = {
    1: (10, 12),  2: (10, 40),  3: (10, 68),
    4: (28, 12),  5: (28, 40),  6: (28, 68),
    7: (48, 12),  8: (48, 40),  9: (48, 68),
    10: (68, 12), 11: (68, 40), 12: (68, 68),
    13: (88, 12), 14: (88, 40), 15: (88, 68),
    16: (108, 12), 17: (108, 40), 18: (108, 68),
}


def _load_player_meta(match_id: int) -> dict[str, dict]:
    """从 v6 数据加载球员元信息 (player_id, number)。"""
    root = Path(__file__).parent.parent.parent
    v6_path = root / "data" / "computed" / f"{match_id}_players_v6.json"
    if not v6_path.exists():
        return {}
    with open(v6_path, encoding="utf-8") as f:
        v6 = json.load(f)
    return {p["name"]: {"player_id": p.get("player_id"), "number": p.get("number")} for p in v6}


def _get_headshot(player_id: int | None) -> np.ndarray | None:
    """加载球员头像为 numpy 数组。优先本地缓存，否则从 Sportmonks CDN 下载。"""
    if not player_id:
        return None
    _PHOTO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = _PHOTO_CACHE_DIR / f"{player_id}.png"
    if cache_path.exists():
        try:
            return plt.imread(str(cache_path))
        except Exception:
            pass  # 损坏文件，重新下载

    # 尝试从 CDN 下载
    import urllib.request
    url = f"https://cdn.sportmonks.com/images/soccer/players/{player_id % 32}/{player_id}.png"
    try:
        urllib.request.urlretrieve(url, str(cache_path))
        if cache_path.exists():
            return plt.imread(str(cache_path))
    except Exception:
        pass
    return None


def _zone_to_coords(zone: int, idx: int, same_zone_count: int) -> tuple[float, float]:
    x, y = _ZONE_COORDS.get(zone, (60, 40))
    if same_zone_count > 1:
        offsets = [0, 6, -6, 10, -10, 14, -14, 3, -3]
        y += offsets[idx % len(offsets)]
    return x, y


def _safe_name(name: str) -> str:
    result = name
    for k, v in _UNICODE_FIX.items():
        result = result.replace(k, v)
    return unicodedata.normalize("NFKD", result).encode("ascii", "ignore").decode("ascii")


def _parse_side(side: str) -> str:
    if "左路" in side:
        return "left"
    if "右路" in side:
        return "right"
    return "center"


def _pitch_x(pos: str, side: str, idx: int, n: int, home: bool) -> float:
    spreads = [0.0, -10, 10, -18, 18, -25, 25, -30, 30]
    jitter = spreads[idx] if idx < len(spreads) else 0
    if home:
        base = {"G": 8, "D": 25, "M": 55, "F": 85}.get(pos, 55)
    else:
        base = {"G": 112, "D": 95, "M": 65, "F": 35}.get(pos, 65)
    return base + jitter * 0.3


def _pitch_y(side: str, idx: int, n: int) -> float:
    if side == "left":
        return 60 - idx * 7
    elif side == "right":
        return 16 + idx * 7
    else:
        center = 38
        offsets = [0, -9, 9, -17, 17, -24, 24, -30]
        return center + (offsets[idx] if idx < len(offsets) else 0)


def _compute_side_distribution(players: list[dict]) -> dict:
    dist = {"left": 0.0, "center": 0.0, "right": 0.0}
    for p in players:
        hot = p.get("hot_zones", [])
        if not hot:
            primary = p.get("primary_zone")
            if primary and 1 <= primary <= 18:
                hot = [primary]
            else:
                s = _parse_side(p.get("side", ""))
                dist[s] += 1
                continue
        l = c = r = 0
        for z in hot:
            if 1 <= z <= 6:
                l += 1
            elif 7 <= z <= 12:
                c += 1
            elif 13 <= z <= 18:
                r += 1
        total_zones = max(l + c + r, 1)
        dist["left"] += l / total_zones
        dist["center"] += c / total_zones
        dist["right"] += r / total_zones
    return dist


def _group_by_zone(players: list[dict], is_home_team: bool) -> list[dict]:
    from collections import defaultdict
    zone_groups = defaultdict(list)
    no_zone = []

    for i, p in enumerate(players):
        raw_zone = p.get("primary_zone")
        if raw_zone and 1 <= raw_zone <= 18:
            if not is_home_team:
                zone = 19 - raw_zone
                p["primary_zone"] = zone
                raw_hot = p.get("hot_zones", [])
                if raw_hot:
                    p["hot_zones"] = [19 - z for z in raw_hot if 1 <= z <= 18]
            else:
                zone = raw_zone
            zone_groups[zone].append((i, p))
        else:
            no_zone.append((i, p))

    result = []
    for zone, group in zone_groups.items():
        n = len(group)
        for zi, (orig_idx, p) in enumerate(group):
            x, y = _zone_to_coords(zone, zi, n)
            p["x"] = x
            p["y"] = y
            p["zone_label"] = f"{zone}区"
            result.append(p)

    for fi, (orig_idx, p) in enumerate(no_zone):
        pos = p.get("pos", "?")
        side = _parse_side(p.get("side", ""))
        p["x"] = _pitch_x(pos, side, fi, len(no_zone) or 1, home=True)
        p["y"] = _pitch_y(side, fi, len(no_zone) or 1)
        p["zone_label"] = ""
        result.append(p)

    return result


def _parse_carry_distance(carry_text: str) -> float:
    if not carry_text:
        return 0
    m = re.search(r"Total carrying distance:\s*([\d.]+)", carry_text)
    return float(m.group(1)) if m else 0


def _short_summary(output_text: str, max_len: int = 40) -> str:
    if not output_text:
        return ""
    lines = output_text.replace("。", "。\n").split("\n")
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("*"):
            continue
        if len(line) > 10 and ("侧" in line or "路" in line or "禁区" in line or "中场" in line or "活动" in line):
            clean = line[:max_len]
            return clean + ".." if len(line) > max_len else clean
    for line in lines:
        line = line.strip()
        if len(line) > 15:
            return line[:max_len] + ".."
    return ""


def plot_tactical_sketch(
    home_name: str,
    away_name: str,
    home_players: list[dict],
    away_players: list[dict],
    output_dir: str,
    dpi: int = 180,
    match_score: str = "",
    match_id: int = 0,
):
    import os as _os
    _os.makedirs(output_dir, exist_ok=True)

    player_meta = _load_player_meta(match_id) if match_id else {}

    for is_home, team_name, players, base_color in [
        (True, home_name, home_players, HOME_ZONE),
        (False, away_name, away_players, AWAY_ZONE),
    ]:
        sorted_players = sorted(players, key=lambda p: -p.get("zscore", 0))[:8]
        out_path = _os.path.join(output_dir, f"{team_name}_sketch.png")
        _plot_single_team(team_name, sorted_players, base_color, out_path,
                          dpi=dpi, match_score=match_score, is_home_team=is_home,
                          player_meta=player_meta)


def _plot_single_team(
    team_name: str,
    players: list[dict],
    team_color: str,
    output_path: str,
    dpi: int = 180,
    match_score: str = "",
    is_home_team: bool = True,
    player_meta: dict | None = None,
):
    if player_meta is None:
        player_meta = {}

    fig, ax = plt.subplots(figsize=(18, 11), dpi=dpi)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(PITCH_GREEN)
    ax.set_xlim(-8, 128)
    ax.set_ylim(-8, 88)
    ax.set_aspect("equal")
    ax.axis("off")

    _draw_pitch(ax)

    zoned = _group_by_zone(players, is_home_team=is_home_team)

    dist = _compute_side_distribution(players)
    _draw_single_team_attack_zones(ax, dist, team_color)

    # ── zone 偏移追踪：同一 zone 内多个标记错开不重叠 ──
    zone_offset: dict[int, int] = {}
    for i, p in enumerate(zoned):
        player_color = _PLAYER_COLORS[i % len(_PLAYER_COLORS)]
        _draw_player_marker(ax, p, player_color, player_meta, zone_offset)

    title = f"战术速写：{team_name}"
    if match_score:
        title += f"  ({match_score})"
    ax.text(60, 85, title, fontsize=21, color=GOLD, ha="center", fontweight="bold")
    ax.text(60, 78, "→ 进攻方向 →", fontsize=10, color=MUTED, ha="center")

    legend_y = -5
    ax.text(5, legend_y, "○ 球员大小 = 贡献分(zscore) | 彩色小圆 = 其他热区 | 同色=同一球员",
            fontsize=8.5, color=MUTED)
    ax.text(5, legend_y - 2.5, f"数据来源: Sofascore 热力图 × 视觉AI解析 (18区网格体系) | 照片: Sportmonks",
            fontsize=8.5, color=MUTED)

    def _display_name(n):
        cn = _cn(n)
        return cn if cn != n else _safe_name(n)
    names = "、".join(_display_name(p["name"]) for p in players[:4])
    summary_y = legend_y - 5.5
    ax.text(60, summary_y, f"{team_name} 核心球员: {names}",
            fontsize=9.5, color=TEXT, ha="center", fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="#0f1923", edgecolor="#1e2d45", alpha=0.8))

    fig.savefig(output_path, dpi=dpi, bbox_inches="tight",
                pad_inches=0.2, facecolor=BG, edgecolor="none")
    plt.close(fig)


def _draw_pitch(ax):
    LINE = PITCH_LINE
    LW = 1.6
    ax.plot([0, 120], [0, 0], color=LINE, lw=LW)
    ax.plot([0, 120], [80, 80], color=LINE, lw=LW)
    ax.plot([0, 0], [0, 80], color=LINE, lw=LW)
    ax.plot([120, 120], [0, 80], color=LINE, lw=LW)
    ax.plot([60, 60], [0, 80], color=LINE, lw=LW, ls="--")
    ax.add_patch(plt.matplotlib.patches.Circle((60, 40), 9.15, fill=False,
                edgecolor=LINE, lw=1.2))
    ax.plot(60, 40, "o", color=LINE, markersize=4)
    for x_base in [0, 120]:
        dx = 1 if x_base == 0 else -1
        ax.plot([x_base, x_base + 18 * dx], [18, 18], color=LINE, lw=LW)
        ax.plot([x_base, x_base + 18 * dx], [62, 62], color=LINE, lw=LW)
        ax.plot([x_base + 18 * dx, x_base + 18 * dx], [18, 62], color=LINE, lw=LW)
        ax.plot([x_base, x_base + 6 * dx], [30, 30], color=LINE, lw=1)
        ax.plot([x_base, x_base + 6 * dx], [50, 50], color=LINE, lw=1)
        ax.plot([x_base + 6 * dx, x_base + 6 * dx], [30, 50], color=LINE, lw=1)
        ax.plot(x_base + 12 * dx, 40, "o", color=LINE, markersize=3)
        arc_center_x = x_base + 12 * dx
        arc_center_y = 40
        if dx == 1:
            arc = Arc((arc_center_x, arc_center_y), 18.3, 18.3, angle=0,
                      theta1=-49, theta2=49, color=LINE, lw=1)
        else:
            arc = Arc((arc_center_x, arc_center_y), 18.3, 18.3, angle=0,
                      theta1=131, theta2=229, color=LINE, lw=1)
        ax.add_patch(arc)
    for x in [40, 80]:
        ax.plot([x, x], [0, 80], color=LINE, lw=0.8, ls=":", alpha=0.5)


def _draw_single_team_attack_zones(ax, dist: dict, color: str):
    total = max(sum(dist.values()), 1.0)
    zones_cfg = [
        ("left", 52, 76, "左路"),
        ("center", 28, 52, "中路"),
        ("right", 4, 28, "右路"),
    ]
    for side_key, y_lo, y_hi, label in zones_cfg:
        ratio = dist.get(side_key, 0.0) / total
        alpha = 0.08 + ratio * 0.22
        rect = FancyBboxPatch((75, y_lo), 41, y_hi - y_lo,
                     boxstyle="round,pad=0.5", facecolor=color, alpha=alpha,
                     edgecolor=color, linewidth=0.8, linestyle="--")
        ax.add_patch(rect)
        ax.text(95.5, (y_lo + y_hi) / 2, f"{label} ({ratio:.0%})",
                fontsize=9, color=color, ha="center", va="center",
                fontweight="bold", alpha=0.9)


def _draw_player_marker(ax, p: dict, color: str, player_meta: dict,
                        zone_offsets: dict[int, int] | None = None):
    """绘制球员标记：
    - 主区：完整标记（大圆 + 头像 + 号码 + 名字 + 数据）
    - 其他热区：简化彩色圆 + 区号，根据 zone_offsets 错开避免重叠
    """
    if zone_offsets is None:
        zone_offsets = {}

    pos = p.get("pos", "?")
    zs = p.get("zscore", 0)
    raw_name = p["name"]
    cn_name = _cn(raw_name)
    name = cn_name if cn_name != raw_name else _safe_name(raw_name)
    output = p.get("output", "")
    carry_text = p.get("carry", "")

    x = p.get("x", 60)
    y = p.get("y", 40)
    hot_zones = p.get("hot_zones", []) or []

    zs_abs = abs(zs)
    radius = 2.5 + min(zs_abs * 1.6, 6.5)
    alpha_val = 0.7 + min(zs_abs / 10, 0.25)

    meta = player_meta.get(raw_name, {})
    player_id = meta.get("player_id")
    headshot = _get_headshot(player_id) if player_id else None
    jersey_num = meta.get("number")

    primary_zone = p.get("primary_zone")

    # 热区偏移步长
    JITTER_DX = 3.5
    JITTER_DY = 3.0

    for hz in hot_zones:
        is_primary = (hz == primary_zone)

        # zone 中心
        base_x, base_y = _ZONE_COORDS.get(hz, (x, y))

        # 所有标记（包括主区）共享 zone 偏移计数，避免多人同 zone 重叠
        idx = zone_offsets.get(hz, 0)
        zone_offsets[hz] = idx + 1
        offsets = [(0, 0), (JITTER_DX, 0), (-JITTER_DX, 0),
                   (0, JITTER_DY), (0, -JITTER_DY),
                   (JITTER_DX, JITTER_DY), (-JITTER_DX, JITTER_DY),
                   (JITTER_DX, -JITTER_DY), (-JITTER_DX, -JITTER_DY)]
        ox, oy = offsets[idx % len(offsets)]
        hx, hy = base_x + ox, base_y + oy

        if is_primary:
            # ── 主区：完整标记 ──
            h_radius = radius
            ax.add_patch(plt.matplotlib.patches.Circle((hx, hy), h_radius,
                         facecolor=color, edgecolor="white", linewidth=1.2,
                         alpha=alpha_val, zorder=10))

            # 头像
            if headshot is not None:
                iox = hx + h_radius + 0.5
                ioy = hy + h_radius * 0.25
                ab = AnnotationBbox(OffsetImage(headshot, zoom=0.12), (iox, ioy),
                                    frameon=True,
                                    bboxprops=dict(boxstyle="circle,pad=0.05",
                                                  facecolor=BG, edgecolor=color, linewidth=1.0),
                                    zorder=13)
                ax.add_artist(ab)

            # 球衣号码
            if jersey_num is not None:
                ax.text(hx + h_radius * 0.35, hy - h_radius * 0.35, str(jersey_num),
                        fontsize=8, color="white", ha="center", va="center",
                        fontweight="bold", zorder=12,
                        bbox=dict(boxstyle="circle,pad=0.10", facecolor=color,
                                 edgecolor="white", linewidth=0.6, alpha=0.9))

            # 位置 + 区号
            ax.text(hx, hy, f"{pos}\n{hz}区", fontsize=6.2, color="white",
                    ha="center", va="center", fontweight="bold",
                    zorder=11, linespacing=1.2)

            # 名字
            nx = hx + h_radius + 1.2
            ny = hy - h_radius
            ax.text(nx, ny, name, fontsize=9.5, color=color, ha="left", va="center",
                    fontweight="bold", zorder=12,
                    bbox=dict(boxstyle="round,pad=0.20", facecolor=BG,
                             edgecolor=color, alpha=0.8, linewidth=0.5))

        else:
            # ── 热区：简化为彩色实心圆 + 区号 ──
            h_radius = 2.5
            ax.add_patch(plt.matplotlib.patches.Circle((hx, hy), h_radius,
                         facecolor=color, edgecolor="white", linewidth=0.8,
                         alpha=0.65, zorder=9))
            ax.text(hx, hy, str(hz), fontsize=5.5, color="white",
                    ha="center", va="center", fontweight="bold", zorder=10)

    # ── 仅主区显示额外数据 ──
    text_x = x + radius + 1.5
    carry_dist = _parse_carry_distance(carry_text)
    data_text = f"z={zs:+.1f}"
    if carry_dist > 0:
        data_text += f"  {carry_dist:.0f}m"
    ax.text(text_x, y - radius - 2.8, data_text, fontsize=6.5, color=MUTED,
            ha="left", va="top", zorder=12)

    summary = _short_summary(output, 35)
    if summary:
        ax.text(text_x, y - radius - 5.0, summary, fontsize=6.2, color=MUTED,
                ha="left", va="top", zorder=12)


def plot_tactical_synthesis(
    match_id: int,
    home_name: str,
    away_name: str,
    output_dir: str,
    dpi: int = 150,
    match_score: str = "",
    vision_data: dict | None = None,
) -> str:
    """生成战术合成图 v2 — 两队同场进攻体系。

    单球场全景：
      - 左侧半场 = 主队(从左→右进攻), 右侧半场 = 客队(从右→左进攻)
      - 每队三路绿色纵向方块：左路/中路/右路，颜色深浅=该路球员占比
      - 方块中央显示百分比数字
      - 底部传球倾向条 + 阵型线索

    Returns:
        输出文件路径
    """
    import os as _os
    _os.makedirs(output_dir, exist_ok=True)

    from src.composer.spatial_summary import (
        _enrich_players, _compute_attack_channels,
        _compute_formation_clues, _compute_passing_profile
    )

    if vision_data is None:
        from src.engine.vision_analyzer import load_vision_cache
        vision_data = load_vision_cache(match_id)
    if vision_data is None:
        return ""

    # ── 加载两队数据 ──
    team_data = {}
    for team, tname in [("home", home_name), ("away", away_name)]:
        players = _enrich_players(match_id, team, vision_data)
        active = [p for p in players if p["hot_zones"] and p["pos"] != "GK"]
        channels = _compute_attack_channels(active)
        formation = _compute_formation_clues(active)
        passing = _compute_passing_profile(active)
        # 计算三路占比 — 归一化到总和100%（一人可同时出现在多路，除以总数）
        raw_counts = {}
        for ch_key in ["进攻左路", "中路", "进攻右路"]:
            raw_counts[ch_key] = channels.get(ch_key, {}).get("count", 0)
        count_sum = sum(raw_counts.values()) or 1
        ratios = {k: v / count_sum for k, v in raw_counts.items()}
        team_data[team] = {
            "name": tname, "ratios": ratios, "formation": formation,
            "passing": passing, "active": active,
        }

    # ── 单图布板 ──
    fig, ax = plt.subplots(figsize=(20, 12), dpi=dpi, facecolor=BG)
    ax.set_xlim(-10, 130)
    ax.set_ylim(-22, 90)
    ax.set_aspect("equal")
    ax.set_facecolor(PITCH_GREEN)
    ax.axis("off")
    _draw_pitch(ax)

    # ── 中线分隔（仅球场范围内） + 方向箭头 ──
    ax.plot([60, 60], [0, 80], color="#ffffff", lw=2.5, alpha=0.5, zorder=3)
    ax.text(30, 82, f"← {home_name}", fontsize=15, color=GOLD, ha="center",
            fontweight="bold")
    ax.text(90, 82, f"{away_name} →", fontsize=15, color=GOLD, ha="center",
            fontweight="bold")
    ax.text(60, 82, match_score, fontsize=14, color=MUTED, ha="center",
            fontweight="bold")

    # ── 两队三路方块 ──
    _draw_team_bars(ax, "home", team_data["home"])
    _draw_team_bars(ax, "away", team_data["away"])

    # ── 球场下方第一行：阵型线索 ──
    from src.composer.spatial_summary import _describe_zones
    for team, x_base in [("home", 5), ("away", 65)]:
        td = team_data[team]
        fm = td["formation"]
        notes = []
        if fm.get("high_line"):
            notes.append("防线高位")
        else:
            notes.append("防线靠后")
        if fm.get("fullback_attack"):
            notes.append("边卫参与进攻")
        if fm.get("striker_deep"):
            notes.append("前锋回撤")
        else:
            notes.append("前锋顶在最前")
        width_bias = fm.get("width_bias", "均衡")
        if width_bias != "均衡":
            notes.append(f"偏向{width_bias}")
        text = " | ".join(notes)
        ax.text(x_base + 25, -5, text, fontsize=9, color=MUTED,
                ha="center", va="top",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="#0f1923",
                         edgecolor="#1e2d45", alpha=0.8))

    # ── 球场下方第二行：两队传球条 ──
    _draw_dual_passing_bar(ax, team_data["home"]["passing"], team_data["home"]["name"],
                           x=5, y=-14, bar_w=50)
    _draw_dual_passing_bar(ax, team_data["away"]["passing"], team_data["away"]["name"],
                           x=65, y=-14, bar_w=50)

    out_path = _os.path.join(output_dir, "tactical_synthesis.png")
    fig.savefig(out_path, dpi=dpi, bbox_inches="tight",
                pad_inches=0.3, facecolor=BG, edgecolor="none")
    plt.close(fig)
    return out_path


def _draw_team_bars(ax, team: str, td: dict):
    """在球场半侧绘制三路横向进攻条。

    纯 Rectangle 无圆角膨胀，绝不越过中线。
    home: x=14→56 (w=42), away: x=64→106 (w=42), 中线60留白8单位。
    """
    ratios = td["ratios"]
    if team == "home":
        bx, bar_w = 14, 42
        rows = [
            ("进攻左路", ratios["进攻左路"], 54, 78),
            ("中路", ratios["中路"], 28, 52),
            ("进攻右路", ratios["进攻右路"], 2, 26),
        ]
    else:
        bx, bar_w = 64, 42
        rows = [
            ("进攻右路", ratios["进攻右路"], 54, 78),
            ("中路", ratios["中路"], 28, 52),
            ("进攻左路", ratios["进攻左路"], 2, 26),
        ]

    for ch_name, ratio, y_lo, y_hi in rows:
        bar_h = y_hi - y_lo
        by = y_lo

        if ratio >= 0.40:
            color = "#005a32"
            edge_color = "#00c853"
        elif ratio >= 0.25:
            color = "#2e7d32"
            edge_color = "#69f0ae"
        else:
            color = "#4caf50"
            edge_color = "#b9f6ca"

        rect = plt.Rectangle((bx, by), bar_w, bar_h,
                              facecolor=color, edgecolor=edge_color,
                              linewidth=2.5, alpha=0.88, zorder=10)
        ax.add_patch(rect)

        # 通道名 + 百分比
        short_name = ch_name.replace("进攻", "")
        pct = f"{ratio:.0%}"
        label_text = f"{short_name} {pct}"
        ha = "left" if team == "home" else "right"
        lx = bx + 5 if team == "home" else bx + bar_w - 5
        ax.text(lx, by + bar_h / 2, label_text,
                fontsize=15, color="white", ha=ha, va="center",
                fontweight="bold", zorder=11)

    # 队名
    center_x = 30 if team == "home" else 90
    ax.text(center_x, 80.5, td["name"],
            fontsize=10, color=GOLD, ha="center", fontweight="bold")


def _draw_dual_passing_bar(ax, passing: dict, team_name: str,
                           x: float, y: float, bar_w: float):
    """传球倾向条 — 字体放大，显眼。"""
    total = passing.get("total", 1) or 1
    f_pct = passing.get("forward_pct", 0) / 100
    l_pct = passing.get("lateral_pct", 0) / 100
    b_pct = passing.get("backward_pct", 0) / 100

    bar_h = 7
    segs = [
        (f_pct, "#31a354", "向前"),
        (l_pct, "#f1c40f", "横向"),
        (b_pct, "#e74c3c", "回传"),
    ]
    x_pos = x
    for ratio, color, label in segs:
        if ratio > 0:
            seg_w = bar_w * ratio
            rect = FancyBboxPatch((x_pos, y), seg_w, bar_h,
                         boxstyle="round,pad=0.15", facecolor=color,
                         edgecolor="none", alpha=0.8, zorder=18)
            ax.add_patch(rect)
            if ratio > 0.12:
                ax.text(x_pos + seg_w / 2, y + bar_h / 2,
                        f"{label} {ratio:.0%}", fontsize=9, color="white",
                        ha="center", va="center", fontweight="bold", zorder=19)
            x_pos += seg_w

    ax.text(x + bar_w / 2, y - 1.5,
            f"{team_name} 传球倾向",
            fontsize=9, color=MUTED, ha="center")
