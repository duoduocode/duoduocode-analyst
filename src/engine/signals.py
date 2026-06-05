from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from src.collector.api_client import (
    MatchEvent,
    PlayerStats,
    RawMatchData,
)
from src.engine.trends import TrendAnalysis, TrendSeries

EPSILON = 0.001


@dataclass
class SignalResult:
    name: str
    category: str
    strength: float
    evidence: dict = field(default_factory=dict)
    narrative_hint: str = ""


def _clip(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _stat(stats: dict, *keys, default=0):
    for k in keys:
        v = stats.get(k)
        if v is not None:
            return float(v) if isinstance(v, (int, float)) else 0
    return float(default)


def _safe_ratio(num: float, den: float) -> float:
    if den <= 0:
        return 0.0
    return num / den


def _player_sum(players: list[PlayerStats], attr: str) -> float:
    return sum(getattr(p, attr, 0) or 0 for p in players)


# ============================================================
# A. Score Deviation — 比分背离
# ============================================================

def signal_xg_upset(raw: RawMatchData, computed: dict = None) -> SignalResult:
    home_xg = _player_sum(raw.home_players, "xg")
    away_xg = _player_sum(raw.away_players, "xg")
    hg, ag = raw.score.home, raw.score.away

    if hg == ag:
        return SignalResult("xg_upset", "score_deviation", 0.0)

    if hg > ag:
        winner_xg, loser_xg = home_xg, away_xg
        winner, loser = raw.home_team.name, raw.away_team.name
        goals = hg
    else:
        winner_xg, loser_xg = away_xg, home_xg
        winner, loser = raw.away_team.name, raw.home_team.name
        goals = ag

    if loser_xg <= winner_xg + 0.3:
        return SignalResult("xg_upset", "score_deviation", 0.0)

    gap = loser_xg - winner_xg
    strength = _clip(gap / 2.0)

    return SignalResult(
        name="xg_upset",
        category="score_deviation",
        strength=strength,
        evidence={
            "winner_xg": round(winner_xg, 2),
            "loser_xg": round(loser_xg, 2),
            "winner_goals": goals,
            "winner": winner,
            "loser": loser,
        },
        narrative_hint=f"{winner}以{goals}球取胜，但xG({winner_xg:.2f})远低于{loser}的xG({loser_xg:.2f})——这是一场典型的效率制胜/运气球比赛",
    )


def signal_conversion_anomaly(raw: RawMatchData, computed: dict = None) -> SignalResult:
    hs, aws = raw.home_stats, raw.away_stats
    h_shots = _stat(hs, "Total Shots")
    a_shots = _stat(aws, "Total Shots")
    hg, ag = raw.score.home, raw.score.away

    h_conv = _safe_ratio(hg, h_shots)
    a_conv = _safe_ratio(ag, a_shots)

    normal_range = (0.05, 0.25)
    anomalies = []
    if h_shots >= 5 and (h_conv < normal_range[0] or h_conv > normal_range[1]):
        anomalies.append(("home", h_conv))
    if a_shots >= 5 and (a_conv < normal_range[0] or a_conv > normal_range[1]):
        anomalies.append(("away", a_conv))

    if not anomalies:
        return SignalResult("conversion_anomaly", "score_deviation", 0.0)

    max_dev = max(abs(c - 0.12) for _, c in anomalies)
    strength = _clip(max_dev / 0.20)

    team_name = raw.home_team.name if anomalies[0][0] == "home" else raw.away_team.name
    rate = anomalies[0][1]
    hint = f"{team_name}射门转化率{rate:.0%}——" + (
        "极高转化率，每脚射门都极具威胁" if rate > 0.25 else "转化率极低，大量射门未能兑现进球"
    )

    return SignalResult(
        name="conversion_anomaly",
        category="score_deviation",
        strength=strength,
        evidence={"home_conversion": round(h_conv, 3), "away_conversion": round(a_conv, 3)},
        narrative_hint=hint,
    )


def signal_penalty_decided(raw: RawMatchData, computed: dict = None) -> SignalResult:
    pen_goals = [e for e in raw.events if e.detail == "goal_penalty"]
    if not pen_goals:
        return SignalResult("penalty_decided", "score_deviation", 0.0)

    hg, ag = raw.score.home, raw.score.away
    diff = abs(hg - ag)
    pen_count = len(pen_goals)

    if pen_count >= diff and diff > 0:
        return SignalResult(
            name="penalty_decided",
            category="score_deviation",
            strength=_clip(pen_count / 3.0),
            evidence={"penalty_goals": pen_count, "goal_diff": diff},
            narrative_hint=f"比赛由{pen_count}个点球决定——点球是改变比分平衡的关键因素",
        )

    if pen_count >= 2:
        return SignalResult(
            name="penalty_decided",
            category="score_deviation",
            strength=0.5,
            evidence={"penalty_goals": pen_count},
            narrative_hint=f"本场出现{pen_count}个点球进球，点球成为比赛的显著叙事线索",
        )

    return SignalResult("penalty_decided", "score_deviation", 0.0)


def signal_red_card_turning(raw: RawMatchData, computed: dict = None) -> SignalResult:
    red_events = [e for e in raw.events if e.detail in ("redcard", "yellowredcard")]
    if not red_events:
        return SignalResult("red_card_turning", "score_deviation", 0.0)

    red = red_events[0]
    minute = red.time_elapsed
    red_team_id = red.team_id

    goals_before = {"home": 0, "away": 0}
    goals_after = {"home": 0, "away": 0}
    for e in raw.events:
        if e.event_type != "Goal" or e.detail in ("pen_shootout_goal", "pen_shootout_miss"):
            continue
        side = "home" if e.team_id == raw.home_team.id else "away"
        if e.time_elapsed <= minute:
            goals_before[side] += 1
        else:
            goals_after[side] += 1

    red_side = "home" if red_team_id == raw.home_team.id else "away"
    other_side = "away" if red_side == "home" else "home"
    net_after = goals_after[other_side] - goals_after[red_side]
    net_before = goals_before[other_side] - goals_before[red_side]
    swing = net_after - net_before

    strength = _clip(abs(swing) / 3.0)
    if strength < 0.2:
        return SignalResult("red_card_turning", "score_deviation", 0.0)

    team_name = raw.home_team.name if red_side == "home" else raw.away_team.name
    return SignalResult(
        name="red_card_turning",
        category="score_deviation",
        strength=strength,
        evidence={"red_card_minute": minute, "red_team": team_name, "goal_swing": swing},
        narrative_hint=f"第{minute}分钟{team_name}的红牌改变了比赛走向——之后净胜球变动{swing:+d}",
    )


def signal_own_goal_impact(raw: RawMatchData, computed: dict = None) -> SignalResult:
    og_events = [e for e in raw.events if e.detail == "owngoal"]
    if not og_events:
        return SignalResult("own_goal_impact", "score_deviation", 0.0)

    hg, ag = raw.score.home, raw.score.away
    og_count = len(og_events)

    if abs(hg - ag) <= og_count and og_count > 0:
        return SignalResult(
            name="own_goal_impact",
            category="score_deviation",
            strength=_clip(og_count / 2.0),
            evidence={"own_goals": og_count, "final_score": f"{hg}-{ag}"},
            narrative_hint=f"乌龙球直接影响了比赛结果——{og_count}个乌龙球在{['均势','焦灼'][min(og_count-1,1)]}的比赛中成为决定性因素",
        )

    return SignalResult("own_goal_impact", "score_deviation", 0.3 if og_count > 0 else 0.0)


def signal_late_winner(raw: RawMatchData, computed: dict = None) -> SignalResult:
    goals = [e for e in raw.events if e.event_type == "Goal" and e.detail not in ("pen_shootout_goal", "pen_shootout_miss")]
    late_goals = [g for g in goals if g.time_elapsed >= 75]

    if not late_goals:
        return SignalResult("late_winner", "score_deviation", 0.0)

    # Final score (use fulltime if available, else score includes extra time)
    final_h = raw.score.fulltime_home or raw.score.home
    final_a = raw.score.fulltime_away or raw.score.away

    # Goals before and after 75'
    goals_before_75 = {"home": 0, "away": 0}
    goals_after_75 = {"home": 0, "away": 0}
    for g in goals:
        side = "home" if g.team_id == raw.home_team.id else "away"
        if g.time_elapsed < 75:
            goals_before_75[side] += 1
        else:
            goals_after_75[side] += 1

    # Who was leading before 75'? (by cumulative goals)
    before_leader = "home" if goals_before_75["home"] > goals_before_75["away"] else ("away" if goals_before_75["away"] > goals_before_75["home"] else "draw")

    # Who actually won the match?
    if final_h > final_a:
        final_winner = "home"
    elif final_a > final_h:
        final_winner = "away"
    else:
        final_winner = "draw"

    # Key condition: the team trailing before 75' must end up WINNING
    if before_leader != "draw" and final_winner != "draw" and before_leader != final_winner:
        team_name = raw.home_team.name if final_winner == "home" else raw.away_team.name
        comeback_goals = goals_after_75[final_winner]
        return SignalResult(
            name="late_winner",
            category="score_deviation",
            strength=_clip(comeback_goals / 3.0 + 0.3),
            evidence={"late_goals": len(late_goals), "comeback_goals": comeback_goals, "before_75": goals_before_75, "after_75": goals_after_75, "final": (final_h, final_a)},
            narrative_hint=f"75分钟后{team_name}连进{comeback_goals}球翻盘逆转——展现了强大的韧性和体能储备",
        )

    return SignalResult("late_winner", "score_deviation", 0.0)


# ============================================================
# B. Efficiency Tear — 效率撕裂
# ============================================================

def signal_possession_waste(raw: RawMatchData, computed: dict = None) -> SignalResult:
    hs, aws = raw.home_stats, raw.away_stats
    h_poss = _stat(hs, "Ball Possession")
    a_poss = _stat(aws, "Ball Possession")
    home_xg = _player_sum(raw.home_players, "xg")
    away_xg = _player_sum(raw.away_players, "xg")

    poss_gap = h_poss - a_poss
    if abs(poss_gap) < 15:
        return SignalResult("possession_waste", "efficiency_tear", 0.0)

    if poss_gap > 0:
        dominant_xg, passive_xg = home_xg, away_xg
        dominant_name = raw.home_team.name
    else:
        dominant_xg, passive_xg = away_xg, home_xg
        dominant_name = raw.away_team.name

    if dominant_xg >= passive_xg + 0.5:
        return SignalResult("possession_waste", "efficiency_tear", 0.0)

    waste_ratio = (passive_xg - dominant_xg) / max(abs(poss_gap), 1)
    strength = _clip(waste_ratio * 3)

    return SignalResult(
        name="possession_waste",
        category="efficiency_tear",
        strength=strength,
        evidence={"possession_gap": abs(poss_gap), "dominant_xg": round(dominant_xg, 2), "passive_xg": round(passive_xg, 2)},
        narrative_hint=f"{dominant_name}控球率高达{max(h_poss,a_poss):.0f}%，但xG({dominant_xg:.2f})反而低于对手({passive_xg:.2f})——控球无效，效率被反杀",
    )


def signal_counter_attack_efficiency(raw: RawMatchData, computed: dict = None) -> SignalResult:
    hs, aws = raw.home_stats, raw.away_stats
    h_poss = _stat(hs, "Ball Possession")
    a_poss = _stat(aws, "Ball Possession")
    home_xg = _player_sum(raw.home_players, "xg")
    away_xg = _player_sum(raw.away_players, "xg")
    h_shots = _stat(hs, "Total Shots")
    a_shots = _stat(aws, "Total Shots")

    for low_poss, low_xg, low_shots, low_name, high_shots in [
        (h_poss, home_xg, h_shots, raw.home_team.name, a_shots),
        (a_poss, away_xg, a_shots, raw.away_team.name, h_shots),
    ]:
        if low_poss < 45 and low_shots > 0:
            xg_per_shot = low_xg / max(low_shots, 1)
            if xg_per_shot > 0.15 and low_xg > 0.5:
                return SignalResult(
                    name="counter_attack_efficiency",
                    category="efficiency_tear",
                    strength=_clip(xg_per_shot / 0.25),
                    evidence={"team": low_name, "possession": low_poss, "xg_per_shot": round(xg_per_shot, 3)},
                    narrative_hint=f"{low_name}控球率仅{low_poss:.0f}%，但每次射门xG高达{xg_per_shot:.3f}——经典的高效反击战术",
                )

    return SignalResult("counter_attack_efficiency", "efficiency_tear", 0.0)


def signal_pass_efficiency_gap(raw: RawMatchData, computed: dict = None) -> SignalResult:
    hs, aws = raw.home_stats, raw.away_stats
    h_pass = _stat(hs, "Total passes")
    a_pass = _stat(aws, "Total passes")
    h_key = _stat(hs, "Key Passes")
    a_key = _stat(aws, "Key Passes")

    h_eff = _safe_ratio(h_key, h_pass)
    a_eff = _safe_ratio(a_key, a_pass)

    if h_pass < 50 or a_pass < 50:
        return SignalResult("pass_efficiency_gap", "efficiency_tear", 0.0)

    eff_gap = abs(h_eff - a_eff)
    if eff_gap < 0.03:
        return SignalResult("pass_efficiency_gap", "efficiency_tear", 0.0)

    stronger = raw.home_team.name if h_eff > a_eff else raw.away_team.name
    return SignalResult(
        name="pass_efficiency_gap",
        category="efficiency_tear",
        strength=_clip(eff_gap / 0.08),
        evidence={"home_key_pass_rate": round(h_eff, 4), "away_key_pass_rate": round(a_eff, 4)},
        narrative_hint=f"{stronger}的关键传球转化率明显更高——传球的目的性和威胁性更强",
    )


def signal_shot_quality_gap(raw: RawMatchData, computed: dict = None) -> SignalResult:
    home_xg = _player_sum(raw.home_players, "xg")
    away_xg = _player_sum(raw.away_players, "xg")
    hs, aws = raw.home_stats, raw.away_stats
    h_shots = _stat(hs, "Total Shots")
    a_shots = _stat(aws, "Total Shots")

    if h_shots < 3 or a_shots < 3:
        return SignalResult("shot_quality_gap", "efficiency_tear", 0.0)

    h_qual = home_xg / max(h_shots, 1)
    a_qual = away_xg / max(a_shots, 1)

    ratio = max(h_qual, a_qual) / max(min(h_qual, a_qual), EPSILON)
    if ratio < 2.0:
        return SignalResult("shot_quality_gap", "efficiency_tear", 0.0)

    better = raw.home_team.name if h_qual > a_qual else raw.away_team.name
    return SignalResult(
        name="shot_quality_gap",
        category="efficiency_tear",
        strength=_clip((ratio - 1.5) / 3.0),
        evidence={"home_xg_per_shot": round(h_qual, 3), "away_xg_per_shot": round(a_qual, 3)},
        narrative_hint=f"{better}的每脚射门平均xG是对手的{ratio:.1f}倍——射门位置和质量差距巨大",
    )


def signal_corner_efficiency(raw: RawMatchData, computed: dict = None) -> SignalResult:
    hs, aws = raw.home_stats, raw.away_stats
    h_corners = _stat(hs, "Corner Kicks")
    a_corners = _stat(aws, "Corner Kicks")

    corner_goals_home = sum(1 for e in raw.events if e.event_type == "Goal" and e.detail == "goal" and e.comments and "corner" in (e.comments or "").lower())
    corner_goals_away = sum(1 for e in raw.events if e.event_type == "Goal" and e.detail == "goal" and e.comments and "corner" in (e.comments or "").lower())

    for corners, goals, name in [
        (h_corners, corner_goals_home, raw.home_team.name),
        (a_corners, corner_goals_away, raw.away_team.name),
    ]:
        if corners >= 5 and goals >= 2:
            return SignalResult(
                name="corner_efficiency",
                category="efficiency_tear",
                strength=_clip(goals / corners * 5),
                evidence={"team": name, "corners": corners, "corner_goals": goals},
                narrative_hint=f"{name}的角球战术极具威胁——{corners}个角球中转化为{goals}个进球",
            )

    return SignalResult("corner_efficiency", "efficiency_tear", 0.0)


def signal_big_chance_conversion(raw: RawMatchData, computed: dict = None) -> SignalResult:
    hs, aws = raw.home_stats, raw.away_stats
    h_bc = _stat(hs, "Big Chances Created")
    a_bc = _stat(aws, "Big Chances Created")
    h_bc_missed = _stat(hs, "Big Chances Missed")
    a_bc_missed = _stat(aws, "Big Chances Missed")

    for bc, missed, name in [
        (h_bc, h_bc_missed, raw.home_team.name),
        (a_bc, a_bc_missed, raw.away_team.name),
    ]:
        if bc >= 3 and missed >= bc * 0.6:
            return SignalResult(
                name="big_chance_conversion",
                category="efficiency_tear",
                strength=_clip(missed / bc),
                evidence={"team": name, "big_chances": bc, "missed": missed},
                narrative_hint=f"{name}创造了{bc}次绝佳机会却错失{missed}次——浪费机会的能力令人震惊",
            )

    return SignalResult("big_chance_conversion", "efficiency_tear", 0.0)


# ============================================================
# C. Individual Hero/Villain — 个人英雄/罪人
# ============================================================

def signal_one_man_team(raw: RawMatchData, computed: dict = None) -> SignalResult:
    for players, team_name in [
        (raw.home_players, raw.home_team.name),
        (raw.away_players, raw.away_team.name),
    ]:
        total_goals = sum(p.goals for p in players)
        if total_goals < 2:
            continue
        for p in players:
            if p.goals >= total_goals * 0.75 and p.goals >= 2:
                return SignalResult(
                    name="one_man_team",
                    category="individual",
                    strength=_clip(p.goals / total_goals + 0.3),
                    evidence={"player": p.name, "team": team_name, "goals": p.goals, "team_goals": total_goals},
                    narrative_hint=f"{p.name}包办了{team_name}{total_goals}个进球中的{p.goals}个——一个人扛起了整支球队的进攻",
                )

    return SignalResult("one_man_team", "individual", 0.0)


def signal_gk_hero(raw: RawMatchData, computed: dict = None) -> SignalResult:
    hs, aws = raw.home_stats, raw.away_stats
    h_saves = _stat(hs, "Goalkeeper Saves")
    a_saves = _stat(aws, "Goalkeeper Saves")

    # xGOT faced by each GK = opponent players' xGOT sum (shots on target quality against this GK)
    home_xgot_faced = _player_sum(raw.away_players, "xgot")
    away_xgot_faced = _player_sum(raw.home_players, "xgot")

    for saves, own_players, opp_players, name, conceded, xgot_faced in [
        (h_saves, raw.home_players, raw.away_players, raw.home_team.name, raw.score.away, home_xgot_faced),
        (a_saves, raw.away_players, raw.home_players, raw.away_team.name, raw.score.home, away_xgot_faced),
    ]:
        # Find the GK who actually played (minutes_played > 0)
        gk = next((p for p in own_players if p.position == "G" and (p.minutes_played or 0) > 0), None)
        if not gk:
            continue

        # 核心指标：xG阻止量 = 对方射正期望进球 − 实际丢球
        xg_prevented = xgot_faced - conceded

        # 辅助指标：扑救成功率
        faced = saves + conceded
        save_pct = _safe_ratio(saves, faced) if faced > 0 else 0

        # 条件：必须面对足够威胁，且确实做出了贡献
        if (saves < 3 and xgot_faced < 0.3) or xg_prevented < 0.1:
            continue

        # 综合评分
        xg_score = _clip(xg_prevented / 1.5)
        pct_score = _clip((save_pct - 0.5) / 0.35) if save_pct > 0.5 else 0
        clean_bonus = 0.15 if conceded == 0 else 0

        strength = _clip(xg_score * 0.6 + pct_score * 0.25 + clean_bonus)

        if strength < 0.15:
            continue

        hints = []
        if xg_prevented >= 0.5:
            hints.append(f"阻止了{xg_prevented:.2f}个预期进球")
        if save_pct >= 0.8:
            hints.append(f"扑救成功率高达{save_pct:.0%}")
        if conceded == 0:
            hints.append(f"零封对手")

        return SignalResult(
            name="gk_hero",
            category="individual",
            strength=round(strength, 2),
            evidence={
                "gk": gk.name, "team": name,
                "saves": int(saves), "conceded": conceded,
                "xgot_faced": round(xgot_faced, 2),
                "xg_prevented": round(xg_prevented, 2),
                "save_pct": round(save_pct, 3),
            },
            narrative_hint=f"{gk.name}{'零封对手' if conceded==0 else '仅丢'+str(conceded)+'球'}，"
                           f"面对{xgot_faced:.2f} xGOT完成{saves}次扑救——" + "；".join(hints),
        )

    return SignalResult("gk_hero", "individual", 0.0)


def signal_gk_disaster(raw: RawMatchData, computed: dict = None) -> SignalResult:
    for players, stats, team_name, conceded in [
        (raw.home_players, raw.home_stats, raw.home_team.name, raw.score.away),
        (raw.away_players, raw.away_stats, raw.away_team.name, raw.score.home),
    ]:
        gk = next((p for p in players if p.position == "G" and (p.minutes_played or 0) > 0), None)
        if not gk:
            continue
        has_error = gk.error_lead_to_goal > 0
        saves = _stat(stats, "Goalkeeper Saves")
        save_pct = _safe_ratio(saves, saves + conceded) if (saves + conceded) > 0 else 1.0

        if has_error or (conceded >= 3 and save_pct < 0.5):
            return SignalResult(
                name="gk_disaster",
                category="individual",
                strength=_clip((conceded / 5.0) + (0.5 if has_error else 0)),
                evidence={"gk": gk.name, "conceded": conceded, "errors": gk.error_lead_to_goal},
                narrative_hint=f"{gk.name}本场表现灾难——失球{conceded}个" + (f"，还出现了{gk.error_lead_to_goal}次直接导致丢球的失误" if has_error else f"，扑救成功率仅{save_pct:.0%}"),
            )

    return SignalResult("gk_disaster", "individual", 0.0)


def signal_super_sub(raw: RawMatchData, computed: dict = None) -> SignalResult:
    for players, team_name in [
        (raw.home_players, raw.home_team.name),
        (raw.away_players, raw.away_team.name),
    ]:
        subs = [p for p in players if p.is_substitute and p.minutes_played > 0]
        for sub in subs:
            contribution = sub.goals * 3 + sub.assists * 2 + sub.shots_on * 0.5
            if contribution >= 3:
                per_min_contrib = contribution / max(sub.minutes_played, 1)
                return SignalResult(
                    name="super_sub",
                    category="individual",
                    strength=_clip(per_min_contrib * 15),
                    evidence={
                        "player": sub.name, "team": team_name,
                        "minutes": sub.minutes_played, "goals": sub.goals,
                        "assists": sub.assists,
                    },
                    narrative_hint=f"替补出场的{sub.name}在仅{sub.minutes_played}分钟内贡献了{sub.goals}球{sub.assists}助——替补奇兵改变战局",
                )

    return SignalResult("super_sub", "individual", 0.0)


def signal_fatal_error(raw: RawMatchData, computed: dict = None) -> SignalResult:
    for players, team_name in [
        (raw.home_players, raw.home_team.name),
        (raw.away_players, raw.away_team.name),
    ]:
        for p in players:
            if p.error_lead_to_goal > 0:
                return SignalResult(
                    name="fatal_error",
                    category="individual",
                    strength=_clip(p.error_lead_to_goal / 2.0),
                    evidence={"player": p.name, "team": team_name, "errors": p.error_lead_to_goal},
                    narrative_hint=f"{p.name}的{p.error_lead_to_goal}次致命失误直接导致丢球——个人失误成为比赛转折点",
                )

    return SignalResult("fatal_error", "individual", 0.0)


def signal_rating_paradox(raw: RawMatchData, computed: dict = None) -> SignalResult:
    for players, team_name in [
        (raw.home_players, raw.home_team.name),
        (raw.away_players, raw.away_team.name),
    ]:
        for p in players:
            if p.rating is None or p.minutes_played < 60:
                continue
            if p.rating >= 7.5 and p.passes_accuracy < 50 and p.duels_won < max(p.duels_total, 1) * 0.3:
                return SignalResult(
                    name="rating_paradox",
                    category="individual",
                    strength=0.6,
                    evidence={"player": p.name, "team": team_name, "rating": p.rating},
                    narrative_hint=f"{p.name}评分高达{p.rating}，但传球成功率仅{p.passes_accuracy}%——高分背后的数据值得深挖",
                )

    return SignalResult("rating_paradox", "individual", 0.0)


# ============================================================
# D. Structural Issues — 结构性问题
# ============================================================

def signal_wing_domination(raw: RawMatchData, computed: dict = None) -> SignalResult:
    hs, aws = raw.home_stats, raw.away_stats
    h_cross = _stat(hs, "Crosses")
    a_cross = _stat(aws, "Crosses")
    h_acc_cross = _stat(hs, "Accurate Crosses")
    a_acc_cross = _stat(aws, "Accurate Crosses")

    cross_ratio = max(h_cross, a_cross) / max(min(h_cross, a_cross), 1)
    if cross_ratio < 2.5 or max(h_cross, a_cross) < 10:
        return SignalResult("wing_domination", "structural", 0.0)

    dominant = raw.home_team.name if h_cross > a_cross else raw.away_team.name
    return SignalResult(
        name="wing_domination",
        category="structural",
        strength=_clip((cross_ratio - 2) / 3.0),
        evidence={"home_crosses": h_cross, "away_crosses": a_cross},
        narrative_hint=f"{dominant}的边路完全压制——传中次数是对手的{cross_ratio:.1f}倍，边路走廊畅通无阻",
    )


def signal_attack_channel_bias(raw: RawMatchData, computed: dict = None) -> SignalResult:
    if computed is None:
        return SignalResult("attack_channel_bias", "structural", 0.0)

    for dist, name in [
        (computed.get("home_attack_distribution", {}), raw.home_team.name),
        (computed.get("away_attack_distribution", {}), raw.away_team.name),
    ]:
        if not dist:
            continue
        values = [dist.get(k, 0) for k in ("left", "center", "right")]
        total = sum(values)
        if total < 10:
            continue
        for i, ch in enumerate(["左路", "中路", "右路"]):
            pct = values[i] / max(total, 1)
            if pct > 0.50:
                return SignalResult(
                    name="attack_channel_bias",
                    category="structural",
                    strength=_clip((pct - 0.45) / 0.20),
                    evidence={"team": name, "channel": ch, "percentage": round(pct * 100)},
                    narrative_hint=f"{name}的进攻{round(pct*100)}%集中在{ch}——进攻方向重度偏斜",
                )

    return SignalResult("attack_channel_bias", "structural", 0.0)


def signal_aerial_domination(raw: RawMatchData, computed: dict = None) -> SignalResult:
    hs, aws = raw.home_stats, raw.away_stats
    h_headers = _stat(hs, "Successful Headers")
    a_headers = _stat(aws, "Successful Headers")

    if max(h_headers, a_headers) < 8:
        return SignalResult("aerial_domination", "structural", 0.0)

    ratio = max(h_headers, a_headers) / max(min(h_headers, a_headers), 1)
    if ratio < 2.0:
        return SignalResult("aerial_domination", "structural", 0.0)

    dominant = raw.home_team.name if h_headers > a_headers else raw.away_team.name
    return SignalResult(
        name="aerial_domination",
        category="structural",
        strength=_clip((ratio - 1.5) / 2.5),
        evidence={"home_headers": h_headers, "away_headers": a_headers},
        narrative_hint=f"{dominant}在空中完全碾压——成功头球是对手的{ratio:.1f}倍，制空权一边倒",
    )


def signal_tactical_fouls(raw: RawMatchData, computed: dict = None) -> SignalResult:
    hs, aws = raw.home_stats, raw.away_stats
    h_fouls = _stat(hs, "Fouls")
    a_fouls = _stat(aws, "Fouls")
    h_yellow = _stat(hs, "Yellow Cards")
    a_yellow = _stat(aws, "Yellow Cards")

    for fouls, yellows, name in [
        (h_fouls, h_yellow, raw.home_team.name),
        (a_fouls, a_yellow, raw.away_team.name),
    ]:
        if fouls >= 10 and yellows <= 2:
            ratio = fouls / max(yellows, 1)
            if ratio >= 5:
                return SignalResult(
                    name="tactical_fouls",
                    category="structural",
                    strength=_clip(ratio / 10.0),
                    evidence={"team": name, "fouls": fouls, "yellows": yellows},
                    narrative_hint=f"{name}犯规{fouls}次却仅获{yellows}张黄牌——精明的战术犯规策略有效打断了对手节奏",
                )

    return SignalResult("tactical_fouls", "structural", 0.0)


def signal_sub_timing_impact(raw: RawMatchData, computed: dict = None) -> SignalResult:
    sub_events = [e for e in raw.events if e.event_type == "subst"]
    if not sub_events:
        return SignalResult("sub_timing_impact", "structural", 0.0)

    first_sub = min(e.time_elapsed for e in sub_events)
    last_sub = max(e.time_elapsed for e in sub_events)

    if first_sub < 30:
        return SignalResult(
            name="sub_timing_impact",
            category="structural",
            strength=0.5,
            evidence={"first_sub": first_sub, "total_subs": len(sub_events)},
            narrative_hint=f"第{first_sub}分钟就出现换人——可能是伤病被动调整或战术主动纠错",
        )

    if last_sub >= 85 and len(sub_events) > 0:
        return SignalResult(
            name="sub_timing_impact",
            category="structural",
            strength=0.3,
            evidence={"last_sub": last_sub},
            narrative_hint=f"第{last_sub}分钟的换人带有拖延时间或最后一搏的色彩",
        )

    return SignalResult("sub_timing_impact", "structural", 0.0)


def signal_formation_mismatch(raw: RawMatchData, computed: dict = None) -> SignalResult:
    home_xg = _player_sum(raw.home_players, "xg")
    away_xg = _player_sum(raw.away_players, "xg")
    hs, aws = raw.home_stats, raw.away_stats
    h_shots_ib = _stat(hs, "Shots insidebox")
    a_shots_ib = _stat(aws, "Shots insidebox")
    h_shots_ob = _stat(hs, "Shots outsidebox")
    a_shots_ob = _stat(aws, "Shots outsidebox")

    for ib, ob, xg, name in [
        (h_shots_ib, h_shots_ob, home_xg, raw.home_team.name),
        (a_shots_ib, a_shots_ob, away_xg, raw.away_team.name),
    ]:
        if ob > ib * 1.5 and ob >= 5:
            return SignalResult(
                name="formation_mismatch",
                category="structural",
                strength=_clip(ob / max(ib + ob, 1) - 0.5),
                evidence={"team": name, "inside_box": ib, "outside_box": ob},
                narrative_hint=f"{name}的射门大部分来自禁区外({ob}vs{ib})——无法穿透对方防线，阵型和打法可能被克制",
            )

    return SignalResult("formation_mismatch", "structural", 0.0)


# ============================================================
# E. Narrative Hooks — 叙事钩子
# ============================================================

def signal_mirror_match(raw: RawMatchData, computed: dict = None) -> SignalResult:
    hs, aws = raw.home_stats, raw.away_stats
    metrics = ["Total Shots", "Shots on Goal", "Total passes", "Corner Kicks", "Fouls"]
    similar_count = 0
    for m in metrics:
        h_val = _stat(hs, m)
        a_val = _stat(aws, m)
        if max(h_val, a_val) > 0:
            ratio = min(h_val, a_val) / max(h_val, a_val)
            if ratio > 0.75:
                similar_count += 1

    if similar_count >= 4:
        return SignalResult(
            name="mirror_match",
            category="narrative",
            strength=_clip(similar_count / 5.0),
            evidence={"similar_metrics": similar_count},
            narrative_hint="两队数据惊人地相似——像是照镜子一样的对局，细节决定成败",
        )

    return SignalResult("mirror_match", "narrative", 0.0)


def signal_high_scoring(raw: RawMatchData, computed: dict = None) -> SignalResult:
    total = raw.score.home + raw.score.away
    if total >= 5:
        return SignalResult(
            name="high_scoring",
            category="narrative",
            strength=_clip(total / 8.0),
            evidence={"total_goals": total},
            narrative_hint=f"全场{total}个进球——进球大战，双方防线大开大合",
        )
    return SignalResult("high_scoring", "narrative", 0.0)


def signal_clean_sheet(raw: RawMatchData, computed: dict = None) -> SignalResult:
    if raw.score.away == 0 or raw.score.home == 0:
        team = raw.home_team.name if raw.score.away == 0 else raw.away_team.name
        return SignalResult(
            name="clean_sheet",
            category="narrative",
            strength=0.4,
            evidence={"team": team},
            narrative_hint=f"{team}零封对手——防守端展现了出色的组织纪律性",
        )
    return SignalResult("clean_sheet", "narrative", 0.0)


def signal_comeback(raw: RawMatchData, computed: dict = None) -> SignalResult:
    goals = [e for e in raw.events if e.event_type == "Goal" and e.detail not in ("pen_shootout_goal", "pen_shootout_miss")]
    if len(goals) < 2:
        return SignalResult("comeback", "narrative", 0.0)

    score_diff = 0
    was_trailing = False
    comeback_team_id = None
    for g in sorted(goals, key=lambda x: x.time_elapsed):
        if g.team_id == raw.home_team.id:
            score_diff += 1
        else:
            score_diff -= 1
        if score_diff < 0 and comeback_team_id is None:
            was_trailing = True
            comeback_team_id = raw.home_team.id
        elif score_diff > 0 and comeback_team_id is None:
            was_trailing = True
            comeback_team_id = raw.away_team.id

    if was_trailing and ((raw.score.home > raw.score.away and comeback_team_id == raw.home_team.id) or
                         (raw.score.away > raw.score.home and comeback_team_id == raw.away_team.id)):
        team_name = raw.home_team.name if comeback_team_id == raw.home_team.id else raw.away_team.name
        return SignalResult(
            name="comeback",
            category="narrative",
            strength=0.7,
            evidence={"team": team_name, "final_score": f"{raw.score.home}-{raw.score.away}"},
            narrative_hint=f"{team_name}在落后情况下完成逆转——展现了强大的心理素质和战术调整能力",
        )

    return SignalResult("comeback", "narrative", 0.0)


def signal_draw_drama(raw: RawMatchData, computed: dict = None) -> SignalResult:
    if raw.score.home == raw.score.away and raw.score.home > 0:
        home_xg = _player_sum(raw.home_players, "xg")
        away_xg = _player_sum(raw.away_players, "xg")
        xg_diff = abs(home_xg - away_xg)
        return SignalResult(
            name="draw_drama",
            category="narrative",
            strength=_clip(xg_diff / 2.0 + 0.3),
            evidence={"score": f"{raw.score.home}-{raw.score.away}", "xg_diff": round(xg_diff, 2)},
            narrative_hint=f"比分{raw.score.home}-{raw.score.away}，但xG差了{xg_diff:.2f}——平局背后的故事远比比分复杂",
        )
    return SignalResult("draw_drama", "narrative", 0.0)


def signal_rare_event(raw: RawMatchData, computed: dict = None) -> SignalResult:
    hs, aws = raw.home_stats, raw.away_stats
    woodwork = _stat(hs, "Hit Woodwork") + _stat(aws, "Hit Woodwork")
    if woodwork >= 3:
        return SignalResult(
            name="rare_event",
            category="narrative",
            strength=_clip(woodwork / 5.0),
            evidence={"woodwork_hits": woodwork},
            narrative_hint=f"全场{woodwork}次击中门框——门柱和横梁成了场上最忙碌的'防守球员'",
        )

    reds = _stat(hs, "Red Cards") + _stat(aws, "Red Cards")
    if reds >= 2:
        return SignalResult(
            name="rare_event",
            category="narrative",
            strength=0.6,
            evidence={"red_cards": reds},
            narrative_hint=f"全场{reds}张红牌——比赛在火药味十足的氛围中进行",
        )

    return SignalResult("rare_event", "narrative", 0.0)


# ============================================================
# F. Knockout/Extra Time Special — 淘汰赛专项
# ============================================================

def signal_halftime_adjustment(raw: RawMatchData, computed: dict = None) -> SignalResult:
    periods = raw.periods
    if len(periods) < 2:
        return SignalResult("halftime_adjustment", "knockout", 0.0)

    p1 = periods[0]
    p2 = periods[1]

    p1_h_shots = _stat(p1.home_stats, "Total Shots")
    p1_a_shots = _stat(p1.away_stats, "Total Shots")
    p2_h_shots = _stat(p2.home_stats, "Total Shots")
    p2_a_shots = _stat(p2.away_stats, "Total Shots")

    p1_diff = p1_h_shots - p1_a_shots
    p2_diff = p2_h_shots - p2_a_shots

    if abs(p1_diff - p2_diff) >= 3:
        if abs(p1_diff) > abs(p2_diff):
            team = raw.home_team.name if p1_diff > 0 else raw.away_team.name
            hint = f"{team}上半场占优但下半场被压制——对手半场调整效果显著"
        else:
            team = raw.home_team.name if p2_diff > 0 else raw.away_team.name
            hint = f"{team}下半场焕然一新——半场调整起到了决定性作用"
        return SignalResult(
            name="halftime_adjustment",
            category="knockout",
            strength=_clip(abs(p1_diff - p2_diff) / 8.0),
            evidence={"first_half_diff": p1_diff, "second_half_diff": p2_diff},
            narrative_hint=hint,
        )

    return SignalResult("halftime_adjustment", "knockout", 0.0)


def signal_extra_time_collapse(raw: RawMatchData, computed: dict = None) -> SignalResult:
    periods = raw.periods
    if len(periods) < 3:
        return SignalResult("extra_time_collapse", "knockout", 0.0)

    regular_periods = [p for p in periods if p.sort_order <= 2]
    et_periods = [p for p in periods if p.sort_order > 2]

    if not regular_periods or not et_periods:
        return SignalResult("extra_time_collapse", "knockout", 0.0)

    reg_shots = sum(_stat(p.home_stats, "Total Shots") + _stat(p.away_stats, "Total Shots") for p in regular_periods)
    et_shots = sum(_stat(p.home_stats, "Total Shots") + _stat(p.away_stats, "Total Shots") for p in et_periods)
    reg_duration = sum(p.period_length for p in regular_periods)
    et_duration = sum(p.period_length for p in et_periods)

    if reg_duration <= 0 or et_duration <= 0:
        return SignalResult("extra_time_collapse", "knockout", 0.0)

    reg_rate = reg_shots / reg_duration
    et_rate = et_shots / max(et_duration, 1)

    if reg_rate > 0 and et_rate < reg_rate * 0.5:
        return SignalResult(
            name="extra_time_collapse",
            category="knockout",
            strength=_clip((1 - et_rate / max(reg_rate, EPSILON)) * 1.5),
            evidence={"reg_shot_rate": round(reg_rate, 2), "et_shot_rate": round(et_rate, 2)},
            narrative_hint=f"加时赛比赛强度急剧下降——常规时间射门频率{reg_rate:.2f}/分钟降至加时赛{et_rate:.2f}/分钟",
        )

    return SignalResult("extra_time_collapse", "knockout", 0.0)


def signal_penalty_shootout_hero(raw: RawMatchData, computed: dict = None) -> SignalResult:
    pen_events = [e for e in raw.events if e.detail in ("pen_shootout_goal", "pen_shootout_miss")]
    if not pen_events:
        return SignalResult("penalty_shootout_hero", "knockout", 0.0)

    goals = [e for e in pen_events if e.detail == "pen_shootout_goal"]
    misses = [e for e in pen_events if e.detail == "pen_shootout_miss"]

    # Build player→team mapping from lineups (shootout events may lack team_name)
    player_team = {}
    for pp, tn in [(raw.home_players, raw.home_team.name), (raw.away_players, raw.away_team.name)]:
        for p in pp:
            player_team[p.name.strip().lower()] = tn
            if p.photo_url and "?" not in p.photo_url:
                pass  # keep first mapping

    def _team_of(player_name: str) -> str:
        """Try event team_name first, fall back to player lineup lookup."""
        if not player_name:
            return ""
        for e in pen_events:
            if e.player_name == player_name and e.team_name:
                return e.team_name
        return player_team.get(player_name.strip().lower(), "")

    if misses:
        # List ALL missers with their teams
        miss_details = []
        for m in misses:
            tn = _team_of(m.player_name)
            miss_details.append(f"{m.player_name}({tn})" if tn else m.player_name)

        miss_str = "、".join(miss_details)
        strength = _clip(0.5 + len(misses) * 0.15)  # more misses = more drama

        return SignalResult(
            name="penalty_shootout_hero",
            category="knockout",
            strength=strength,
            evidence={
                "penalty_goals": len(goals),
                "penalty_misses": len(misses),
                "missers": miss_details,
            },
            narrative_hint=f"点球大战{len(misses)}人罚失（{miss_str}）——点球成为了英雄与失意者的分水岭",
        )

    return SignalResult("penalty_shootout_hero", "knockout", 0.0)


def signal_lead_protect_mode(raw: RawMatchData, computed: dict = None) -> SignalResult:
    periods = raw.periods
    if len(periods) < 2:
        return SignalResult("lead_protect_mode", "knockout", 0.0)

    p1 = periods[0]
    p2 = periods[1]
    h_poss_p1 = _stat(p1.home_stats, "Ball Possession")
    a_poss_p1 = _stat(p1.away_stats, "Ball Possession")
    h_poss_p2 = _stat(p2.home_stats, "Ball Possession")
    a_poss_p2 = _stat(p2.away_stats, "Ball Possession")

    if h_poss_p1 > 55 and h_poss_p2 < 45:
        return SignalResult(
            name="lead_protect_mode",
            category="knockout",
            strength=0.5,
            evidence={"team": raw.home_team.name, "p1_poss": h_poss_p1, "p2_poss": h_poss_p2},
            narrative_hint=f"{raw.home_team.name}控球率从{h_poss_p1:.0f}%骤降至{h_poss_p2:.0f}%——取得领先后切换为防守模式",
        )
    if a_poss_p1 > 55 and a_poss_p2 < 45:
        return SignalResult(
            name="lead_protect_mode",
            category="knockout",
            strength=0.5,
            evidence={"team": raw.away_team.name, "p1_poss": a_poss_p1, "p2_poss": a_poss_p2},
            narrative_hint=f"{raw.away_team.name}控球率从{a_poss_p1:.0f}%骤降至{a_poss_p2:.0f}%——取得领先后切换为防守模式",
        )

    return SignalResult("lead_protect_mode", "knockout", 0.0)


def signal_et_sub_impact(raw: RawMatchData, computed: dict = None) -> SignalResult:
    et_periods = [p for p in raw.periods if p.sort_order > 2]
    if not et_periods:
        return SignalResult("et_sub_impact", "knockout", 0.0)

    et_subs = [e for e in raw.events if e.event_type == "subst" and e.period_id and e.period_id > 2]
    if et_subs:
        return SignalResult(
            name="et_sub_impact",
            category="knockout",
            strength=0.4,
            evidence={"et_subs": len(et_subs)},
            narrative_hint=f"加时赛有{len(et_subs)}次换人——教练用尽最后的人力资源进行战术调整",
        )

    return SignalResult("et_sub_impact", "knockout", 0.0)


def signal_diff_stage_rhythm(raw: RawMatchData, computed: dict = None) -> SignalResult:
    periods = raw.periods
    if len(periods) < 3:
        return SignalResult("diff_stage_rhythm", "knockout", 0.0)

    stage_stats = {}
    for p in periods:
        desc = p.description
        total_shots = _stat(p.home_stats, "Total Shots") + _stat(p.away_stats, "Total Shots")
        stage_stats[desc] = total_shots

    values = list(stage_stats.values())
    if len(values) >= 3:
        max_val = max(values)
        min_val = min(values)
        if min_val > 0 and max_val / min_val >= 3:
            return SignalResult(
                name="diff_stage_rhythm",
                category="knockout",
                strength=_clip((max_val / max(min_val, 1) - 2) / 3.0),
                evidence=stage_stats,
                narrative_hint="不同比赛阶段的进攻节奏差异巨大——常规时间、加时赛、点球大战呈现完全不同的面貌",
            )

    return SignalResult("diff_stage_rhythm", "knockout", 0.0)


def signal_period_goal_cluster(raw: RawMatchData, computed: dict = None) -> SignalResult:
    periods = raw.periods
    if len(periods) < 2:
        return SignalResult("period_goal_cluster", "knockout", 0.0)

    period_goals = {}
    for e in raw.events:
        if e.event_type == "Goal" and e.detail not in ("pen_shootout_goal", "pen_shootout_miss"):
            pid = e.period_id if e.period_id else 1
            period_goals[pid] = period_goals.get(pid, 0) + 1

    for pid, goals in period_goals.items():
        if goals >= 3:
            pd_desc = next((p.description for p in periods if p.sort_order == pid), f"第{pid}时段")
            return SignalResult(
                name="period_goal_cluster",
                category="knockout",
                strength=_clip(goals / 5.0),
                evidence={"period": pd_desc, "goals": goals},
                narrative_hint=f"{pd_desc}集中出现了{goals}个进球——这是比赛的疯狂时段",
            )

    return SignalResult("period_goal_cluster", "knockout", 0.0)


def signal_dominant_et(raw: RawMatchData, computed: dict = None) -> SignalResult:
    et_periods = [p for p in raw.periods if p.sort_order > 2]
    if not et_periods:
        return SignalResult("dominant_et", "knockout", 0.0)

    h_et_shots = sum(_stat(p.home_stats, "Total Shots") for p in et_periods)
    a_et_shots = sum(_stat(p.away_stats, "Total Shots") for p in et_periods)

    if max(h_et_shots, a_et_shots) >= 4:
        ratio = max(h_et_shots, a_et_shots) / max(min(h_et_shots, a_et_shots), 1)
        if ratio >= 3:
            dominant = raw.home_team.name if h_et_shots > a_et_shots else raw.away_team.name
            return SignalResult(
                name="dominant_et",
                category="knockout",
                strength=_clip((ratio - 2) / 3.0),
                evidence={"dominant": dominant, "home_et_shots": h_et_shots, "away_et_shots": a_et_shots},
                narrative_hint=f"{dominant}在加时赛完全掌控——射门次数{h_et_shots if dominant == raw.home_team.name else a_et_shots}远超对手",
            )

    return SignalResult("dominant_et", "knockout", 0.0)


# ============================================================
# G. Trends-driven — 趋势驱动信号
# ============================================================

def signal_rhythm_swing(trend_analysis: TrendAnalysis, raw: RawMatchData) -> SignalResult:
    phases = trend_analysis.rhythm_phases
    if len(phases) < 3:
        return SignalResult("rhythm_swing", "trends", 0.0)

    swings = 0
    for i in range(1, len(phases)):
        if phases[i]["dominant"] != phases[i - 1]["dominant"]:
            swings += 1

    if swings >= 3:
        return SignalResult(
            name="rhythm_swing",
            category="trends",
            strength=_clip(swings / 6.0),
            evidence={"swings": swings, "phases": phases},
            narrative_hint=f"比赛节奏经历{swings}次转换——双方交替掌控局面，没有一方能持续压制",
        )

    return SignalResult("rhythm_swing", "trends", 0.0)


def signal_duel_decay_alert(trend_analysis: TrendAnalysis, raw: RawMatchData) -> SignalResult:
    for decays, team_name in [
        (trend_analysis.duel_decay_home, raw.home_team.name),
        (trend_analysis.duel_decay_away, raw.away_team.name),
    ]:
        for d in decays:
            if d.severity in ("moderate", "severe"):
                return SignalResult(
                    name="duel_decay_alert",
                    category="trends",
                    strength=_clip(0.5 if d.severity == "moderate" else 0.8),
                    evidence={
                        "team": team_name,
                        "early_rate": d.early_win_rate,
                        "late_rate": d.late_win_rate,
                        "decay": d.decay,
                        "severity": d.severity,
                    },
                    narrative_hint=f"{team_name}的对抗成功率从{d.early_win_rate:.2f}降至{d.late_win_rate:.2f}——体能下降或斗志消退值得关注",
                )

    return SignalResult("duel_decay_alert", "trends", 0.0)


def signal_stamina_fade(trend_analysis: TrendAnalysis, raw: RawMatchData) -> SignalResult:
    fade = max(trend_analysis.pressing_fade_home, trend_analysis.pressing_fade_away)
    if fade < 0.2:
        return SignalResult("stamina_fade", "trends", 0.0)

    fading_team = raw.home_team.name if trend_analysis.pressing_fade_home >= trend_analysis.pressing_fade_away else raw.away_team.name
    return SignalResult(
        name="stamina_fade",
        category="trends",
        strength=_clip(fade * 1.5),
        evidence={
            "team": fading_team,
            "home_fade": trend_analysis.pressing_fade_home,
            "away_fade": trend_analysis.pressing_fade_away,
        },
        narrative_hint=f"{fading_team}的压迫效率在比赛后半段显著下降（衰减{fade:.0%}）——体能瓶颈可能成为败因",
    )


def signal_tactical_shift(trend_analysis: TrendAnalysis, raw: RawMatchData) -> SignalResult:
    for style, team_name in [
        (trend_analysis.style_shift_home, raw.home_team.name),
        (trend_analysis.style_shift_away, raw.away_team.name),
    ]:
        if style.get("shift_detected"):
            direction = style["direction"]
            if direction == "more_direct":
                hint = f"{team_name}在比赛中转向更直接的打法——长传/传中比例明显上升"
            elif direction == "more_possessional":
                hint = f"{team_name}在比赛中转向更耐心的控球打法——短传比例上升"
            else:
                continue
            return SignalResult(
                name="tactical_shift",
                category="trends",
                strength=_clip(style.get("magnitude", 0) * 2),
                evidence=style,
                narrative_hint=hint,
            )

    return SignalResult("tactical_shift", "trends", 0.0)


def signal_turning_point_alert(trend_analysis: TrendAnalysis, raw: RawMatchData) -> SignalResult:
    points = trend_analysis.turning_points
    strong_points = [p for p in points if p.confidence >= 0.5]
    if not strong_points:
        return SignalResult("turning_point_alert", "trends", 0.0)

    top = sorted(strong_points, key=lambda p: p.confidence, reverse=True)[:3]
    hints = "; ".join(p.description for p in top)
    return SignalResult(
        name="turning_point_alert",
        category="trends",
        strength=_clip(len(strong_points) / 4.0),
        evidence={"points": [{"minute": p.minute, "metric": p.metric, "desc": p.description} for p in top]},
        narrative_hint=f"趋势数据捕捉到多个比赛转折点: {hints}",
    )


def signal_momentum_surge(trend_analysis: TrendAnalysis, raw: RawMatchData) -> SignalResult:
    for type_id in (42, 43, 44):
        h_series = trend_analysis.home_series.get(type_id)
        a_series = trend_analysis.away_series.get(type_id)
        if not h_series or not a_series:
            continue

        from src.engine.trends import detect_slope_changes
        h_changes = detect_slope_changes(h_series, window_size=8, threshold=0.50)
        a_changes = detect_slope_changes(a_series, window_size=8, threshold=0.50)

        all_changes = [(c, raw.home_team.name) for c in h_changes] + [(c, raw.away_team.name) for c in a_changes]
        surges = [c for c, _ in all_changes if c.direction == "accelerating" and c.magnitude >= 0.6]
        if surges:
            top_surge = max(surges, key=lambda c: c.magnitude)
            for c, tn in all_changes:
                if c is top_surge:
                    return SignalResult(
                        name="momentum_surge",
                        category="trends",
                        strength=_clip(top_surge.magnitude / 1.5),
                        evidence={
                            "team": tn,
                            "minute": top_surge.minute,
                            "magnitude": round(top_surge.magnitude, 2),
                        },
                        narrative_hint=f"第{top_surge.minute}分钟前后{tn}突然发力——进攻节奏急剧攀升，进入暴走模式",
                    )

    return SignalResult("momentum_surge", "trends", 0.0)


# ============================================================
# H. Event-Trend Hybrid — 事件×趋势结合分析
# ============================================================

def _trend_window_sum(series: "TrendSeries", start_min: int, end_min: int) -> float:
    """Sum of increments within [start_min, end_min). Returns 0 if no data."""
    if not series or not series.increments:
        return 0.0
    total = 0.0
    for inc, m in zip(series.increments, series.minutes):
        if start_min <= m < end_min:
            total += inc
    return total


def _trend_window_avg(series: "TrendSeries", start_min: int, end_min: int) -> float:
    """Average increment per minute within [start_min, end_min)."""
    if not series or not series.increments:
        return 0.0
    total = 0.0
    count = 0
    for inc, m in zip(series.increments, series.minutes):
        if start_min <= m < end_min:
            total += inc
            count += 1
    return total / count if count > 0 else 0.0


def _get_trend(trend_analysis, is_home: bool, type_id: int):
    """Get TrendSeries for a team, by type_id."""
    if not trend_analysis:
        return None
    series_dict = trend_analysis.home_series if is_home else trend_analysis.away_series
    return series_dict.get(type_id)


# ----- H1: 换人对趋势的影响 -----

def signal_sub_impact_on_trend(trend_analysis, raw) -> "SignalResult":
    """Compare trend metrics 10 min before vs after each substitution."""
    sub_events = [e for e in raw.events if e.event_type == "subst"]
    if not sub_events or not trend_analysis:
        return SignalResult("sub_impact_on_trend", "event_impact", 0.0)

    for sub_e in sub_events:
        sub_min = sub_e.time_elapsed
        # Determine which team made the sub
        is_home = sub_e.team_id == raw.home_team.id
        team_name = raw.home_team.name if is_home else raw.away_team.name

        # Key metrics to check: shots(42), attacks(43), possession(45)
        impacts = []
        for type_id, metric_name in [(42, "射门"), (43, "进攻"), (45, "控球")]:
            series = _get_trend(trend_analysis, is_home, type_id)
            if not series:
                continue
            before = _trend_window_avg(series, max(0, sub_min - 10), sub_min)
            after = _trend_window_avg(series, sub_min, min(sub_min + 10, 130))
            if before > 0 and after > 0:
                change_pct = (after - before) / before
                if abs(change_pct) > 0.4:
                    impacts.append((metric_name, change_pct))

        if len(impacts) >= 2:
            avg_change = sum(abs(c) for _, c in impacts) / len(impacts)
            direction = "提升" if sum(c for _, c in impacts) > 0 else "下降"
            detail = "; ".join(f"{m}{'+' if c > 0 else ''}{c*100:.0f}%" for m, c in impacts)
            return SignalResult(
                name="sub_impact_on_trend",
                category="event_impact",
                strength=_clip(avg_change * 1.5),
                evidence={
                    "team": team_name, "sub_minute": sub_min,
                    "player_in": sub_e.player_name, "player_out": sub_e.assist_name,
                    "impacts": detail,
                },
                narrative_hint=f"{team_name}第{sub_min}分钟换上{sub_e.player_name}后，{direction}明显——{detail}",
            )

    return SignalResult("sub_impact_on_trend", "event_impact", 0.0)


# ----- H2: 红牌对趋势的影响 -----

def signal_red_card_collapse(trend_analysis, raw) -> "SignalResult":
    """After a red card, check if pressing/defense metrics collapsed."""
    red_events = [e for e in raw.events if e.detail in ("redcard", "yellowredcard")]
    if not red_events or not trend_analysis:
        return SignalResult("red_card_collapse", "event_impact", 0.0)

    for red_e in red_events:
        red_min = red_e.time_elapsed
        is_home = red_e.team_id == raw.home_team.id
        team_name = raw.home_team.name if is_home else raw.away_team.name

        # Defensive metrics: tackles(78), duels_won(106), ball_recoveries(27271)
        decays = []
        for type_id, metric_name in [(78, "抢断"), (106, "赢得对抗"), (27271, "球权回收")]:
            series = _get_trend(trend_analysis, is_home, type_id)
            if not series:
                continue
            before = _trend_window_avg(series, max(0, red_min - 15), red_min)
            after = _trend_window_avg(series, red_min, min(red_min + 15, 130))
            if before > 0:
                change_pct = (after - before) / before
                if change_pct < -0.2:  # decline > 20%
                    decays.append((metric_name, abs(change_pct)))

        if len(decays) >= 2:
            avg_decay = sum(d for _, d in decays) / len(decays)
            detail = "; ".join(f"{m}↓{d*100:.0f}%" for m, d in decays)
            return SignalResult(
                name="red_card_collapse",
                category="event_impact",
                strength=_clip(avg_decay * 1.5 + 0.3),
                evidence={
                    "team": team_name, "red_minute": red_min,
                    "player": red_e.player_name, "decays": detail,
                },
                narrative_hint=f"{red_e.player_name}第{red_min}分钟被罚下后，{team_name}防守体系崩溃——{detail}",
            )

    return SignalResult("red_card_collapse", "event_impact", 0.0)


# ----- H3: 进球后的动量转换 -----

def signal_goal_momentum_shift(trend_analysis, raw) -> "SignalResult":
    """After a goal, check which team gained momentum in the next 15 min."""
    goal_events = [e for e in raw.events
                   if e.event_type == "Goal" and e.detail not in ("pen_shootout_goal", "pen_shootout_miss")]
    if not goal_events or not trend_analysis:
        return SignalResult("goal_momentum_shift", "event_impact", 0.0)

    for goal_e in goal_events:
        goal_min = goal_e.time_elapsed

        # For both teams, compare shots+attacks rate in [goal_min, goal_min+15] vs [goal_min-15, goal_min]
        def _team_momentum(is_home):
            rates_before = []
            rates_after = []
            for type_id in (42, 43):  # shots, attacks
                series = _get_trend(trend_analysis, is_home, type_id)
                if not series:
                    continue
                b = _trend_window_avg(series, max(0, goal_min - 15), goal_min)
                a = _trend_window_avg(series, goal_min, min(goal_min + 15, 130))
                rates_before.append(b)
                rates_after.append(a)
            if rates_before and rates_after:
                avg_before = sum(rates_before) / len(rates_before)
                avg_after = sum(rates_after) / len(rates_after)
                if avg_before > 0:
                    return (avg_after - avg_before) / avg_before, avg_before, avg_after
            return 0, 0, 0

        h_change, h_b, h_a = _team_momentum(True)
        a_change, a_b, a_a = _team_momentum(False)

        # Significant shift: one team surged while the other didn't
        delta = h_change - a_change
        if abs(delta) > 0.5:
            gaining = raw.home_team.name if delta > 0 else raw.away_team.name
            return SignalResult(
                name="goal_momentum_shift",
                category="event_impact",
                strength=_clip(abs(delta) / 2.0),
                evidence={
                    "goal_minute": goal_min, "scorer": goal_e.player_name,
                    "gaining_team": gaining,
                    "home_change": round(h_change, 2), "away_change": round(a_change, 2),
                },
                narrative_hint=f"{goal_e.player_name}第{goal_min}分钟进球后，{gaining}明显接管了比赛节奏——攻防势头彻底转移",
            )

    return SignalResult("goal_momentum_shift", "event_impact", 0.0)


# ----- H4: VAR对比赛节奏的干扰 -----

def signal_var_disruption(trend_analysis, raw) -> "SignalResult":
    """After VAR, check if the game's action frequency was disrupted."""
    var_events = [e for e in raw.events if e.detail == "var" or e.event_type == "VAR"]
    if not var_events or not trend_analysis:
        return SignalResult("var_disruption", "event_impact", 0.0)

    for var_e in var_events:
        var_min = var_e.time_elapsed

        # Composite action index: shots + tackles + attacks (both teams)
        total_before = 0.0
        total_after = 0.0
        for is_home in (True, False):
            for type_id in (42, 78, 43):  # shots, tackles, attacks
                series = _get_trend(trend_analysis, is_home, type_id)
                if not series:
                    continue
                total_before += _trend_window_avg(series, max(0, var_min - 5), var_min)
                total_after += _trend_window_avg(series, var_min, min(var_min + 5, 130))

        if total_before > 0:
            disruption = 1.0 - (total_after / total_before)
            if disruption > 0.3:
                return SignalResult(
                    name="var_disruption",
                    category="event_impact",
                    strength=_clip(disruption * 2.0),
                    evidence={
                        "var_minute": var_min,
                        "action_drop_pct": f"{disruption*100:.0f}%",
                    },
                    narrative_hint=f"第{var_min}分钟VAR介入后，比赛节奏被打乱——攻防频率下降{disruption*100:.0f}%",
                )

    return SignalResult("var_disruption", "event_impact", 0.0)


# ----- H5: 趋势转折点与事件关联 -----

def signal_event_coincident_inflection(trend_analysis, raw) -> "SignalResult":
    """When trend turning points coincide with major events within ±3 min."""
    if not trend_analysis:
        return SignalResult("event_coincident_inflection", "event_impact", 0.0)

    strong_tps = [tp for tp in trend_analysis.turning_points if tp.confidence >= 0.5]
    if not strong_tps:
        return SignalResult("event_coincident_inflection", "event_impact", 0.0)

    # Collect major events with their minutes
    major_events = []
    for e in raw.events:
        if e.event_type == "Goal" and e.detail not in ("pen_shootout_goal", "pen_shootout_miss"):
            major_events.append((e.time_elapsed, "进球", e.player_name))
        elif e.detail in ("redcard", "yellowredcard"):
            major_events.append((e.time_elapsed, "红牌", e.player_name))
        elif e.detail == "var" or e.event_type == "VAR":
            major_events.append((e.time_elapsed, "VAR", ""))
        elif e.event_type == "subst":
            major_events.append((e.time_elapsed, "换人", e.player_name))

    matches = []
    for tp in strong_tps:
        for ev_min, ev_type, ev_player in major_events:
            if abs(tp.minute - ev_min) <= 3:
                matches.append((tp, ev_type, ev_player, ev_min))
                break

    if matches:
        best_match = max(matches, key=lambda m: m[0].confidence)
        tp, ev_type, ev_player, ev_min = best_match
        return SignalResult(
            name="event_coincident_inflection",
            category="event_impact",
            strength=_clip(tp.confidence + 0.3),
            evidence={
                "turning_point_minute": tp.minute,
                "turning_point_metric": tp.metric,
                "linked_event": f"{ev_type}({ev_min}')",
                "linked_player": ev_player,
                "confidence": tp.confidence,
            },
            narrative_hint=f"第{tp.minute}分钟{tp.metric}出现转折点（置信度{tp.confidence:.0%}），"
                           f"与第{ev_min}分钟的{ev_type}直接相关——这不是巧合",
        )

    return SignalResult("event_coincident_inflection", "event_impact", 0.0)


# ============================================================
# I. Player Contribution Kings — 进攻王/防守王/均衡王
# ============================================================

# Weight constants
_W_GOAL = 25; _W_AST = 15; _W_XG = 20; _W_SOT = 5; _W_KP = 6; _W_DRB = 1            # 成功过人 × 成功率% — 自然区分量(1/1→1.0, 7/7→7.0)
_W_P3RD = 1.5; _W_FLD = 5   # fouls_drawn — 被侵犯（含制造点球）
_W_TOUCH = 0.03; _W_PASS_ACC = 0.05   # 传球成功率%
_W_PASS_TOT = 0.02; _W_CROSS = 1      # 传中
_W_FINISH = 10   # 终结质量 = xGOT - xG (典型范围 -1 ~ +1)
_W_SHOOT_PERF = 5  # shooting_performance (SportMonks, 典型范围 -2 ~ +2)

_W_TKW = 10; _W_INT = 8; _W_CLR = 3; _W_BLK = 8; _W_REC = 4; _W_DUW = 1    # 赢得对抗 × 成功率%
_W_SAVES = 15; _W_XGP = 30; _W_GK_CLR = 3; _W_GK_REC = 3

_BONUS_WINNING = 20    # 制胜球
_BONUS_EQUALIZER = 15  # 扳平球（维持到终场）
_BONUS_SUPER_SUB = 20  # 替补上场5分钟内进球
_BONUS_FIRST_GOAL = 10 # 胜方首开记录
_BONUS_LATE_WINNER = 25 # 终场前5分钟内的制胜绝杀（胜方仅赢1球）
_MIN_MINUTES = 30

_king_cache: dict = {}  # cache {match_id: computed_king_data}


def _compute_king_scores(raw: RawMatchData) -> dict:
    """Returns {team_name: {players, kings}} for both teams. Cached per match."""
    cache_key = raw.match_id
    if cache_key in _king_cache:
        return _king_cache[cache_key]

    result = {}
    events = raw.events
    goals = [e for e in events if e.event_type == "Goal" and e.detail not in ("pen_shootout_goal", "pen_shootout_miss")]
    subs = [e for e in events if e.event_type == "subst"]

    def _tkl_won(p):
        t = (p.tackles_total or 0)
        pct = (p.tackles_won_pct or 0) / 100
        return t * pct

    def _find_winning_goal_scorer():
        """Last goal that put the eventual winner ahead for good."""
        if raw.score.home == raw.score.away:
            return None
        winner_is_home = raw.score.home > raw.score.away
        sorted_goals = sorted(goals, key=lambda g: (g.period_id or 0, g.time_elapsed))
        h, a = 0, 0
        last_winner_goal = None
        for g in sorted_goals:
            is_home = g.team_id == raw.home_team.id
            if is_home:
                h += 1
            else:
                a += 1
            # Check: does this goal give the eventual winner their winning margin?
            if winner_is_home and h > a:
                last_winner_goal = g.player_name
            elif not winner_is_home and a > h:
                last_winner_goal = g.player_name
        return last_winner_goal

    def _get_match_end_minute():
        """Determine actual match end minute based on periods.
        If extra time (sort_order 3-4) exists, end = 120.
        If penalty shootout only, end = 120 (football play ends at extra time).
        Otherwise, end = 90.
        """
        max_sort = 0
        for pd in raw.periods:
            if pd.sort_order > max_sort:
                max_sort = pd.sort_order
        if max_sort >= 3:
            return 120  # extra time or penalties
        return 90

    def _find_equalizer_scorer():
        """
        Equalizer = tying goal scored in the LAST 5 MINUTES of the match
         (including extra time), and the score stays tied to the end.
        """
        if raw.score.home != raw.score.away or raw.score.home == 0:
            return None
        sorted_goals = sorted(goals, key=lambda g: (g.period_id or 0, g.time_elapsed))
        if not sorted_goals:
            return None
        end_minute = _get_match_end_minute()
        # Track score progression, find the goal that tied it
        h, a = 0, 0
        equalizer = None
        for g in sorted_goals:
            is_home = g.team_id == raw.home_team.id
            if is_home:
                h += 1
            else:
                a += 1
            if h == a:
                # Only count if the goal is in the last 5 minutes
                if g.time_elapsed >= end_minute - 5:
                    equalizer = g.player_name
        return equalizer

    def _find_super_sub_scorers():
        """Substitutes who scored within 5 min of coming on."""
        result = {}
        for sub in subs:
            sub_in = sub.assist_name  # 换上球员
            sub_time = sub.time_elapsed
            if not sub_in:
                continue
            for goal in goals:
                if goal.player_name and goal.player_name.strip().lower() == sub_in.strip().lower():
                    diff = goal.time_elapsed - sub_time
                    if 1 <= diff <= 5:
                        result[sub_in] = diff
        return result

    winning_scorer = _find_winning_goal_scorer()
    equalizer_scorer = _find_equalizer_scorer()
    super_sub_map = _find_super_sub_scorers()

    def _find_first_goal_scorer():
        """Winner's first goal scorer (only for non-draw matches)."""
        if raw.score.home == raw.score.away:
            return None
        winner_is_home = raw.score.home > raw.score.away
        sorted_goals = sorted(goals, key=lambda g: (g.period_id or 0, g.time_elapsed))
        if not sorted_goals:
            return None
        # First goal scored by the eventual winner
        h, a = 0, 0
        for g in sorted_goals:
            is_home = g.team_id == raw.home_team.id
            if is_home:
                h += 1
            else:
                a += 1
            if winner_is_home and h > a:
                return g.player_name
            elif not winner_is_home and a > h:
                return g.player_name
        return None

    def _find_late_winner_scorer():
        """Last goal that won the game by 1 margin, scored in the final 5 min of normal/extra time."""
        if raw.score.home == raw.score.away:
            return None
        goal_diff = abs(raw.score.home - raw.score.away)
        if goal_diff != 1:
            return None
        # Determine actual match end (90 or 120) based on period structure
        end_minute = _get_match_end_minute()
        # Match ended without extra time, find latest goal within 5 min of end
        sorted_goals = sorted(goals, key=lambda g: (g.period_id or 0, g.time_elapsed))
        if not sorted_goals:
            return None
        # Find the goal that made the winning margin
        winner_is_home = raw.score.home > raw.score.away
        h, a = 0, 0
        last_winner_margin_goal = None
        for g in sorted_goals:
            is_home = g.team_id == raw.home_team.id
            if is_home:
                h += 1
            else:
                a += 1
            if winner_is_home and h > a and (h - a) == 1:
                last_winner_margin_goal = g
            elif not winner_is_home and a > h and (a - h) == 1:
                last_winner_margin_goal = g
        if last_winner_margin_goal and last_winner_margin_goal.time_elapsed >= end_minute - 5:
            return last_winner_margin_goal.player_name
        return None

    first_goal_scorer = _find_first_goal_scorer()
    late_winner_scorer = _find_late_winner_scorer()

    for pp, tn in [(raw.home_players, raw.home_team.name), (raw.away_players, raw.away_team.name)]:
        players = []
        for p in pp:
            pos = (p.position or "").strip()
            mins = (p.minutes_played or 0)
            if mins < _MIN_MINUTES:
                continue

            if pos == "G":
                # Goalkeeper: defense-only scoring
                saves = p.saves or 0
                xg_prevented = _player_sum(
                    raw.away_players if pp is raw.home_players else raw.home_players, "xgot"
                ) - (raw.score.away if pp is raw.home_players else raw.score.home)
                clr = p.clearances or 0
                rec = p.ball_recoveries or 0

                min_factor = min(mins / 90, 1.0)
                def_score = round(
                    (saves * _W_SAVES + xg_prevented * _W_XGP + clr * _W_GK_CLR + rec * _W_GK_REC) * min_factor, 1
                )
                players.append({
                    "name": p.name, "pos": pos, "mins": mins, "rating": p.rating,
                    "attack": 0.0, "defense": def_score, "balanced": 0.0,
                })
                continue

            # Outfield player
            goals_n = p.goals or 0
            ast = p.assists or 0
            xg = p.xg or 0
            sot = p.shots_on or 0
            kp = p.passes_key or 0
            drb_suc = p.dribbles_success or 0
            drb_att = p.dribbles_attempts or 0
            drb_rate = (drb_suc / drb_att * 100) if drb_att > 0 else 0  # 过人成功率%
            p3rd = p.passes_final_third or 0
            fld = p.fouls_drawn or 0
            # 新增 9 项
            tch = p.touches or 0
            pass_acc = p.passes_accuracy or 0     # 已有的百分比值
            pass_tot = p.passes_total or 0
            crs = p.crosses or 0
            xgot = p.xgot or 0
            finish = (xgot - xg) if (xgot is not None and xg is not None) else 0  # 终结质量
            shoot_perf = p.shooting_performance or 0

            tk = _tkl_won(p)
            inter = p.tackles_interceptions or 0
            clr = p.clearances or 0
            blk = p.blocked_shots or 0
            rec = p.ball_recoveries or 0
            duw = p.duels_won or 0
            dut = p.duels_total or 0
            duw_rate = (duw / dut * 100) if dut > 0 else 0  # 对抗成功率%

            min_factor = min(mins / 90, 1.0)

            raw_att = (goals_n * _W_GOAL + ast * _W_AST + xg * _W_XG + sot * _W_SOT
                       + kp * _W_KP + drb_suc * (drb_rate / 100) * _W_DRB + p3rd * _W_P3RD + fld * _W_FLD
                       + tch * _W_TOUCH + pass_acc * _W_PASS_ACC + pass_tot * _W_PASS_TOT
                       + crs * _W_CROSS + finish * _W_FINISH + shoot_perf * _W_SHOOT_PERF)
            attack_score = raw_att * min_factor

            # Bonus: winning / equalizer / super sub / first goal / late winner
            if p.name == winning_scorer:
                attack_score += _BONUS_WINNING
            if p.name == equalizer_scorer:
                attack_score += _BONUS_EQUALIZER
            if p.name in super_sub_map:
                attack_score += _BONUS_SUPER_SUB
            if p.name == first_goal_scorer:
                attack_score += _BONUS_FIRST_GOAL
            if p.name == late_winner_scorer:
                attack_score += _BONUS_LATE_WINNER

            raw_def = (tk * _W_TKW + inter * _W_INT + clr * _W_CLR + blk * _W_BLK + rec * _W_REC
                       + duw * (duw_rate / 100) * _W_DUW)
            defense_score = raw_def * min_factor

            attack_score = round(attack_score, 1)
            defense_score = round(defense_score, 1)

            # Balanced = harmonic mean
            if attack_score > 0 and defense_score > 0:
                balanced_score = round(2 * attack_score * defense_score / (attack_score + defense_score), 1)
            else:
                balanced_score = 0.0

            players.append({
                "name": p.name, "pos": pos, "mins": mins, "rating": p.rating,
                "attack": attack_score, "defense": defense_score, "balanced": balanced_score,
            })

        outfield = [pl for pl in players if pl["pos"] != "G"]

        result[tn] = {
            "players": players,
            "offensive_king": max(outfield, key=lambda x: x["attack"]) if outfield else None,
            "defensive_king": max(outfield, key=lambda x: x["defense"]) if outfield else None,
            "balanced_king": max(outfield, key=lambda x: x["balanced"]) if outfield else None,
        }

    _king_cache[cache_key] = result
    return result


def signal_offensive_king(raw: RawMatchData, computed: dict = None) -> SignalResult:
    king_data = _compute_king_scores(raw)
    evidence = {}
    lines = []
    max_score = 0
    for tn in [raw.home_team.name, raw.away_team.name]:
        outfield = [p for p in king_data[tn]["players"] if p["pos"] != "G"]
        top3 = sorted(outfield, key=lambda x: x["attack"], reverse=True)[:3]
        evidence[tn] = [{"name": p["name"], "pos": p["pos"], "rating": p["rating"],
                         "mins": p["mins"], "attack": p["attack"]} for p in top3]
        k = top3[0]
        if k["attack"] >= 5:
            lines.append(f"{tn}: {k['name']}({k['attack']:.0f}分)")
            max_score = max(max_score, k["attack"])

    if not lines:
        return SignalResult("offensive_king", "player_contribution", 0.0)

    return SignalResult(
        name="offensive_king",
        category="player_contribution",
        strength=_clip(max_score / 100),
        evidence={"top3": evidence},
        narrative_hint=f"进攻贡献王 —— " + "；".join(lines),
    )


def signal_defensive_king(raw: RawMatchData, computed: dict = None) -> SignalResult:
    king_data = _compute_king_scores(raw)
    evidence = {}
    lines = []
    max_score = 0
    for tn in [raw.home_team.name, raw.away_team.name]:
        outfield = [p for p in king_data[tn]["players"] if p["pos"] != "G"]
        top3 = sorted(outfield, key=lambda x: x["defense"], reverse=True)[:3]
        evidence[tn] = [{"name": p["name"], "pos": p["pos"], "rating": p["rating"],
                         "mins": p["mins"], "defense": p["defense"]} for p in top3]
        k = top3[0]
        if k["defense"] >= 5:
            lines.append(f"{tn}: {k['name']}({k['defense']:.0f}分)")
            max_score = max(max_score, k["defense"])

    if not lines:
        return SignalResult("defensive_king", "player_contribution", 0.0)

    return SignalResult(
        name="defensive_king",
        category="player_contribution",
        strength=_clip(max_score / 100),
        evidence={"top3": evidence},
        narrative_hint=f"防守贡献王 —— " + "；".join(lines),
    )


def signal_balanced_king(raw: RawMatchData, computed: dict = None) -> SignalResult:
    king_data = _compute_king_scores(raw)
    evidence = {}
    lines = []
    max_score = 0
    for tn in [raw.home_team.name, raw.away_team.name]:
        outfield = [p for p in king_data[tn]["players"] if p["pos"] != "G"]
        top3 = sorted(outfield, key=lambda x: x["balanced"], reverse=True)[:3]
        evidence[tn] = [{"name": p["name"], "pos": p["pos"], "rating": p["rating"],
                         "mins": p["mins"], "attack": p["attack"], "defense": p["defense"],
                         "balanced": p["balanced"]} for p in top3]
        k = top3[0]
        if k["balanced"] >= 5:
            lines.append(f"{tn}: {k['name']}")
            max_score = max(max_score, k["balanced"])

    if not lines:
        return SignalResult("balanced_king", "player_contribution", 0.0)

    return SignalResult(
        name="balanced_king",
        category="player_contribution",
        strength=_clip(max_score / 100),
        evidence={"top3": evidence},
        narrative_hint=f"攻防均衡王 —— " + "、".join(lines),
    )


# ----- I. PPDA 压迫强度 -----

def signal_pressing_intensity(raw: RawMatchData, computed: dict = None) -> SignalResult:
    """基于PPDA指标检测压迫强度差异。
    PPDA越低表示压迫越强（对手每次传球前遭遇更多防守动作）。
    """
    if computed is None:
        return SignalResult("pressing_intensity", "structural", 0.0)

    hp = getattr(computed, "home_ppda", 0) or 0
    ap = getattr(computed, "away_ppda", 0) or 0
    if hp <= 0 or ap <= 0:
        return SignalResult("pressing_intensity", "structural", 0.0)

    # Determine the more pressing team
    if hp < ap:
        press_team = raw.home_team.name
        opp_team = raw.away_team.name
        press_ppda = hp
        opp_ppda = ap
    else:
        press_team = raw.away_team.name
        opp_team = raw.home_team.name
        press_ppda = ap
        opp_ppda = hp

    ratio = opp_ppda / max(press_ppda, 0.1)

    # Strength: ratio > 2 = strong press, or single team PPDA < 6
    if ratio >= 2.0 or press_ppda < 6:
        strength = _clip(0.3 + 0.15 * ratio)
        if press_ppda < 5:
            hint = f"{press_team} 采用**高压迫**战术（PPDA={press_ppda}），对手{opp_team}每次传球前都要面对高强度逼抢。"
        elif press_ppda < 8:
            hint = f"{press_team} 压迫明显强于{opp_team}（PPDA {press_ppda} vs {opp_ppda}），主动在中前场施压。"
        else:
            hint = f"{press_team} 压迫强度显著领先{opp_team}（PPDA比 {ratio:.1f}:1）。"
        return SignalResult(
            name="pressing_intensity",
            category="structural",
            strength=strength,
            evidence={"home_ppda": hp, "away_ppda": ap, "ratio": round(ratio, 1)},
            narrative_hint=hint,
        )

    return SignalResult("pressing_intensity", "structural", 0.0)


# ============================================================
# Main detector — runs all
# ============================================================

ALL_DETECTORS = [
    ("xg_upset", signal_xg_upset),
    ("conversion_anomaly", signal_conversion_anomaly),
    ("penalty_decided", signal_penalty_decided),
    ("red_card_turning", signal_red_card_turning),
    ("own_goal_impact", signal_own_goal_impact),
    ("late_winner", signal_late_winner),
    ("possession_waste", signal_possession_waste),
    ("counter_attack_efficiency", signal_counter_attack_efficiency),
    ("pass_efficiency_gap", signal_pass_efficiency_gap),
    ("shot_quality_gap", signal_shot_quality_gap),
    ("corner_efficiency", signal_corner_efficiency),
    ("big_chance_conversion", signal_big_chance_conversion),
    ("one_man_team", signal_one_man_team),
    ("gk_hero", signal_gk_hero),
    ("gk_disaster", signal_gk_disaster),
    ("super_sub", signal_super_sub),
    ("fatal_error", signal_fatal_error),
    ("rating_paradox", signal_rating_paradox),
    ("wing_domination", signal_wing_domination),
    ("attack_channel_bias", signal_attack_channel_bias),
    ("aerial_domination", signal_aerial_domination),
    ("tactical_fouls", signal_tactical_fouls),
    ("sub_timing_impact", signal_sub_timing_impact),
    ("formation_mismatch", signal_formation_mismatch),
    ("mirror_match", signal_mirror_match),
    ("high_scoring", signal_high_scoring),
    ("clean_sheet", signal_clean_sheet),
    ("comeback", signal_comeback),
    ("draw_drama", signal_draw_drama),
    ("rare_event", signal_rare_event),
    ("halftime_adjustment", signal_halftime_adjustment),
    ("extra_time_collapse", signal_extra_time_collapse),
    ("penalty_shootout_hero", signal_penalty_shootout_hero),
    ("lead_protect_mode", signal_lead_protect_mode),
    ("et_sub_impact", signal_et_sub_impact),
    ("diff_stage_rhythm", signal_diff_stage_rhythm),
    ("period_goal_cluster", signal_period_goal_cluster),
    ("dominant_et", signal_dominant_et),
    # I. Player Contribution Kings
    ("offensive_king", signal_offensive_king),
    ("defensive_king", signal_defensive_king),
    ("balanced_king", signal_balanced_king),
    # J. PPDA 压迫强度
    ("pressing_intensity", signal_pressing_intensity),
]

TRENDS_DETECTORS = [
    ("rhythm_swing", signal_rhythm_swing),
    ("duel_decay_alert", signal_duel_decay_alert),
    ("stamina_fade", signal_stamina_fade),
    ("tactical_shift", signal_tactical_shift),
    ("turning_point_alert", signal_turning_point_alert),
    ("momentum_surge", signal_momentum_surge),
    # H. Event-Trend Hybrid
    ("sub_impact_on_trend", signal_sub_impact_on_trend),
    ("red_card_collapse", signal_red_card_collapse),
    ("goal_momentum_shift", signal_goal_momentum_shift),
    ("var_disruption", signal_var_disruption),
    ("event_coincident_inflection", signal_event_coincident_inflection),
]


def detect_all(raw: RawMatchData, computed: dict = None,
               trend_analysis: TrendAnalysis = None) -> list[SignalResult]:
    results = []

    for name, detector in ALL_DETECTORS:
        try:
            result = detector(raw, computed)
            if result.strength >= 0.15:
                results.append(result)
        except Exception:
            pass

    if trend_analysis is not None:
        for name, detector in TRENDS_DETECTORS:
            try:
                result = detector(trend_analysis, raw)
                if result.strength >= 0.15:
                    results.append(result)
            except Exception:
                pass

    results.sort(key=lambda r: r.strength, reverse=True)
    return results


def get_top_signals(results: list[SignalResult], top_n: int = 6) -> list[SignalResult]:
    categorized = {}
    for r in results:
        categorized.setdefault(r.category, []).append(r)

    top = []
    for cat_signals in categorized.values():
        top.append(max(cat_signals, key=lambda r: r.strength))

    remaining = [r for r in results if r not in top]
    top.extend(sorted(remaining, key=lambda r: r.strength, reverse=True)[:top_n - len(top)])

    return sorted(top, key=lambda r: r.strength, reverse=True)[:top_n]
