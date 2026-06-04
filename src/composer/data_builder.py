from __future__ import annotations

import re
from typing import Optional

from src.collector.api_client import RawMatchData
from src.composer.prompt_loader import PromptLoader
from src.engine.metrics import ComputedData, _stat
from src.engine.signals import SignalResult
from src.engine.trends import TrendAnalysis

CATEGORY_CN = {
    "score_deviation": "比分背离",
    "efficiency_tear": "效率撕裂",
    "individual": "个人英雄",
    "structural": "结构问题",
    "narrative": "叙事钩子",
    "knockout": "淘汰赛专项",
    "trends": "趋势驱动",
    "event_trend": "事件x趋势",
    "player_contribution": "球员贡献王",
}

# Signals that always describe the whole game (never time-specific)
GLOBAL_SIGNAL_NAMES = {
    "xg_upset", "conversion_anomaly", "penalty_decided",
    "possession_waste", "counter_attack_efficiency",
    "pass_efficiency_gap", "shot_quality_gap", "corner_efficiency",
    "big_chance_conversion",
    "one_man_team", "gk_hero", "gk_disaster", "super_sub",
    "fatal_error", "rating_paradox",
    "wing_domination", "attack_channel_bias", "aerial_domination",
    "tactical_fouls", "sub_timing_impact", "formation_mismatch",
    "mirror_match", "high_scoring", "clean_sheet", "comeback",
    "draw_drama", "rare_event",
    "offensive_king", "defensive_king", "balanced_king",
    "rhythm_swing", "duel_decay_alert", "stamina_fade", "tactical_shift",
    "var_disruption",
}


def _player_sum(players, attr):
    return sum(getattr(p, attr, 0) or 0 for p in players)


def _extract_minute_from_signal(sig: SignalResult) -> Optional[int]:
    """Try to extract the minute a signal refers to."""
    text = sig.narrative_hint + " " + str(sig.evidence)

    # Explicit minute in hint: "第72分钟" or "第106分钟"
    m = re.search(r"第\s*(\d+)\s*分钟", text)
    if m:
        return int(m.group(1))

    # Evidence fields with minute info
    for key in ("minute", "red_card_minute", "late_goal_minute"):
        if key in sig.evidence:
            return int(sig.evidence[key])

    return None


def _classify_signals(
    signals: list[SignalResult],
) -> tuple[list[dict], list[dict]]:
    """Split signals into time-specific and global."""
    time_signals: list[dict] = []
    global_signals: list[dict] = []

    for sig in signals:
        d = {
            "name": sig.name,
            "category": CATEGORY_CN.get(sig.category, sig.category),
            "strength": sig.strength,
            "hint": sig.narrative_hint,
            "evidence": sig.evidence,
        }

        if sig.name in GLOBAL_SIGNAL_NAMES:
            global_signals.append(d)
            continue

        minute = _extract_minute_from_signal(sig)
        if minute is not None:
            d["minute"] = minute
            time_signals.append(d)
        else:
            global_signals.append(d)

    return time_signals, global_signals


def _build_phase_windows(match_duration: int) -> list[tuple[int, int, str]]:
    """Create standard phase windows based on match duration."""
    phases = []
    if match_duration <= 90:
        phases = [
            (0, 15, "开局试探"),
            (15, 30, "中场拉锯"),
            (30, 45, "半场收官"),
            (45, 60, "下半场调整"),
            (60, 75, "决战阶段"),
            (75, 90, "冲刺收官"),
        ]
    elif match_duration <= 120:
        phases = [
            (0, 15, "开局试探"),
            (15, 30, "中场拉锯"),
            (30, 45, "半场收官"),
            (45, 60, "下半场调整"),
            (60, 75, "决战阶段"),
            (75, 90, "常规时间冲刺"),
            (90, 105, "加时上半场"),
            (105, 120, "加时下半场"),
        ]
    else:
        phases = [
            (0, 15, "开局试探"),
            (15, 30, "中场拉锯"),
            (30, 45, "半场收官"),
            (45, 60, "下半场调整"),
            (60, 75, "决战阶段"),
            (75, 90, "常规时间冲刺"),
            (90, 105, "加时上半场"),
            (105, 120, "加时下半场"),
            (120, match_duration, "点球大战"),
        ]
    return phases


