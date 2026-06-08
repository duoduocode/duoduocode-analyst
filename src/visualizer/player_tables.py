"""
Player Contribution Table Formatter v6

Outputs structured tables for player contribution analysis.
Supports both terminal (unicode box) and Markdown formats.
"""

from __future__ import annotations

from typing import Optional
from src.engine.player_insights_v6 import (
    PlayerInsightV6, ContributionScore,
    C1_DISPLAY_ORDER, C1_DISPLAY_NAMES,
    C2_DISPLAY_ORDER, C2_DISPLAY_NAMES,
    C3_DISPLAY_ORDER, C3_DISPLAY_NAMES,
    C4_DISPLAY_ORDER, C4_DISPLAY_NAMES,
    C5_DISPLAY_ORDER, C5_DISPLAY_NAMES,
)


def _pad(s: str, width: int, align: str = "<") -> str:
    """Pad CJK-aware: each CJK char ~2 width."""
    cjk_count = sum(1 for c in s if '\u4e00' <= c <= '\u9fff' or '\u3000' <= c <= '\u303f' or '\uff00' <= c <= '\uffef')
    ascii_count = len(s) - cjk_count
    display_width = ascii_count + cjk_count * 2
    pad_len = max(0, width - display_width)
    if align == "<":
        return s + " " * pad_len
    elif align == ">":
        return " " * pad_len + s
    else:
        left = pad_len // 2
        right = pad_len - left
        return " " * left + s + " " * right


def _fmt_val(v, default="-" ) -> str:
    if v is None:
        return default
    if isinstance(v, float):
        if abs(v) < 0.001 and v != 0:
            return "0"
        return f"{v:.1f}" if abs(v) >= 0.1 else f"{v:.2f}"
    return str(v)


def _team_highlight(name: str, team: str) -> str:
    """Optional: add asterisk for home team."""
    return name


# ═══════════════════════════════════════════════════════════════
# Table 1: Player Contribution Summary
# ═══════════════════════════════════════════════════════════════

