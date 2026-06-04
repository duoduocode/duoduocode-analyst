from __future__ import annotations

import re
from pathlib import Path

from src.collector.api_client import PlayerStats, RawMatchData
from src.composer.data_builder import _classify_signals, _build_phases
from src.engine.metrics import ComputedData, _stat
from src.engine.signals import SignalResult, _compute_king_scores

CATEGORY_CN = {
    "score_deviation": "比分背离",
    "efficiency_tear": "效率撕裂",
    "individual": "个人英雄",
    "structural": "结构问题",
    "narrative": "叙事钩子",
    "knockout": "淘汰赛专项",
    "trends": "趋势驱动",
    "event_trend": "事件x趋势",
    "player_contribution": "球员贡献",
}


def _player_photo_html(photo_url: str, size: int = 40) -> str:
    if not photo_url:
        return ""
    return (
        f'<img src="{photo_url}" width="{size}" height="{size}" '
        f'style="border-radius:50%;vertical-align:middle;margin-right:6px;" />'
    )


def _team_logo_html(logo_url: str, size: int = 24) -> str:
    if not logo_url:
        return ""
    return (
        f'<img src="{logo_url}" width="{size}" height="{size}" '
        f'style="vertical-align:middle;margin-right:4px;" />'
    )


def _parse_narrative_sections(text: str) -> dict:
    sections = {}
    pattern = r"【(.+?)】\s*\n(.*?)(?=\n【|\Z)"
    matches = re.findall(pattern, text, re.DOTALL)
    for title, content in matches:
        key = title.strip()
        sections[key] = content.strip()
    if not sections:
        sections["全文"] = text.strip()
    return sections


# ────────────────────────────────────────────────
# Phase arc: the match timeline
# ────────────────────────────────────────────────

def _generate_phases_arc_html(raw: RawMatchData, signals: list[SignalResult]) -> str:
    """Generate a visual match timeline with events and signals per phase."""
    time_signals, _global_signals = _classify_signals(signals)
    phases = _build_phases(raw, time_signals)

    # Filter to phases that have content
    active_phases = [p for p in phases if p["events"] or p["signals"] or p["stats"]]
    if not active_phases:
        return ""

    md = "## 比赛弧线\n\n"
    md += "> 按时间线展示关键事件与关联信号，还原比赛推进过程。\n\n"

    for ph in active_phases:
        emoji = {"开局试探": "🌅", "中场拉锯": "⚔️", "半场收官": "⏸️",
                 "下半场调整": "🔄", "决战阶段": "🔥", "常规时间冲刺": "⏰",
                 "冲刺收官": "⏰", "加时上半场": "💪", "加时下半场": "🥵",
                 "点球大战": "🎯"}.get(ph["label"], "📌")

        md += f"### {emoji} {ph['start']}' - {ph['end']}'  {ph['label']}\n\n"

        if ph["stats"]:
            md += f"> {ph['stats']}\n\n"

        if ph["events"]:
            for ev in ph["events"]:
                icon = {"进球": "⚽", "纪律": "🟨", "换人": "🔄", "VAR": "📺",
                        "射门": "🎯"}.get(ev["type"], "📌")
                md += f"- {icon} **{ev['minute']}'** {ev['team']} — {ev['description']}\n"
            md += "\n"

        if ph["signals"]:
            md += "**信号标注**:\n"
            for sig in ph["signals"]:
                md += (
                    f"- `{sig['name']}` "
                    f"[{sig['category']}] "
                    f"{sig['hint'][:80]}...\n"
                )
            md += "\n"

    return md


# ────────────────────────────────────────────────
# Signal appendix: compact table
# ────────────────────────────────────────────────

def _generate_signal_appendix_html(
    raw: RawMatchData, signals: list[SignalResult]
) -> str:
    if not signals:
        return ""

    md = "## 信号附录\n\n"
    md += "> 52个检测器的结果速览，触发信号按强度排序。\n\n"
    md += "| # | 信号 | 类别 | 强度 | 触发? |\n"
    md += "|---|------|------|:----:|:---:|\n"

    for i, sig in enumerate(signals, 1):
        cat_cn = CATEGORY_CN.get(sig.category, sig.category)
        bar_len = min(int(sig.strength * 10), 10)
        bar = "█" * bar_len + "░" * (10 - bar_len)
        triggered = "✓" if sig.strength > 0 else "—"
        md += f"| {i} | `{sig.name}` | {cat_cn} | `{bar}` | {triggered} |\n"

    md += "\n"
    return md


# ────────────────────────────────────────────────
# Key events timeline
# ────────────────────────────────────────────────

