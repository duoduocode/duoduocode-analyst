"""
战术分析图表生成模块

生成 7 张图表：
  1. 战术维度双雷达图 (PNG)
  2. 时段射门分组柱状图 (PNG)
  3. PPDA 衰退双线折线图 (PNG)
  4. 控球率摇摆面积图 (PNG)
  5. 关键事件时间轴 + 执行评分卡 + 克制矩阵 (HTML 内联)

风格与球员贡献图表保持一致：暗色背景 #1a1a2e、主队绿/客队蓝配色。
"""

from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

from src.visualizer import HOME_COLOR, AWAY_COLOR, NEUTRAL_COLOR, HIGHLIGHT_COLOR

BG_COLOR = "#1a1a2e"
TEXT_COLOR = "#ecf0f1"
GRID_COLOR = "#2c3e50"
HOME_LIGHT = "#55efc4"
AWAY_LIGHT = "#74b9ff"


def _setup_style(ax, title: str = ""):
    """统一暗色风格设置。"""
    ax.set_facecolor(BG_COLOR)
    ax.tick_params(colors=TEXT_COLOR, labelsize=9)
    ax.spines["bottom"].set_color(GRID_COLOR)
    ax.spines["left"].set_color(GRID_COLOR)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.grid(True, alpha=0.2, color=GRID_COLOR)
    if title:
        ax.set_title(title, color=TEXT_COLOR, fontsize=13, fontweight="bold", pad=12)


def plot_tactical_radar(
    home_name: str, away_name: str,
    home_vals: dict, away_vals: dict,
    home_gaps: dict,
    output_path: str, dpi: int = 150,
) -> str:
    """图1: 战术维度双雷达图（含控球率）。"""
    dimensions = ["控球率", "长传占比", "传中占比", "三区传球", "向前比例", "压迫强度", "高位抢断", "封堵倾向"]
    keys = ["possession_pct", "long_ball_ratio", "cross_ratio", "final_third_pass_ratio",
            "forward_ratio", "ppda", "high_press_ratio", "clearance_ratio"]

    # 归一化到 0-1（比赛内相对）
    def normalize(vals, dim_keys):
        max_vals = {}
        for k in dim_keys:
            hv = home_vals.get(k, 0)
            av = away_vals.get(k, 0)
            max_vals[k] = max(abs(hv), abs(av), 0.01)
        return [min(abs(vals.get(k, 0)) / max_vals[k], 1.0) for k in dim_keys]

    home_norm = normalize(home_vals, keys)
    away_norm = normalize(away_vals, keys)

    N = len(dimensions)
    angles = [n / float(N) * 2 * np.pi for n in range(N)]
    angles += angles[:1]
    home_norm += home_norm[:1]
    away_norm += away_norm[:1]

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
    ax.set_facecolor(BG_COLOR)
    fig.patch.set_facecolor(BG_COLOR)

    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(dimensions, fontsize=9, color=TEXT_COLOR)
    ax.set_ylim(0, 1.1)
    ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticklabels(["20%", "40%", "60%", "80%", "100%"], fontsize=7, color=NEUTRAL_COLOR)
    ax.yaxis.grid(True, alpha=0.25, color=GRID_COLOR)
    ax.xaxis.grid(True, alpha=0.25, color=GRID_COLOR)

    ax.fill(angles, home_norm, alpha=0.2, color=HOME_COLOR)
    ax.plot(angles, home_norm, linewidth=2, color=HOME_COLOR, label=home_name, marker="o", markersize=5)
    ax.fill(angles, away_norm, alpha=0.2, color=AWAY_COLOR)
    ax.plot(angles, away_norm, linewidth=2, color=AWAY_COLOR, label=away_name, marker="s", markersize=5, linestyle="--")

    ax.set_title(f"战术维度对比 — {home_name} vs {away_name}", color=TEXT_COLOR,
                 fontsize=14, fontweight="bold", pad=25)
    ax.legend(loc="upper right", bbox_to_anchor=(1.15, 1.12), fontsize=9,
              facecolor=BG_COLOR, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR)

    # Value 标注
    for i, (dim, key) in enumerate(zip(dimensions, keys)):
        hv = home_vals.get(key, 0)
        av = away_vals.get(key, 0)
        if abs(hv) > 0 and abs(av) > 0:
            gap = max(abs(hv), abs(av)) / max(min(abs(hv), abs(av)), 0.01)
            if gap > 1.3:
                ax.annotate(f"{gap:.1f}x", xy=(angles[i], 1.05),
                            fontsize=7, color=HIGHLIGHT_COLOR, ha="center", fontweight="bold")

    fig.tight_layout()
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight", facecolor=BG_COLOR)
    plt.close(fig)
    return output_path


