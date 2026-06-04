from __future__ import annotations

import re
from pathlib import Path

from src.collector.api_client import PlayerStats, RawMatchData
from src.composer.data_builder import _classify_signals, _build_phases
from src.engine.metrics import ComputedData, _stat
from src.engine.signals import SignalResult

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
    key_events = [e for e in events if e.event_type in ("Goal", "Card", "subst")]
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