def table_summary(
    insights: list[PlayerInsightV6],
    match_name: str,
    score: str,
    fmt: str = "terminal",
) -> str:
    """
    Table 1: One row per player — pos, #, name, minutes, C1-C6 scores, key raw stats, role.
    """
    lines = []
    sep = "|" if fmt == "markdown" else "│"
    hdr_sep = "|" if fmt == "markdown" else "╪"

    # Header
    header_cols = ["位", "#", "球员", "分钟",
                   "C1攻", "C2推", "C3控", "C4防", "C5抗", "C6事",
                   "进球", "xG", "传球", "抢断", "关键传", "角色"]
    widths = [2, 3, 12, 4, 5, 5, 5, 5, 5, 5, 4, 5, 4, 4, 5, 8]

    def _row(values, widths, sep_char="│"):
        parts = []
        for i, v in enumerate(values):
            parts.append(_pad(str(v), widths[i], "^" if i < 2 else "<"))
        return sep_char + sep_char.join(parts) + sep_char

    def _sep(char="─", cross="┼"):
        parts = [char * w for w in widths]
        return cross.join(parts)

    # Title
    lines.append(f"球员贡献概要 — {match_name} | 比分 {score}")
    lines.append("-" * 80)

    # Header row (weights)
    lines.append(_row(header_cols, widths))

    if fmt != "markdown":
        lines.append("╞" + "╪".join(["═" * w for w in widths]) + "╡")

    # Data rows — sort by max contribution
    def _sort_key(p: PlayerInsightV6):
        c1 = p.contributions.get("C1", ContributionScore(0, 99, 0, "", {})).zscore
        c2 = p.contributions.get("C2", ContributionScore(0, 99, 0, "", {})).zscore
        c3 = p.contributions.get("C3", ContributionScore(0, 99, 0, "", {})).zscore
        c4 = p.contributions.get("C4", ContributionScore(0, 99, 0, "", {})).zscore
        c5 = p.contributions.get("C5", ContributionScore(0, 99, 0, "", {})).zscore
        return -max(c1, c2, c3, c4, c5)

    sorted_insights = sorted(insights, key=_sort_key)

    for pi in sorted_insights:
        c1 = pi.contributions.get("C1", ContributionScore(0, 99, 0, "", {}))
        c2 = pi.contributions.get("C2", ContributionScore(0, 99, 0, "", {}))
        c3 = pi.contributions.get("C3", ContributionScore(0, 99, 0, "", {}))
        c4 = pi.contributions.get("C4", ContributionScore(0, 99, 0, "", {}))
        c5 = pi.contributions.get("C5", ContributionScore(0, 99, 0, "", {}))
        c6 = pi.contributions.get("C6", ContributionScore(0, 0, 0, "", {}))

        if pi.pos == "G":
            c7 = pi.contributions.get("C7", ContributionScore(0, 0, 0, "", {}))
            c1_str = " GK"
            c2_str = " GK"
            c4_str = " GK"
            c5_str = " GK"
        else:
            c1_str = _fmt_val(c1.zscore)
            c2_str = _fmt_val(c2.zscore)
            c4_str = _fmt_val(c4.zscore)
            c5_str = _fmt_val(c5.zscore)

        # Mark top-3 with ▲
        for attr, val in [("c1_str", c1), ("c2_str", c2), ("c3_str", c3), ("c4_str", c4), ("c5_str", c5)]:
            if isinstance(val, ContributionScore) and val.rank <= 3 and val.zscore > 0:
                if attr == "c1_str":
                    c1_str += "▲"
                elif attr == "c2_str":
                    c2_str += "▲"
                elif attr == "c4_str":
                    c4_str += "▲"
                elif attr == "c5_str":
                    c5_str += "▲"

        c3_str = _fmt_val(c3.zscore)
        if c3.rank <= 3 and c3.zscore > 0:
            c3_str += "▲"

        c6_str = _fmt_val(c6.zscore)
        if c6.zscore > 0:
            c6_str = "★" + c6_str

        # Key raw stats
        goals = pi.sv("goals", 0)
        xg = pi.sv("xg", 0)
        passes_total = pi.sv("passes_total", 0)
        tackles = pi.sv("tackles_total", 0)
        key_passes = pi.sv("passes_key", 0)

        role_name = pi.role.name if pi.role else "-"

        name_short = pi.name[:11] if len(pi.name) > 11 else pi.name
        mins_str = str(pi.minutes)

        values = [
            pi.pos, str(pi.number), name_short, mins_str,
            c1_str, c2_str, c3_str, c4_str, c5_str, c6_str,
            str(int(goals)), _fmt_val(xg), str(int(passes_total)),
            str(int(tackles)), str(int(key_passes)), role_name,
        ]
        lines.append(_row(values, widths))

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# Table 2.A~2.E: Dimension Detail Tables
# ═══════════════════════════════════════════════════════════════

def _dimension_detail_table(
    insights: list[PlayerInsightV6],
    dim_key: str,          # "C1" ~ "C5"
    dim_label: str,        # e.g., "C1 进攻贡献"
    metric_count: int,
    display_order: list[str],
    display_names: dict[str, str],
    fmt: str = "terminal",
) -> str:
    """Generic dimension detail table builder."""
    lines = []

    # Header
    short_names = [display_names.get(k, k) for k in display_order]
    header = ["球员", "Z综"] + short_names

    # Filter: only outfield players (no GK for C1/C2/C4/C5)
    outfield = [pi for pi in insights if pi.pos != "G"]
    if not outfield:
        return ""

    cols = len(header)
    col_w = 10 if cols <= 8 else 8 if cols <= 12 else 6

    def _fmt_cell(val):
        if isinstance(val, float):
            if abs(val) < 0.01:
                return "0"
            if abs(val) >= 100:
                return str(int(val))
            return f"{val:.1f}" if abs(val) >= 1 else f"{val:.2f}"
        return str(val)

    # Weights row
    weights_row = ["", ""]
    for k in display_order:
        weights_row.append("")
    header_str = f"{dim_label} ({metric_count}项)"
    lines.append(header_str)
    lines.append("-" * (cols * (col_w + 1)))

    # Header
    hdr_parts = []
    for i, h in enumerate(header):
        hdr_parts.append(h.ljust(col_w - 1) if i > 0 else h.ljust(10))
    lines.append(" ".join(hdr_parts))

    # Sort by zscore
    sorted_insights = sorted(outfield, key=lambda pi: -pi.contributions.get(dim_key, ContributionScore(0, 99, 0, "", {})).zscore)

    for pi in sorted_insights:
        c = pi.contributions.get(dim_key)
        if c is None:
            continue
        name_short = pi.name[:9] if len(pi.name) > 9 else pi.name
        row = [name_short.ljust(10), _fmt_cell(c.zscore).rjust(col_w - 2)]

        for k in display_order:
            raw = pi.raw_stats.get(k, 0)
            if raw is None:
                raw = 0
            # Format based on type
            if isinstance(raw, float):
                if abs(raw) < 0.01:
                    val = "0"
                elif abs(raw) >= 100:
                    val = str(int(raw))
                elif abs(raw) >= 1:
                    val = f"{raw:.1f}" if raw == int(raw) else f"{raw:.2f}"
                else:
                    val = f"{raw:.3f}"
            else:
                val = str(int(raw) if isinstance(raw, float) else raw)
            row.append(val.rjust(col_w - 2))

        lines.append(" ".join(row))

    return "\n".join(lines)