def plot_shot_xg_timeline(
    home_name: str, away_name: str,
    shot_segments: dict,
    output_path: str, dpi: int = 150,
) -> str:
    """射门时段分布 + xG/xGOT 累积曲线。双 panel（主客各一个子图）。

    每个子图：
    - 左轴：堆叠柱状 — 射正(深色) + 射偏(浅色)
    - 右轴：累积 xG 曲线(实线) + 累积 xGOT 曲线(虚线)
    - xG vs xGOT 的间距揭示射门质量
    """
    fig, (ax_h, ax_a) = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    fig.patch.set_facecolor(BG_COLOR)

    windows = ["0-15", "15-30", "30-45", "45-60", "60-75", "75-90"]
    x = np.arange(len(windows))

    for ax, shots_on, shots_off, xg_list, xgot_list, name, bar_color, team_key in [
        (ax_h,
         shot_segments.get("home_on", shot_segments.get("home", [])),
         shot_segments.get("home_off", [0] * 6),
         shot_segments.get("home_xg", [0] * 6),
         shot_segments.get("home_xgot", [0] * 6),
         home_name, HOME_COLOR, "home"),
        (ax_a,
         shot_segments.get("away_on", shot_segments.get("away", [])),
         shot_segments.get("away_off", [0] * 6),
         shot_segments.get("away_xg", [0] * 6),
         shot_segments.get("away_xgot", [0] * 6),
         away_name, AWAY_COLOR, "away"),
    ]:
        ax.set_facecolor(BG_COLOR)

        # 堆叠柱状
        width = 0.55
        bars_off = ax.bar(x, shots_off, width, label="射偏",
                          color=bar_color, alpha=0.35, edgecolor=bar_color, linewidth=0.5)
        bars_on = ax.bar(x, shots_on, width, bottom=shots_off, label="射正",
                         color=bar_color, alpha=0.9, edgecolor=bar_color, linewidth=0.5)

        # 柱上标注总射门数
        for i, (on, off) in enumerate(zip(shots_on, shots_off)):
            total = on + off
            if total > 0:
                ax.text(i, total + 0.3, str(total), ha="center", va="bottom",
                        fontsize=8, color=TEXT_COLOR)

        # 累积 xG / xGOT 曲线 (右轴)
        ax2 = ax.twinx()
        cum_xg = np.cumsum(xg_list)
        cum_xgot = np.cumsum(xgot_list)

        ax2.plot(x, cum_xg, color="#f39c12", linewidth=2.2, marker="o", markersize=6,
                 label=f"累积 xG ({round(cum_xg[-1], 2) if len(cum_xg) > 0 else 0})", zorder=5)
        ax2.plot(x, cum_xgot, color=bar_color, linewidth=1.8, marker="s", markersize=5,
                 linestyle="--", label=f"累积 xGOT ({round(cum_xgot[-1], 2) if len(cum_xgot) > 0 else 0})", zorder=5)

        # 标注最终值
        if len(cum_xg) > 0 and cum_xg[-1] > 0:
            ax2.annotate(f"{cum_xg[-1]:.2f}", xy=(5, cum_xg[-1]),
                         fontsize=8, color="#f39c12", fontweight="bold",
                         xytext=(5, 3), textcoords="offset points")
        if len(cum_xgot) > 0 and cum_xgot[-1] > 0:
            ax2.annotate(f"{cum_xgot[-1]:.2f}", xy=(5, cum_xgot[-1]),
                         fontsize=8, color=bar_color, fontweight="bold",
                         xytext=(5, -12), textcoords="offset points")

        ax2.set_ylabel("xG", color="#f39c12", fontsize=8)
        ax2.tick_params(axis="y", colors="#f39c12", labelsize=7)

        # 图例
        lines1, labels1 = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labels1 + labels2, loc="upper left",
                  fontsize=8, facecolor=BG_COLOR, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR)

        _setup_style(ax, f"{name}")
        ax.set_ylabel("射门次数", color=TEXT_COLOR, fontsize=8)
        ax.set_xticks(x)
        ax.set_xticklabels(windows, fontsize=9, color=TEXT_COLOR)

    # 纵轴范围
    max_h = max(max(shot_segments.get("home_on", [0])), max(shot_segments.get("home_off", [0])),
                max(shot_segments.get("away_on", [0])), max(shot_segments.get("away_off", [0])))
    for ax in [ax_h, ax_a]:
        ax.set_ylim(0, max(max_h * 1.5, 3))

    fig.suptitle(f"射门时段分布 xG 累积 — {home_name} vs {away_name}",
                 color=TEXT_COLOR, fontsize=13, fontweight="bold", y=1.01)
    fig.tight_layout()
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight", facecolor=BG_COLOR)
    plt.close(fig)
    return output_path


def plot_shot_bars(
    home_name: str, away_name: str,
    home_shots: list[int], away_shots: list[int],
    output_path: str, dpi: int = 150,
) -> str:
    """图2: 时段射门分组柱状图（6窗口）— 保留向后兼容。"""
    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor(BG_COLOR)
    ax.set_facecolor(BG_COLOR)

    windows = ["0-15", "15-30", "30-45", "45-60", "60-75", "75-90"]
    x = np.arange(len(windows))
    width = 0.35

    bars1 = ax.bar(x - width / 2, home_shots, width, label=home_name,
                   color=HOME_COLOR, alpha=0.85, edgecolor=HOME_COLOR)
    bars2 = ax.bar(x + width / 2, away_shots, width, label=away_name,
                   color=AWAY_COLOR, alpha=0.85, edgecolor=AWAY_COLOR)

    for bar in bars1:
        h = bar.get_height()
        if h > 0:
            ax.text(bar.get_x() + bar.get_width() / 2., h + 0.3, str(int(h)),
                    ha="center", va="bottom", fontsize=8, color=TEXT_COLOR)
    for bar in bars2:
        h = bar.get_height()
        if h > 0:
            ax.text(bar.get_x() + bar.get_width() / 2., h + 0.3, str(int(h)),
                    ha="center", va="bottom", fontsize=8, color=TEXT_COLOR)

    ax.set_xticks(x)
    ax.set_xticklabels(windows, fontsize=10, color=TEXT_COLOR)
    _setup_style(ax, f"时段射门分布 — {home_name} vs {away_name}")
    ax.set_ylabel("射门次数", color=TEXT_COLOR, fontsize=10)
    ax.legend(facecolor=BG_COLOR, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR, fontsize=9)
    ax.set_ylim(0, max(max(home_shots), max(away_shots)) * 1.4 if max(home_shots + away_shots) > 0 else 5)

    fig.tight_layout()
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight", facecolor=BG_COLOR)
    plt.close(fig)
    return output_path