def _build_phases(
    raw: RawMatchData,
    time_signals: list[dict],
) -> list[dict]:
    """Build phase-based data for the timeline."""
    # Determine match duration
    max_minute = 90
    for ev in raw.events:
        if ev.time_elapsed > max_minute:
            max_minute = ev.time_elapsed
    if raw.score.penalty_home is not None:
        max_minute = max(max_minute, 125)

    windows = _build_phase_windows(max_minute)
    phases = []

    for start, end, label in windows:
        phase = {
            "start": start,
            "end": end,
            "label": label,
            "events": [],
            "signals": [],
            "stats": "",
        }

        # Assign events
        for ev in raw.events:
            if ev.event_type not in ("Goal", "Card", "subst", "VAR", "Shot"):
                continue
            # Skip penalty shootout events (not real match goals)
            if ev.detail in ("pen_shootout_goal", "pen_shootout_miss"):
                continue
            if start <= ev.time_elapsed < end:
                desc_parts = [ev.player_name]
                if ev.assist_name and ev.event_type == "Goal":
                    desc_parts.append(f"(助: {ev.assist_name})")
                if ev.detail == "owngoal":
                    desc_parts.append("[乌龙]")
                elif ev.detail == "goal_penalty":
                    desc_parts.append("[点球]")
                elif ev.detail == "missed_penalty":
                    desc_parts.append("[点球罚失]")
                if ev.detail in ("yellowcard",):
                    desc_parts.append("[黄牌]")
                elif ev.detail in ("redcard", "yellowredcard"):
                    desc_parts.append("[红牌]")

                ev_type_label = {
                    "Goal": "进球", "Card": "纪律",
                    "subst": "换人", "VAR": "VAR",
                    "Shot": "射门",
                }.get(ev.event_type, ev.event_type)

                phase["events"].append({
                    "minute": ev.time_elapsed,
                    "type": ev_type_label,
                    "description": " ".join(desc_parts),
                    "team": ev.team_name,
                })

        # Assign time-specific signals
        for sig in time_signals:
            sig_minute = sig.get("minute", -1)
            if start <= sig_minute < end:
                phase["signals"].append(sig)

        # Build stats string from period data if available
        for p in raw.periods:
            p_start = _period_start_minute(p.sort_order, p.description)
            if p_start is not None and start <= p_start < end:
                h_shots = int(_stat(p.home_stats, "Total Shots", default=0))
                a_shots = int(_stat(p.away_stats, "Total Shots", default=0))
                h_poss = int(_stat(p.home_stats, "Ball Possession", default=50))
                a_poss = int(_stat(p.away_stats, "Ball Possession", default=50))
                phase["stats"] = f"{p.description}: 射门{h_shots}-{a_shots} 控球{h_poss}%-{a_poss}%"

        phases.append(phase)

    return phases


def _period_start_minute(sort_order: int, description: str) -> Optional[int]:
    """Estimate the start minute of a period."""
    desc_lower = description.lower().replace("-", " ")
    if "1st half" in desc_lower or "上半场" in description:
        return 0
    if "2nd half" in desc_lower or "下半场" in description:
        return 45
    if "extra time 1" in desc_lower or "加时上半场" in description:
        return 90
    if "extra time 2" in desc_lower or "加时下半场" in description:
        return 105
    if "penalty" in desc_lower or "点球" in description:
        return 120
    return sort_order * 15  # fallback


def _build_event_list(raw: RawMatchData) -> list[dict]:
    result = []
    for ev in raw.events:
        if ev.event_type in ("Goal", "Card", "subst", "VAR"):
            desc_parts = [ev.player_name]
            if ev.assist_name and ev.event_type == "Goal":
                desc_parts.append(f"(助攻: {ev.assist_name})")
            if ev.detail == "owngoal":
                desc_parts.append("(乌龙球)")
            elif ev.detail == "goal_penalty":
                desc_parts.append("(点球)")
            elif ev.detail == "missed_penalty":
                desc_parts.append("(点球罚失)")
            result.append({
                "minute": ev.time_elapsed,
                "type": ev.event_type,
                "description": " ".join(desc_parts),
                "team": ev.team_name,
            })
    result.sort(key=lambda e: e["minute"])
    return result[:30]