def _generate_key_events_html(
    events: list, home_name: str, away_name: str
) -> str:
    key_events = [e for e in events if e.event_type in ("Goal", "Card", "subst")
                  and e.detail not in ("pen_shootout_goal", "pen_shootout_miss")]
    if not key_events:
        return ""

    md = "## 关键事件时间线\n\n"
    for ev in key_events:
        icon = {"Goal": "⚽", "Card": "🟨", "subst": "🔄"}.get(ev.event_type, "📌")
        desc = f"{ev.player_name}"
        if ev.assist_name and ev.event_type == "Goal":
            desc += f" (助: {ev.assist_name})"
        if ev.detail == "goal_penalty":
            desc += " [点球]"
        elif ev.detail == "missed_penalty":
            desc += " [点球罚失]"
        elif ev.detail == "owngoal":
            desc += " [乌龙]"
        md += f"- {icon} **{ev.time_elapsed}'** {ev.team_name}: {desc}\n"
    md += "\n"

    return md


# ────────────────────────────────────────────────
# Player ratings table
# ────────────────────────────────────────────────

def _generate_players_html(
    raw: RawMatchData, section_title: str = "## 球员评分\n\n"
) -> str:
    md = section_title

    for players, team_name, team_logo in [
        (raw.home_players, raw.home_team.name, raw.home_team.logo_url),
        (raw.away_players, raw.away_team.name, raw.away_team.logo_url),
    ]:
        logo = _team_logo_html(team_logo)
        md += f"### {logo} {team_name}\n\n"
        md += (
            "| 球员 | 位置 | 评分 | 分钟 | 进球 | 助攻 | "
            "射正 | 关键传球 | 抢断 | 过人 | 传球% |\n"
        )
        md += (
            "|------|:--:|:----:|:----:|:----:|:----:|"
            ":----:|:--------:|:----:|:----:|:-----:|\n"
        )

        sorted_players = sorted(players, key=lambda p: p.minutes_played, reverse=True)
        for p in sorted_players:
            if p.minutes_played <= 0:
                continue
            photo = _player_photo_html(p.photo_url, 24)
            rating_str = f"{p.rating:.1f}" if p.rating is not None else "-"
            pass_acc = f"{p.passes_accuracy:.0f}" if p.passes_accuracy else "-"
            md += (
                f"| {photo} {p.name} | {p.position} | {rating_str} | "
                f"{p.minutes_played} | {p.goals} | {p.assists} | "
                f"{p.shots_on} | {p.passes_key} | {p.tackles_total} | "
                f"{p.dribbles_success} | {pass_acc} |\n"
            )
        md += "\n"

    return md


# ────────────────────────────────────────────────
# Player contribution kings (进攻王/防守王/均衡王)
# ────────────────────────────────────────────────

def _generate_kings_html(raw: RawMatchData) -> str:
    """Generate Top 3 offensive/defensive/balanced contribution tables for both teams."""
    king_data = _compute_king_scores(raw)

    md = "## 球员贡献排行榜\n\n"
    md += (
        "> 进攻分 = (进球x25 + 助攻x15 + xGx20 + 射正x5 + 关键传球x6 + 过人x5 + 三区传球x1.5) x 分钟系数 + 事件加成\n"
        "> 防守分 = (成功抢断x10 + 拦截x8 + 解围x3 + 封堵x8 + 球权回收x4 + 赢得对抗x4) x 分钟系数\n"
        "> 均衡分 = 2 x 进攻分 x 防守分 / (进攻分 + 防守分)，门将不参与排名\n\n"
    )

    categories = [
        ("进攻王", "attack", "进攻分", "{:.1f}"),
        ("防守王", "defense", "防守分", "{:.1f}"),
        ("均衡王", "balanced", "均衡分", "{:.1f}"),
    ]

    for cat_label, key, col_label, fmt in categories:
        md += f"### {cat_label} Top 3\n\n"

        for team_name in [raw.home_team.name, raw.away_team.name]:
            td = king_data.get(team_name, {})
            outfield = [p for p in td.get("players", []) if p["pos"] != "G"]
            top3 = sorted(outfield, key=lambda x: x[key], reverse=True)[:3]

            if not top3:
                continue

            md += f"**{team_name}**\n\n"

            if key == "balanced":
                md += "| 排名 | 球员 | 位置 | 评分 | 出场 | 进攻分 | 防守分 | 均衡分 |\n"
                md += "|:---:|------|:---:|:---:|:---:|:---:|:---:|:---:|\n"
                for i, p in enumerate(top3, 1):
                    md += (
                        f"| {i} | {p['name']} | {p['pos']} | {p['rating']} | {p['mins']}' | "
                        f"{p['attack']:.1f} | {p['defense']:.1f} | {p['balanced']:.1f} |\n"
                    )
            else:
                md += f"| 排名 | 球员 | 位置 | 评分 | 出场 | {col_label} |\n"
                md += "|:---:|------|:---:|:---:|:---:|:---:|\n"
                for i, p in enumerate(top3, 1):
                    md += (
                        f"| {i} | {p['name']} | {p['pos']} | {p['rating']} | {p['mins']}' | "
                        f"{p[key]:.1f} |\n"
                    )
            md += "\n"

    return md


# ────────────────────────────────────────────────
# Main report builder
# ────────────────────────────────────────────────