def plot_ppda_bar(
    home_name: str, away_name: str,
    home_ppda_val: float, away_ppda_val: float,
    output_path: str, dpi: int = 150,
) -> str:
    """图3: PPDA 全场对比柱状图（无逐窗口数据时使用）。"""
    fig, ax = plt.subplots(figsize=(6, 5))
    fig.patch.set_facecolor(BG_COLOR)
    ax.set_facecolor(BG_COLOR)

    teams = [home_name, away_name]
    values = [home_ppda_val, away_ppda_val]
    colors = [HOME_COLOR, AWAY_COLOR]

    bars = ax.bar(teams, values, color=colors, alpha=0.85, width=0.4)

    for bar, val in zip(bars, values):
        if val > 0:
            ax.text(bar.get_x() + bar.get_width() / 2., bar.get_height() + 0.5,
                    str(val), ha="center", va="bottom", fontsize=14,
                    color=TEXT_COLOR, fontweight="bold")

    _setup_style(ax, "全场压迫强度 (PPDA — 数值越低压迫越强)")
    ax.set_ylabel("PPDA", color=TEXT_COLOR, fontsize=10)
    # 越低越好，所以不设反序
    ax.set_ylim(0, max(values) * 1.3 if max(values) > 0 else 10)
    ax.invert_yaxis()

    fig.tight_layout()
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight", facecolor=BG_COLOR)
    plt.close(fig)
    return output_path


def plot_possession_area(
    home_name: str, away_name: str,
    home_trend: list[float], away_trend: list[float],
    output_path: str, dpi: int = 150,
) -> str:
    """图4: 控球率摇摆面积图。"""
    fig, ax = plt.subplots(figsize=(10, 4))
    fig.patch.set_facecolor(BG_COLOR)
    ax.set_facecolor(BG_COLOR)

    n = len(home_trend)
    x_labels = [f"{i * 5}-{(i + 1) * 5}" for i in range(n)]
    x = np.arange(n)

    ax.fill_between(x, 0, home_trend, alpha=0.5, color=HOME_COLOR, label=home_name)
    ax.fill_between(x, home_trend, 100, alpha=0.5, color=AWAY_COLOR, label=away_name)

    ax.plot(x, home_trend, color=HOME_COLOR, linewidth=1.5)
    ax.axhline(y=50, color=TEXT_COLOR, linestyle="--", alpha=0.3, linewidth=0.8)

    ax.set_xticks(x)
    ax.set_xticklabels(x_labels, fontsize=8, color=TEXT_COLOR, rotation=45)
    _setup_style(ax, f"控球率摇摆 — {home_name} vs {away_name}")
    ax.set_ylabel("控球率 %", color=TEXT_COLOR, fontsize=10)
    ax.set_ylim(0, 100)
    ax.legend(facecolor=BG_COLOR, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR, fontsize=9,
              loc="upper right")

    fig.tight_layout()
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight", facecolor=BG_COLOR)
    plt.close(fig)
    return output_path