def _build_key_players(players):
    key = [p for p in players if p.minutes_played >= 60 and p.rating is not None]
    key.sort(key=lambda p: p.rating or 0, reverse=True)
    result = []
    for p in key[:6]:
        result.append({
            "name": p.name,
            "position": p.position,
            "rating": p.rating,
            "minutes": p.minutes_played,
            "goals": p.goals,
            "assists": p.assists,
            "shots_on": p.shots_on,
            "passes_key": p.passes_key,
            "tackles_total": p.tackles_total,
            "xg": round(p.xg, 2) if p.xg else 0,
        })
    return result


def _build_trend_summary(trend_analysis: TrendAnalysis, raw: RawMatchData) -> list[str]:
    lines = []

    if trend_analysis.turning_points:
        tp = trend_analysis.turning_points[:3]
        lines.append(f"转折点({len(tp)}个): " + "; ".join(
            f"{t.minute}' {t.description}" for t in tp
        ))

    if trend_analysis.duel_decay_home:
        for d in trend_analysis.duel_decay_home:
            if d.severity != "none":
                lines.append(
                    f"{raw.home_team.name}对抗衰减: 前半段{d.early_win_rate}/min → 后半段{d.late_win_rate}/min "
                    f"({d.severity}, -{d.decay:.0%})"
                )
    if trend_analysis.duel_decay_away:
        for d in trend_analysis.duel_decay_away:
            if d.severity != "none":
                lines.append(
                    f"{raw.away_team.name}对抗衰减: 前半段{d.early_win_rate}/min → 后半段{d.late_win_rate}/min "
                    f"({d.severity}, -{d.decay:.0%})"
                )

    if trend_analysis.pressing_fade_home > 0.05:
        lines.append(f"{raw.home_team.name}压迫效率衰减: {trend_analysis.pressing_fade_home:.0%}")
    if trend_analysis.pressing_fade_away > 0.05:
        lines.append(f"{raw.away_team.name}压迫效率衰减: {trend_analysis.pressing_fade_away:.0%}")

    if trend_analysis.style_shift_home.get("shift_detected"):
        d = trend_analysis.style_shift_home
        desc = "更直接" if d["direction"] == "more_direct" else "更控球"
        lines.append(f"{raw.home_team.name}风格转变: {desc} (强度{d['magnitude']:.0%})")
    if trend_analysis.style_shift_away.get("shift_detected"):
        d = trend_analysis.style_shift_away
        desc = "更直接" if d["direction"] == "more_direct" else "更控球"
        lines.append(f"{raw.away_team.name}风格转变: {desc} (强度{d['magnitude']:.0%})")

    if trend_analysis.rhythm_phases and len(trend_analysis.rhythm_phases) >= 3:
        phase_descs = []
        for ph in trend_analysis.rhythm_phases:
            dom = {"home": raw.home_team.name, "away": raw.away_team.name, "balanced": "均势"}[ph["dominant"]]
            phase_descs.append(f"{ph['start_minute']}-{ph['end_minute']}' {dom}")
        lines.append("节奏阶段: " + " → ".join(phase_descs))

    return lines


