"""
战术速写图生成模块

从球员空间行为数据 + 球队空间合成数据中提取结构化信息，
绘制战术概览图——展示两队阵型、进攻重心、核心球员活动区域、
攻防切换方向。与「战术速写」章节文字配合使用。
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse
import numpy as np

try:
    from mplsoccer import Pitch
    HAS_MPLSOCCER = True
except ImportError:
    HAS_MPLSOCCER = False

from src.utils.player_names import to_chinese as _cn
from src.visualizer import HOME_COLOR, AWAY_COLOR

BG_COLOR = "#1a1a2e"
TEXT_COLOR = "#ecf0f1"
GRID_COLOR = "#2c3e50"
HOME_HEAT = "#55efc4"
AWAY_HEAT = "#74b9ff"
HOME_ARROW = "#00ff88"    # 亮绿箭头，深绿底布上可见
AWAY_ARROW = "#4da6ff"    # 亮蓝箭头
ZONE_ALPHA = 0.28
ARROW_ALPHA = 0.65


def plot_tactical_sketch(
    spatial_synthesis_text: str,
    home_name: str,
    away_name: str,
    home_players: list[dict],
    away_players: list[dict],
    output_path: str,
    dpi: int = 150,
    match_score: str = "",
):
    """生成战术速写概览图。

    Args:
        spatial_synthesis_text: build_team_spatial_synthesis() 的输出
        home_name: 主队名
        away_name: 客队名
        home_players: 主队关键球员 [{name, pos, side, output, ...}]
        away_players: 客队关键球员 [{name, pos, side, output, ...}]
        output_path: PNG 输出路径
        dpi: 分辨率
        match_score: 比分文本（如 "3 - 0"）
    """
    if not HAS_MPLSOCCER:
        _fallback_pitch(home_name, away_name, home_players, away_players,
                        output_path, dpi, match_score)
        return

    # ── 解析两队左右偏重 ──
    h_left = h_right = a_left = a_right = 0
    for p in home_players:
        if "左路" in p.get("side", ""):
            h_left += 1
        elif "右路" in p.get("side", ""):
            h_right += 1
        else:
            h_left += 0.5
            h_right += 0.5
    for p in away_players:
        if "左路" in p.get("side", ""):
            a_left += 1
        elif "右路" in p.get("side", ""):
            a_right += 1
        else:
            a_left += 0.5
            a_right += 0.5

    h_total = max(h_left + h_right, 1)
    a_total = max(a_left + a_right, 1)
    h_bias = (h_right - h_left) / h_total   # +1=全右, -1=全左
    a_bias = (a_right - a_left) / a_total

    # ── 创建画布（mplsoccer draw() 内部创建 figure） ──
    pitch = Pitch(
        pitch_type="statsbomb",
        pitch_color="#1e3d2e",       # 深草绿底色，可见
        line_color="#5a7a6a",        # 球场线条，与底色有对比
        linewidth=1.2,
    )
    fig, ax = pitch.draw(figsize=(16, 10))
    fig.set_facecolor(BG_COLOR)

    # ── 绘制进攻重心区域（半透明椭圆 + 侧边色条） ──
    _draw_attack_zone(ax, pitch, h_bias, home=True)
    _draw_attack_zone(ax, pitch, a_bias, home=False)

    # ── 绘制关键球员名 ──
    _draw_player_labels(ax, pitch, home_players, home=True, left_bias=h_bias)
    _draw_player_labels(ax, pitch, away_players, home=False, left_bias=a_bias)

    # ── 进攻方向箭头 ──
    _draw_attack_arrows(ax, h_bias, a_bias)

    # ── 标题与图例 ──
    title = f"{home_name} vs {away_name}"
    if match_score:
        title += f"  ({match_score})"
    ax.set_title(f"战术速写：{title}", fontsize=18, color=TEXT_COLOR,
                 fontweight="bold", pad=25, fontfamily="sans-serif")

    # 图例
    legend_y = 0.97
    ax.text(0.05, legend_y, home_name, transform=ax.transAxes,
            fontsize=13, color=HOME_HEAT, fontweight="bold",
            va="top", fontfamily="sans-serif")
    ax.text(0.05, legend_y - 0.04, "进攻方向 →", transform=ax.transAxes,
            fontsize=10, color=TEXT_COLOR, va="top", fontfamily="sans-serif",
            alpha=0.6)
    ax.text(0.95, legend_y, away_name, transform=ax.transAxes,
            fontsize=13, color=AWAY_HEAT, fontweight="bold",
            va="top", ha="right", fontfamily="sans-serif")
    ax.text(0.95, legend_y - 0.04, "← 进攻方向", transform=ax.transAxes,
            fontsize=10, color=TEXT_COLOR, va="top", ha="right",
            fontfamily="sans-serif", alpha=0.6)

    # 底部战术摘要
    _draw_tactical_summary(ax, home_name, away_name, h_bias, a_bias,
                           home_players, away_players)

    plt.tight_layout(pad=2)
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight",
                facecolor=BG_COLOR, edgecolor="none")
    plt.close(fig)


def _draw_attack_zone(ax, pitch, bias: float, home: bool):
    """绘制一方的进攻集中区域。

    从进攻方向看，左侧 X=100~120（对方禁区），右侧 X=0~20（防守半场）。
    home: 从左→右攻（x方向 0→120），away: 从右→左攻（x方向 120→0）。
    """
    color = HOME_HEAT if home else AWAY_HEAT
    label = "进攻重心"

    if home:
        # 主队进攻方向：右（x 80→120 为进攻三区）
        # bias > 0 → 偏右（攻右路），bias < 0 → 偏左（攻左路）
        # Y: 0=bottom(left touchline), 80=top(right touchline)
        # 攻左路=Y 60~80, 攻右路=Y 0~20, 均衡=Y 30~50
        if abs(bias) < 0.25:
            cy = 40  # 中路
            y_span = 25
        elif bias > 0:
            cy = 65  # 攻画面下方 = 右路
            y_span = 20
        else:
            cy = 15  # 攻画面上方 = 左路
            y_span = 20

        # 在进攻三区画区域
        for xi in [85, 95, 105]:
            ax.add_patch(Ellipse(
                (xi, cy), width=12, height=y_span,
                color=color, alpha=ZONE_ALPHA, zorder=1,
            ))
        ax.annotate(label, xy=(105, cy - y_span / 2 - 4), fontsize=8,
                    color=color, ha="center", alpha=0.75,
                    fontfamily="sans-serif")
    else:
        # 客队进攻方向：左（x 40→0 为进攻三区）
        if abs(bias) < 0.25:
            cy = 40
            y_span = 25
        elif bias > 0:
            cy = 65  # 攻画面下方 = 右路
            y_span = 20
        else:
            cy = 15  # 攻画面上方 = 左路
            y_span = 20

        for xi in [35, 25, 15]:
            ax.add_patch(Ellipse(
                (xi, cy), width=12, height=y_span,
                color=color, alpha=ZONE_ALPHA, zorder=1,
            ))
        ax.annotate(label, xy=(15, cy - y_span / 2 - 4), fontsize=8,
                    color=color, ha="center", alpha=0.75,
                    fontfamily="sans-serif")


def _draw_player_labels(ax, pitch, players: list[dict], home: bool, left_bias: float):
    """在球场上标注关键球员名。"""
    color = HOME_HEAT if home else AWAY_HEAT
    n = min(len(players), 6)
    for i, p in enumerate(players[:n]):
        # 根据左右偏重决定 Y 坐标
        side = p.get("side", "")
        # Y: 0(bottom)=自己视角的右路, 80(top)=自己视角的左路
        # 对于 home 队，画面上方=左路
        if home:
            if "左路" in side:
                y = 70 - i * 4       # 左上
                x = 50 + i * 10
            elif "右路" in side:
                y = 10 + i * 4       # 右下
                x = 50 + i * 10
            else:
                y = 40
                x = 40 + i * 12
        else:
            if "左路" in side:
                y = 10 + i * 4       # 下方=左路（客队视角）
                x = 70 - i * 10
            elif "右路" in side:
                y = 70 - i * 4       # 上方=右路
                x = 70 - i * 10
            else:
                y = 40
                x = 80 - i * 12

        name = _cn(p["name"])
        ax.annotate(name, xy=(x, y), fontsize=9,
                    color=color, ha="center", va="center",
                    fontweight="bold", fontfamily="sans-serif",
                    bbox=dict(boxstyle="round,pad=0.3",
                              facecolor=BG_COLOR, edgecolor=color,
                              alpha=0.7, linewidth=0.8),
                    zorder=5)


def _draw_attack_arrows(ax, h_bias: float, a_bias: float):
    """绘制进攻方向箭头。"""
    # 主队：从左向右攻（长箭头）
    for y in [15, 40, 65]:
        ax.annotate("", xy=(108, y), xytext=(18, y),
                    arrowprops=dict(arrowstyle="->", color=HOME_ARROW,
                                    lw=2.5, alpha=ARROW_ALPHA),
                    zorder=0)
    # 客队：从右向左攻
    for y in [15, 40, 65]:
        ax.annotate("", xy=(12, y), xytext=(102, y),
                    arrowprops=dict(arrowstyle="->", color=AWAY_ARROW,
                                    lw=2.5, alpha=ARROW_ALPHA),
                    zorder=0)


def _draw_tactical_summary(ax, home_name, away_name, h_bias, a_bias,
                           home_players, away_players):
    """在图表底部输出战术摘要文字。"""
    # 主队描述
    if abs(h_bias) < 0.2:
        h_side = "中路均衡"
    elif h_bias > 0:
        h_side = "偏向右路进攻"
    else:
        h_side = "偏向左路进攻"

    if abs(a_bias) < 0.2:
        a_side = "中路均衡"
    elif a_bias > 0:
        a_side = "偏向右路进攻"
    else:
        a_side = "偏向左路进攻"

    h_names = "、".join(_cn(p["name"]) for p in home_players[:4])
    a_names = "、".join(_cn(p["name"]) for p in away_players[:4])

    text = (
        f"{home_name}：{h_side} | 核心：{h_names}\n"
        f"{away_name}：{a_side} | 核心：{a_names}"
    )
    ax.text(0.5, -0.06, text, transform=ax.transAxes,
            fontsize=10, color=TEXT_COLOR, ha="center", va="top",
            fontfamily="sans-serif", alpha=0.75,
            bbox=dict(boxstyle="round,pad=0.5",
                      facecolor="#0d1117", edgecolor=GRID_COLOR,
                      alpha=0.65))


def _fallback_pitch(home_name, away_name, home_players, away_players,
                    output_path, dpi, match_score):
    """无 mplsoccer 时的纯 matplotlib 回退方案。"""
    fig, ax = plt.subplots(figsize=(16, 10), facecolor=BG_COLOR)
    ax.set_facecolor(BG_COLOR)

    # 画简易球场
    ax.plot([0, 120], [0, 0], color=GRID_COLOR, lw=2)       # 底线
    ax.plot([0, 120], [80, 80], color=GRID_COLOR, lw=2)     # 底线
    ax.plot([0, 0], [0, 80], color=GRID_COLOR, lw=2)        # 边线
    ax.plot([120, 120], [0, 80], color=GRID_COLOR, lw=2)    # 边线
    ax.plot([60, 60], [0, 80], color=GRID_COLOR, lw=1.5, ls="--")  # 中线

    # 禁区
    for x in [0, 120]:
        dir_sign = 1 if x == 0 else -1
        ax.plot([x, x + dir_sign * 18], [18, 18], color=GRID_COLOR, lw=1.2)
        ax.plot([x, x + dir_sign * 18], [62, 62], color=GRID_COLOR, lw=1.2)
        ax.plot([x + dir_sign * 18, x + dir_sign * 18], [18, 62], color=GRID_COLOR, lw=1.2)
        # 小禁区
        ax.plot([x, x + dir_sign * 6], [30, 30], color=GRID_COLOR, lw=0.8)
        ax.plot([x, x + dir_sign * 6], [50, 50], color=GRID_COLOR, lw=0.8)
        ax.plot([x + dir_sign * 6, x + dir_sign * 6], [30, 50], color=GRID_COLOR, lw=0.8)

    ax.set_xlim(-5, 125)
    ax.set_ylim(-5, 85)
    ax.axis("off")

    # 标题
    title = f"战术速写：{home_name} vs {away_name}"
    if match_score:
        title += f"  ({match_score})"
    ax.set_title(title, fontsize=18, color=TEXT_COLOR, fontweight="bold", pad=20)

    # 图例
    ax.text(10, 82, f"← {away_name} 进攻方向", fontsize=10, color=AWAY_HEAT, alpha=0.6)
    ax.text(110, 82, f"{home_name} 进攻方向 →", fontsize=10, color=HOME_HEAT, alpha=0.6, ha="right")

    # 标注球员
    for i, p in enumerate(home_players[:5]):
        ax.text(25 + i * 18, 50 + (i % 3) * 12, _cn(p["name"]),
                fontsize=9, color=HOME_HEAT, fontweight="bold")

    for i, p in enumerate(away_players[:5]):
        ax.text(95 - i * 18, 50 - (i % 3) * 12, _cn(p["name"]),
                fontsize=9, color=AWAY_HEAT, fontweight="bold")

    fig.savefig(output_path, dpi=dpi, bbox_inches="tight",
                facecolor=BG_COLOR, edgecolor="none")
    plt.close(fig)
