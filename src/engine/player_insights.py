"""
11 Player Contribution Detectors — Modern Football Analysis

Each detector takes ALL player stats (up to 47 type_ids) and event bonuses,
outputs scored rankings with evidence data.

Detectors:
  D1  推进价值 (Progression Value)
  D2  压迫与反压迫 (Press & Counter-press)
  D3  无球价值/Gravity (Off-ball Value)
  D4  节奏控制/节拍器 (Tempo Control)
  D5  双向负荷 (Two-way Load)
  D6  时机价值 (Timing Value)
  D7  效率与产量背离 (Efficiency vs Volume)
  D8  角色偏离度 (Role Deviation)
  D9  连接器 (Connector)
  D10 终结质量 (Finishing Quality)
  D11 xG背离度 (xG Deviation)
  D12 纯终结者 (Pure Finisher)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional


# ═══════════════════════════════════════════════════════════════
# Position Classification
# ═══════════════════════════════════════════════════════════════
# SportMonks V3 position_id:
#   24 = Goalkeeper
#   2-10, 25 = Defender
#   11-18, 26 = Midfielder
#   19-27, 28, 156, 164, 165, 166 = Forward/Winger

GOALKEEPER_IDS = {24}
DEFENDER_IDS = {2, 3, 4, 5, 6, 7, 8, 9, 10, 25}
MIDFIELDER_IDS = {11, 12, 13, 14, 15, 16, 17, 18, 26}
FORWARD_IDS = {19, 20, 21, 22, 23, 27, 28, 156, 164, 165, 166}


def classify_position(pos_id: int) -> str:
    if pos_id in GOALKEEPER_IDS:
        return "G"
    if pos_id in DEFENDER_IDS:
        return "D"
    if pos_id in MIDFIELDER_IDS:
        return "M"
    if pos_id in FORWARD_IDS:
        return "F"
    return "?"


# ═══════════════════════════════════════════════════════════════
# Data Structures
# ═══════════════════════════════════════════════════════════════

@dataclass
class PlayerData:
    """Aggregated player stats from raw lineups."""
    player_id: int
    name: str
    position_id: int
    pos: str            # G/D/M/F
    team_name: str      # home / away
    stats: dict         # type_id → value
    photo_url: str = ""

    def sv(self, type_id: int, default=0.0):
        v = self.stats.get(type_id)
        if v is None:
            return default
        return float(v) if isinstance(v, (int, float)) else default

    def sv_int(self, type_id: int, default=0):
        v = self.stats.get(type_id)
        if v is None:
            return default
        return int(v) if isinstance(v, (int, float)) else default


@dataclass
class DetectorResult:
    """Result of a single detector for a single player."""
    name: str
    score: float
    evidence: dict = field(default_factory=dict)


@dataclass
class EventBonuses:
    """Event-driven bonuses for a player."""
    winning_goal: bool = False          # 制胜球
    equalizer: bool = False             # 绝平球
    late_winner: bool = False           # 绝杀 (85'+)
    first_goal: bool = False            # 胜方首开记录
    super_sub: bool = False             # 替补出场5分钟内进球/助攻
    scored_penalty: bool = False        # 点球进球

    def any(self) -> bool:
        return any([self.winning_goal, self.equalizer, self.late_winner,
                     self.first_goal, self.super_sub, self.scored_penalty])

    def as_bonus(self) -> float:
        score = 0.0
        if self.winning_goal: score += 3.0
        if self.late_winner: score += 3.5
        if self.equalizer: score += 2.5
        if self.first_goal: score += 2.0
        if self.super_sub: score += 2.5
        if self.scored_penalty: score += 0.5
        return score

    def labels(self) -> list[str]:
        result = []
        if self.winning_goal: result.append("制胜球")
        if self.late_winner: result.append("绝杀")
        if self.equalizer: result.append("绝平球")
        if self.first_goal: result.append("首开记录")
        if self.super_sub: result.append("超级替补")
        if self.scored_penalty: result.append("点球进球")
        return result


# ═══════════════════════════════════════════════════════════════
# Utility Functions
# ═══════════════════════════════════════════════════════════════

def zscore(values: list[float]) -> list[float]:
    """Z-score normalization."""
    if not values:
        return [0.0] * len(values)
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    std = math.sqrt(variance) if len(values) > 1 else 1.0
    if std < 0.001:
        std = 1.0
    return [(v - mean) / std for v in values]


def zscore_composite(
    players: list[PlayerData],
    metrics: dict[str, tuple[int, float]],
) -> list[tuple[str, float, dict]]:
    """
    metrics: {label: (type_id, weight)}
    Returns: [(name, composite_score, {label: {'raw':..., 'z':..., 'w':...}})]
    """
    scores = {p.name: 0.0 for p in players}
    breakdown = {p.name: {} for p in players}

    for label, (tid, weight) in metrics.items():
        raw_vals = [p.sv(tid) for p in players]
        zs = zscore(raw_vals)
        for i, p in enumerate(players):
            raw = p.sv(tid)
            z = zs[i]
            contrib = z * weight
            scores[p.name] += contrib
            breakdown[p.name][label] = {
                "raw": raw, "z": round(z, 3), "contrib": round(contrib, 3),
            }

    ranked = sorted(scores.items(), key=lambda x: -x[1])
    return [(name, round(score, 3), breakdown[name]) for name, score in ranked]


def top_n(results: list[tuple[str, float, dict]], n: int = 3):
    return results[:n]


# ═══════════════════════════════════════════════════════════════
# D1: 推进价值 (Progression Value)
# ═══════════════════════════════════════════════════════════════

D1_METRICS = {
    "三区传球":        (27269, 1.0),
    "成功过人":        (109, 0.8),
    "传中":           (98, 0.6),
    "精准传中":        (99, 0.4),
    "长传成功":        (123, 0.5),
    "关键传球":        (117, 0.7),
    "长传次数":        (122, 0.4),
    "创造机会":        (9706, 0.6),
    "创造绝佳机会":     (580, 0.8),
    "传中成功率":       (1533, 0.3),
    "尝试过人":        (108, 0.5),
}


def detect_progression(players: list[PlayerData]) -> list[DetectorResult]:
    results = zscore_composite(players, D1_METRICS)
    return [DetectorResult(name=n, score=s, evidence=e) for n, s, e in results]


# ═══════════════════════════════════════════════════════════════
# D2: 压迫与反压迫 (Press & Counter-press)
# ═══════════════════════════════════════════════════════════════

D2_METRICS = {
    "球权回收":        (27271, 1.0),
    "成功抢断":        (27267, 1.2),
    "抢断":           (78, 0.8),
    "赢得对抗":        (106, 0.6),
    "封堵射门":        (97, 0.5),
    "被过人":          (110, -0.8),
    "输掉对抗":        (1491, -0.5),
    "抢断成功率":       (27268, 0.6),
}


def detect_pressing(players: list[PlayerData]) -> list[DetectorResult]:
    results = zscore_composite(players, D2_METRICS)
    return [DetectorResult(name=n, score=s, evidence=e) for n, s, e in results]


# ═══════════════════════════════════════════════════════════════
# D3: 无球价值 / Gravity
# ═══════════════════════════════════════════════════════════════

D3_METRICS = {
    "被犯规":          (96, 1.0),
    "总对抗":          (105, 0.6),
    "赢得对抗":        (106, 0.5),
    "赢得空中对抗":     (107, 0.4),
    "赢得点球":        (115, 2.0),
    "空中对抗总数":     (27274, 0.4),
    "空中成功率":       (27275, 0.3),
    "对抗成功率":       (27276, 0.3),
    "输掉对抗":        (1491, -0.3),
}


def detect_gravity(players: list[PlayerData]) -> list[DetectorResult]:
    results = zscore_composite(players, D3_METRICS)
    return [DetectorResult(name=n, score=s, evidence=e) for n, s, e in results]


# ═══════════════════════════════════════════════════════════════
# D4: 节奏控制 / 节拍器
# ═══════════════════════════════════════════════════════════════

def detect_tempo(players: list[PlayerData]) -> list[DetectorResult]:
    team_passes = sum(p.sv(80) for p in players)
    team_touches = sum(p.sv(120) for p in players)
    if team_passes == 0:
        team_passes = 1
    if team_touches == 0:
        team_touches = 1

    results = []
    for p in players:
        passes = max(p.sv(80), 1)
        acc = p.sv(116)
        p3rd = p.sv(27269)
        touches = p.sv(120)
        back_passes = p.sv(27272)
        acc_pct = p.sv(1584)

        pass_share = passes / team_passes
        touch_share = touches / team_touches
        accuracy_val = acc_pct if acc_pct > 0 else (acc / passes * 100 if passes > 0 else 0)
        fwd_ratio = p3rd / passes if passes > 0 else 0
        back_penalty = back_passes / passes if passes > 0 else 0

        score = (
            pass_share * 100
            + (accuracy_val / 100) * 2
            + fwd_ratio * 10
            + touch_share * 100
            - back_penalty * 5
        )
        evidence = {
            "传球": int(passes),
            "传球占比": round(pass_share * 100, 1),
            "准确率": round(accuracy_val, 1),
            "三区传球": int(p3rd),
            "向前比": round(fwd_ratio * 100, 1),
            "回传": int(back_passes),
            "触球": int(touches),
            "触球占比": round(touch_share * 100, 1),
        }
        results.append(DetectorResult(name=p.name, score=round(score, 3), evidence=evidence))

    results.sort(key=lambda x: -x.score)
    return results


# ═══════════════════════════════════════════════════════════════
# D5: 双向负荷 (Two-way Load)
# ═══════════════════════════════════════════════════════════════

D5_ATK_METRICS = {
    "射门": (42, 1.0), "xG": (5304, 1.5), "xGOT": (5305, 1.0),
    "关键传球": (117, 1.2), "成功过人": (109, 0.8),
    "进球": (52, 2.0), "助攻": (79, 1.5), "三区传球": (27269, 0.6),
}

D5_DEF_METRICS = {
    "抢断": (78, 1.0), "拦截": (100, 1.0), "球权回收": (27271, 1.0),
    "封堵射门": (97, 0.8), "解围": (101, 0.5), "赢得对抗": (106, 0.6),
    "被过人": (110, -0.5), "被抢断": (94, -0.5),
    "导致丢球失误": (571, -2.0), "导致射门失误": (48997, -1.0),
}


def detect_twoway(players: list[PlayerData]) -> list[DetectorResult]:
    atk_ranked = zscore_composite(players, D5_ATK_METRICS)
    def_ranked = zscore_composite(players, D5_DEF_METRICS)

    atk_scores = {n: s for n, s, _ in atk_ranked}
    def_scores = {n: s for n, s, _ in def_ranked}

    # Rank-based harmonic mean
    a_order = sorted(atk_scores.items(), key=lambda x: -x[1])
    d_order = sorted(def_scores.items(), key=lambda x: -x[1])
    a_rank = {n: i + 1 for i, (n, _) in enumerate(a_order)}
    d_rank = {n: i + 1 for i, (n, _) in enumerate(d_order)}

    results = []
    for p in players:
        n = p.name
        ar = a_rank.get(n, len(players))
        dr = d_rank.get(n, len(players))
        hm = 2 * ar * dr / (ar + dr) if (ar + dr) > 0 else len(players)
        evidence = {
            "进攻排名": f"{ar}/{len(players)}",
            "防守排名": f"{dr}/{len(players)}",
            "进攻z": round(atk_scores.get(n, 0), 2),
            "防守z": round(def_scores.get(n, 0), 2),
        }
        results.append(DetectorResult(name=n, score=round(hm, 1), evidence=evidence))

    results.sort(key=lambda x: x.score)  # lower = better
    return results


# ═══════════════════════════════════════════════════════════════
# D6: 时机价值 (Timing Value)
# ═══════════════════════════════════════════════════════════════

def detect_timing(
    players: list[PlayerData],
    bonuses: dict[str, EventBonuses],
) -> list[DetectorResult]:
    results = []
    for p in players:
        eb = bonuses.get(p.name, EventBonuses())
        score = eb.as_bonus()
        g = p.sv_int(52)
        a = p.sv_int(79)
        pen_scored = p.sv_int(111)
        if g > 0:
            score += 0.5
        if a > 0:
            score += 0.3
        if pen_scored > 0:
            score += 0.5

        if score > 0:
            evidence = {
                "进球": g, "助攻": a, "点球进球": pen_scored,
                "事件加成": eb.labels(),
            }
            results.append(DetectorResult(name=p.name, score=round(score, 2), evidence=evidence))

    results.sort(key=lambda x: -x.score)
    return results


# ═══════════════════════════════════════════════════════════════
# D7: 效率与产量背离 (Efficiency vs Volume)
# ═══════════════════════════════════════════════════════════════

def detect_efficiency(players: list[PlayerData]) -> list[DetectorResult]:
    results = []
    for p in players:
        mins = max(p.sv(119), 1)
        if mins < 15:
            continue
        p90 = mins / 90.0

        xg90 = p.sv(5304) / p90
        kp90 = p.sv(117) / p90
        shots90 = p.sv(42) / p90
        drib90 = p.sv(109) / p90
        fouls_drawn90 = p.sv(96) / p90
        shots_on90 = p.sv(86) / p90
        shooting_perf90 = p.sv(9685) / p90

        score = (
            xg90 * 3.0
            + kp90 * 2.0
            + shots90 * 1.5
            + drib90 * 1.0
            + fouls_drawn90 * 0.5
            + shots_on90 * 1.5
            + shooting_perf90 * 2.0
        )
        evidence = {
            "分钟": int(mins),
            "xG/90": round(xg90, 3),
            "KP/90": round(kp90, 2),
            "射门/90": round(shots90, 2),
            "射正/90": round(shots_on90, 2),
            "过人/90": round(drib90, 2),
            "射门表现/90": round(shooting_perf90, 3),
            "xG": round(p.sv(5304), 3),
            "KP": int(p.sv(117)),
        }
        results.append(DetectorResult(name=p.name, score=round(score, 3), evidence=evidence))

    results.sort(key=lambda x: -x.score)
    return results


# ═══════════════════════════════════════════════════════════════
# D8: 角色偏离度 (Role Deviation)
# ═══════════════════════════════════════════════════════════════

ROLE_METRICS = {
    "D": {
        "三区传球": (27269, 1.0), "关键传球": (117, 1.0), "传中": (98, 0.8),
        "成功过人": (109, 0.5), "射门": (42, 0.7), "被犯规": (96, 0.5),
    },
    "M": {
        "抢断": (78, 0.8), "拦截": (100, 0.8), "解围": (101, 0.5),
        "封堵射门": (97, 0.5), "射门": (42, 0.6), "进球": (52, 0.8), "xG": (5304, 0.6),
    },
    "F": {
        "抢断": (78, 1.0), "拦截": (100, 0.8), "球权回收": (27271, 0.8),
        "封堵射门": (97, 0.7), "解围": (101, 0.4), "传球总数": (80, 0.5),
    },
}


def detect_role_deviation(players: list[PlayerData]) -> list[DetectorResult]:
    all_results = []
    for pos in ["D", "M", "F"]:
        pos_players = [p for p in players if p.pos == pos]
        if len(pos_players) < 2:
            continue
        metrics = ROLE_METRICS[pos]
        ranked = zscore_composite(pos_players, metrics)
        for name, score, bd in ranked:
            if score > 0.3:
                all_results.append(DetectorResult(
                    name=name, score=round(score, 3),
                    evidence={"位置": pos, "偏离分": round(score, 2), **bd},
                ))

    all_results.sort(key=lambda x: -x.score)
    return all_results


# ═══════════════════════════════════════════════════════════════
# D9: 连接器 (Connector)
# ═══════════════════════════════════════════════════════════════

D9_METRICS = {
    "三区传球":        (27269, 1.0),
    "成功过人":        (109, 0.5),
    "准确传球":        (116, 0.5),
    "长传成功":        (123, 0.3),
    "关键传球":        (117, 0.7),
    "长传次数":        (122, 0.3),
    "长传成功率":       (27270, 0.3),
    "创造机会":        (9706, 0.5),
}


def detect_connector(players: list[PlayerData]) -> list[DetectorResult]:
    results = zscore_composite(players, D9_METRICS)
    return [DetectorResult(name=n, score=s, evidence=e) for n, s, e in results]


# ═══════════════════════════════════════════════════════════════
# D10: 终结质量 (Finishing Quality)
# ═══════════════════════════════════════════════════════════════

def detect_finishing(players: list[PlayerData]) -> list[DetectorResult]:
    results = []
    for p in players:
        s = p
        shots = max(s.sv(42), 1)
        xg = s.sv(5304)
        xgot = s.sv(5305)
        goals = s.sv_int(52)
        shots_on = s.sv(86)
        woodwork = s.sv_int(64)
        shooting_perf = s.sv(9685)
        pen_scored = s.sv_int(111)

        # Exclude penalty xG from per-shot quality calculation
        # Penalty xG ≈ 0.76 (standard value)
        PENALTY_XG = 0.76
        non_pen_xg = max(xg - pen_scored * PENALTY_XG, 0)
        non_pen_shots = max(shots - pen_scored, 1)

        # Sub-metrics
        xg_per_shot = non_pen_xg / non_pen_shots  # 非点球 xG/射门
        xgot_quality = xgot - xg                  # 射正后质量提升
        actual_finish = goals - xgot              # 门将反应以外
        sot_ratio = shots_on / shots if shots > 0 else 0  # 射正率

        score = (
            xg_per_shot * 2.0
            + max(xgot_quality, 0) * 1.5
            + actual_finish * 1.0
            + sot_ratio * 1.0
            + shooting_perf * 1.5
            + woodwork * 0.8
        )
        evidence = {
            "射门": int(shots),
            "xG": round(xg, 3),
            "xG/射门": round(xg_per_shot, 4),
            "非点球xG": round(non_pen_xg, 3),
            "xGOT": round(xgot, 3),
            "射正质量": round(xgot_quality, 3),
            "进球": goals,
            "点球进球": pen_scored,
            "实际终结": round(actual_finish, 3),
            "射正": int(shots_on),
            "射正率": round(sot_ratio * 100, 1),
            "射门表现": round(shooting_perf, 3),
            "中框": woodwork,
        }
        results.append(DetectorResult(name=p.name, score=round(score, 3), evidence=evidence))

    results.sort(key=lambda x: -x.score)
    return results


# ═══════════════════════════════════════════════════════════════
# D11: xG 背离度 (xG Deviation)
# ═══════════════════════════════════════════════════════════════

def detect_xg_deviation(players: list[PlayerData]) -> list[DetectorResult]:
    results = []
    for p in players:
        goals = p.sv_int(52)
        xg = p.sv(5304)
        shots = max(p.sv(42), 1)
        deviation = goals - xg

        # Determine label
        if deviation >= 0.5:
            label = "超预期终结者"
        elif goals == 0 and xg >= 0.5:
            label = "xG欠债者"
        elif abs(deviation) <= 0.15 and goals > 0:
            label = "完美表现"
        elif shots >= 3 and xg < 0.3 and goals == 0:
            label = "浪射惩罚"
        else:
            label = ""

        # Score = absolute deviation
        abs_score = abs(deviation)
        if abs_score > 0.1 or label:
            evidence = {
                "进球": goals, "xG": round(xg, 3),
                "偏差": round(deviation, 3),
                "xG/射门": round(xg / shots, 4),
                "射门": int(shots),
                "标签": label,
            }
            results.append(DetectorResult(name=p.name, score=round(abs_score, 3), evidence=evidence))

    results.sort(key=lambda x: -x.score)
    return results


# ═══════════════════════════════════════════════════════════════
# D12: 纯终结者 (Pure Finisher)
# ═══════════════════════════════════════════════════════════════

def detect_pure_finisher(players: list[PlayerData], team_goals: int) -> list[DetectorResult]:
    """
    识别\"一个人的进攻线\"：进球占全队比例极高的纯终结者型中锋。
    Kane、Haaland 这类球员可能在 D1-D9 过程数据中表现不佳，
    但他们的价值在最后一击。D12 为这类球员正名。
    """
    if team_goals == 0:
        return []

    results = []
    for p in players:
        goals = p.sv_int(52)
        assists = p.sv_int(79)
        if goals == 0:
            continue

        g_share = goals / team_goals  # 进球占全队比例
        shots = max(p.sv(42), 1)
        xg = p.sv(5304)
        xg_share = xg / max(sum(p2.sv(5304) for p2 in players), 0.01)  # xG占全队比例
        g_xg_diff = goals - xg  # 终结超预期

        # Sub-metrics
        goal_share_score = g_share * 10  # 进球占比越高越好
        conversion = goals / shots if shots > 0 else 0  # 转化率
        conversion_score = conversion * 3
        xg_dominance = xg_share * 5  # xG 占比
        clutch = assists * 0.5  # 还能助攻

        score = (
            goal_share_score
            + conversion_score
            + xg_dominance
            + g_xg_diff * 1.0
            + clutch
        )

        label = ""
        if g_share >= 1.0:
            label = "包办全队进球"
        elif g_share >= 0.5:
            label = "一个人的进攻线"
        elif g_share >= 0.33:
            label = "主要火力点"

        evidence = {
            "进球": goals,
            "全队进球": team_goals,
            "进球占比": round(g_share * 100, 1),
            "xG占比": round(xg_share * 100, 1),
            "射门": int(shots),
            "转化率": round(conversion * 100, 1),
            "超预期": round(g_xg_diff, 3),
            "助攻": assists,
            "标签": label,
        }
        results.append(DetectorResult(name=p.name, score=round(score, 3), evidence=evidence))

    results.sort(key=lambda x: -x.score)
    return results


# ═══════════════════════════════════════════════════════════════
# Event Bonus Computation (from events list)
# ═══════════════════════════════════════════════════════════════

def compute_event_bonuses(
    events: list[dict],
    home_id: int,
    away_id: int,
    score_home: int,
    score_away: int,
    end_minute: int = 90,
) -> dict[str, EventBonuses]:
    """
    Parse events to determine event bonuses for each player.
    events: raw event dicts with keys: type_id, player_name, related_player_name, minute, participant_id
    """
    goals = []
    subs = []
    for e in events:
        tid = e.get("type_id", 0)
        pn = e.get("player_name", "")
        rn = e.get("related_player_name", "")
        m = e.get("minute", 0)
        team_id = e.get("participant_id", 0)
        if tid in (14, 16, 16):  # goal, penalty goal
            goals.append({"player_name": pn, "team_id": team_id, "minute": m, "is_penalty": tid == 16})
        elif tid == 18:
            subs.append({"player_name": pn, "related_name": rn, "minute": m})

    bonuses: dict[str, EventBonuses] = {}

    def get_bonus(name: str) -> EventBonuses:
        nl = name.strip().lower() if name else ""
        for k in bonuses:
            if k.strip().lower() == nl:
                return bonuses[k]
        eb = EventBonuses()
        if name:
            bonuses[name] = eb
        return eb

    is_draw = score_home == score_away
    home_wins = score_home > score_away
    sg = sorted(goals, key=lambda g: g["minute"])
    late_threshold = end_minute - 5

    # Winning goal: the goal that put the winning team ahead for good
    if not is_draw:
        wh = home_wins
        h = a = 0
        last = None
        for g in sg:
            if g["team_id"] == home_id:
                h += 1
            else:
                a += 1
            if (wh and h > a) or (not wh and a > h):
                last = g["player_name"]
        if last:
            eb = get_bonus(last)
            eb.winning_goal = True
            # Check if it's a late winner
            for g in sg:
                if g["player_name"] == last and g["minute"] >= late_threshold:
                    eb.late_winner = True

    # Equalizer: late equalizing goal in a non-draw match
    if not is_draw and score_home + score_away > 0:
        h = a = 0
        eq = None
        for g in sg:
            if g["team_id"] == home_id:
                h += 1
            else:
                a += 1
            if h == a and g["minute"] >= late_threshold:
                eq = g["player_name"]
        if eq:
            get_bonus(eq).equalizer = True

    # First goal (for winning team)
    if not is_draw and sg:
        wh = home_wins
        for g in sg:
            if (wh and g["team_id"] == home_id) or (not wh and g["team_id"] == away_id):
                get_bonus(g["player_name"]).first_goal = True
                break

    # Super sub: subbed on and scored/assisted within 5 minutes
    for s in subs:
        si = s["player_name"]
        st = s["minute"]
        if not si:
            continue
        for g in goals:
            if g["player_name"] and g["player_name"].strip().lower() == si.strip().lower():
                diff = g["minute"] - st
                if 1 <= diff <= 5:
                    get_bonus(si).super_sub = True

    # Penalty goals
    for g in sg:
        if g.get("is_penalty"):
            get_bonus(g["player_name"]).scored_penalty = True

    return bonuses


# ═══════════════════════════════════════════════════════════════
# Main Runner
# ═══════════════════════════════════════════════════════════════

@dataclass
class AllDetectorResults:
    """Aggregated results from all 12 detectors."""
    match_name: str
    D1_progression: dict[str, list[DetectorResult]]   # team → results
    D2_pressing: dict[str, list[DetectorResult]]
    D3_gravity: dict[str, list[DetectorResult]]
    D4_tempo: dict[str, list[DetectorResult]]
    D5_twoway: dict[str, list[DetectorResult]]
    D6_timing: list[DetectorResult]
    D7_efficiency: dict[str, list[DetectorResult]]
    D8_role_deviation: dict[str, list[DetectorResult]]
    D9_connector: dict[str, list[DetectorResult]]
    D10_finishing: dict[str, list[DetectorResult]]
    D11_xg_deviation: dict[str, list[DetectorResult]]
    D12_pure_finisher: dict[str, list[DetectorResult]]

    def all_team_results(self) -> list[tuple[str, str, list[DetectorResult]]]:
        """Yields (detector_name, team_name, results)."""
        for dname in ["D1", "D2", "D3", "D4", "D5", "D7", "D8", "D9", "D10", "D11", "D12"]:
            d = getattr(self, f"{dname}_progression" if dname == "D1"
                        else f"{dname}_pressing" if dname == "D2"
                        else f"{dname}_gravity" if dname == "D3"
                        else f"{dname}_tempo" if dname == "D4"
                        else f"{dname}_twoway" if dname == "D5"
                        else f"{dname}_efficiency" if dname == "D7"
                        else f"{dname}_role_deviation" if dname == "D8"
                        else f"{dname}_connector" if dname == "D9"
                        else f"{dname}_finishing" if dname == "D10"
                        else f"{dname}_xg_deviation" if dname == "D11"
                        else f"{dname}_pure_finisher")
            for team_name, results in d.items():
                yield (dname, team_name, results)

    def summary_hits(self, min_hits: int = 2) -> dict[str, dict]:
        """Count how many detectors each player appears in (top-3 per team per detector)."""
        from collections import defaultdict
        hits = defaultdict(lambda: {"count": 0, "roles": [], "score": 0.0})

        for dname, team_name, results in self.all_team_results():
            for r in results[:3]:
                if r.score == 0:
                    continue
                hits[r.name]["count"] += 1
                hits[r.name]["roles"].append(dname)
                hits[r.name]["score"] += abs(r.score)

        # D6 is match-wide
        for r in self.D6_timing[:3]:
            hits[r.name]["count"] += 1
            hits[r.name]["roles"].append("D6")
            hits[r.name]["score"] += r.score

        return {k: v for k, v in sorted(hits.items(),
                key=lambda x: (-x[1]["count"], -x[1]["score"]))
                if v["count"] >= min_hits}


def run_all_detectors(
    lineups: list[dict],
    home_id: int,
    away_id: int,
    score_home: int,
    score_away: int,
    events: list[dict],
    end_minute: int = 90,
    home_name: str = "Home",
    away_name: str = "Away",
) -> AllDetectorResults:
    """
    Main entry point. Takes raw fixture data and runs all 11 detectors.

    Returns AllDetectorResults with per-team rankings.
    """
    # Parse players
    position_cache = {}
    home_players = []
    away_players = []

    for lu in lineups:
        pid = lu.get("player_id")
        tid = lu.get("team_id")
        pname = lu.get("player_name", f"Player #{pid}")
        if not pid:
            continue

        if pid not in position_cache:
            pos_id = 0
            for det in lu.get("details", []):
                pl = det.get("player", {})
                if pl:
                    pos_id = pl.get("position_id", lu.get("position_id", 0))
                    break
            if pos_id == 0:
                pos_id = lu.get("position_id", 0)

            # Photo URL
            photo_url = ""
            player_obj = {}
            for det in lu.get("details", []):
                pl = det.get("player", {})
                if pl:
                    player_obj = pl
                    break
            if player_obj:
                photo_url = player_obj.get("image_path", "")
            if not photo_url:
                photo_url = f"https://cdn.sportmonks.com/images/soccer/players/{pid % 32}/{pid}.png"

            position_cache[pid] = (classify_position(pos_id), pos_id, photo_url)

        pos, pos_id, photo_url = position_cache[pid]
        stats = {}
        for det in lu.get("details", []):
            type_id = det.get("type_id")
            if type_id:
                stats[type_id] = det.get("data", {}).get("value")

        pd = PlayerData(
            player_id=pid, name=pname,
            position_id=pos_id, pos=pos,
            team_name=home_name if tid == home_id else away_name,
            stats=stats, photo_url=photo_url,
        )
        if tid == home_id:
            home_players.append(pd)
        else:
            away_players.append(pd)

    # Sort by minutes
    for pl in [home_players, away_players]:
        pl.sort(key=lambda p: -(p.sv(119) or 0))

    # Event bonuses
    bonuses = compute_event_bonuses(events, home_id, away_id, score_home, score_away, end_minute)

    # Exclude GK from outfield detectors
    def outfield(plist):
        return [p for p in plist if p.pos != "G"]

    # Run all detectors
    results = AllDetectorResults(
        match_name=f"{home_name} vs {away_name}",

        D1_progression={
            home_name: detect_progression(outfield(home_players)),
            away_name: detect_progression(outfield(away_players)),
        },
        D2_pressing={
            home_name: detect_pressing(outfield(home_players)),
            away_name: detect_pressing(outfield(away_players)),
        },
        D3_gravity={
            home_name: detect_gravity(outfield(home_players)),
            away_name: detect_gravity(outfield(away_players)),
        },
        D4_tempo={
            home_name: detect_tempo(home_players),
            away_name: detect_tempo(away_players),
        },
        D5_twoway={
            home_name: detect_twoway(home_players),
            away_name: detect_twoway(away_players),
        },
        D6_timing=detect_timing(home_players + away_players, bonuses),

        D7_efficiency={
            home_name: detect_efficiency(home_players),
            away_name: detect_efficiency(away_players),
        },
        D8_role_deviation={
            home_name: detect_role_deviation(home_players),
            away_name: detect_role_deviation(away_players),
        },
        D9_connector={
            home_name: detect_connector(outfield(home_players)),
            away_name: detect_connector(outfield(away_players)),
        },
        D10_finishing={
            home_name: detect_finishing(outfield(home_players)),
            away_name: detect_finishing(outfield(away_players)),
        },
        D11_xg_deviation={
            home_name: detect_xg_deviation(outfield(home_players)),
            away_name: detect_xg_deviation(outfield(away_players)),
        },
        D12_pure_finisher={
            home_name: detect_pure_finisher(outfield(home_players), score_home),
            away_name: detect_pure_finisher(outfield(away_players), score_away),
        },
    )

    return results
