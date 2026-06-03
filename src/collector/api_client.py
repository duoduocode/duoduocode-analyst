from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import requests

# ============================================================
# SportMonks V3 stat type_id → name 映射表
# ============================================================

# 球队级统计 type_id → key 名称（用于 home_stats / away_stats dict）
FIXTURE_STAT_MAP: dict[int, str] = {
    # 射门
    42: "Total Shots",
    86: "Shots on Goal",
    41: "Shots off Goal",
    58: "Blocked Shots",
    49: "Shots insidebox",
    50: "Shots outsidebox",
    54: "Goal Attempts",
    64: "Hit Woodwork",
    47: "Penalties",
    580: "Big Chances Created",
    581: "Big Chances Missed",
    # 进球
    52: "Goals",
    # 传球
    80: "Total passes",
    81: "Successful Passes",
    82: "Passes %",
    117: "Key Passes",
    62: "Long Balls",
    63: "Short Passes",
    98: "Crosses",
    99: "Accurate Crosses",
    # 控球
    45: "Ball Possession",
    43: "Attacks",
    44: "Dangerous Attacks",
    46: "Ball Safe",
    # 定位球
    34: "Corner Kicks",
    51: "Offsides",
    53: "Goal Kicks",
    55: "Free Kicks",
    60: "Throwins",
    # 防守
    78: "Tackles",
    100: "Interceptions",
    65: "Successful Headers",
    57: "Goalkeeper Saves",
    # 对抗与盘带
    106: "Duels Won",
    108: "Dribbles Attempts",
    109: "Successful Dribbles",
    # 进球/失球
    79: "Assists",
    88: "Goals Conceded",
    # 纪律
    56: "Fouls",
    84: "Yellow Cards",
    83: "Red Cards",
    # 其他
    59: "Substitutions",
    87: "Injuries",
}

# 球员级统计 type_id → PlayerStats 字段名
PLAYER_STAT_MAP: dict[int, str] = {
    # 基础
    118: "rating",
    119: "minutes_played",
    52: "goals",
    79: "assists",
    # 射门
    42: "shots_total",
    86: "shots_on",
    # 传球
    80: "passes_total",
    117: "passes_key",
    1584: "passes_accuracy",
    # 防守
    78: "tackles_total",
    100: "tackles_interceptions",
    # 对抗
    105: "duels_total",
    106: "duels_won",
    # 盘带
    108: "dribbles_attempts",
    109: "dribbles_success",
    # 犯规
    56: "fouls_committed",
    96: "fouls_drawn",
    83: "redcards",
    84: "yellowcards",
    # 其他
    98: "crosses",
    57: "saves",
    47: "penalties",
    # 高阶 (套餐升级后可用)
    5304: "xg",
    5305: "xgot",
    27271: "ball_recoveries",
}

# 用于 passes_accuracy 百分比计算（SportMonks 返回百分比时是整数，直接可用）
# type_id=82 球队级返回百分比值


# ============================================================
# 数据模型（保持与下游兼容）
# ============================================================

@dataclass
class TeamInfo:
    id: int
    name: str
    logo_url: str


@dataclass
class ScoreInfo:
    home: int
    away: int
    halftime_home: int
    halftime_away: int
    fulltime_home: Optional[int] = None
    fulltime_away: Optional[int] = None
    extratime_home: Optional[int] = None
    extratime_away: Optional[int] = None
    penalty_home: Optional[int] = None
    penalty_away: Optional[int] = None


@dataclass
class PlayerStats:
    id: int
    name: str
    number: int
    position: str
    grid: Optional[str]
    is_substitute: bool
    minutes_played: int
    rating: Optional[float]
    photo_url: str = ""
    goals: int = 0
    assists: int = 0
    shots_total: int = 0
    shots_on: int = 0
    passes_total: int = 0
    passes_key: int = 0
    passes_accuracy: int = 0
    tackles_total: int = 0
    tackles_interceptions: int = 0
    duels_total: int = 0
    duels_won: int = 0
    dribbles_attempts: int = 0
    dribbles_success: int = 0
    fouls_committed: int = 0
    fouls_drawn: int = 0
    xg: float = 0.0
    xgot: float = 0.0
    ball_recoveries: int = 0


@dataclass
class MatchEvent:
    time_elapsed: int
    time_extra: Optional[int]
    team_id: int
    team_name: str
    player_name: str
    assist_name: Optional[str]
    event_type: str
    detail: str
    comments: Optional[str]


@dataclass
class LineupPlayer:
    id: int
    name: str
    number: int
    position: str
    grid: Optional[str]


@dataclass
class LineupInfo:
    formation: str
    players: list[LineupPlayer]