def build_narrative(
    raw: RawMatchData,
    computed: ComputedData,
    signals: list[SignalResult],
    trend_analysis: TrendAnalysis = None,
    prompt_loader: PromptLoader = None,
) -> tuple[str, str]:
    if prompt_loader is None:
        prompt_loader = PromptLoader("prompts")

    hs = raw.home_stats
    aws = raw.away_stats

    # Classify signals into time-specific and global
    time_signals, global_signals = _classify_signals(signals)

    # Build time phases
    phases = _build_phases(raw, time_signals)

    # Build key players
    home_key = _build_key_players(raw.home_players)
    away_key = _build_key_players(raw.away_players)

    # Build trend summary
    trend_lines = _build_trend_summary(trend_analysis, raw) if trend_analysis else []

    # Coach info
    home_coach = raw.home_coach.name if raw.home_coach else "未知"
    away_coach = raw.away_coach.name if raw.away_coach else "未知"

    args = {
        "home_team": raw.home_team.name,
        "away_team": raw.away_team.name,
        "home_goals": raw.score.home,
        "away_goals": raw.score.away,
        "halftime_home": raw.score.halftime_home,
        "halftime_away": raw.score.halftime_away,
        "fulltime_home": raw.score.fulltime_home,
        "fulltime_away": raw.score.fulltime_away,
        "extratime_home": raw.score.extratime_home,
        "extratime_away": raw.score.extratime_away,
        "penalty_home": raw.score.penalty_home,
        "penalty_away": raw.score.penalty_away,
        "home_possession": int(float(_stat(hs, "Ball Possession", default=50))),
        "away_possession": int(float(_stat(aws, "Ball Possession", default=50))),
        "home_shots": int(float(_stat(hs, "Total Shots", default=0))),
        "away_shots": int(float(_stat(aws, "Total Shots", default=0))),
        "home_shots_on": int(float(_stat(hs, "Shots on Goal", default=0))),
        "away_shots_on": int(float(_stat(aws, "Shots on Goal", default=0))),
        "home_xg": round(_player_sum(raw.home_players, "xg"), 2),
        "away_xg": round(_player_sum(raw.away_players, "xg"), 2),
        "home_big_chances": int(float(_stat(hs, "Big Chances Created", default=0))),
        "away_big_chances": int(float(_stat(aws, "Big Chances Created", default=0))),
        "home_shots_ib": int(float(_stat(hs, "Shots insidebox", default=0))),
        "away_shots_ib": int(float(_stat(aws, "Shots insidebox", default=0))),
        "home_pass_acc": int(float(_stat(hs, "Passes %", default=75))),
        "away_pass_acc": int(float(_stat(aws, "Passes %", default=75))),
        "home_corners": int(float(_stat(hs, "Corner Kicks", default=0))),
        "away_corners": int(float(_stat(aws, "Corner Kicks", default=0))),
        "home_tackles": int(float(_stat(hs, "Tackles", default=0))),
        "away_tackles": int(float(_stat(aws, "Tackles", default=0))),
        "home_fouls": int(float(_stat(hs, "Fouls", default=0))),
        "away_fouls": int(float(_stat(aws, "Fouls", default=0))),
        "home_yellows": int(float(_stat(hs, "Yellow Cards", default=0))),
        "away_yellows": int(float(_stat(aws, "Yellow Cards", default=0))),
        "home_reds": int(float(_stat(hs, "Red Cards", default=0))),
        "away_reds": int(float(_stat(aws, "Red Cards", default=0))),
        # New: phase-based structure
        "phases": phases,
        "global_signals": global_signals,
        "trend_lines": trend_lines,
        # Player and coach
        "home_key_players": home_key,
        "away_key_players": away_key,
        "home_coach": home_coach,
        "away_coach": away_coach,
        "coaches": bool(raw.home_coach or raw.away_coach),
    }

    return prompt_loader.render("narrative", **args)