def build_report(
    raw: RawMatchData,
    computed: ComputedData,
    narrative_text: str,
    signals: list[SignalResult],
    image_paths: dict,
    output_dir: str,
) -> str:
    hs = raw.home_stats
    aws = raw.away_stats
    home_logo = _team_logo_html(raw.home_team.logo_url)
    away_logo = _team_logo_html(raw.away_team.logo_url)

    sections = _parse_narrative_sections(narrative_text)

    # ── Header ──
    md = (
        f"# {home_logo} {raw.home_team.name} "
        f"{raw.score.home}-{raw.score.away} "
        f"{raw.away_team.name} {away_logo}\n\n"
    )

    title = sections.get("标题", "")
    if title:
        md += f"> ## {title}\n\n"

    intro = sections.get("导语", "")
    if intro:
        md += f"> {intro}\n\n"

    md += "---\n\n"

    # ── 1. LLM 比赛复盘（核心叙事）──
    replay = sections.get("比赛复盘", "")
    if replay:
        md += "## 比赛复盘\n\n"
        md += f"{replay}\n\n"
        md += "---\n\n"

    # ── 2. 核心数据面板 ──
    home_xg = round(sum(p.xg for p in raw.home_players), 2)
    away_xg = round(sum(p.xg for p in raw.away_players), 2)

    md += "## 核心数据面板\n\n"
    md += f"| 指标 | {raw.home_team.name} | {raw.away_team.name} |\n"
    md += "|---|---:|---:|\n"
    md += f"| 控球率 | {int(float(_stat(hs, 'Ball Possession', default=50)))}% | {int(float(_stat(aws, 'Ball Possession', default=50)))}% |\n"
    md += f"| 预期进球 (xG) | {home_xg} | {away_xg} |\n"
    md += f"| 射门 / 射正 | {int(float(_stat(hs, 'Total Shots', default=0)))} / {int(float(_stat(hs, 'Shots on Goal', default=0)))} | {int(float(_stat(aws, 'Total Shots', default=0)))} / {int(float(_stat(aws, 'Shots on Goal', default=0)))} |\n"
    md += f"| 绝佳机会 | {int(float(_stat(hs, 'Big Chances Created', default=0)))} | {int(float(_stat(aws, 'Big Chances Created', default=0)))} |\n"
    md += f"| 禁区内射门 | {int(float(_stat(hs, 'Shots insidebox', default=0)))} | {int(float(_stat(aws, 'Shots insidebox', default=0)))} |\n"
    md += f"| 传球成功率 | {int(float(_stat(hs, 'Passes %', default=75)))}% | {int(float(_stat(aws, 'Passes %', default=75)))}% |\n"
    md += f"| 角球 | {int(float(_stat(hs, 'Corner Kicks', default=0)))} | {int(float(_stat(aws, 'Corner Kicks', default=0)))} |\n"
    md += f"| 抢断 / 犯规 / 黄牌 | {int(float(_stat(hs, 'Tackles', default=0)))} / {int(float(_stat(hs, 'Fouls', default=0)))} / {int(float(_stat(hs, 'Yellow Cards', default=0)))} | {int(float(_stat(aws, 'Tackles', default=0)))} / {int(float(_stat(aws, 'Fouls', default=0)))} / {int(float(_stat(aws, 'Yellow Cards', default=0)))} |\n"
    md += f"| 传中 / 头球 | {int(float(_stat(hs, 'Crosses', default=0)))} / {int(float(_stat(hs, 'Successful Headers', default=0)))} | {int(float(_stat(aws, 'Crosses', default=0)))} / {int(float(_stat(aws, 'Successful Headers', default=0)))} |\n"
    home_rec = int(float(_stat(hs, "Ball Recoveries", default=0))) or sum(
        p.ball_recoveries for p in raw.home_players
    )
    away_rec = int(float(_stat(aws, "Ball Recoveries", default=0))) or sum(
        p.ball_recoveries for p in raw.away_players
    )
    md += f"| 球权回收 | {home_rec} | {away_rec} |\n\n"

    if computed:
        md += f"| 自创指标 | {raw.home_team.name} | {raw.away_team.name} |\n"
        md += "|---|---:|---:|\n"
        md += f"| CI 控制指数 | {computed.home_ci} | {computed.away_ci} |\n"
        md += f"| TCR 威胁转化率 | {computed.home_tcr} | {computed.away_tcr} |\n"
        md += f"| PE 压迫效率 | {computed.home_pe} | {computed.away_pe} |\n"
        if hasattr(computed, "ldi_result") and computed.ldi_result:
            ld = computed.ldi_result
            md += (
                f"| LDI 运气偏离 | {ld.get('ldi', '-')} "
                f"({ld.get('interpretation', '')}) | — |\n"
            )
        md += "\n"

    # ── 3. 比赛弧线（phase timeline）──
    arc_html = _generate_phases_arc_html(raw, signals)
    if arc_html:
        md += arc_html
        md += "---\n\n"

    # ── 3.5. 球员贡献排行榜 ──
    kings_html = _generate_kings_html(raw)
    if kings_html:
        md += kings_html
        md += "---\n\n"

    # ── 4. Momentum chart ──
    if image_paths.get("momentum"):
        md += f"![动量曲线]({image_paths['momentum']})\n\n"

    # ── 5. 数据深挖 ──
    deep_dive = sections.get("数据深挖", "")
    if deep_dive:
        md += "## 数据深挖\n\n"
        md += f"{deep_dive}\n\n"
        md += "---\n\n"

    # ── 6. Shot map ──
    if image_paths.get("shots"):
        md += f"![射门分布]({image_paths['shots']})\n\n"

    # ── 7. 战术点评 ──
    tactics = sections.get("战术点评", "")
    if tactics:
        md += "## 战术点评\n\n"
        md += f"{tactics}\n\n"

        if image_paths.get("pass_home"):
            md += f"![传球网络 - {raw.home_team.name}]({image_paths['pass_home']})\n\n"
        if image_paths.get("pass_away"):
            md += f"![传球网络 - {raw.away_team.name}]({image_paths['pass_away']})\n\n"
        md += "---\n\n"

    # ── 8. 球员特写 ──
    players_section = sections.get("球员特写", "")
    if players_section:
        md += "## 球员特写\n\n"
        md += f"{players_section}\n\n"

        if image_paths.get("radar_hidden"):
            md += f"![隐性MVP雷达]({image_paths['radar_hidden']})\n\n"

        md += "---\n\n"

    # ── 9. 关键事件时间线 ──
    events_html = _generate_key_events_html(
        raw.events, raw.home_team.name, raw.away_team.name
    )
    if events_html:
        md += events_html
        md += "---\n\n"

    # ── 10. 信号附录 ──
    sig_appendix = _generate_signal_appendix_html(raw, signals)
    if sig_appendix:
        md += sig_appendix
        md += "---\n\n"

    # ── 11. 球员评分表 ──
    md += _generate_players_html(raw)

    # ── 12. 总结 ──
    verdict = sections.get("总结", "")
    if verdict:
        md += "---\n\n"
        md += "## 总结\n\n"
        md += f"> {verdict}\n\n"

    # ── 13. xG 模拟图 ──
    if image_paths.get("xg_hist"):
        md += f"![xG模拟]({image_paths['xg_hist']})\n\n"

    # Footer
    if image_paths.get("subs_home"):
        md += f"![换人效果]({image_paths['subs_home']})\n\n"

    md += "\n*报告由 AI 足球分析员自动生成 | 数据来源：SportMonks*\n"

    # ── Write files ──
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    report_path = out_dir / "report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(md)

    html_path = out_dir / "report.html"
    try:
        import markdown

        html_content = markdown.markdown(md, extensions=["tables", "fenced_code"])
        html_wrapper = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