def generate_tactical_html_cards(tactical_data: dict, home_name: str, away_name: str) -> str:
    """HTML 内联卡片：关键事件时间轴 + 执行效果 + 对位分析。所有术语已翻译为中文。"""

    # ── 事件时间轴 ──
    key_events = tactical_data.get("match_flow", {}).get("key_event_impacts", [])
    timeline_rows = ""
    for ev in key_events:
        minute = ev.get("minute", "?")
        etype = ev.get("event_type", "")
        team = ev.get("team", "")
        context = ev.get("context", "")
        team_color = HOME_COLOR if team == "home" else AWAY_COLOR
        icon_map = {"进球": "⚽", "点球破门": "⚽", "红牌": "🟥", "乌龙球": "💥", "黄牌": "🟨"}
        icon = icon_map.get(etype, "📌")
        timeline_rows += f"""
        <div style="display:flex;align-items:center;padding:5px 0;border-bottom:1px solid {GRID_COLOR}">
          <span style="color:{NEUTRAL_COLOR};min-width:40px;font-size:11px;font-weight:bold">{minute}'</span>
          <span style="margin-right:6px;font-size:14px">{icon}</span>
          <span style="color:{team_color};min-width:80px;font-size:11px">{team_name(team, home_name, away_name)}</span>
          <span style="color:{TEXT_COLOR};font-size:11px;flex:1">{context}</span>
        </div>"""

    # ── 执行效果卡 ──
    dim_cn = {
        "possession": "传控渗透", "long_ball": "长传冲击", "crossing": "传中抢点",
        "penetration": "三区穿插", "directness": "向前推进",
        "press_intensity": "压迫限制", "high_press": "高位抢断",
        "deep_block": "落位防守", "interception": "线路拦截",
    }

    def _exec_card(team_key: str, team_color: str, tname: str):
        ex = tactical_data.get(team_key, {}).get("execution", {})
        attack = ex.get("attack", {})
        defense = ex.get("defense", {})

        att_total = attack.get("total_score", 0)
        def_total = defense.get("total_score", 0)

        # 进攻简述
        ad = attack.get("dimensions", [])
        pos_ad = [dim_cn.get(d["dim"], d["dim"]) for d in ad if d["score"] > 0]
        neg_ad = [dim_cn.get(d["dim"], d["dim"]) for d in ad if d["score"] <= 0]
        if pos_ad:
            att_summary = f"<span style='color:{HOME_COLOR}'>强项: {'、'.join(pos_ad)}</span>"
        else:
            att_summary = "<span style='color:#95a5a6'>无明显强项</span>"
        if neg_ad:
            att_summary += f"<br><span style='color:{HIGHLIGHT_COLOR}'>弱项: {'、'.join(neg_ad)}</span>"

        # 防守简述
        dd = defense.get("dimensions", [])
        pos_dd = [dim_cn.get(d["dim"], d["dim"]) for d in dd if d["score"] > 0]
        neg_dd = [dim_cn.get(d["dim"], d["dim"]) for d in dd if d["score"] <= 0]
        if pos_dd:
            def_summary = f"<span style='color:{HOME_COLOR}'>强项: {'、'.join(pos_dd)}</span>"
        else:
            def_summary = "<span style='color:#95a5a6'>无明显强项</span>"
        if neg_dd:
            def_summary += f"<br><span style='color:{HIGHLIGHT_COLOR}'>弱项: {'、'.join(neg_dd)}</span>"

        # 数据明细
        all_dims = ad + dd
        dim_rows = ""
        for d in all_dims:
            s = d.get("score", 0)
            s_bg = "rgba(46,204,113,0.15)" if s > 0 else ("rgba(231,76,60,0.12)" if s < 0 else "transparent")
            s_color = HOME_COLOR if s > 0 else (HIGHLIGHT_COLOR if s < 0 else NEUTRAL_COLOR)
            label = dim_cn.get(d["dim"], d["dim"])
            dim_rows += f"""
            <tr style="background:{s_bg}">
              <td style="color:{TEXT_COLOR};font-size:10px;padding:2px 4px">{label}</td>
              <td style="color:{NEUTRAL_COLOR};font-size:10px;text-align:right;padding:2px 4px">{d.get('input_gap','-')}</td>
              <td style="color:{s_color};font-weight:bold;font-size:10px;text-align:right;padding:2px 6px">{s:+.1f}</td>
            </tr>"""

        return f"""
        <div style="flex:1;min-width:280px;background:#162a38;border-radius:10px;padding:14px;
                    border-top:3px solid {team_color}">
          <h4 style="color:{team_color};margin:0 0 10px;font-size:14px">{tname}</h4>
          <div style="display:flex;gap:12px;margin-bottom:10px">
            <div style="flex:1;background:{BG_COLOR};border-radius:6px;padding:8px">
              <div style="color:{TEXT_COLOR};font-size:9px;margin-bottom:3px">进攻效果</div>
              <div style="font-size:11px;line-height:1.6">{att_summary}</div>
            </div>
            <div style="flex:1;background:{BG_COLOR};border-radius:6px;padding:8px">
              <div style="color:{TEXT_COLOR};font-size:9px;margin-bottom:3px">防守效果</div>
              <div style="font-size:11px;line-height:1.6">{def_summary}</div>
            </div>
          </div>
          <table style="width:100%;border-collapse:collapse;margin-top:8px">
            <tr>
              <th style="text-align:left;color:#7f8c8d;font-size:9px;padding:2px 4px">攻防维度</th>
              <th style="text-align:right;color:#7f8c8d;font-size:9px;padding:2px 4px">投入</th>
              <th style="text-align:right;color:#7f8c8d;font-size:9px;padding:2px 6px">效果</th>
            </tr>
            {dim_rows}
          </table>
        </div>"""

    h_card = _exec_card("home", HOME_COLOR, home_name)
    a_card = _exec_card("away", AWAY_COLOR, away_name)

    # ── 对位分析 ──
    coaching = tactical_data.get("coaching", {})
    pairs = coaching.get("mismatch_pairs", [])
    style = coaching.get("style_clash", "")
    style_labels = {
        "possession_vs_counter": f"传控对防守反击 — {home_name}主导控球，{away_name}伺机反击",
        "possession_dominant": "单方控球主导",
        "long_ball_vs_press": "长传冲击对高位压迫",
        "direct_duel": "双方长传快攻对轰",
        "mirror_match": "镜像对决",
        "mixed_styles": "混合风格",
    }

    pairs_html = ""
    for p in pairs:
        ot = home_name if p.get("off_team") == "home" else away_name
        off_label = dim_cn.get(p.get("off_dim", ""), p.get("off_dim", ""))
        def_label = dim_cn.get(p.get("def_dim", ""), p.get("def_dim", ""))
        r = p.get("result", 0)
        r_color = HOME_COLOR if r > 0 else HIGHLIGHT_COLOR
        r_icon = "✓" if r > 0 else "✗"
        pairs_html += f"""
        <div style="display:flex;align-items:center;padding:3px 0;font-size:11px">
          <span style="color:{r_color};margin-right:6px;font-weight:bold">{r_icon}</span>
          <span style="color:{HOME_COLOR if p.get('off_team')=='home' else AWAY_COLOR}">{ot}</span>
          <span style="color:{NEUTRAL_COLOR};margin:0 4px">{off_label} → {def_label}</span>
        </div>"""

    mismatch = coaching.get("tactical_mismatch", {})

    html = f"""
<div class="tactical-analysis">

  <h3 style="color:{TEXT_COLOR};margin:20px 0 8px;font-size:15px">关键事件时间线</h3>
  <div style="background:#162a38;border-radius:10px;padding:10px 14px;margin-bottom:16px">
    {timeline_rows if timeline_rows else '<p style="color:#95a5a6;font-size:11px">本场未检测到关键事件冲击</p>'}
  </div>

  <h3 style="color:{TEXT_COLOR};margin:20px 0 8px;font-size:15px">战术执行效果</h3>
  <div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:16px">
    {h_card}
    {a_card}
  </div>

  <h3 style="color:{TEXT_COLOR};margin:20px 0 8px;font-size:15px">战术对位分析</h3>
  <div style="background:#162a38;border-radius:10px;padding:14px">
    <p style="color:{TEXT_COLOR};font-size:13px;margin:0 0 6px">
      阵型对抗: <span style="color:{HOME_COLOR};font-weight:bold">{style_labels.get(style, style)}</span>
    </p>
    {pairs_html if pairs_html else '<p style="color:#95a5a6;font-size:11px">未检测到显著战术克制关系</p>'}
  </div>

</div>"""

    return html