def table_c1_detail(insights: list[PlayerInsightV6], fmt: str = "terminal") -> str:
    return _dimension_detail_table(
        insights, "C1", "C1 进攻贡献", 15,
        C1_DISPLAY_ORDER, C1_DISPLAY_NAMES, fmt,
    )


def table_c2_detail(insights: list[PlayerInsightV6], fmt: str = "terminal") -> str:
    return _dimension_detail_table(
        insights, "C2", "C2 推进贡献", 12,
        C2_DISPLAY_ORDER, C2_DISPLAY_NAMES, fmt,
    )


def table_c3_detail(insights: list[PlayerInsightV6], fmt: str = "terminal") -> str:
    return _dimension_detail_table(
        insights, "C3", "C3 控制贡献 (8项,不含captain/rating)", 8,
        C3_DISPLAY_ORDER, C3_DISPLAY_NAMES, fmt,
    )


def table_c4_detail(insights: list[PlayerInsightV6], fmt: str = "terminal") -> str:
    return _dimension_detail_table(
        insights, "C4", "C4 防守贡献", 10,
        C4_DISPLAY_ORDER, C4_DISPLAY_NAMES, fmt,
    )


def table_c5_detail(insights: list[PlayerInsightV6], fmt: str = "terminal") -> str:
    return _dimension_detail_table(
        insights, "C5", "C5 对抗贡献", 13,
        C5_DISPLAY_ORDER, C5_DISPLAY_NAMES, fmt,
    )


# ═══════════════════════════════════════════════════════════════
# Table 2.F: C6 Key Events Detail
# ═══════════════════════════════════════════════════════════════

def table_c6_detail(insights: list[PlayerInsightV6], fmt: str = "terminal") -> str:
    lines = []
    lines.append("C6 关键事件")
    lines.append("-" * 70)

    events_header = f"{'球员':<12} {'总分':>4} {'制胜':>4} {'绝杀':>4} {'绝平':>4} {'首开':>4} {'造点':>4} {'替补':>4} {'标签':<15}"
    lines.append(events_header)

    for pi in sorted(insights, key=lambda x: -x.contributions.get("C6", ContributionScore(0, 0, 0, "", {})).zscore):
        eb = pi.event_bonus
        if eb is None:
            continue
        c6 = pi.contributions.get("C6")
        if c6 is None or (c6.zscore == 0 and not eb.any()):
            continue
        name_short = pi.name[:11] if len(pi.name) > 11 else pi.name
        row = (
            f"{name_short:<12} "
            f"{_fmt_val(c6.zscore):>4} "
            f"{'Y' if eb.winning_goal else '-':>4} "
            f"{'Y' if eb.late_winner else '-':>4} "
            f"{'Y' if eb.equalizer else '-':>4} "
            f"{'Y' if eb.first_goal else '-':>4} "
            f"{'Y' if eb.won_penalty else '-':>4} "
            f"{'Y' if eb.super_sub else '-':>4} "
            f"{eb.c6_label():<15}"
        )
        lines.append(row)

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# Table 2.G: C7 Goalkeeper Detail
# ═══════════════════════════════════════════════════════════════