def build_narrative_v3(
    raw: RawMatchData,
    computed: ComputedData,
    signals: list[SignalResult],
    hard_facts,
    sub_impacts: list[dict],
    trend_analysis: TrendAnalysis = None,
    prompt_loader: PromptLoader = None,
) -> tuple[str, str]:
    """Build prompt for v3 six-section narrative using narrative_v3.yaml template."""
    if prompt_loader is None:
        prompt_loader = PromptLoader("prompts")

    hs = raw.home_stats
    aws = raw.away_stats

    # Stage/venue info
    stage = raw.stage_info or {}
    venue = raw.venue_info or {}
    league_name = stage.get("name", "")
    venue_name = venue.get("name", "未知球场")
    city = venue.get("city_name", "")
    stage_text = f"，{stage.get('name', '')}" if league_name else ""

    # Formations
    formations = raw.formations or []
    home_formation = "?"
    away_formation = "?"
    for f in formations:
        if f.get("location") == "home":
            home_formation = f.get("formation", "?")
        else:
            away_formation = f.get("formation", "?")

    # Match duration
    if raw.score.extratime_home is not None:
        match_duration = "120分钟+点球大战"
    elif raw.score.halftime_home is not None:
        match_duration = "90分钟"
    else:
        match_duration = "全场"

    # Hard facts text
    hf_lines = []
    hf_lines.append(f"控球有效率：{raw.home_team.name} {hard_facts.possession_xg_ratio_home} xG/1%控球 vs {raw.away_team.name} {hard_facts.possession_xg_ratio_away}")
    xg_dev = hard_facts.xg_deviation_home
    if abs(xg_dev) > 0.3:
        hf_lines.append(f"xG背离：{raw.home_team.name} 实际进球比 xG {'多' if xg_dev > 0 else '少'}{abs(xg_dev):.2f}")
    xg_dev_a = hard_facts.xg_deviation_away
    if abs(xg_dev_a) > 0.3:
        hf_lines.append(f"xG背离：{raw.away_team.name} 实际进球比 xG {'多' if xg_dev_a > 0 else '少'}{abs(xg_dev_a):.2f}")
    if hard_facts.attack_rhythm:
        r = hard_facts.attack_rhythm
        if r.get("home_shots_ratio", 1) > 1.5:
            hf_lines.append(f"射门节奏：{raw.home_team.name} 下半场射门 {int(r.get('home_shots_h2', 0))}（上半场 {int(r.get('home_shots_h1', 0))}），增长 {r['home_shots_ratio']}x")
        if r.get("away_shots_ratio", 1) > 1.5:
            hf_lines.append(f"射门节奏：{raw.away_team.name} 下半场射门 {int(r.get('away_shots_h2', 0))}（上半场 {int(r.get('away_shots_h1', 0))}），增长 {r['away_shots_ratio']}x")
    if hard_facts.passing_profile:
        pp = hard_facts.passing_profile
        hf_lines.append(f"传球风格：{raw.home_team.name} 长传占比 {pp.get('home_long_ball_pct', 0)}%、传中占比 {pp.get('home_cross_pct', 0)}%  |  {raw.away_team.name} 长传占比 {pp.get('away_long_ball_pct', 0)}%、传中占比 {pp.get('away_cross_pct', 0)}%")
    if hard_facts.defensive_decay.get("windows"):
        dd = hard_facts.defensive_decay
        hf_lines.append(f"防守强度衰减：{raw.home_team.name} {dd.get('home_decay_pct', '?')}%  |  {raw.away_team.name} {dd.get('away_decay_pct', '?')}%")
    if hard_facts.time_pressure.get("leading_team"):
        hf_lines.append(f"末段压力：领先方 {hard_facts.time_pressure['leading_team']}，末段射门比 {hard_facts.time_pressure.get('late_shots_home', 0)}:{hard_facts.time_pressure.get('late_shots_away', 0)}")
    hard_facts_text = "\n".join(hf_lines)

    # Event timeline text
    event_lines = []
    for e in raw.events:
        mi = e.time_elapsed or "?"
        x = f"+{e.time_extra}" if e.time_extra else ""
        icon = {"Goal": "⚽", "Card": "🟨", "subst": "🔄", "VAR": "📺", "Info": "ℹ️"}.get(e.event_type, e.event_type)
        if e.event_type == "Goal" and "penalty" in str(e.detail):
            icon = "⚽(P)"
        event_lines.append(f"{mi}'{x} {icon} {e.player_name or '-'} [{e.detail or ''}]")
    event_timeline_text = "\n".join(event_lines[:50])

    # Sub impacts text
    si_lines = []
    for si in sub_impacts:
        si_lines.append(
            f"{si['minute_display']} {si['team']}: {si['player_on']} ↑ / {si['player_off']} ↓ | "
            f"意图: {si['intent']} | "
            f"控球变化: {si.get('control_before', '?')}→{si.get('control_after', '?')} | "
            f"射门变化: {si.get('shots_before', '?')}→{si.get('shots_after', '?')} | "
            f"效果: {si.get('effectiveness', '?')}"
        )
    sub_impacts_text = "\n".join(si_lines) if si_lines else "无换人数据"

    # Signals text
    sig_lines = []
    for s in signals[:6]:
        sig_lines.append(f"[{CATEGORY_CN.get(s.category, s.category)}] {s.name}: {s.narrative_hint[:120]}")
    signals_text = "\n".join(sig_lines)

    # Period stats
    per_lines = []
    for p in (raw.periods or []):
        desc = p.description
        hs_p = p.home_stats
        as_p = p.away_stats
        if not hs_p:
            continue
        per_lines.append(
            f"{desc}: {raw.home_team.name} 射门 {int(_stat(hs_p, 'Total Shots'))}（控球 {int(_stat(hs_p, 'Ball Possession'))}%）| "
            f"{raw.away_team.name} 射门 {int(_stat(as_p, 'Total Shots', default=0))}（控球 {int(_stat(as_p, 'Ball Possession', default=0))}%）"
        )
    period_stats_text = "\n".join(per_lines)

    # Player stats
    pl_lines = []
    for team_label, players in [("主队", raw.home_players), ("客队", raw.away_players)]:
        pl_lines.append(f"\n{team_label}:")
        for p in sorted(players, key=lambda x: x.rating or 0, reverse=True)[:8]:
            xg_val = f"xG={p.xg:.2f}" if p.xg else ""
            pl_lines.append(
                f"  {p.name} #{p.number} {p.position} "
                f"评分:{p.rating or '-'} min {p.minutes_played}' "
                f"射{p.shots_total}/{p.shots_on} 传{p.passes_total} {xg_val}"
            )
    player_stats_text = "\n".join(pl_lines)

    args = {
        "league": league_name,
        "stage_text": stage_text,
        "venue_name": venue_name,
        "city": city,
        "home_name": raw.home_team.name,
        "away_name": raw.away_team.name,
        "home_goals": raw.score.home,
        "away_goals": raw.score.away,
        "ht_home": raw.score.halftime_home,
        "ht_away": raw.score.halftime_away,
        "pen_home": raw.score.penalty_home or 0,
        "pen_away": raw.score.penalty_away or 0,
        "home_formation": home_formation,
        "away_formation": away_formation,
        "match_duration": match_duration,
        "home_possession": int(float(_stat(hs, "Ball Possession", default=50))),
        "away_possession": int(float(_stat(aws, "Ball Possession", default=50))),
        "home_shots": int(float(_stat(hs, "Total Shots", default=0))),
        "away_shots": int(float(_stat(aws, "Total Shots", default=0))),
        "home_sot": int(float(_stat(hs, "Shots on Goal", default=0))),
        "away_sot": int(float(_stat(aws, "Shots on Goal", default=0))),
        "home_xg": round(sum(p.xg for p in raw.home_players if p.xg), 2),
        "away_xg": round(sum(p.xg for p in raw.away_players if p.xg), 2),
        "home_passes": int(float(_stat(hs, "Total passes", default=0))),
        "away_passes": int(float(_stat(aws, "Total passes", default=0))),
        "home_pass_pct": int(float(_stat(hs, "Passes %", default=75))),
        "away_pass_pct": int(float(_stat(aws, "Passes %", default=75))),
        "home_corners": int(float(_stat(hs, "Corner Kicks", default=0))),
        "away_corners": int(float(_stat(aws, "Corner Kicks", default=0))),
        "home_yellows": int(float(_stat(hs, "Yellow Cards", default=0))),
        "away_yellows": int(float(_stat(aws, "Yellow Cards", default=0))),
        "hard_facts_text": hard_facts_text,
        "event_timeline_text": event_timeline_text,
        "sub_impacts_text": sub_impacts_text,
        "signals_text": signals_text,
        "period_stats_text": period_stats_text,
        "player_stats_text": player_stats_text,
    }

    return prompt_loader.render("narrative_v3", **args)
