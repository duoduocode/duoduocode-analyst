"""
Player Contribution Detectors v6 — Two-Layer Narrative Model

Layer 1: Seven-dimensional contribution model (C1-C7)
  - C1: Attacking Contribution (15 metrics)
  - C2: Progression Contribution (12 metrics)
  - C3: Control Contribution (8 metrics, captain/rating removed)
  - C4: Defensive Contribution (10 metrics)
  - C5: Duel & Recovery Contribution (13 metrics)
  - C6: Key Events (event-driven, no Z-score)
  - C7: Goalkeeper (4-D per-90, G only)

Layer 2: Role Inference
  - Cosine similarity matching against role prototypes
  - Generates role name + narrative description

ref: design/球员贡献检测器方案-v6.md
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from src.engine.key_events import detect_key_events, KeyEventResult
from collections import defaultdict


# ═══════════════════════════════════════════════════════════════
# Position Classification
# ═══════════════════════════════════════════════════════════════

def classify_pos_by_string(pos_str: str) -> str:
    """Classify position from 'G'/'D'/'M'/'F' string (raw data format)."""
    if not pos_str:
        return "?"
    return pos_str[0].upper() if pos_str[0].upper() in "GDMF" else "?"


# ═══════════════════════════════════════════════════════════════
# Data Structures
# ═══════════════════════════════════════════════════════════════

@dataclass
class PlayerV6:
    """Player data from raw JSON."""
    player_id: int
    name: str
    number: int
    pos: str               # G/D/M/F (from raw position field)
    team: str              # "home" or "away"
    team_name: str         # actual team name
    minutes: int
    is_substitute: bool
    raw_stats: dict        # flat dict of all stat fields

    def sv(self, key: str, default=0.0):
        """Get stat value by field name (string key, not type_id)."""
        v = self.raw_stats.get(key)
        if v is None:
            return default
        return float(v) if isinstance(v, (int, float)) else default

    def sv_int(self, key: str, default=0) -> int:
        """Get stat value as int."""
        v = self.raw_stats.get(key)
        if v is None:
            return default
        return int(v) if isinstance(v, (int, float)) else default


@dataclass
class EventBonusesV6:
    """Event-driven bonuses for a player."""
    winning_goal: bool = False
    equalizer: bool = False
    late_winner: bool = False
    first_goal: bool = False
    super_sub: bool = False
    scored_penalty: bool = False
    won_penalty: bool = False
    pen_shootout_goal: bool = False
    pen_shootout_miss: bool = False
    pen_shootout_save: bool = False   # GK: saved a penalty in shootout
    yellow_card: bool = False
    red_card: bool = False
    yellowred_card: bool = False

    def compute_score(self) -> float:
        """C6 event score. 绝杀和制胜球不重复加分."""
        score = 0.0
        # 绝杀优先于制胜球 — 同一球只取最高
        if self.late_winner:
            score += 4.5
        elif self.winning_goal:
            score += 4.0
        if self.equalizer:
            score += 3.0
        if self.first_goal:
            score += 3.0
        if self.won_penalty:
            score += 3.0
        if self.super_sub:
            score += 2.5
        if self.pen_shootout_save:
            score += 3.5
        if self.pen_shootout_goal:
            score += 1.5
        if self.pen_shootout_miss:
            score -= 2.0
        if self.yellow_card:
            score -= 0.5
        if self.yellowred_card:
            score -= 3.0
        if self.red_card:
            score -= 4.0
        return score

    def labels(self) -> list[str]:
        result = []
        if self.late_winner: result.append("绝杀")
        elif self.winning_goal: result.append("制胜球")
        if self.equalizer: result.append("绝平球")
        if self.first_goal: result.append("首开记录")
        if self.won_penalty: result.append("制造点球")
        if self.super_sub: result.append("超级替补")
        if self.pen_shootout_save: result.append("点球大战扑救")
        if self.pen_shootout_goal: result.append("点球大战进球")
        if self.pen_shootout_miss: result.append("点球大战射失")
        if self.yellow_card: result.append("黄牌")
        if self.red_card: result.append("直红")
        if self.yellowred_card: result.append("两黄变红")
        return result

    def c6_label(self) -> str:
        """Single label for C6 column."""
        s = self.compute_score()
        if self.pen_shootout_save and s >= 3:
            return "点球守护神"
        if s >= 4.0:
            if self.late_winner:
                return "绝杀英雄"
            return "关键先生"
        if s < -2.0:
            return "葬送比赛"
        if s > 0:
            return "关键事件"
        return "-"

    def any(self) -> bool:
        """Whether any event was triggered."""
        return any([
            self.winning_goal, self.equalizer, self.late_winner,
            self.first_goal, self.super_sub, self.scored_penalty,
            self.won_penalty, self.pen_shootout_goal, self.pen_shootout_miss,
            self.yellow_card, self.red_card, self.yellowred_card,
        ])


@dataclass
class ContributionScore:
    """Result for a single contribution dimension for a player."""
    zscore: float             # composite Z-score
    rank: int                 # rank within team
    percentile: int           # percentile within team (0-100)
    label: str                # best label
    raw_metrics: dict         # {metric_name: raw_value}


@dataclass
class RoleResult:
    """Role inference result."""
    name: str
    confidence: float
    narrative: str


@dataclass
class PlayerInsightV6:
    """Full player insight — contribution vector + role."""
    player_id: int
    name: str
    number: int
    pos: str
    team: str
    team_name: str
    minutes: int
    is_substitute: bool
    contributions: dict[str, ContributionScore]  # "C1"~"C7"
    role: Optional[RoleResult]
    event_bonus: Optional[EventBonusesV6]
    raw_stats: dict = field(default_factory=dict)
    llm_summary: str = ""  # LLM-generated player analysis

    def sv(self, key: str, default=0.0):
        """Get stat value by field name."""
        v = self.raw_stats.get(key)
        if v is None:
            return default
        return float(v) if isinstance(v, (int, float)) else default


# ═══════════════════════════════════════════════════════════════
# Utility: Z-score Composite
# ═══════════════════════════════════════════════════════════════

def _zscore(values: list[float]) -> list[float]:
    if not values:
        return [0.0] * len(values)
    mean = sum(values) / len(values)
    n = len(values)
    variance = sum((v - mean) ** 2 for v in values) / n
    std = math.sqrt(variance) if n > 1 else 1.0
    if std < 0.001:
        std = 1.0
    return [max(-3.0, min(3.0, (v - mean) / std)) for v in values]


def zscore_composite_v6(
    players: list[PlayerV6],
    metrics: list[tuple[str, float]],   # [(stat_field_name, weight), ...]
) -> tuple[dict[str, float], dict[str, dict]]:
    """
    Returns:
      scores: {player_name: composite_zscore}  (soft-capped via tanh to [-10,10])
      breakdown: {player_name: {stat_field_name: {'raw':v, 'z':z, 'w':weight}}}
    """
    scores = {p.name: 0.0 for p in players}
    breakdown = {p.name: {} for p in players}

    for field, weight in metrics.items():
        raw_vals = [p.sv(field) for p in players]
        zs = _zscore(raw_vals)
        for i, p in enumerate(players):
            contrib = zs[i] * weight
            scores[p.name] += contrib
            breakdown[p.name][field] = {
                "raw": raw_vals[i],
                "z": round(zs[i], 3),
                "w": weight,
                "contrib": round(contrib, 3),
            }

    # Soft-cap composite to suppress extreme values from low-variance metrics
    # (e.g., 1 goal in a 1-0 game). Uses tanh(x/SCALE)*SCALE.
    SCALE = 6.0
    for name in scores:
        raw = scores[name]
        scores[name] = round(math.tanh(raw / SCALE) * SCALE, 3)

    return scores, breakdown


def _rank_and_label(
    scores: dict[str, float],
    top_n: int = 3,
    label_map: dict[str, str] = None,
) -> dict[str, tuple[int, int, str]]:
    """
    Returns: {name: (rank, percentile, label)}
    label_map = {name: label} for special labels; fallback = standard percentile label.
    """
    n = len(scores)
    if n == 0:
        return {}
    sorted_names = sorted(scores, key=lambda x: -scores[x])
    result = {}
    for i, name in enumerate(sorted_names):
        rank = i + 1
        pct = int(round(100 - (rank - 1) / n * 100))
        label = ""
        if label_map and name in label_map:
            label = label_map[name]
        result[name] = (rank, pct, label)
    return result


# ═══════════════════════════════════════════════════════════════
# C1: 进攻贡献 (15 metrics)
# ═══════════════════════════════════════════════════════════════

C1_METRICS = {
    "goals": 1.5,       # reduced from 2.5 — avoid 1-goal domination
    "assists": 1.5,     # reduced from 2.0
    "xg": 1.2,          # reduced from 2.0
    "penalties_scored": 1.0,
    "shots_total": 1.0,
    "shots_on": 1.5,
    "xgot": 1.2,
    "shooting_performance": 1.5,
    "hit_woodwork": 0.8,
    "big_chances_created": 1.5,
    "chances_created": 1.0,
    "passes_key": 1.0,
    "shots_off": -0.5,
    "shots_blocked": -0.3,
    "big_chances_missed": -1.5,
}

C1_DISPLAY_ORDER = [
    "goals", "assists", "xg", "penalties_scored", "shots_total",
    "shots_on", "xgot", "shooting_performance", "hit_woodwork",
    "big_chances_created", "chances_created", "passes_key",
    "shots_off", "shots_blocked", "big_chances_missed",
]

C1_DISPLAY_NAMES = {
    "goals": "进球", "assists": "助攻", "xg": "xG",
    "penalties_scored": "点球进", "shots_total": "射门", "shots_on": "射正",
    "xgot": "xGOT", "shooting_performance": "SP", "hit_woodwork": "中框",
    "big_chances_created": "创绝佳", "chances_created": "创机会",
    "passes_key": "关键传", "shots_off": "射偏", "shots_blocked": "被封",
    "big_chances_missed": "失绝佳",
}

C1_WEIGHTS = {"goals": 1.5, "assists": 1.5, "xg": 1.2, "penalties_scored": 1.0,
              "shots_total": 1.0, "shots_on": 1.5, "xgot": 1.2,
              "shooting_performance": 1.5, "hit_woodwork": 0.8,
              "big_chances_created": 1.5, "chances_created": 1.0,
              "passes_key": 1.0, "shots_off": -0.5, "shots_blocked": -0.3,
              "big_chances_missed": -1.5}


# ═══════════════════════════════════════════════════════════════
# C2: 推进贡献 (12 metrics)
# ═══════════════════════════════════════════════════════════════

C2_METRICS = {
    "passes_final_third": 1.5,
    "dribbles_success": 1.0,
    "dribbles_attempts": 0.6,
    "crosses": 0.8,
    "crosses_accurate": 0.6,
    "crosses_accuracy": 0.4,
    "long_balls": 0.7,
    "long_balls_won": 0.5,
    "long_balls_won_pct": 0.3,
    "penalties_won": 1.2,
    "fouls_drawn": 0.8,
    "offsides": -0.3,
}

C2_DISPLAY_ORDER = [
    "passes_final_third", "dribbles_success", "dribbles_attempts",
    "crosses", "crosses_accurate", "crosses_accuracy",
    "long_balls", "long_balls_won", "long_balls_won_pct",
    "penalties_won", "fouls_drawn", "offsides",
]

C2_DISPLAY_NAMES = {
    "passes_final_third": "三区传", "dribbles_success": "成过人",
    "dribbles_attempts": "尝过人", "crosses": "传中", "crosses_accurate": "精准传",
    "crosses_accuracy": "传中%", "long_balls": "长传",
    "long_balls_won": "成长传", "long_balls_won_pct": "长传%",
    "penalties_won": "赢点", "fouls_drawn": "被犯", "offsides": "越位",
}


# ═══════════════════════════════════════════════════════════════
# C3: 控制贡献 (8 metrics — captain/rating removed)
# ═══════════════════════════════════════════════════════════════

C3_METRICS = {
    "passes_total": 1.5,
    "passes_accurate": 1.0,
    "passes_accuracy": 0.8,
    "touches": 1.2,
    "back_passes": -0.4,
    "possession_lost": -1.0,
    "dispossessed": -0.8,
    "minutes_played": 0.3,
}

C3_DISPLAY_ORDER = [
    "passes_total", "passes_accurate", "passes_accuracy",
    "touches", "back_passes", "possession_lost", "dispossessed",
    "minutes_played",
]

C3_DISPLAY_NAMES = {
    "passes_total": "总传球", "passes_accurate": "准传球",
    "passes_accuracy": "传球%", "touches": "触球",
    "back_passes": "回传", "possession_lost": "丢球权",
    "dispossessed": "被抢断", "minutes_played": "分钟",
}


# ═══════════════════════════════════════════════════════════════
# C4: 防守贡献 (10 metrics)
# ═══════════════════════════════════════════════════════════════

C4_METRICS = {
    "clearances": 1.5,
    "tackles_total": 1.0,
    "tackles_won": 1.0,
    "tackles_won_pct": 0.6,
    "tackles_interceptions": 1.0,
    "blocked_shots": 0.8,
    "dribbled_past": -0.8,
    "error_lead_to_goal": -3.0,
    "error_lead_to_shot": -1.5,
    "penalties_committed": -1.5,
}

C4_DISPLAY_ORDER = [
    "clearances", "tackles_total", "tackles_won", "tackles_won_pct",
    "tackles_interceptions", "blocked_shots", "dribbled_past",
    "error_lead_to_goal", "error_lead_to_shot", "penalties_committed",
]

C4_DISPLAY_NAMES = {
    "clearances": "解围", "tackles_total": "抢断", "tackles_won": "成抢断",
    "tackles_won_pct": "抢断%", "tackles_interceptions": "拦截",
    "blocked_shots": "封堵", "dribbled_past": "被过",
    "error_lead_to_goal": "致丢球", "error_lead_to_shot": "致射门",
    "penalties_committed": "送点",
}


# ═══════════════════════════════════════════════════════════════
# C5: 对抗贡献 (13 metrics)
# ═══════════════════════════════════════════════════════════════

C5_METRICS = {
    "duels_total": 0.8,
    "duels_won": 1.2,
    "duels_lost": -0.6,
    "duels_won_pct": 0.5,
    "aerials_won": 0.8,
    "aerials": 0.5,
    "aerials_lost": -0.4,
    "aerials_won_pct": 0.3,
    "ball_recoveries": 1.0,
    "fouls_drawn": 0.5,
    "fouls_committed": -0.5,
    "yellowcards": -0.3,
    "redcards": -2.0,
}

C5_DISPLAY_ORDER = [
    "duels_total", "duels_won", "duels_lost", "duels_won_pct",
    "aerials_won", "aerials", "aerials_lost", "aerials_won_pct",
    "ball_recoveries", "fouls_drawn", "fouls_committed",
    "yellowcards", "redcards",
]

C5_DISPLAY_NAMES = {
    "duels_total": "总对抗", "duels_won": "赢对抗", "duels_lost": "输对抗",
    "duels_won_pct": "对抗%", "aerials_won": "赢空中", "aerials": "总空中",
    "aerials_lost": "输空中", "aerials_won_pct": "空中%",
    "ball_recoveries": "球权回", "fouls_drawn": "被犯",
    "fouls_committed": "犯规", "yellowcards": "黄牌", "redcards": "红牌",
}


# ═══════════════════════════════════════════════════════════════
# C1-C5 Label Rules
# ═══════════════════════════════════════════════════════════════

def _c1_label(players: list[PlayerV6], scores: dict[str, float]) -> dict[str, str]:
    """C1 labels: 头号火力点 / 机会创造者 / 高效射手"""
    n = len(players)
    sorted_names = sorted(scores, key=lambda x: -scores[x])
    labels = {}
    for i, name in enumerate(sorted_names):
        p = next(p2 for p2 in players if p2.name == name)
        goals = p.sv_int("goals")
        sp = p.sv("shooting_performance")
        if i < 2 and goals > 0:
            labels[name] = "头号火力点"
        elif goals == 0 and i < 3 and scores[name] > 0.5:
            labels[name] = "机会创造者"
        elif sp >= 1.0 and goals > 0 and scores[name] > 0:
            labels[name] = "高效射手"
    return labels


def _c2_label(players: list[PlayerV6], scores: dict[str, float]) -> dict[str, str]:
    """C2 labels: 长传制导 / 边路快马 / 推进引擎"""
    n = len(players)
    sorted_names = sorted(scores, key=lambda x: -scores[x])
    labels = {}
    for i, name in enumerate(sorted_names):
        if scores[name] <= 0:
            continue
        p = next(p2 for p2 in players if p2.name == name)
        lb = p.sv("long_balls_won")
        cr = p.sv("crosses")
        dr = p.sv("dribbles_success")
        if i < 2 and lb + (p.sv("long_balls") * 0.5) > cr + dr:
            labels[name] = "长传制导"
        elif i < 2 and dr + cr > lb:
            labels[name] = "边路快马"
        elif i < 3:
            labels[name] = "推进引擎"
    return labels


def _c3_label(players: list[PlayerV6], scores: dict[str, float]) -> dict[str, str]:
    """C3 labels: 控场大师 / 球权保险箱 / 节拍器"""
    n = len(players)
    sorted_names = sorted(scores, key=lambda x: -scores[x])
    labels = {}
    # find top passer & top touch
    max_passes = max(p.sv("passes_total") for p in players)
    max_touch = max(p.sv("touches") for p in players)
    for i, name in enumerate(sorted_names):
        if scores[name] <= 0:
            continue
        p = next(p2 for p2 in players if p2.name == name)
        if i < 3 and (p.sv("passes_total") == max_passes or p.sv("touches") == max_touch):
            labels[name] = "控场大师"
        elif i < 3 and p.sv("possession_lost") + p.sv("dispossessed") < 5:
            labels[name] = "球权保险箱"
        elif i < 3:
            labels[name] = "节拍器"
    return labels


def _c4_label(players: list[PlayerV6], scores: dict[str, float]) -> dict[str, str]:
    """C4 labels: 防守铁闸 / 清道夫"""
    n = len(players)
    sorted_names = sorted(scores, key=lambda x: -scores[x])
    labels = {}
    max_clr = max(p.sv("clearances") for p in players)
    max_blk = max(p.sv("blocked_shots") for p in players)
    for i, name in enumerate(sorted_names):
        if scores[name] <= 0:
            continue
        p = next(p2 for p2 in players if p2.name == name)
        if p.sv_int("error_lead_to_goal") > 0:
            labels[name] = "致命失误"
            continue
        if (p.sv("clearances") == max_clr or p.sv("blocked_shots") == max_blk) and p.sv_int("error_lead_to_goal") == 0:
            labels[name] = "清道夫"
        elif i < 3:
            labels[name] = "防守铁闸"
    return labels


def _c5_label(players: list[PlayerV6], scores: dict[str, float]) -> dict[str, str]:
    """C5 labels: 缠斗高手 / 空中霸主 / 球权回收机"""
    n = len(players)
    sorted_names = sorted(scores, key=lambda x: -scores[x])
    labels = {}
    max_aerial = max(p.sv("aerials_won") for p in players)
    max_rec = max(p.sv("ball_recoveries") for p in players)
    for i, name in enumerate(sorted_names):
        if scores[name] <= 0:
            continue
        p = next(p2 for p2 in players if p2.name == name)
        if p.sv("aerials_won") == max_aerial and max_aerial > 0:
            labels[name] = "空中霸主"
        elif p.sv("ball_recoveries") == max_rec and max_rec > 0:
            labels[name] = "球权回收机"
        elif i < 3:
            labels[name] = "缠斗高手"
    return labels


# ═══════════════════════════════════════════════════════════════
# Contribution Subtitles
# ═══════════════════════════════════════════════════════════════

C_SUBTITLES = {
    "C1": "创造机会，转化进球",
    "C2": "构建攻势，推进阵地",
    "C3": "掌控节奏，寻找机会",
    "C4": "抢断拦截，阻止得分",
    "C5": "积极拼抢，拿下球权",
}

C_DIM_NAMES = {
    "C1": "进攻贡献", "C2": "推进贡献", "C3": "控制贡献",
    "C4": "防守贡献", "C5": "对抗贡献",
}

# ═══════════════════════════════════════════════════════════════
# C7: 门将贡献 (4-D per-90)
# ═══════════════════════════════════════════════════════════════

_c7_result: dict[str, dict] = {}  # {player_name: {...}}, global so we can cross-compare


def _gk_save_score(gk: PlayerV6) -> float:
    saves = gk.sv("saves")
    saves_ib = gk.sv("saves_inside_box")
    conceded = max(gk.sv("goalkeeper_goals_conceded"), 1)
    return (saves + saves_ib * 1.5) / conceded


def _gk_control_score(gk: PlayerV6, minutes: float) -> float:
    ghc = gk.sv("good_high_claim")
    punches = gk.sv("punches")
    aw = gk.sv("aerials_won")
    clr = gk.sv("clearances")
    p90 = minutes / 90.0
    return (ghc * 1.5 + punches * 1.0 + aw * 0.8 + clr * 0.5) / max(p90, 0.1)


def _gk_pass_score(gk: PlayerV6, minutes: float) -> float:
    acc_pct = gk.sv("passes_accuracy") / 100.0
    acc = gk.sv("passes_accurate")
    lbw = gk.sv("long_balls_won")
    lbw_pct = gk.sv("long_balls_won_pct") / 100.0
    pl = gk.sv("possession_lost")
    p90 = max(minutes / 90.0, 0.1)
    return (acc_pct * 0.4 + (acc / 90) * 0.3 + (lbw / 90) * 0.2 + lbw_pct * 0.1 - (pl / 90) * 0.3) * (minutes / 90.0)


def _gk_error_score(gk: PlayerV6) -> float:
    return gk.sv_int("error_lead_to_goal") * (-5.0) + gk.sv_int("error_lead_to_shot") * (-2.0)


def detect_goalkeeper(gk_home: Optional[PlayerV6], gk_away: Optional[PlayerV6]) -> dict[str, dict]:
    """C7: Goalkeeper contribution. Returns {name: {score, label, breakdown}}."""
    global _c7_result
    result = {}

    for gk in [gk_home, gk_away]:
        if gk is None:
            continue
        minutes = max(gk.minutes, 1)
        save = round(_gk_save_score(gk), 3)
        control = round(_gk_control_score(gk, minutes), 3)
        pas = round(_gk_pass_score(gk, minutes), 3)
        err = round(_gk_error_score(gk), 3)

        composite = round(save * 0.40 + control * 0.30 + pas * 0.20 + err * 0.10, 3)

        # Label: compare to opponent
        label = "稳定输出"
        conceded = gk.sv_int("goalkeeper_goals_conceded")
        if conceded == 0:
            label = "零封"

        result[gk.name] = {
            "score": composite,
            "label": label,
            "breakdown": {
                "扑救分": round(save, 2),
                "控制分": round(control, 2),
                "出球分": round(pas, 2),
                "失误分": round(err, 2),
            },
            "raw": {
                "saves": gk.sv_int("saves"),
                "saves_inside_box": gk.sv_int("saves_inside_box"),
                "goalkeeper_goals_conceded": conceded,
                "good_high_claim": gk.sv_int("good_high_claim"),
                "punches": gk.sv_int("punches"),
                "aerials_won": gk.sv_int("aerials_won"),
                "clearances": gk.sv_int("clearances"),
                "passes_accuracy": round(gk.sv("passes_accuracy"), 1),
                "passes_accurate": gk.sv_int("passes_accurate"),
                "long_balls_won": gk.sv_int("long_balls_won"),
                "long_balls_won_pct": round(gk.sv("long_balls_won_pct"), 1),
                "possession_lost": gk.sv_int("possession_lost"),
                "error_lead_to_goal": gk.sv_int("error_lead_to_goal"),
                "error_lead_to_shot": gk.sv_int("error_lead_to_shot"),
            },
        }

    # Cross-compare for "叹息之墙" / "脚下有雷"
    vs = list(result.values())
    if len(vs) == 2:
        s0, s1 = vs[0]["score"], vs[1]["score"]
        if s0 >= s1 * 2 and s0 > 2:
            for name in result:
                if result[name]["score"] == s0:
                    result[name]["label"] = "叹息之墙"
        elif s1 >= s0 * 2 and s1 > 2:
            for name in result:
                if result[name]["score"] == s1:
                    result[name]["label"] = "叹息之墙"
        for name, v in result.items():
            if v["breakdown"]["失误分"] < -1 and v["breakdown"]["出球分"] < 0:
                v["label"] = "脚下有雷"

    _c7_result = result
    return result


# ═══════════════════════════════════════════════════════════════
# C6: Event Bonus Computation
# ═══════════════════════════════════════════════════════════════

def compute_event_bonuses_v6(
    events: list[dict],
    home_id: int,
    away_id: int,
    score_home: int,
    score_away: int,
    periods: list[dict] | None = None,
    home_gk_name: str = "",
    away_gk_name: str = "",
) -> dict[str, EventBonusesV6]:
    """
    Parse events and compute C6 bonuses for each player.
    Uses unified key_events module for first_goal / equalizer / winning_goal / late_winner.
    events: raw event dicts from data/raw/{id}/raw_data.json
    """
    bonuses: dict[str, EventBonusesV6] = {}

    def get_bonus(name: str) -> EventBonusesV6:
        if not name:
            return EventBonusesV6()
        key = name.strip().lower()
        for k in bonuses:
            if k.lower() == key:
                return bonuses[k]
        eb = EventBonusesV6()
        bonuses[name.strip()] = eb
        return eb

    # ── Collect goals, subs, cards from raw events ──
    goals: list[dict] = []
    subs: list[dict] = []
    cards: list[dict] = []
    for e in events:
        tid = e.get("type_id", 0)
        et = e.get("event_type", "")
        pn = (e.get("player_name") or "").strip()
        rn = (e.get("related_player_name") or "").strip()
        # time_elapsed = event minute (cumulative within match period)
        time_elapsed = e.get("time_elapsed", 0) or e.get("minute", 0) or 0
        team_id = e.get("team_id", 0) or e.get("participant_id", 0)
        period_id = e.get("period_id", 0) or 1

        if tid in (14, 16) or et == "Goal":
            is_penalty = tid == 16
            detail = e.get("detail", "")
            goals.append({
                "player_name": pn, "team_id": team_id,
                "time_elapsed": time_elapsed, "period_id": period_id,
                "is_penalty": is_penalty,
                "detail": detail,
            })
        elif tid == 18 or et == "subst":
            subs.append({"player_in": pn, "player_out": rn,
                         "minute": time_elapsed, "time_elapsed": time_elapsed})
        elif tid in (19, 20, 21) or et == "Card":
            cards.append({"player": pn, "type_id": tid, "minute": time_elapsed})

    # ── Use unified key event detection ──
    ke = detect_key_events(goals, subs, home_id, away_id, score_home, score_away, periods)

    # ── Apply results to bonuses ──
    for name in ke.first_goal_scorers:
        get_bonus(name).first_goal = True
    if ke.equalizer_scorer:
        get_bonus(ke.equalizer_scorer).equalizer = True
    if ke.winning_goal_scorer:
        get_bonus(ke.winning_goal_scorer).winning_goal = True
    if ke.late_winner_scorer:
        get_bonus(ke.late_winner_scorer).late_winner = True
    for name in ke.penalty_scorers:
        get_bonus(name).scored_penalty = True
    for name in ke.super_sub_scorers:
        get_bonus(name).super_sub = True
    for name in ke.pen_shootout_scorers:
        get_bonus(name).pen_shootout_goal = True
    for name in ke.pen_shootout_missers:
        get_bonus(name).pen_shootout_miss = True

    # ── Pen shootout saves: for each miss, credit opposing GK ──
    if home_gk_name or away_gk_name:
        for e in events:
            if e.get("detail") == "pen_shootout_miss":
                miss_team = e.get("team_id", 0) or e.get("participant_id", 0)
                if miss_team == home_id and away_gk_name:
                    get_bonus(away_gk_name).pen_shootout_save = True
                elif miss_team == away_id and home_gk_name:
                    get_bonus(home_gk_name).pen_shootout_save = True

    # ── Cards (not handled by unified module) ──
    for c in cards:
        eb = get_bonus(c["player"])
        if c["type_id"] == 19:
            eb.yellow_card = True
        elif c["type_id"] == 20:
            eb.yellowred_card = True
        elif c["type_id"] == 21:
            eb.red_card = True

    return bonuses


# ═══════════════════════════════════════════════════════════════
# Layer 2: LLM Player Analysis
# ═══════════════════════════════════════════════════════════════

# Old cosine-similarity role inference kept as fallback
ROLE_PROTOTYPES = {
    "蹲坑中卫":     {"pos": "D", "v": {"C1": 0.1, "C2": 0.3, "C3": 0.4, "C4": 5.0, "C5": 4.0, "C6": 0.0}},
    "出球后卫":     {"pos": "D", "v": {"C1": 0.3, "C2": 4.0, "C3": 3.5, "C4": 3.5, "C5": 2.5, "C6": 0.0}},
    "进攻型边卫":   {"pos": "D", "v": {"C1": 1.0, "C2": 5.0, "C3": 2.0, "C4": 2.5, "C5": 2.0, "C6": 0.0}},
    "全能后卫":     {"pos": "D", "v": {"C1": 1.5, "C2": 3.0, "C3": 3.0, "C4": 4.0, "C5": 3.5, "C6": 0.0}},
    "节拍器":       {"pos": "M", "v": {"C1": 0.5, "C2": 3.0, "C3": 5.0, "C4": 1.0, "C5": 1.0, "C6": 0.0}},
    "扫荡后腰":     {"pos": "M", "v": {"C1": 0.2, "C2": 1.0, "C3": 2.0, "C4": 5.0, "C5": 5.0, "C6": 0.0}},
    "全能中场":     {"pos": "M", "v": {"C1": 2.0, "C2": 3.0, "C3": 3.5, "C4": 3.0, "C5": 3.5, "C6": 0.5}},
    "进攻组织者":   {"pos": "M", "v": {"C1": 2.5, "C2": 4.5, "C3": 3.0, "C4": 0.5, "C5": 1.0, "C6": 1.0}},
    "串联枢纽":     {"pos": "M", "v": {"C1": 0.8, "C2": 2.5, "C3": 4.0, "C4": 1.5, "C5": 1.0, "C6": 0.0}},
    "终结者":       {"pos": "F", "v": {"C1": 5.0, "C2": 0.5, "C3": 0.5, "C4": 0.1, "C5": 1.0, "C6": 2.0}},
    "全能中锋":     {"pos": "F", "v": {"C1": 4.0, "C2": 3.0, "C3": 3.0, "C4": 1.0, "C5": 2.5, "C6": 1.0}},
    "边路突击手":   {"pos": "F", "v": {"C1": 2.5, "C2": 5.0, "C3": 1.5, "C4": 0.5, "C5": 2.0, "C6": 1.0}},
    "伪九号":       {"pos": "F", "v": {"C1": 2.0, "C2": 3.0, "C3": 4.0, "C4": 0.5, "C5": 1.5, "C6": 1.0}},
}


def _cosine_similarity(a: dict[str, float], b: dict[str, float]) -> float:
    keys = set(a.keys()) | set(b.keys())
    dot = sum(a.get(k, 0.0) * b.get(k, 0.0) for k in keys)
    na = math.sqrt(sum(v ** 2 for v in a.values()))
    nb = math.sqrt(sum(v ** 2 for v in b.values()))
    if na < 0.001 or nb < 0.001:
        return 0.0
    return dot / (na * nb)


def infer_role(contrib_vector: dict[str, float], pos: str) -> RoleResult:
    """Fallback role inference via cosine similarity."""
    candidates = [(name, info) for name, info in ROLE_PROTOTYPES.items()
                  if info["pos"] == pos]
    if not candidates:
        return RoleResult(
            name=f"均衡型{'后卫' if pos == 'D' else '中场' if pos == 'M' else '前锋'}",
            confidence=0.0, narrative="")
    best_name, best_info = max(
        candidates, key=lambda x: _cosine_similarity(contrib_vector, x[1]["v"]))
    confidence = _cosine_similarity(contrib_vector, best_info["v"])
    if confidence < 0.35:
        pos_name = {"D": "后卫", "M": "中场", "F": "前锋"}.get(pos, "球员")
        return RoleResult(name=f"均衡型{pos_name}", confidence=round(confidence, 3), narrative="")
    return RoleResult(name=best_name, confidence=round(confidence, 3), narrative="")


# ═══════════════════════════════════════════════════════════════
# Metric Ranking Computation
# ═══════════════════════════════════════════════════════════════

def _compute_metric_rankings(
    all_outfield: list[PlayerV6],
    team_scores: dict[str, dict[str, float]],
    all_breakdowns: dict[str, dict[str, dict]],
) -> dict[str, dict[str, dict]]:
    """
    Compute per-metric team rank and match-wide rank for each player.
    Only ranks players with >0 minutes.

    Returns: {player_name: {dim_key: {metric_name: {"team_rank": int, "match_rank": int}}}}
    """
    DIM_ORDERS = {
        "C1": C1_DISPLAY_ORDER, "C2": C2_DISPLAY_ORDER,
        "C3": C3_DISPLAY_ORDER, "C4": C4_DISPLAY_ORDER,
        "C5": C5_DISPLAY_ORDER,
    }

    # Build team groupings
    teams: dict[str, list[PlayerV6]] = {}
    for p in all_outfield:
        if p.minutes <= 0:
            continue
        teams.setdefault(p.team_name, []).append(p)

    result: dict[str, dict[str, dict]] = {}

    for p in all_outfield:
        result[p.name] = {}
        if p.minutes <= 0:
            continue

        team_list = teams.get(p.team_name, [])

        for dim_key in ["C1", "C2", "C3", "C4", "C5"]:
            breakdown = all_breakdowns.get(p.name, {}).get(dim_key, {})
            if not breakdown:
                continue
            result[p.name][dim_key] = {}

            for metric in DIM_ORDERS.get(dim_key, []):
                pval = breakdown.get(metric, {}).get("raw", 0)

                # Team rank: higher is better (even for negative metrics, since Z handles polarity)
                team_vals = [(p2.name, all_breakdowns.get(p2.name, {}).get(dim_key, {}).get(metric, {}).get("raw", 0))
                             for p2 in team_list if p2.minutes > 0]
                team_vals.sort(key=lambda x: -x[1])
                team_rank = next((i + 1 for i, (n, _) in enumerate(team_vals) if n == p.name), len(team_vals))

                # Match rank
                all_vals = [(p2.name, all_breakdowns.get(p2.name, {}).get(dim_key, {}).get(metric, {}).get("raw", 0))
                            for p2 in all_outfield if p2.minutes > 0]
                all_vals.sort(key=lambda x: -x[1])
                match_rank = next((i + 1 for i, (n, _) in enumerate(all_vals) if n == p.name), len(all_vals))

                result[p.name][dim_key][metric] = {
                    "team_rank": team_rank,
                    "match_rank": match_rank,
                }

    return result


# ═══════════════════════════════════════════════════════════════
# LLM Player Analysis (Layer 2)
# ═══════════════════════════════════════════════════════════════

def _load_prompt_template() -> dict:
    """Load player analysis prompt from YAML file."""
    import yaml
    import os
    prompt_path = os.path.join(os.path.dirname(__file__), "..", "..", "prompts", "player_analysis.yaml")
    prompt_path = os.path.normpath(prompt_path)
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"  [WARN] Prompt template not found: {prompt_path}")
        return {}


def _player_dim_detail(
    player_data: dict,
    dim_keys: list[str],  # which dims to include
) -> list[dict]:
    """Build structured dim detail list for prompt rendering."""
    result = []
    for dim_key in dim_keys:
        dim_data = player_data.get("dim_data", {}).get(dim_key, {})
        if not dim_data:
            continue
        dim_name = C_DIM_NAMES.get(dim_key, dim_key)
        zscore = dim_data.get("zscore", 0)
        rank = dim_data.get("rank", 99)
        label = dim_data.get("label", "")

        raw_metrics = dim_data.get("raw_metrics", {})
        # Handle both nested dict (C1-C5) and flat value (C7) formats
        metrics = []
        for mname, mdata in raw_metrics.items():
            if isinstance(mdata, dict):
                raw_val = mdata.get("raw", 0)
                z = mdata.get("z", 0)
                contrib = abs(mdata.get("contrib", 0))
                tr = mdata.get("_team_rank", "")
                mr = mdata.get("_match_rank", "")
            else:
                raw_val = mdata
                z = 0
                contrib = 0
                tr = mr = ""
            disp_name = C1_DISPLAY_NAMES.get(mname, mname)
            metrics.append({
                "name": disp_name,
                "raw": raw_val,
                "z": round(z, 2) if isinstance(z, (int, float)) else 0,
                "team_rank": tr,
                "match_rank": mr,
                "_sort": contrib,
            })
        metrics.sort(key=lambda x: -x["_sort"])
        metrics = metrics[:8]
        for m in metrics:
            del m["_sort"]

        entry = {
            "dim_name": dim_name,
            "zscore": round(zscore, 2),
            "rank": rank,
            "label": label,
            "metrics": metrics,
        }
        result.append(entry)
    return result


def _build_all_players_prompt(
    key_players: list[dict],
    other_players: list[dict],
    match_info: dict,
    template: dict,
) -> str:
    """Build LLM prompt for all players using Jinja2 from YAML template."""
    from jinja2 import Template

    home_name = match_info["home_name"]
    away_name = match_info["away_name"]
    score = match_info["score"]

    result_parts = [f"{home_name} {score} {away_name}"]
    et_info = match_info.get("extra_time_info", "")
    pso_info = match_info.get("penalty_info", "")
    if et_info:
        result_parts.append(et_info)
    if pso_info:
        result_parts.append(pso_info)

    # Enrich key players with structured dim_detail
    enriched_key = []
    for kp in key_players:
        enriched_key.append({
            "name": kp["name"],
            "team": kp["team"],
            "pos": kp["pos"],
            "minutes": kp["minutes"],
            "positive_dims": kp["positive_dims"],
            "events": kp.get("events", []),
            "dim_detail": _player_dim_detail(kp, kp.get("positive_dim_keys", [])),
        })

    # Enrich other players with ALL dims (including C7 for goalkeepers)
    enriched_other = []
    outfield_dims = ["C1", "C2", "C3", "C4", "C5"]
    gk_dims = ["C1", "C2", "C3", "C4", "C5", "C7"]
    for op in other_players:
        dims = gk_dims if op.get("pos") == "G" else outfield_dims
        enriched_other.append({
            "name": op["name"],
            "team": op["team"],
            "pos": op["pos"],
            "minutes": op["minutes"],
            "events": op.get("events", []),
            "dim_detail": _player_dim_detail(op, dims),
        })

    context = {
        "match_context": "、".join(result_parts),
        "total_players": len(key_players) + len(other_players),
        "key_players": enriched_key,
        "other_players": enriched_other,
    }

    user_template = template.get("user", "")
    tpl = Template(user_template)
    return tpl.render(**context)


def _extract_match_info(raw_data: dict) -> dict:
    """Extract match info for LLM prompt."""
    home_name = raw_data["home_team"]["name"]
    away_name = raw_data["away_team"]["name"]
    sh = raw_data["score"]["home"]
    sa = raw_data["score"]["away"]
    score = f"{sh}-{sa}"

    periods = raw_data.get("periods", [])
    et_info = ""
    pso_info = ""
    for pd in periods:
        so = pd.get("sort_order", 0)
        if so == 3:
            et_info = "常规时间平局后进入加时赛"
        elif so == 5:
            pso_events = pd.get("events", [])
            if pso_events:
                goals = [e for e in pso_events if e.get("detail") == "pen_shootout_goal"]
                misses = [e for e in pso_events if e.get("detail") == "pen_shootout_miss"]
                h_goals = sum(1 for g in goals if g.get("team_id") == raw_data["home_team"]["id"])
                a_goals = sum(1 for g in goals if g.get("team_id") == raw_data["away_team"]["id"])
                miss_names = '、'.join(m.get('player_name', '') for m in misses) if misses else '无'
                pso_info = f"点球大战：{home_name} {h_goals}-{a_goals} {away_name}（射失: {miss_names}）"

    return {
        "home_name": home_name,
        "away_name": away_name,
        "score": score,
        "extra_time_info": et_info,
        "penalty_info": pso_info,
    }


def _llm_analyze_all_players(
    key_players: list[dict],
    other_players: list[dict],
    match_info: dict,
    llm_client,
) -> dict[str, str]:
    """Call LLM to analyze ALL players in batches. Returns {player_name: summary}."""
    template = _load_prompt_template()
    if not template:
        return {}

    system_prompt = template.get("system", "")
    all_summaries: dict[str, str] = {}

    # Combine all players, mark source
    all_entries = []
    for kp in key_players:
        all_entries.append(("key", kp))
    for op in other_players:
        all_entries.append(("other", op))

    # Batch size: ~15 players per call to keep output tokens manageable
    BATCH_SIZE = 15
    tokens_per_player = 200  # ~150 chars × 0.7 tok/char + overhead

    for batch_start in range(0, len(all_entries), BATCH_SIZE):
        batch = all_entries[batch_start:batch_start + BATCH_SIZE]
        batch_key = [e for e in batch if e[0] == "key"]
        batch_other = [e for e in batch if e[0] == "other"]
        batch_kp = [kp for _, kp in batch_key]
        batch_op = [op for _, op in batch_other]

        prompt = _build_all_players_prompt(batch_kp, batch_op, match_info, template)
        n_in_batch = len(batch_kp) + len(batch_op)
        needed_tokens = max(n_in_batch * tokens_per_player, 2048)

        try:
            response = llm_client.generate(system_prompt, prompt, max_tokens=needed_tokens)
        except Exception as e:
            print(f"  [WARN] LLM batch {batch_start // BATCH_SIZE + 1} failed: {e}")
            continue

        # Build known-name index
        batch_names = [kp["name"] for kp in batch_kp] + [op["name"] for op in batch_op]

        for line in response.split('\n'):
            line = line.strip()
            if not line:
                continue
            line = line.strip('*').strip()
            for sep in [':', '：']:
                if sep in line:
                    parts = line.split(sep, 1)
                    raw_name = parts[0].strip().lstrip('-').strip()
                    text = parts[1].strip() if len(parts) > 1 else ""
                    if not text:
                        break
                    matched = _fuzzy_match_name(raw_name, batch_names)
                    if matched:
                        all_summaries[matched] = text
                    break

    return all_summaries


def _fuzzy_match_name(raw: str, candidates: list[str]) -> str | None:
    """Fuzzy match a raw name string to the closest candidate."""
    # Clean the raw name
    clean = raw.strip()
    # Remove leading markers like "1.", "2.", "- ", "**", etc
    import re
    clean = re.sub(r'^[\d\.\-\*\s]+', '', clean).strip()

    # Exact match
    if clean in candidates:
        return clean

    # Case-insensitive
    clean_lower = clean.lower()
    for c in candidates:
        if c.lower() == clean_lower:
            return c

    # Normalize diacritics: remove accents for comparison
    import unicodedata
    def strip_accents(s):
        return ''.join(ch for ch in unicodedata.normalize('NFD', s)
                       if unicodedata.category(ch) != 'Mn')
    clean_ascii = strip_accents(clean).lower()
    for c in candidates:
        if strip_accents(c).lower() == clean_ascii:
            return c

    # Substring match: candidate contains raw or raw contains candidate
    for c in candidates:
        if clean_lower in c.lower() or c.lower() in clean_lower:
            return c

    # Last-name match
    for c in candidates:
        c_parts = c.lower().split()
        clean_parts = clean_lower.split()
        if len(clean_parts) >= 1 and len(c_parts) >= 1:
            if clean_parts[-1] == c_parts[-1]:
                return c

    return None


# ═══════════════════════════════════════════════════════════════
# Main Runner
# ═══════════════════════════════════════════════════════════════

def load_players_from_raw(raw_data: dict) -> tuple[list[PlayerV6], list[PlayerV6], int, int]:
    """Load PlayerV6 list from raw_data.json format."""
    home_players = []
    away_players = []
    home_id = raw_data["home_team"]["id"]
    away_id = raw_data["away_team"]["id"]

    for p in raw_data.get("home_players", []):
        hp = PlayerV6(
            player_id=p["id"],
            name=p["name"],
            number=p.get("number", 0),
            pos=classify_pos_by_string(p.get("position", "")),
            team="home",
            team_name=raw_data["home_team"]["name"],
            minutes=p.get("minutes_played", 0) or 0,
            is_substitute=p.get("is_substitute", False),
            raw_stats=p,  # flat dict
        )
        home_players.append(hp)

    for p in raw_data.get("away_players", []):
        ap = PlayerV6(
            player_id=p["id"],
            name=p["name"],
            number=p.get("number", 0),
            pos=classify_pos_by_string(p.get("position", "")),
            team="away",
            team_name=raw_data["away_team"]["name"],
            minutes=p.get("minutes_played", 0) or 0,
            is_substitute=p.get("is_substitute", False),
            raw_stats=p,
        )
        away_players.append(ap)

    return home_players, away_players, home_id, away_id


def run_v6(raw_data: dict, llm_client=None) -> list[PlayerInsightV6]:
    """
    Main entry for v6 two-layer analysis.

    Args:
        raw_data: loaded from data/raw/{match_id}/raw_data.json
        llm_client: optional LLMClient for Layer 2 player analysis.
                    If None, falls back to cosine-similarity role inference.

    Returns:
        list[PlayerInsightV6] sorted by contribution score
    """
    home_players, away_players, home_id, away_id = load_players_from_raw(raw_data)
    all_players = home_players + away_players
    score_home = raw_data["score"]["home"]
    score_away = raw_data["score"]["away"]
    events = raw_data.get("events", [])

    # Resolve goalkeeper names for pen_shootout_save detection
    # Pick the GK with the most minutes (the one who actually played)
    home_gks = sorted([p for p in home_players if p.pos == "G"], key=lambda x: -x.minutes)
    away_gks = sorted([p for p in away_players if p.pos == "G"], key=lambda x: -x.minutes)
    home_gk = home_gks[0].name if home_gks else ""
    away_gk = away_gks[0].name if away_gks else ""

    # Compute event bonuses
    event_bonuses = compute_event_bonuses_v6(events, home_id, away_id, score_home, score_away,
                                               raw_data.get("periods", []),
                                               home_gk_name=home_gk, away_gk_name=away_gk)

    # Also detect penalties_won from stats
    for p in all_players:
        if p.sv_int("penalties_won") > 0:
            eb = event_bonuses.get(p.name)
            if eb is None:
                eb = EventBonusesV6()
                event_bonuses[p.name] = eb
            eb.won_penalty = True

    # ── Collect all breakdowns for cross-team ranking ──
    all_breakdowns: dict[str, dict[str, dict]] = {}  # {player_name: {dim_key: {metric: {raw,...}}}}

    results: list[PlayerInsightV6] = []

    # Process each team independently for C1-C5
    for team_name, team_players in [("home", home_players), ("away", away_players)]:
        outfield = [p for p in team_players if p.pos != "G"]
        all_team = [p for p in team_players]

        # C1
        c1_scores, c1_breakdown = zscore_composite_v6(outfield, C1_METRICS)
        c1_labels = _c1_label(outfield, c1_scores)
        c1_ranked = _rank_and_label(c1_scores, top_n=3, label_map=c1_labels)

        # C2
        c2_scores, c2_breakdown = zscore_composite_v6(outfield, C2_METRICS)
        c2_labels = _c2_label(outfield, c2_scores)
        c2_ranked = _rank_and_label(c2_scores, top_n=3, label_map=c2_labels)

        # C3
        c3_scores, c3_breakdown = zscore_composite_v6(outfield, C3_METRICS)
        c3_labels = _c3_label(outfield, c3_scores)
        c3_ranked = _rank_and_label(c3_scores, top_n=3, label_map=c3_labels)

        # C4
        c4_scores, c4_breakdown = zscore_composite_v6(outfield, C4_METRICS)
        c4_labels = _c4_label(outfield, c4_scores)
        c4_ranked = _rank_and_label(c4_scores, top_n=3, label_map=c4_labels)

        # C5
        c5_scores, c5_breakdown = zscore_composite_v6(outfield, C5_METRICS)
        c5_labels = _c5_label(outfield, c5_scores)
        c5_ranked = _rank_and_label(c5_scores, top_n=3, label_map=c5_labels)

        # Collect breakdowns for ranking
        for name in c1_breakdown:
            all_breakdowns.setdefault(name, {})["C1"] = c1_breakdown[name]
        for name in c2_breakdown:
            all_breakdowns.setdefault(name, {})["C2"] = c2_breakdown[name]
        for name in c3_breakdown:
            all_breakdowns.setdefault(name, {})["C3"] = c3_breakdown[name]
        for name in c4_breakdown:
            all_breakdowns.setdefault(name, {})["C4"] = c4_breakdown[name]
        for name in c5_breakdown:
            all_breakdowns.setdefault(name, {})["C5"] = c5_breakdown[name]

        for p in team_players:
            if p.minutes < 15:
                continue

            contributions = {}
            if p.pos != "G":
                contributions["C1"] = ContributionScore(
                    zscore=round(c1_scores.get(p.name, 0), 2),
                    rank=c1_ranked.get(p.name, (len(outfield), 0, ""))[0],
                    percentile=c1_ranked.get(p.name, (len(outfield), 0, ""))[1],
                    label=c1_ranked.get(p.name, (0, 0, ""))[2],
                    raw_metrics=c1_breakdown.get(p.name, {}),
                )
                contributions["C2"] = ContributionScore(
                    zscore=round(c2_scores.get(p.name, 0), 2),
                    rank=c2_ranked.get(p.name, (len(outfield), 0, ""))[0],
                    percentile=c2_ranked.get(p.name, (len(outfield), 0, ""))[1],
                    label=c2_ranked.get(p.name, (0, 0, ""))[2],
                    raw_metrics=c2_breakdown.get(p.name, {}),
                )
                contributions["C3"] = ContributionScore(
                    zscore=round(c3_scores.get(p.name, 0), 2),
                    rank=c3_ranked.get(p.name, (len(outfield), 0, ""))[0],
                    percentile=c3_ranked.get(p.name, (len(outfield), 0, ""))[1],
                    label=c3_ranked.get(p.name, (0, 0, ""))[2],
                    raw_metrics=c3_breakdown.get(p.name, {}),
                )
                contributions["C4"] = ContributionScore(
                    zscore=round(c4_scores.get(p.name, 0), 2),
                    rank=c4_ranked.get(p.name, (len(outfield), 0, ""))[0],
                    percentile=c4_ranked.get(p.name, (len(outfield), 0, ""))[1],
                    label=c4_ranked.get(p.name, (0, 0, ""))[2],
                    raw_metrics=c4_breakdown.get(p.name, {}),
                )
                contributions["C5"] = ContributionScore(
                    zscore=round(c5_scores.get(p.name, 0), 2),
                    rank=c5_ranked.get(p.name, (len(outfield), 0, ""))[0],
                    percentile=c5_ranked.get(p.name, (len(outfield), 0, ""))[1],
                    label=c5_ranked.get(p.name, (0, 0, ""))[2],
                    raw_metrics=c5_breakdown.get(p.name, {}),
                )

            # C6
            eb = event_bonuses.get(p.name, EventBonusesV6())
            c6_score = eb.compute_score()
            c6_labels = eb.labels()
            contributions["C6"] = ContributionScore(
                zscore=round(c6_score, 1),
                rank=0,
                percentile=0,
                label=eb.c6_label(),
                raw_metrics={"事件": c6_labels if c6_labels else ["-"]},
            )

            # C7 (goalkeeper only - placeholder, filled later)
            if p.pos == "G":
                contributions["C7"] = ContributionScore(
                    zscore=0, rank=0, percentile=0, label="", raw_metrics={},
                )

            insight = PlayerInsightV6(
                player_id=p.player_id,
                name=p.name,
                number=p.number,
                pos=p.pos,
                team=p.team,
                team_name=p.team_name,
                minutes=p.minutes,
                is_substitute=p.is_substitute,
                contributions=contributions,
                role=None,
                event_bonus=eb,
                raw_stats=p.raw_stats,
            )
            results.append(insight)

    # C7: run after all players loaded
    gk_home = next((p for p in home_players if p.pos == "G"), None)
    gk_away = next((p for p in away_players if p.pos == "G"), None)
    detect_goalkeeper(gk_home, gk_away)

    # ── Compute per-metric ranks (team + match-wide) ──
    all_outfield = [p for p in all_players if p.pos != "G" and p.minutes > 0]
    metric_ranks = _compute_metric_rankings(all_outfield, {}, all_breakdowns)

    # Inject metric ranks into each player's ContributionScore.raw_metrics
    for ri in results:
        if ri.pos == "G":
            gk_result = _c7_result.get(ri.name, {})
            ri.contributions["C7"] = ContributionScore(
                zscore=round(gk_result.get("score", 0), 2),
                rank=0, percentile=0,
                label=gk_result.get("label", ""),
                raw_metrics=gk_result.get("raw", {}),
            )
            continue

        player_ranks = metric_ranks.get(ri.name, {})
        for dim_key in ["C1", "C2", "C3", "C4", "C5"]:
            contrib = ri.contributions.get(dim_key)
            if contrib is None:
                continue
            dim_ranks = player_ranks.get(dim_key, {})
            for mname in contrib.raw_metrics:
                metric_rank = dim_ranks.get(mname, {})
                contrib.raw_metrics[mname]["_team_rank"] = metric_rank.get("team_rank", 0)
                contrib.raw_metrics[mname]["_match_rank"] = metric_rank.get("match_rank", 0)

    # ── Layer 2: Identify key players + LLM analysis ──
    # Key player = rank ≤ 5 in ANY C1-C5 dimension (within their team) AND zscore > 0
    key_players_data = []
    other_players_data = []
    for ri in results:
        if ri.minutes < 15:
            continue
        ri_team_players = home_players if ri.team == "home" else away_players
        team_size = len([p for p in ri_team_players if p.pos != "G" and p.minutes >= 15])

        eb = ri.event_bonus
        events_list = eb.labels() if eb else ["-"]

        player_entry = {
            "name": ri.name,
            "team": ri.team_name,
            "pos": ri.pos,
            "minutes": ri.minutes,
            "events": events_list,
        }

        # Collect all dims data
        dim_data = {}
        positive_dims = []
        positive_dim_keys = []
        for dim_key in ["C1", "C2", "C3", "C4", "C5"]:
            contrib = ri.contributions.get(dim_key)
            if contrib is None:
                continue
            dim_data[dim_key] = {
                "zscore": contrib.zscore,
                "rank": contrib.rank,
                "label": contrib.label,
                "raw_metrics": contrib.raw_metrics,
            }
            if contrib.rank <= min(5, team_size) and contrib.zscore > 0:
                dim_name = C_DIM_NAMES.get(dim_key, dim_key)
                positive_dims.append(dim_name)
                positive_dim_keys.append(dim_key)

        player_entry["dim_data"] = dim_data

        if positive_dims and ri.pos != "G":
            player_entry["positive_dims"] = positive_dims
            player_entry["positive_dim_keys"] = positive_dim_keys
            key_players_data.append(player_entry)
        elif ri.pos != "G":
            player_entry["positive_dims"] = []  # non-key outfield
            player_entry["positive_dim_keys"] = []
            other_players_data.append(player_entry)

    # Add goalkeepers to other_players
    for ri in results:
        if ri.pos == "G" and ri.minutes >= 15:
            eb = ri.event_bonus
            events_list = eb.labels() if eb else ["-"]
            gk_entry = {
                "name": ri.name,
                "team": ri.team_name,
                "pos": ri.pos,
                "minutes": ri.minutes,
                "events": events_list,
                "dim_data": {
                    "C7": {
                        "zscore": ri.contributions.get("C7", ContributionScore(0, 0, 0, "", {})).zscore,
                        "rank": 0,
                        "label": ri.contributions.get("C7", ContributionScore(0, 0, 0, "", {})).label,
                        "raw_metrics": ri.contributions.get("C7", ContributionScore(0, 0, 0, "", {})).raw_metrics,
                    }
                },
                "positive_dims": [],
                "positive_dim_keys": [],
            }
            other_players_data.append(gk_entry)

    # LLM analysis or fallback
    llm_summaries = {}
    if llm_client and (key_players_data or other_players_data):
        match_info = _extract_match_info(raw_data)
        total = len(key_players_data) + len(other_players_data)
        print(f"  LLM analyzing {total} players ({len(key_players_data)} key, {len(other_players_data)} other)...")
        llm_summaries = _llm_analyze_all_players(
            key_players_data, other_players_data, match_info, llm_client,
        )
        print(f"  LLM summaries received: {len(llm_summaries)}")

    # Apply role/LLM results to each insight
    for ri in results:
        if ri.name in llm_summaries:
            ri.llm_summary = llm_summaries[ri.name]
            ri.role = RoleResult(
                name="LLM分析",
                confidence=1.0,
                narrative=llm_summaries[ri.name],
            )
        elif ri.pos in ("D", "M", "F"):
            # Fallback: cosine similarity
            contrib_vector = {
                "C1": ri.contributions.get("C1", ContributionScore(0, 99, 0, "", {})).zscore,
                "C2": ri.contributions.get("C2", ContributionScore(0, 99, 0, "", {})).zscore,
                "C3": ri.contributions.get("C3", ContributionScore(0, 99, 0, "", {})).zscore,
                "C4": ri.contributions.get("C4", ContributionScore(0, 99, 0, "", {})).zscore,
                "C5": ri.contributions.get("C5", ContributionScore(0, 99, 0, "", {})).zscore,
                "C6": ri.contributions.get("C6", ContributionScore(0, 0, 0, "", {})).zscore,
            }
            ri.role = infer_role(contrib_vector, ri.pos)
        elif ri.pos == "G":
            ri.role = RoleResult(name="门将", confidence=0.0, narrative="")

    # Sort: by top contribution zscore
    results.sort(key=lambda x: -max(
        [v.zscore for k, v in x.contributions.items() if k != "C6"],
        default=0,
    ))

    return results