def table_c7_detail(insights: list[PlayerInsightV6], fmt: str = "terminal") -> str:
    gks = [pi for pi in insights if pi.pos == "G"]
    if not gks:
        return ""

    lines = []
    lines.append("C7 门将贡献")
    lines.append("-" * 80)

    header = f"{'球员':<12} {'综合':>5} {'扑救':>4} {'禁区扑':>5} {'失球':>4} {'摘高':>4} {'击球':>4} {'传球%':>5} {'长传':>4} {'成长传':>5} {'丢球':>4} {'致丢':>4} {'角色':<10}"
    lines.append(header)

    for pi in sorted(gks, key=lambda x: -x.contributions.get("C7", ContributionScore(0, 0, 0, "", {})).zscore):
        c7 = pi.contributions.get("C7")
        if c7 is None:
            continue
        raw = c7.raw_metrics
        name_short = pi.name[:11] if len(pi.name) > 11 else pi.name
        row = (
            f"{name_short:<12} "
            f"{_fmt_val(c7.zscore):>5} "
            f"{str(raw.get('saves', 0)):>4} "
            f"{str(raw.get('saves_inside_box', 0)):>5} "
            f"{str(raw.get('goalkeeper_goals_conceded', 0)):>4} "
            f"{str(raw.get('good_high_claim', 0)):>4} "
            f"{str(raw.get('punches', 0)):>4} "
            f"{_fmt_val(raw.get('passes_accuracy', 0)):>5} "
            f"{str(raw.get('long_balls_won', 0)):>4} "
            f"{str(raw.get('long_balls_won_pct', 0)):>5} "
            f"{str(raw.get('possession_lost', 0)):>4} "
            f"{str(raw.get('error_lead_to_goal', 0)):>4} "
            f"{c7.label:<10}"
        )
        lines.append(row)

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# Table 3: Role Distribution (cross-match)
# ═══════════════════════════════════════════════════════════════

def table_role_summary(all_match_results: dict[str, list[PlayerInsightV6]]) -> str:
    """
    all_match_results: {match_id: [PlayerInsightV6], ...}
    """
    lines = []
    lines.append("球员角色分布 — 三场汇总")
    lines.append("=" * 80)

    # Collect all roles
    all_roles: dict[str, dict[str, list[str]]] = {}  # {role: {match_id: [player_names]}}

    for match_id, insights in all_match_results.items():
        for pi in insights:
            if pi.role and pi.pos != "G":
                role = pi.role.name
                if role not in all_roles:
                    all_roles[role] = {}
                if match_id not in all_roles[role]:
                    all_roles[role][match_id] = []
                all_roles[role][match_id].append(f"{pi.name}({pi.team_name},{pi.minutes}')")

    # Sort roles by type
    role_order = [
        "蹲坑中卫", "出球后卫", "进攻型边卫", "全能后卫",
        "节拍器", "扫荡后腰", "全能中场", "进攻组织者", "串联枢纽",
        "终结者", "全能中锋", "边路突击手", "伪九号",
    ]
    sorted_roles = [r for r in role_order if r in all_roles] + \
                   [r for r in sorted(all_roles) if r not in role_order]

    match_ids = sorted(all_match_results.keys())

    for role in sorted_roles:
        lines.append(f"\n【{role}】")
        for mid in match_ids:
            players = all_roles[role].get(mid, [])
            players_str = ", ".join(players) if players else "—"
            lines.append(f"  {mid}: {players_str}")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# Full Match Report
# ═══════════════════════════════════════════════════════════════

def full_match_report(insights: list[PlayerInsightV6], match_id: str, match_name: str, score: str) -> str:
    """Generate full player contribution report for one match."""
    sections = []

    # Match info
    sections.append(f"{'=' * 60}")
    sections.append(f"  球员贡献分析 — {match_name} | ID: {match_id}")
    sections.append(f"  比分: {score}")
    sections.append(f"{'=' * 60}")
    sections.append("")

    # Table 1: Summary
    sections.append(table_summary(insights, match_name, score))
    sections.append("")

    # Table 2.A~2.G: Detail tables
    sections.append("─" * 60)
    sections.append(table_c1_detail(insights))
    sections.append("")
    sections.append(table_c2_detail(insights))
    sections.append("")
    sections.append(table_c3_detail(insights))
    sections.append("")
    sections.append(table_c4_detail(insights))
    sections.append("")
    sections.append(table_c5_detail(insights))
    sections.append("")
    sections.append(table_c6_detail(insights))
    sections.append("")
    sections.append(table_c7_detail(insights))
    sections.append("")

    # Role narratives
    sections.append("─" * 60)
    sections.append("第二层：角色叙事")
    sections.append("")
    for pi in insights:
        if pi.role and pi.role.narrative:
            sections.append(pi.role.narrative)
            sections.append("")

    return "\n".join(sections)