body {{ font-family: 'Microsoft YaHei', 'PingFang SC', sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; line-height: 1.8; }}
img {{ max-width: 100%; }}
table {{ border-collapse: collapse; width: 100%; font-size: 14px; }}
td, th {{ border: 1px solid #ddd; padding: 6px 8px; text-align: center; }}
th {{ background: #f5f5f5; }}
blockquote {{ border-left: 4px solid #2ecc71; padding-left: 16px; color: #555; }}
h1 img, h3 img {{ border-radius: 50%; vertical-align: middle; }}
h2 {{ border-bottom: 2px solid #2ecc71; padding-bottom: 6px; margin-top: 32px; }}
h3 {{ margin-top: 24px; }}
</style></head><body>{html_content}</body></html>"""
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_wrapper)
    except Exception:
        pass

    return report_path


def _event_timeline_sided_html(
    events: list, home_name: str, away_name: str, home_id: int, away_id: int
) -> str:
    """Timeline with center line, home events on the left, away on the right."""
    key_events = [
        e for e in events
        if e.event_type in ("Goal", "Card", "subst")
        and e.detail not in ("pen_shootout_goal", "pen_shootout_miss")
    ]
    if not key_events:
        return ""

    key_events.sort(key=lambda e: (e.period_id or 0, e.time_elapsed or 0))

    html = '<div class="tl">\n'
    # center line is drawn by CSS ::before on .tl

    for ev in key_events:
        mi = ev.time_elapsed or "?"
        team_name = ev.team_name or ""
        is_home = ev.team_id == home_id
        side_class = "tl-left" if is_home else "tl-right"

        icon_map = {"Goal": "⚽", "Card": "🟨", "subst": "🔄", "VAR": "📺"}
        icon = icon_map.get(ev.event_type, "📌")

        desc = ev.player_name or ""
        if ev.event_type == "Goal":
            if ev.assist_name:
                desc += f'&nbsp;<small>(A: {ev.assist_name})</small>'
            if ev.detail == "goal_penalty":
                desc += '&nbsp;<small>[P]</small>'
            elif ev.detail == "missed_penalty":
                desc += '&nbsp;<small>[罚失]</small>'
        elif ev.event_type == "subst":
            player_in = ev.assist_name or "?"
            player_out = ev.player_name or "?"
            desc = f'{player_in} ↑<br/><small>↓ {player_out}</small>'
        elif ev.event_type == "Card":
            color = {"yellowcard": "#f0c040", "redcard": "#e04040",
                     "yellowredcard": "#e04040"}.get(ev.detail, "#f0c040")
            icon = f'<span style="color:{color}">■</span>'

        card_color = "#2ecc71" if is_home else "#3498db"
        border_side = "left" if not is_home else "right"

        html += f'  <div class="{side_class} tl-item">\n'
        html += f'    <div class="tl-icon">{icon}</div>\n'
        html += f'    <div class="tl-content" style="border-{border_side}:3px solid {card_color}">\n'
        html += f'      <span class="tl-time">{mi}\'</span>&nbsp;{desc}\n'
        html += f'      <div class="tl-team">{team_name}</div>\n'
        html += f'    </div>\n'
        html += f'  </div>\n'

    html += '</div>'
    return html


def build_report_v3_html(
    raw: RawMatchData,
    narrative_text: str,
    image_paths: dict,
    output_dir: str,
    hard_facts=None,
    sub_impacts: list[dict] = None,
    signals: list[SignalResult] = None,
    computed = None,
) -> str:
    """v3 HTML report: direct HTML generation with rich styling and visuals."""

    hs = raw.home_stats
    aws = raw.away_stats
    home_logo_url = raw.home_team.logo_url
    away_logo_url = raw.away_team.logo_url
    home_name = raw.home_team.name
    away_name = raw.away_team.name

    sections = _parse_narrative_sections(narrative_text)

    home_xg = round(sum(p.xg for p in raw.home_players), 2)
    away_xg = round(sum(p.xg for p in raw.away_players), 2)

    stage = raw.stage_info or {}
    venue = raw.venue_info or {}
    league_name = stage.get("name", "")
    venue_name = venue.get("name", "未知球场")
    city_name = venue.get("city_name", "")
    venue_img = venue.get("image_path", "") if isinstance(venue, dict) else ""

    # ── HTML build ──
    H = []  # HTML lines
    H.append('<!DOCTYPE html>')
    H.append('<html lang="zh-CN"><head><meta charset="utf-8">')
    H.append('<meta name="viewport" content="width=device-width, initial-scale=1.0">')
    H.append(f'<title>{home_name} vs {away_name} — 比赛报告</title>')
    H.append('<style>')
    H.append('*{margin:0;padding:0;box-sizing:border-box}')
    H.append('body{font-family:"Microsoft YaHei","PingFang SC",sans-serif;background:#0f1923;color:#d0d8e0;line-height:1.8}')
    H.append('.container{max-width:960px;margin:0 auto;padding:20px}')
    H.append('img{max-width:100%;border-radius:4px}')
    H.append('h1{color:#fff;font-size:24px;text-align:center;margin:10px 0}')
    H.append('h2{color:#e0e8f0;font-size:20px;border-bottom:2px solid #2ecc71;padding-bottom:8px;margin:32px 0 16px}')
    H.append('h3{color:#c0d0e0;font-size:16px;margin:20px 0 8px}')
    H.append('.scoreboard{text-align:center;margin:20px 0}')
    H.append('.scoreboard .teams{font-size:22px;color:#fff}')
    H.append('.scoreboard .teams img{width:48px;height:48px;border-radius:50%;vertical-align:middle;margin:0 12px}')
    H.append('.scoreboard .score{font-size:40px;font-weight:bold;color:#2ecc71;margin:0 16px}')
    H.append('.meta{text-align:center;color:#8ab4d6;font-size:14px;margin:8px 0}')
    H.append('.meta img{margin:12px 0;max-height:200px;object-fit:cover}')
    H.append('.stat-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:16px 0}')
    H.append('.stat-row{display:flex;justify-content:space-between;align-items:center;padding:6px 12px;background:#162a38;border-radius:6px}')
    H.append('.stat-label{color:#6b8fa3;font-size:13px}')
    H.append('.stat-vals{font-size:14px;font-weight:bold}')
    H.append('.stat-home{color:#2ecc71}')
    H.append('.stat-away{color:#3498db}')
    H.append('.insight-box{background:#162a38;border-left:4px solid #2ecc71;padding:12px 16px;margin:16px 0;border-radius:0 8px 8px 0}')
    H.append('.insight-box li{color:#bcd4e6;font-size:14px;margin:4px 0}')
    H.append('.tl{position:relative;padding:10px 0}')
    H.append('.tl:before{content:"";position:absolute;left:50%;top:0;bottom:0;width:2px;background:#3a5068}')
    H.append('.tl-item{position:relative;display:flex;align-items:flex-start;margin:12px 0}')
    H.append('.tl-left{flex-direction:row;padding-right:calc(50% + 20px)}')
    H.append('.tl-right{flex-direction:row-reverse;padding-left:calc(50% + 20px)}')
    H.append('.tl-icon{font-size:20px;min-width:36px;text-align:center}')
    H.append('.tl-content{background:#162a38;border-radius:8px;padding:8px 12px;font-size:13px;max-width:90%}')
    H.append('.tl-time{color:#2ecc71;font-weight:bold;font-size:12px}')
    H.append('.tl-team{font-size:11px;color:#6b8fa3;margin-top:2px}')
    H.append('.tl-home .tl-content{border-right:3px solid #2ecc71}')  # fixed: use border-right on item container
    H.append('.tl-away .tl-content{border-left:3px solid #3498db}')
    H.append('table{width:100%;border-collapse:collapse;margin:12px 0;font-size:13px}')
    H.append('td,th{padding:8px 10px;text-align:center;border-bottom:1px solid #1e3a4d}')
    H.append('th{background:#1e3a4d;color:#8ab4d6;font-weight:bold;font-size:12px}')
    H.append('tr:nth-child(even){background:#12222e}')
    H.append('.player-photo{border-radius:50%;width:28px;height:28px;vertical-align:middle;margin-right:4px}')
    H.append('.kings{display:grid;grid-template-columns:repeat(2,1fr);gap:16px;margin:16px 0}')
    H.append('.kings h4{color:#8ab4d6;margin:8px 0 4px;text-align:center}')
    H.append('.footer{text-align:center;color:#4a6a80;font-size:12px;margin:30px 0 10px;border-top:1px solid #1e3a4d;padding-top:16px}')
    H.append('@media(max-width:700px){.kings{grid-template-columns:1fr}}')
    H.append('</style></head><body><div class="container">')

    # ── Header / Scoreboard ──
    H.append(f'<h1>{league_name}</h1>' if league_name else '')
    H.append('<div class="scoreboard">')
    H.append(f'<span class="teams"><img src="{home_logo_url}" alt="">{home_name}</span>')
    H.append(f'<span class="score">{raw.score.home} - {raw.score.away}</span>')
    H.append(f'<span class="teams">{away_name}<img src="{away_logo_url}" alt=""></span>')
    H.append('</div>')
    H.append(f'<div class="meta">📍 {venue_name}，{city_name}</div>')

    # Venue photo
    if venue_img:
        H.append(f'<div class="meta"><img src="{venue_img}" alt="球场"></div>')

    # Score details
    score_line = f'⏱️ 半场 {raw.score.halftime_home}-{raw.score.halftime_away}'
    if raw.score.extratime_home is not None:
        score_line += f' | 加时 {raw.score.extratime_home}-{raw.score.extratime_away}'
    if raw.score.penalty_home is not None:
        score_line += f' | 点球 {raw.score.penalty_home}-{raw.score.penalty_away}'
    H.append(f'<div class="meta">{score_line}</div>')

    # ── Section 1: 封面导语 ──
    cover = sections.get("封面导语", "")
    if cover:
        H.append(f'<div class="insight-box" style="border-left-color:#3498db;font-size:15px;"><p>{cover}</p></div>')

    # Lineup image
    if image_paths.get("lineup"):
        H.append(f'<p style="text-align:center"><img src="{image_paths["lineup"]}" alt="首发阵容"></p>')

    # ── 核心数据面板 ──
    H.append('<h2>核心数据面板</h2>')
    stats_pairs = [
        ("控球率", f'{int(float(_stat(hs,"Ball Possession",default=50)))}%', f'{int(float(_stat(aws,"Ball Possession",default=50)))}%'),
        ("预期进球 xG", str(home_xg), str(away_xg)),
        ("射门 / 射正", f'{int(float(_stat(hs,"Total Shots")))}/{int(float(_stat(hs,"Shots on Goal")))}', f'{int(float(_stat(aws,"Total Shots")))}/{int(float(_stat(aws,"Shots on Goal")))}'),
        ("绝佳机会", str(int(float(_stat(hs,"Big Chances Created")))), str(int(float(_stat(aws,"Big Chances Created"))))),
        ("禁区内射门", str(int(float(_stat(hs,"Shots insidebox")))), str(int(float(_stat(aws,"Shots insidebox"))))),
        ("传球成功率", f'{int(float(_stat(hs,"Passes %",default=75)))}%', f'{int(float(_stat(aws,"Passes %",default=75)))}%'),
        ("角球", str(int(float(_stat(hs,"Corner Kicks")))), str(int(float(_stat(aws,"Corner Kicks"))))),
        ("抢断/犯规/黄牌", f'{int(float(_stat(hs,"Tackles")))}/{int(float(_stat(hs,"Fouls")))}/{int(float(_stat(hs,"Yellow Cards")))}', f'{int(float(_stat(aws,"Tackles")))}/{int(float(_stat(aws,"Fouls")))}/{int(float(_stat(aws,"Yellow Cards")))}'),
    ]
    H.append('<div class="stat-grid">')
    for label, hv, av in stats_pairs:
        H.append(f'<div class="stat-row"><span class="stat-label">{label}</span><span class="stat-vals"><span class="stat-home">{hv}</span> &nbsp; <span class="stat-away">{av}</span></span></div>')
    H.append('</div>')

    # ── 数据洞察摘要 (enriched) ──
    if hard_facts:
        H.append('<div class="insight-box"><h3 style="color:#2ecc71;margin-bottom:8px">📊 数据洞察摘要</h3><ul>')
        hf = hard_facts
        if hf.possession_xg_ratio_home:
            H.append(f'<li><b>控球有效性</b>：{home_name} 每1%控球产出 <span class="stat-home">{hf.possession_xg_ratio_home:.3f}</span> xG，{away_name} <span class="stat-away">{hf.possession_xg_ratio_away:.3f}</span> xG。{"主队控球更有实质性威胁" if hf.possession_xg_ratio_home > hf.possession_xg_ratio_away else "客队控球效率更高"}</li>')
        if hf.xg_overperformer:
            H.append(f'<li><b>xG背离</b>：{hf.xg_overperformer} 实际进球超预期（{home_name} {hf.xg_deviation_home:+.2f}，{away_name} {hf.xg_deviation_away:+.2f}）</li>')
        r = hf.attack_rhythm
        if r and r.get("home_shots_ratio", 0) > 1.5:
            H.append(f'<li><b>射门节奏飙升</b>：{home_name} 上下半场射门 {int(r.get("home_shots_h1",0))}→{int(r.get("home_shots_h2",0))}，增长 <b>{r["home_shots_ratio"]}x</b></li>')
        if r and r.get("away_shots_ratio", 0) > 1.5:
            H.append(f'<li><b>射门节奏飙升</b>：{away_name} 上下半场射门 {int(r.get("away_shots_h1",0))}→{int(r.get("away_shots_h2",0))}，增长 <b>{r["away_shots_ratio"]}x</b></li>')
        if hf.passing_profile:
            pp = hf.passing_profile
            H.append(f'<li><b>传球风格</b>：{home_name} 长传占比 {pp.get("home_long_ball_pct",0)}%、传中 {pp.get("home_cross_pct",0)}% | {away_name} 长传 {pp.get("away_long_ball_pct",0)}%、传中 {pp.get("away_cross_pct",0)}%</li>')
        if hf.defensive_decay.get("home_decay_pct"):
            dd = hf.defensive_decay
            H.append(f'<li><b>防守衰减</b>：{home_name} {dd.get("home_decay_pct","?")}% | {away_name} {dd.get("away_decay_pct","?")}%</li>')
        if hf.player_efficiency:
            pe = hf.player_efficiency
            if pe.get("top_xg90"):
                top = pe["top_xg90"][0]
                H.append(f'<li><b>xG之王</b>：{top["name"]} 每90分钟xG {top["xg_per_90"]}，全场最高</li>')
        H.append('</ul></div>')

    # Efficiency comparison chart
    if image_paths.get("efficiency"):
        H.append(f'<p style="text-align:center"><img src="{image_paths["efficiency"]}" alt="效率对比"></p>')

    # ── Section 2: 比赛节奏 ──
    rhythm = sections.get("比赛节奏", "")
    if rhythm:
        H.append('<h2>📈 比赛节奏</h2>')
        H.append(f'<p>{rhythm}</p>')
        if image_paths.get("momentum"):
            H.append(f'<p style="text-align:center"><img src="{image_paths["momentum"]}" alt="趋势走势"></p>')

    # ── Section 3: 效率悖论 ──
    efficiency = sections.get("效率悖论", "")
    if efficiency:
        H.append('<h2>⚡ 效率悖论</h2>')
        H.append(f'<p>{efficiency}</p>')
        if image_paths.get("xg_hist"):
            H.append(f'<p style="text-align:center"><img src="{image_paths["xg_hist"]}" alt="xG模拟"></p>')

    # ── Section 4: 战术解码 ──
    tactics = sections.get("战术解码", "")
    if tactics:
        H.append('<h2>🧩 战术解码</h2>')
        H.append(f'<p>{tactics}</p>')
        if image_paths.get("pass_home"):
            H.append(f'<p style="text-align:center"><img src="{image_paths["pass_home"]}" alt="传球网络-主队"></p>')
        if image_paths.get("pass_away"):
            H.append(f'<p style="text-align:center"><img src="{image_paths["pass_away"]}" alt="传球网络-客队"></p>')

    # ── Section 5: 人物志 + 进攻/防守/均衡之王 ──
    characters = sections.get("人物志", "")
    if characters:
        H.append('<h2>🎭 人物志</h2>')
        H.append(f'<p>{characters}</p>')

    # Kings table (replaces radar)
    H.append('<h3>进攻/防守/均衡之王 Top 3</h3>')
    king_data = _compute_king_scores(raw)

    categories = [
        ("攻击之王", "attack", "进攻分"),
        ("防守之王", "defense", "防守分"),
        ("均衡之王", "balanced", "均衡分"),
    ]
    for cat_label, key, col_label in categories:
        H.append(f'<h4 style="color:#2ecc71;text-align:center;margin-top:12px">{cat_label}</h4>')
        H.append('<div class="kings">')
        for team_name in [home_name, away_name]:
            td = king_data.get(team_name, {})
            outfield = [p for p in td.get("players", []) if p["pos"] != "G"]
            top3 = sorted(outfield, key=lambda x: x[key], reverse=True)[:3]
            if not top3:
                continue
            H.append(f'<div><h4 style="color:{"#2ecc71" if team_name == home_name else "#3498db"}">{team_name}</h4>')
            if key == "balanced":
                H.append('<table><tr><th>#</th><th>球员</th><th>位</th><th>评分</th><th>出场</th><th>进攻分</th><th>防守分</th><th>均衡分</th></tr>')
                for i, p in enumerate(top3, 1):
                    H.append(f'<tr><td>{i}</td><td>{p["name"]}</td><td>{p["pos"]}</td><td>{p["rating"]}</td><td>{p["mins"]}\'</td><td>{p["attack"]:.1f}</td><td>{p["defense"]:.1f}</td><td style="color:#2ecc71;font-weight:bold">{p["balanced"]:.1f}</td></tr>')
            else:
                H.append(f'<table><tr><th>#</th><th>球员</th><th>位</th><th>评分</th><th>出场</th><th>{col_label}</th></tr>')
                for i, p in enumerate(top3, 1):
                    H.append(f'<tr><td>{i}</td><td>{p["name"]}</td><td>{p["pos"]}</td><td>{p["rating"]}</td><td>{p["mins"]}\'</td><td style="color:#2ecc71;font-weight:bold">{p[key]:.1f}</td></tr>')
            H.append('</table></div>')
        H.append('</div>')

    # Sub impacts chart
    if image_paths.get("subs"):
        H.append(f'<p style="text-align:center"><img src="{image_paths["subs"]}" alt="换人效果"></p>')

    # ── Section 6: 数据深潜 ──
    deep_dive = sections.get("数据深潜", "")
    if deep_dive:
        H.append('<h2>🔬 数据深潜</h2>')
        H.append(f'<p>{deep_dive}</p>')

    # Player ratings table
    H.append('<h3>球员评分全表</h3>')
    for players, team_name, logo in [(raw.home_players, home_name, home_logo_url), (raw.away_players, away_name, away_logo_url)]:
        H.append(f'<h4><img src="{logo}" style="width:24px;height:24px;vertical-align:middle;border-radius:50%;margin-right:6px">{team_name}</h4>')
        H.append('<table><tr><th></th><th>球员</th><th>位</th><th>评分</th><th>分钟</th><th>进球</th><th>助攻</th><th>射正</th><th>关键传</th><th>抢断</th><th>过人</th><th>传球%</th></tr>')
        sorted_pl = sorted(players, key=lambda p: p.minutes_played, reverse=True)
        for p in sorted_pl:
            if p.minutes_played <= 0:
                continue
            photo = f'<img src="{p.photo_url}" class="player-photo">' if p.photo_url else ""
            rating = f'{p.rating:.1f}' if p.rating is not None else "-"
            pass_acc = f'{p.passes_accuracy:.0f}' if p.passes_accuracy else "-"
            H.append(f'<tr><td>{photo}</td><td>{p.name}</td><td>{p.position}</td><td>{rating}</td><td>{p.minutes_played}</td><td>{p.goals}</td><td>{p.assists}</td><td>{p.shots_on}</td><td>{p.passes_key}</td><td>{p.tackles_total}</td><td>{p.dribbles_success}</td><td>{pass_acc}</td></tr>')
        H.append('</table>')

    # ── Key events timeline (vertical center line, home left, away right) ──
    H.append('<h2>📋 关键事件时间线</h2>')
    H.append(_event_timeline_sided_html(raw.events, home_name, away_name, raw.home_team.id, raw.away_team.id))

    # Footer
    H.append('<div class="footer">报告由 AI 足球分析员 v3 自动生成 | 数据来源：SportMonks API</div>')

    H.append('</div></body></html>')

    html_content = "\n".join(H)

    # ── Write files ──
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    html_path = out_dir / "report_v3.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    # Also save MD for reference
    md_path = out_dir / "report_v3.md"
    _save_md_report(out_dir / "report_v3.md", sections, image_paths, raw, home_name, away_name, home_xg, away_xg, hs, aws, hard_facts)

    return str(html_path)


def _save_md_report(md_path, sections, image_paths, raw, home_name, away_name, home_xg, away_xg, hs, aws, hard_facts):
    """Save a simple Markdown version for reference."""
    md = f"# {home_name} {raw.score.home} - {raw.score.away} {away_name}\n\n"
    for sec in ["封面导语", "比赛节奏", "效率悖论", "战术解码", "人物志", "数据深潜"]:
        content = sections.get(sec, "")
        if content:
            md += f"## {sec}\n\n{content}\n\n"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