def plot_event_timeline_png(
    raw, home_name: str, away_name: str,
    output_path: str, dpi: int = 200,
) -> str:
    """生成全场事件时间轴 PNG 图片（matplotlib）。
    
    三栏布局：主队事件 | 时间线 | 客队事件。
    球员显示姓名和号码，不含头像。
    """
    # ── 构建球员查找表 ──
    def _build_player_dict(players):
        d = {}
        for p in players:
            if isinstance(p, dict):
                raw_name = (p.get("name", "") or "").replace("\xa0", " ").strip()
                num = str(p.get("number", "") or "")
                d[raw_name] = num
                orig = (p.get("name", "") or "").strip()
                if orig and orig not in d:
                    d[orig] = num
            else:
                raw_name = (p.name or "").replace("\xa0", " ").strip()
                num = str(getattr(p, "number", "") or "")
                d[raw_name] = num
                orig = (p.name or "").strip()
                if orig and orig not in d:
                    d[orig] = num
        return d

    home_pd = _build_player_dict(raw.home_players)
    away_pd = _build_player_dict(raw.away_players)
    all_pd = {**home_pd, **away_pd}

    def _player_str(name: str) -> str:
        if not name:
            return ""
        clean = name.replace("\xa0", " ").strip()
        num = all_pd.get(clean, all_pd.get(name.strip(), ""))
        if num:
            return f"{clean} #{num}"
        return clean

    # ── 收集排序事件 ──
    all_events = []
    for period in raw.periods:
        for ev in period.events:
            all_events.append((period.sort_order, ev))
    all_events.sort(key=lambda x: (x[0], x[1].time_elapsed, x[1].time_extra or 0))

    # ── 构建行数据 ──
    period_names = {1: "上半场", 2: "下半场", 3: "加时赛", 5: "点球大战"}
    rows = []  # (type, label/team, text, sort_order)
    prev_sort = None
    for sort_order, ev in all_events:
        # 时段分隔
        if sort_order != prev_sort:
            if prev_sort == 1 and sort_order == 2:
                rows.append(("sep", "", "中场休息", 1.5))
            if prev_sort in (1, 2) and sort_order == 3:
                rows.append(("sep", "", "常规时间 1-1 → 加时赛", 2.5))
            if prev_sort in (2, 3) and sort_order == 5:
                rows.append(("sep", "", "加时赛 1-1 → 点球大战", 4))
            rows.append(("label", "", period_names.get(sort_order, f"阶段{sort_order}"), sort_order))
            prev_sort = sort_order

        is_home = ev.team_id == raw.home_team.id
        is_pen = (sort_order == 5)
        minute_str = f"PK{ev.time_elapsed}" if is_pen else f"{ev.time_elapsed}'"
        if ev.time_extra and not is_pen:
            minute_str = f"{ev.time_elapsed}+{ev.time_extra}'"

        if ev.event_type == "Goal":
            detail = ev.detail or ""
            is_own = "owngoal" in detail
            is_pen_goal = "penalty" in detail or "pen_shootout" in detail
            is_miss = "miss" in detail and is_pen

            if is_own:
                icon = "OG"
            elif is_miss:
                icon = "X miss"
            elif is_pen_goal:
                icon = "G(P)" if not is_pen else "V"
            else:
                icon = "G"
            ps = _player_str(ev.player_name or "")
            text = f"{icon} {ps}"
            if ev.assist_name:
                text += f"\n   助攻: {_player_str(ev.assist_name)}"
            rows.append(("event", "home" if is_home else "away", text, sort_order, minute_str))

        elif ev.event_type == "Card":
            detail = ev.detail or ""
            icon = "RED" if "red" in detail else "YC"
            ps = _player_str(ev.player_name or "")
            text = f"{icon} {ps}"
            if ev.comments:
                text += f"\n   {ev.comments}"
            rows.append(("event", "home" if is_home else "away", text, sort_order, minute_str))

        elif ev.event_type == "subst":
            out_name = _player_str(ev.player_name or "")
            in_name = _player_str(ev.assist_name or "")
            text = f"SUB >{in_name}\n   <{out_name}"
            rows.append(("event", "home" if is_home else "away", text, sort_order, minute_str))

    # ── 计算尺寸 ──
    event_count = sum(1 for r in rows if r[0] == "event")
    row_h = 0.55  # 每行英寸
    total_h = max(10, len(rows) * row_h + 1.2)
    fig_w = 10

    fig, ax = plt.subplots(figsize=(fig_w, total_h), dpi=dpi)
    fig.patch.set_facecolor(BG_COLOR)
    ax.set_facecolor(BG_COLOR)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, len(rows))
    ax.axis("off")

    col_left = 0.15
    col_center = 4.9
    col_right = 5.1
    center_x = 5.0
    text_w_left = 4.2
    text_w_right = 4.2

    y = len(rows)
    for rtype, side, text, sorder, *rest in reversed(rows):
        y -= 1

        if rtype == "label":
            ax.axhline(y=y + 0.5, xmin=0.1, xmax=0.9, color=GRID_COLOR, linewidth=0.5)
            ax.text(center_x, y + 0.35, text, fontsize=10, color=TEXT_COLOR,
                    ha="center", va="center", fontweight="bold")
            ax.axhline(y=y + 0.65, xmin=0.1, xmax=0.9, color=GRID_COLOR, linewidth=0.5)
            continue

        if rtype == "sep":
            ax.axhline(y=y + 0.5, xmin=0.05, xmax=0.95, color=GRID_COLOR, linewidth=1, linestyle="--")
            ax.text(center_x, y + 0.35, text, fontsize=8, color="#7f8c8d",
                    ha="center", va="center")
            continue

        # 事件行
        minute_str = rest[0] if rest else ""
        is_home = (side == "home")
        color = HOME_COLOR if is_home else AWAY_COLOR

        # 竖线（覆盖整行）
        ax.axvline(x=center_x, ymin=(y + 0.05) / len(rows), ymax=(y + 0.95) / len(rows),
                   color=GRID_COLOR, linewidth=1.5, zorder=0)

        # 时间圆
        circle = plt.Circle((center_x, y + 0.5), 0.28, facecolor=TIMELINE_CARD_BG,
                            edgecolor=color, linewidth=1.8, zorder=5)
        ax.add_patch(circle)
        ax.text(center_x, y + 0.5, minute_str, fontsize=6, color=TEXT_COLOR,
                ha="center", va="center", fontweight="bold", zorder=6)

        # 事件卡片 — 主队在左、客队在右
        box_x = col_left if is_home else col_right
        box_w = text_w_left
        box_y = y + 0.1
        box_h = 0.75

        import matplotlib.patches as mpatches
        rect = mpatches.FancyBboxPatch((box_x, box_y), box_w, box_h,
                                       boxstyle="round,pad=0.08", linewidth=1.2,
                                       edgecolor=color, facecolor=TIMELINE_CARD_BG,
                                       zorder=3)
        ax.add_patch(rect)

        # 左侧色条
        ax.plot([box_x + 0.04, box_x + 0.04], [box_y + 0.08, box_y + box_h - 0.08],
                color=color, linewidth=2.5, zorder=4)

        # 文字
        lines = text.split("\n")
        tx = box_x + 0.3
        ty = box_y + box_h / 2
        if len(lines) > 1:
            ty += 0.12
        for li, line in enumerate(lines):
            fs = 6.5 if li == 0 else 5.5
            lc = TEXT_COLOR if li == 0 else "#95a5a6"
            ax.text(tx, ty - li * 0.22, line, fontsize=fs, color=lc,
                    va="center", zorder=5)

    # 标题
    score_text = f"{home_name} {raw.score.home} - {raw.score.away} {away_name}"
    ax.text(center_x, len(rows) + 0.3, score_text, fontsize=13, color=TEXT_COLOR,
            ha="center", va="bottom", fontweight="bold")
    ax.text(col_left + 1.5, len(rows) + 0.0, home_name, fontsize=9, color=HOME_COLOR, ha="center")
    ax.text(col_right + 1.5, len(rows) + 0.0, away_name, fontsize=9, color=AWAY_COLOR, ha="center")

    fig.savefig(output_path, dpi=dpi, bbox_inches="tight", facecolor=BG_COLOR,
                edgecolor="none")
    plt.close(fig)
    return output_path