@dataclass
class RawMatchData:
    match_id: int
    fixture_id: int
    home_team: TeamInfo
    away_team: TeamInfo
    score: ScoreInfo
    status: str
    home_stats: dict = field(default_factory=dict)
    away_stats: dict = field(default_factory=dict)
    home_players: list[PlayerStats] = field(default_factory=list)
    away_players: list[PlayerStats] = field(default_factory=list)
    events: list[MatchEvent] = field(default_factory=list)
    home_lineup: Optional[LineupInfo] = None
    away_lineup: Optional[LineupInfo] = None


# ============================================================
# SportMonks API Client
# ============================================================

class SportMonksClient:
    """SportMonks Football API V3 客户端"""

    def __init__(self, config: dict):
        raw_token = config.get("api_token", "")
        if raw_token.startswith("${"):
            env_key = raw_token.strip("${").strip("}")
            raw_token = os.environ.get(env_key, "")
        self.api_token = os.environ.get("SPORTMONKS_API_TOKEN", raw_token)
        self.base_url = config.get("base_url", "https://api.sportmonks.com/v3/football")

    def _get(self, endpoint: str, params: dict = None) -> dict:
        url = f"{self.base_url}{endpoint}"
        if params is None:
            params = {}
        params["api_token"] = self.api_token

        resp = requests.get(url, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        if data.get("error"):
            raise RuntimeError(f"SportMonks API error: {data['error']}")
        return data.get("data", data)

    def get_fixture_with_details(self, match_id: int) -> dict:
        """一次性获取比赛全部数据（统计+事件+阵容+球员统计+比分+球队信息）"""
        includes = "statistics;lineups.details;events;participants;scores"
        return self._get(f"/fixtures/{match_id}", {"include": includes})

    def get_fixtures_by_date(self, league_id: int, season: int, date: str) -> list[dict]:
        """按日期获取联赛比赛列表"""
        # SportMonks: /fixtures?filters=fixtureLeagues:{league_id}&filters=fixtureSeason:{season_id}&...
        # 简化：按日期查询
        params = {
            "include": "participants",
            "filters": f"fixtureLeagues:{league_id}",
        }
        result = self._get(f"/fixtures/date/{date}", params)
        if isinstance(result, dict) and "data" in result:
            return result.get("data", [])
        if isinstance(result, list):
            return result
        return []


# ============================================================
# 解析工具函数
# ============================================================

def _safe_float(value, default=0.0):
    if value is None:
        return default
    if isinstance(value, str):
        value = value.replace("%", "").strip()
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _safe_int(value, default=0):
    if value is None:
        return default
    if isinstance(value, str):
        value = value.replace("%", "").strip()
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default


def _safe_str(value, default=""):
    if value is None:
        return default
    return str(value)


def _parse_fixture_statistics(statistics: list[dict]) -> dict:
    """将 SportMonks statistics 数组解析为 {key: value} 字典"""
    parsed = {}
    for item in statistics:
        type_id = item.get("type_id", 0)
        key = FIXTURE_STAT_MAP.get(type_id)
        if key is None:
            continue
        value_data = item.get("data", {})
        value = value_data.get("value") if isinstance(value_data, dict) else value_data
        if value is not None:
            try:
                if isinstance(value, str) and "%" in value:
                    parsed[key] = float(value.replace("%", ""))
                else:
                    parsed[key] = float(value)
                    if parsed[key] == int(parsed[key]):
                        parsed[key] = int(parsed[key])
            except (ValueError, TypeError):
                parsed[key] = value
    return parsed


def _parse_player_detail_stats(details: list[dict]) -> dict:
    """将 SportMonks lineup details 数组解析为 {field_name: value} 字典"""
    parsed = {}
    for item in details:
        type_id = item.get("type_id", 0)
        field_name = PLAYER_STAT_MAP.get(type_id)
        if field_name is None:
            continue
        value_data = item.get("data", {})
        value = value_data.get("value") if isinstance(value_data, dict) else value_data
        if value is not None:
            try:
                if isinstance(value, str) and "%" in value:
                    parsed[field_name] = float(value.replace("%", ""))
                else:
                    parsed[field_name] = float(value)
                    # float fields that should NOT be cast to int
                    if parsed[field_name] == int(parsed[field_name]) \
                            and field_name not in ("passes_accuracy", "xg", "xgot"):
                        parsed[field_name] = int(parsed[field_name])
            except (ValueError, TypeError):
                parsed[field_name] = value
    return parsed


def _parse_player_from_lineup(lu: dict, player_image_path: str = "") -> PlayerStats:
    """从 SportMonks lineup 条目解析为 PlayerStats"""
    player_id = lu.get("player_id", 0)
    player_name = lu.get("player_name", "")
    jersey_number = _safe_int(lu.get("jersey_number"), 0)
    position_id = lu.get("position_id", 0)
    type_id = lu.get("type_id", 11)  # 11=start, 12=sub
    is_substitute = type_id == 12  # 12 = substitute in SportMonks lineup types
    formation_field = lu.get("formation_field", "")

    details = lu.get("details", [])
    parsed = _parse_player_detail_stats(details)

    # 获取 rating
    rating = parsed.get("rating")
    if rating is not None:
        rating = float(rating)

    # 获取 passes_accuracy - SportMonks 可能返回百分比整数
    passes_accuracy = parsed.get("passes_accuracy", 0)
    # 如果 > 1 且没有可靠数据，尝试从 total/accurate 计算
    passes_total = _safe_int(parsed.get("passes_total"))
    if passes_accuracy > 100 and passes_total > 0:
        # 可能是准确传球次数而不是百分比，需要转换为百分比
        passes_accuracy = round(passes_accuracy / max(passes_total, 1) * 100, 1)
    elif passes_total > 0 and passes_accuracy == 0:
        # 回退：设为 0
        pass

    # 图片 URL
    photo_url = player_image_path if player_image_path else ""

    return PlayerStats(
        id=player_id,
        name=player_name,
        number=jersey_number,
        position=_position_id_to_name(position_id),
        grid=formation_field if formation_field else None,
        is_substitute=is_substitute,
        minutes_played=_safe_int(parsed.get("minutes_played")),
        rating=rating,
        photo_url=photo_url,
        goals=_safe_int(parsed.get("goals")),
        assists=_safe_int(parsed.get("assists")),
        shots_total=_safe_int(parsed.get("shots_total")),
        shots_on=_safe_int(parsed.get("shots_on")),
        passes_total=passes_total,
        passes_key=_safe_int(parsed.get("passes_key")),
        passes_accuracy=_safe_int(passes_accuracy) if passes_accuracy <= 100 else 0,
        tackles_total=_safe_int(parsed.get("tackles_total")),
        tackles_interceptions=_safe_int(parsed.get("tackles_interceptions")),
        duels_total=_safe_int(parsed.get("duels_total")),
        duels_won=_safe_int(parsed.get("duels_won")),
        dribbles_attempts=_safe_int(parsed.get("dribbles_attempts")),
        dribbles_success=_safe_int(parsed.get("dribbles_success")),
        fouls_committed=_safe_int(parsed.get("fouls_committed")),
        fouls_drawn=_safe_int(parsed.get("fouls_drawn")),
        xg=_safe_float(parsed.get("xg"), 0.0),
        xgot=_safe_float(parsed.get("xgot"), 0.0),
        ball_recoveries=_safe_int(parsed.get("ball_recoveries")),
    )


def _position_id_to_name(position_id: int) -> str:
    """SportMonks position_id → 位置缩写"""
    mapping = {
        24: "G",  # Goalkeeper
        25: "D",  # Defender (full-back)
        26: "D",  # Defender (centre-back)
        27: "M",  # Midfielder
        28: "F",  # Attacker (winger)
        29: "F",  # Attacker (striker)
        30: "D",  # Defender
        31: "M",  # Midfielder
        32: "F",  # Attacker
    }
    return mapping.get(position_id, "?")


def _parse_events(events_raw: list[dict], home_team_id: int, away_team_id: int) -> list[MatchEvent]:
    """将 SportMonks events 数组解析为 MatchEvent 列表"""
    # SportMonks event type_id (integer) → 我们的 event_type 映射
    # 基于 fixture 19683241 (PSG vs Arsenal 含加时+点球大战) 实测验证
    event_type_map = {
        10: "Info",             # penalty awarded / event info
        14: "Goal",             # goal (open play) — 运动战进球
        15: "Shot",             # shot attempt (not a goal) — 射门尝试
        16: "Goal",             # penalty goal — 点球进球
        17: "Goal",             # missed penalty — 点球罚失（仍计为射门相关）
        18: "subst",            # substitution — 换人
        19: "Card",             # yellow card — 黄牌
        20: "Card",             # second yellow → red card
        21: "Card",             # straight red card
        22: "Goal",             # penalty shootout miss/saved — 点球大战罚失/被扑
        23: "Goal",             # penalty shootout goal — 点球大战进球
        55: "VAR",              # VAR review (未实测确认)
    }

    # type_id → detail string
    type_detail_map = {
        10: "penalty_awarded",
        14: "goal",
        15: "shot_attempt",
        16: "goal_penalty",
        17: "missed_penalty",
        18: "substitution",
        19: "yellowcard",
        20: "yellowredcard",
        21: "redcard",
        22: "pen_shootout_miss",
        23: "pen_shootout_goal",
        55: "var",
    }

    result = []
    sorted_events = sorted(events_raw, key=lambda e: e.get("sort_order", e.get("minute", 0)))

    for ev in sorted_events:
        type_id = ev.get("type_id", 0)
        ev_type = event_type_map.get(type_id, f"type_{type_id}")
        detail = type_detail_map.get(type_id, f"type_{type_id}")

        # 球员信息 - SportMonks 直接用 player_name
        player_name = ev.get("player_name", "")
        related_name = ev.get("related_player_name", "")

        # 球队信息
        participant_id = ev.get("participant_id", 0)
        if participant_id == home_team_id:
            team_id = home_team_id
        elif participant_id == away_team_id:
            team_id = away_team_id
        else:
            team_id = participant_id

        # 对于 substitution (type_id=18):
        #   player_name = 换上的球员 (player in)
        #   related_player_name = 换下的球员 (player out)
        # 按现有逻辑: player_name 存换下的球员, assist_name 存换上的球员
        # 对于 goal (type_id=14/16/23):
        #   player_name = 进球者
        #   related_player_name = 助攻者
        if ev_type == "subst":
            assist_name = player_name         # 换上的球员 → assist_name
            player_name_for_event = related_name  # 换下的球员 → player_name
        elif ev_type == "Goal":
            assist_name = related_name or None  # 助攻者
            player_name_for_event = player_name
        else:
            assist_name = None
            player_name_for_event = player_name

        result.append(MatchEvent(
            time_elapsed=_safe_int(ev.get("minute")),
            time_extra=_safe_int(ev.get("extra_minute")) if ev.get("extra_minute") else None,
            team_id=team_id,
            team_name=ev.get("participant_name", ""),
            player_name=player_name_for_event,
            assist_name=assist_name,
            event_type=ev_type,
            detail=detail,
            comments=ev.get("info") if ev.get("info") else None,
        ))

    return result


def _parse_lineup_from_fixture(lineups_data: list[dict], team_id: int) -> Optional[LineupInfo]:
    """从 SportMonks lineups 数据中解析阵型信息"""
    for lu in lineups_data:
        if lu.get("team_id") == team_id:
            formation = lu.get("formation", "")
            if not formation:
                # 尝试从 formation_field 推算
                formation = "4-4-2"  # fallback
            # 提取首发球员
            players = []
            detail = lu.get("details", [])
            # lineups 直接给的是球员列表，不是嵌套结构
            # SportMonks: lineups 本身就是首发+替补的 flat list
            # 首发 type_id=11, 替补 type_id=12
            return LineupInfo(
                formation=formation,
                players=[],  # lineup players 只用于传球网络图，需要时再从 players 数据构建
            )
    return None


# ============================================================
# 主数据获取函数
# ============================================================

def fetch_all(match_id: int, config: dict) -> RawMatchData:
    """从 SportMonks API 获取单场比赛全部数据"""
    client = SportMonksClient(config)
    data = client.get_fixture_with_details(match_id)

    # --- 解析球队信息 ---
    participants = data.get("participants", [])
    home_team_data = None
    away_team_data = None
    for p in participants:
        meta = p.get("meta", {})
        if meta.get("location") == "home":
            home_team_data = p
        else:
            away_team_data = p

    if not home_team_data or not away_team_data:
        # fallback: 第一个是主队
        home_team_data = participants[0]
        away_team_data = participants[1]

    home_team = TeamInfo(
        id=home_team_data.get("id", 0),
        name=home_team_data.get("name", ""),
        logo_url=home_team_data.get("image_path", ""),
    )
    away_team = TeamInfo(
        id=away_team_data.get("id", 0),
        name=away_team_data.get("name", ""),
        logo_url=away_team_data.get("image_path", ""),
    )

    # --- 解析比分 ---
    scores = data.get("scores", [])
    score_info = _parse_scores(scores, home_team.id, away_team.id)

    # --- 解析球队统计 ---
    statistics = data.get("statistics", [])
    home_stats = {}
    away_stats = {}
    for stat_item in statistics:
        participant_id = stat_item.get("participant_id", 0)
        type_id = stat_item.get("type_id", 0)
        key = FIXTURE_STAT_MAP.get(type_id)
        if key is None:
            continue
        value_data = stat_item.get("data", {})
        value = value_data.get("value") if isinstance(value_data, dict) else value_data
        if value is not None:
            try:
                if isinstance(value, str) and "%" in value:
                    value = float(value.replace("%", ""))
                else:
                    value = float(value)
                    if value == int(value):
                        value = int(value)
            except (ValueError, TypeError):
                pass
            target = home_stats if participant_id == home_team.id else away_stats
            target[key] = value

    # --- 解析球员数据（来自 lineups.details） ---
    lineups = data.get("lineups", [])
    home_players = []
    away_players = []
    formation_home = "4-3-3"
    formation_away = "4-3-3"

    # 按球队分组 lineups
    home_lineups = [lu for lu in lineups if lu.get("team_id") == home_team.id]
    away_lineups = [lu for lu in lineups if lu.get("team_id") == away_team.id]

    # Player image check
    for lu in home_lineups:
        player = _parse_player_from_lineup(lu)
        if not player.photo_url and player.id:
            player.photo_url = f"https://cdn.sportmonks.com/images/soccer/players/{player.id % 32}/{player.id}.png"
        home_players.append(player)

    for lu in away_lineups:
        player = _parse_player_from_lineup(lu)
        if not player.photo_url and player.id:
            player.photo_url = f"https://cdn.sportmonks.com/images/soccer/players/{player.id % 32}/{player.id}.png"
        away_players.append(player)

    # 尝试从 lineups 矩阵数据中提取阵型
    home_lineup = _parse_lineup_from_fixture(lineups, home_team.id)
    away_lineup = _parse_lineup_from_fixture(lineups, away_team.id)

    # --- 解析事件 ---
    events = _parse_events(data.get("events", []), home_team.id, away_team.id)

    # --- 状态 ---
    state_id = data.get("state_id", 5)
    status_map = {1: "NS", 2: "LIVE", 3: "HT", 4: "BT", 5: "FT", 6: "AET", 7: "PEN", 8: "PST", 9: "SUSP", 10: "INT"}
    status = status_map.get(state_id, "FT")

    raw = RawMatchData(
        match_id=match_id,
        fixture_id=match_id,
        home_team=home_team,
        away_team=away_team,
        score=score_info,
        status=status,
        home_stats=home_stats,
        away_stats=away_stats,
        home_players=home_players,
        away_players=away_players,
        events=events,
        home_lineup=home_lineup,
        away_lineup=away_lineup,
    )

    _save_raw_data(raw)
    return raw


def _parse_scores(scores: list[dict], home_team_id: int, away_team_id: int) -> ScoreInfo:
    """解析 SportMonks scores 数组为 ScoreInfo"""
    result = ScoreInfo(home=0, away=0, halftime_home=0, halftime_away=0)

    # Score descriptions in SportMonks:
    # "CURRENT" = full time/goals
    # "HT" = half time
    # "FT" = full time
    # "ET" = extra time
    # "PEN" = penalties

    for s in scores:
        desc = s.get("description", "")
        score_data = s.get("score", {})
        participant_id = s.get("participant_id", 0)

        goals = _safe_int(score_data.get("goals", 0)) if isinstance(score_data, dict) else _safe_int(score_data)

        if desc == "CURRENT":
            if participant_id == home_team_id:
                result.home = goals
            else:
                result.away = goals

        elif desc in ("HT", "HALFTIME"):
            if participant_id == home_team_id:
                result.halftime_home = goals
            else:
                result.halftime_away = goals

        elif desc == "FT":
            if participant_id == home_team_id:
                result.fulltime_home = goals
            else:
                result.fulltime_away = goals

        elif desc == "ET":
            if participant_id == home_team_id:
                result.extratime_home = goals
            else:
                result.extratime_away = goals

        elif desc == "PEN":
            if participant_id == home_team_id:
                result.penalty_home = goals
            else:
                result.penalty_away = goals

    # 如果 HT 没单独返回，从 CURRENT 推测
    if result.halftime_home == 0 and result.halftime_away == 0:
        result.halftime_home = 0
        result.halftime_away = 0

    return result


def _save_raw_data(raw: RawMatchData):
    """保存原始数据到本地 JSON 缓存"""
    import dataclasses

    base = Path("data/raw") / str(raw.match_id)
    base.mkdir(parents=True, exist_ok=True)

    def _serialize(obj):
        if dataclasses.is_dataclass(obj):
            result = {}
            for f in dataclasses.fields(obj):
                val = getattr(obj, f.name)
                if isinstance(val, list):
                    result[f.name] = [_serialize(v) for v in val]
                elif dataclasses.is_dataclass(val):
                    result[f.name] = _serialize(val)
                else:
                    result[f.name] = val
            return result
        return obj

    data = _serialize(raw)
    with open(base / "raw_data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