def team_name(team_key: str, home_name: str, away_name: str) -> str:
    return home_name if team_key == "home" else away_name


# ═══════════════════════════════════════════════════════════════
# 全场事件时间轴
# ═══════════════════════════════════════════════════════════════

PLAYER_PHOTO_SIZE = 28  # px
TIMELINE_CENTER_WIDTH = 64  # px
TIMELINE_CARD_BG = "#162a38"
CARD_BORDER = "#1e3a4d"


def generate_event_timeline_html(raw, home_name: str, away_name: str) -> str:
    """生成全场事件纵向时间轴 HTML。
    
    从左到右三栏布局：主队事件 | 时间轴 | 客队事件。
    涵盖常规时间、加时赛、点球大战所有事件。
    换人展示双方球员姓名、号码、头像。
    """
    # ── 构建球员查找表 ──
    def _build_player_dict(players, team_key):
        d = {}
        for p in players:
            if isinstance(p, dict):
                raw_name = (p.get("name", "") or "").replace("\xa0", " ").strip()
                d[raw_name] = {
                    "number": str(p.get("number", "") or ""),
                    "photo": p.get("photo_url", "") or "",
                    "team": team_key,
                }
                orig = (p.get("name", "") or "").strip()
                if orig and orig not in d:
                    d[orig] = d[raw_name]
            else:
                raw_name = (p.name or "").replace("\xa0", " ").strip()
                d[raw_name] = {
                    "number": str(getattr(p, "number", "") or ""),
                    "photo": getattr(p, "photo_url", "") or "",
                    "team": team_key,
                }
                orig = (p.name or "").strip()
                if orig and orig not in d:
                    d[orig] = d[raw_name]
        return d

    home_players = _build_player_dict(raw.home_players, "home")
    away_players = _build_player_dict(raw.away_players, "away")
    all_players = {**home_players, **away_players}

    def _lookup(name: str) -> dict:
        if not name:
            return {}
        clean = name.replace("\xa0", " ").strip()
        return all_players.get(clean, all_players.get(name.strip(), {}))

    def _player_photo_html(info: dict) -> str:
        url = info.get("photo", "")
        if not url:
            return (f'<span style="display:inline-block;width:{PLAYER_PHOTO_SIZE}px;'
                    f'height:{PLAYER_PHOTO_SIZE}px;border-radius:50%;background:#2c3e50;'
                    f'text-align:center;line-height:{PLAYER_PHOTO_SIZE}px;font-size:10px;'
                    f'color:#7f8c8d">?</span>')
        return (f'<img src="{url}" '
                f'style="width:{PLAYER_PHOTO_SIZE}px;height:{PLAYER_PHOTO_SIZE}px;'
                f'border-radius:50%;object-fit:cover" '
                f'onerror="this.style.display=\'none\'" />')

    def _player_badge(name: str, info: dict) -> str:
        num = info.get("number", "")
        num_str = f" #{num}" if num else ""
        photo = _player_photo_html(info)
        return (f'<span style="display:inline-flex;align-items:center;gap:5px;white-space:nowrap">'
                f'{photo}'
                f'<span style="color:{TEXT_COLOR};font-size:11px">{name}{num_str}</span>'
                f'</span>')

    # ── 格式化单条事件为 HTML ──
    def _event_html(minute_str: str, icon: str, content: str, team_key: str, is_home: bool,
                    accent_color: str = TEXT_COLOR) -> str:
        side = "home" if is_home else "away"
        color = HOME_COLOR if is_home else AWAY_COLOR

        # 内容区
        content_html = (f'<div style="background:{TIMELINE_CARD_BG};border-radius:8px;'
                        f'padding:6px 10px;border-left:3px solid {color};min-height:38px">'
                        f'<div style="display:flex;align-items:flex-start;gap:6px">'
                        f'<span style="font-size:15px;flex-shrink:0">{icon}</span>'
                        f'<span style="color:{TEXT_COLOR};font-size:11px;line-height:1.5">{content}</span>'
                        f'</div></div>')

        # 时间徽章（z-index 高过竖线）
        time_badge = (f'<div style="background:{TIMELINE_CARD_BG};border-radius:50%;'
                      f'width:38px;height:38px;display:flex;align-items:center;justify-content:center;'
                      f'border:2px solid {color};flex-shrink:0;position:relative;z-index:2">'
                      f'<span style="color:{accent_color};font-size:10px;font-weight:bold">{minute_str}</span>'
                      f'</div>')

        # 左侧空位或事件
        left_cell = content_html if is_home else '<div></div>'
        right_cell = content_html if not is_home else '<div></div>'

        return (f'<div style="display:flex;align-items:stretch;min-height:50px">'
                f'<div style="flex:1;padding:4px 8px">{left_cell}</div>'
                f'<div style="width:{TIMELINE_CENTER_WIDTH}px;display:flex;flex-direction:column;'
                f'align-items:center;justify-content:center;flex-shrink:0;position:relative">'
                # 竖线 (z-index:1, 在徽章下面)
                f'<div style="position:absolute;top:0;bottom:0;left:50%;transform:translateX(-50%);'
                f'width:2px;background:{GRID_COLOR};z-index:1"></div>'
                f'{time_badge}'
                f'</div>'
                f'<div style="flex:1;padding:4px 8px">{right_cell}</div>'
                f'</div>')

    def _period_header(label: str, subtitle: str = "") -> str:
        sub = f'<div style="font-size:10px;color:#7f8c8d;margin-top:2px">{subtitle}</div>' if subtitle else ""
        return (f'<div style="display:flex;align-items:center;margin:12px 0 4px;gap:10px">'
                f'<div style="flex:1;height:1px;background:{GRID_COLOR}"></div>'
                f'<div style="text-align:center;flex-shrink:0">'
                f'<span style="color:{TEXT_COLOR};font-size:13px;font-weight:bold">{label}</span>'
                f'{sub}'
                f'</div>'
                f'<div style="flex:1;height:1px;background:{GRID_COLOR}"></div>'
                f'</div>')

    # ── 收集并排序所有事件 ──
    all_events = []
    for period in raw.periods:
        for ev in period.events:
            all_events.append((period.sort_order, ev))

    all_events.sort(key=lambda x: (x[0], x[1].time_elapsed, x[1].time_extra or 0))

    # ── 生成各期事件 HTML ──
    period_names = {1: "上半场", 2: "下半场", 3: "加时赛", 5: "点球大战"}
    current_period = None
    period_bodies = []
    current_body = []

    for sort_order, ev in all_events:
        if sort_order != current_period:
            if current_body:
                period_bodies.append((current_period, current_body))
            current_period = sort_order
            current_body = []

        is_home = ev.team_id == raw.home_team.id
        is_pen = (sort_order == 5)
        minute_str = f"PK{ev.time_elapsed}" if is_pen else f"{ev.time_elapsed}'"
        if ev.time_extra:
            minute_str = f"{ev.time_elapsed}+{ev.time_extra}'" if not is_pen else minute_str

        if ev.event_type == "Goal":
            detail = ev.detail or ""
            is_own = "owngoal" in detail
            is_pen_goal = "penalty" in detail or "pen_shootout" in detail

            if is_own:
                icon = "💥"
                accent = HIGHLIGHT_COLOR
            elif is_pen_goal and is_pen:
                icon = "✅" if "goal" in detail else "❌"
                accent = HOME_COLOR if "goal" in detail else HIGHLIGHT_COLOR
            elif is_pen_goal:
                icon = "⚽(P)"
                accent = HOME_COLOR
            else:
                icon = "⚽"
                accent = HOME_COLOR

            scorer_name = (ev.player_name or "").replace("\xa0", " ").strip()
            scorer_info = _lookup(scorer_name)
            content_parts = [_player_badge(scorer_name, scorer_info)]
            if ev.assist_name:
                assist_name = ev.assist_name.replace("\xa0", " ").strip()
                assist_info = _lookup(assist_name)
                content_parts.append(f'<span style="color:#7f8c8d;font-size:10px">助攻: '
                                     f'{_player_badge(assist_name, assist_info)}</span>')
            if is_pen and "miss" in detail:
                content_parts.append(f'<span style="color:{HIGHLIGHT_COLOR};font-size:10px">罚失</span>')
            current_body.append(_event_html(minute_str, icon, "".join(content_parts),
                                            "home" if is_home else "away", is_home, accent))

        elif ev.event_type == "Card":
            detail = ev.detail or ""
            if "red" in detail:
                icon = "🟥"
                accent = HIGHLIGHT_COLOR
            else:
                icon = "🟨"
                accent = "#f1c40f"
            player_name = (ev.player_name or "").replace("\xa0", " ").strip()
            player_info = _lookup(player_name)
            reason = ev.comments or ""
            content = _player_badge(player_name, player_info)
            if reason:
                content += f'<br><span style="color:#7f8c8d;font-size:10px">{reason}</span>'
            current_body.append(_event_html(minute_str, icon, content,
                                            "home" if is_home else "away", is_home, accent))

        elif ev.event_type == "subst":
            icon = "🔄"
            out_name = (ev.player_name or "").replace("\xa0", " ").strip()
            in_name = (ev.assist_name or "").replace("\xa0", " ").strip()
            out_info = _lookup(out_name)
            in_info = _lookup(in_name)
            content = (f'{_player_badge(in_name, in_info)}'
                       f'<span style="color:#7f8c8d;margin:0 4px;font-size:10px">↑</span>'
                       f'<br>'
                       f'{_player_badge(out_name, out_info)}'
                       f'<span style="color:#7f8c8d;margin:0 4px;font-size:10px">↓</span>')
            current_body.append(_event_html(minute_str, icon, content,
                                            "home" if is_home else "away", is_home, TEXT_COLOR))

    if current_body:
        period_bodies.append((current_period, current_body))

    # ── 组装最终 HTML ──
    html_parts = []
    # 比分头
    score_text = f"{home_name} {raw.score.home} - {raw.score.away} {away_name}"
    html_parts.append(
        f'<div style="text-align:center;padding:12px 0 6px">'
        f'<span style="color:{TEXT_COLOR};font-size:18px;font-weight:bold">{score_text}</span>'
        f'</div>'
    )

    prev_sort = None
    for sort_order, events in period_bodies:
        # 半场分隔
        if prev_sort == 1 and sort_order == 2:
            html_parts.append(_period_header("中场休息", ""))
        if prev_sort == 2 and sort_order == 3:
            html_parts.append(_period_header("常规时间 1-1", "加时赛"))
        if prev_sort in (2, 3) and sort_order == 5:
            html_parts.append(_period_header("1-1", "点球大战"))
        
        pname = period_names.get(sort_order, f"阶段{sort_order}")
        html_parts.append(_period_header(pname, ""))
        html_parts.extend(events)
        prev_sort = sort_order

    html = f"""
<div class="event-timeline" style="background:{BG_COLOR};border-radius:12px;padding:12px 8px 20px;
            border:1px solid {CARD_BORDER};max-width:900px;margin:0 auto">
  {"".join(html_parts)}
</div>"""

    return html


def save_timeline_png(raw, home_name: str, away_name: str, output_path: str) -> str:
    """Render event timeline HTML to a high-resolution PNG using headless Chromium.

    Args:
        raw: RawMatchData with events/players.
        home_name / away_name: Team names for the header.
        output_path: File path for the output PNG.

    Returns:
        The output_path on success.
    """
    html = generate_event_timeline_html(raw, home_name, away_name)
    wrapper_css = f"""
    <style>
      html, body {{ margin:0; padding:0; width:980px; background:{BG_COLOR}; }}
      body {{ display:flex; justify-content:center; min-height:100vh; padding:10px 0; }}
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
        page = browser.new_page(viewport={"width": 980, "height": 800}, device_scale_factor=2)
        page.set_content(full_html)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)
        page.screenshot(path=str(out), full_page=True)
        browser.close()

    return str(out)


def generate_all_tactical_charts(
    tactical_data: dict,
    home_name: str, away_name: str,
    images_dir: str, dpi: int = 150,
) -> dict:
    """生成所有战术图表 PNG。返回相对路径 dict。"""
    img = Path(images_dir)
    img.mkdir(parents=True, exist_ok=True)
    result = {}

    home_raw = tactical_data["home"]["tactical_raw"]
    away_raw = tactical_data["away"]["tactical_raw"]
    home_rel = tactical_data["home"]["match_relative"]

    # 雷达图
    radar_path = str(img / "tactical_radar.png")
    plot_tactical_radar(home_name, away_name, home_raw, away_raw, home_rel, radar_path, dpi)
    result["tactical_radar"] = radar_path

    # 射门 + xG/xGOT 累积图表
    shot_segments = tactical_data["match_flow"]["shot_segments"]
    shot_path = str(img / "tactical_shots.png")
    plot_shot_xg_timeline(home_name, away_name, shot_segments, shot_path, dpi)
    result["tactical_shots"] = shot_path

    # PPDA 全场柱状图
    ppda_data = tactical_data["match_flow"]["ppda"]
    ppda_path = str(img / "tactical_ppda.png")
    plot_ppda_bar(home_name, away_name,
                  ppda_data["home"]["full_match"],
                  ppda_data["away"]["full_match"],
                  ppda_path, dpi)
    result["tactical_ppda"] = ppda_path

    # 控球面积图
    possession_trend = tactical_data["match_flow"]["possession_trend"]
    poss_path = str(img / "tactical_possession.png")
    plot_possession_area(home_name, away_name,
                         possession_trend["home"], possession_trend["away"],
                         poss_path, dpi)
    result["tactical_possession"] = poss_path

    return result
