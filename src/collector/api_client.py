from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import requests

# ============================================================
# SportMonks V3 stat type_id → name 映射表
# ============================================================

FIXTURE_STAT_MAP: dict[int, str] = {
    42: "Total Shots",        86: "Shots on Goal",
    41: "Shots off Goal",     58: "Blocked Shots",
    49: "Shots insidebox",    50: "Shots outsidebox",
    54: "Goal Attempts",      64: "Hit Woodwork",
    47: "Penalties",          580: "Big Chances Created",
    581: "Big Chances Missed", 52: "Goals",
    80: "Total passes",       81: "Successful Passes",
    82: "Passes %",           117: "Key Passes",
    62: "Long Balls",         63: "Short Passes",
    98: "Crosses",            99: "Accurate Crosses",
    45: "Ball Possession",    43: "Attacks",
    44: "Dangerous Attacks",  46: "Ball Safe",
    34: "Corner Kicks",       51: "Offsides",
    53: "Goal Kicks",         55: "Free Kicks",
    60: "Throwins",
    78: "Tackles",            100: "Interceptions",
    65: "Successful Headers", 57: "Goalkeeper Saves",
    106: "Duels Won",         108: "Dribbles Attempts",
    109: "Successful Dribbles",
    79: "Assists",            88: "Goals Conceded",
    56: "Fouls",              84: "Yellow Cards",
    83: "Red Cards",          59: "Substitutions",
    87: "Injuries",
}

PLAYER_STAT_MAP: dict[int, str] = {
    118: "rating",            119: "minutes_played",
    52: "goals",              79: "assists",
    42: "shots_total",        86: "shots_on",
    80: "passes_total",       117: "passes_key",
    1584: "passes_accuracy",
    78: "tackles_total",      100: "tackles_interceptions",
    105: "duels_total",       106: "duels_won",
    108: "dribbles_attempts", 109: "dribbles_success",
    56: "fouls_committed",    96: "fouls_drawn",
    83: "redcards",           84: "yellowcards",
    98: "crosses",            57: "saves",
    47: "penalties",          40: "captain",
    1490: "man_of_match",     120: "touches",
    101: "clearances",        97: "blocked_shots",
    571: "error_lead_to_goal",
    27269: "passes_final_third", 27268: "tackles_won_pct",
    27273: "possession_lost",    27271: "ball_recoveries",
    5304: "xg",               5305: "xgot",
    9685: "shooting_performance",
}


# ============================================================
# 数据模型
# ============================================================

@dataclass
class TeamInfo:
    id: int
    name: str
    logo_url: str


@dataclass
class CoachInfo:
    id: int
    name: str
    photo_url: str


@dataclass
class ScoreInfo:
    home: int
    away: int
    halftime_home: int = 0
    halftime_away: int = 0
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
    passes_accuracy: float = 0
    passes_final_third: int = 0
    tackles_total: int = 0
    tackles_interceptions: int = 0
    tackles_won_pct: float = 0
    duels_total: int = 0
    duels_won: int = 0
    dribbles_attempts: int = 0
    dribbles_success: int = 0
    fouls_committed: int = 0
    fouls_drawn: int = 0
    yellowcards: int = 0
    redcards: int = 0
    xg: float = 0.0
    xgot: float = 0.0
    ball_recoveries: int = 0
    possession_lost: int = 0
    error_lead_to_goal: int = 0
    shooting_performance: float = 0.0
    captain: bool = False
    man_of_match: bool = False
    saves: int = 0
    penalties: int = 0
    crosses: int = 0
    blocked_shots: int = 0
    clearances: int = 0
    touches: int = 0


@dataclass
class MatchEvent:
    time_elapsed: int
    time_extra: Optional[int]
    period_id: int
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
class PeriodScore:
    description: str
    sort_order: int
    home_goals: int
    away_goals: int


@dataclass
class PeriodData:
    sort_order: int
    description: str
    period_length: int
    home_stats: dict
    away_stats: dict
    events: list[MatchEvent]


@dataclass
class TrendPoint:
    minute: int
    value: float
    period_id: int


@dataclass
class RawMatchData:
    match_id: int
    fixture_id: int
    home_team: TeamInfo
    away_team: TeamInfo
    home_coach: Optional[CoachInfo]
    away_coach: Optional[CoachInfo]
    score: ScoreInfo
    period_scores: list[PeriodScore]
    status: str
    home_stats: dict = field(default_factory=dict)
    away_stats: dict = field(default_factory=dict)
    home_players: list[PlayerStats] = field(default_factory=list)
    away_players: list[PlayerStats] = field(default_factory=list)
    events: list[MatchEvent] = field(default_factory=list)
    periods: list[PeriodData] = field(default_factory=list)
    home_lineup: Optional[LineupInfo] = None
    away_lineup: Optional[LineupInfo] = None
    trends: dict = field(default_factory=dict)


# ============================================================
# SportMonks Client
# ============================================================

class SportMonksClient:
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
        includes = (
            "statistics;periods.statistics;periods.events;"
            "trends;lineups.details;events;"
            "participants;scores;coaches;referees"
        )
        return self._get(f"/fixtures/{match_id}", {"include": includes})

    def get_fixtures_by_date(self, league_id: int, season: int, date: str) -> list[dict]:
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


def _extract_value(stat_item: dict):
    value_data = stat_item.get("data", {})
    value = value_data.get("value") if isinstance(value_data, dict) else value_data
    if value is None:
        return None
    try:
        if isinstance(value, str) and "%" in value:
            value = float(value.replace("%", ""))
        else:
            value = float(value)
            if value == int(value):
                value = int(value)
    except (ValueError, TypeError):
        pass
    return value


def _parse_statistics(statistics: list[dict]) -> dict:
    parsed = {}
    for item in statistics:
        type_id = item.get("type_id", 0)
        key = FIXTURE_STAT_MAP.get(type_id)
        if key is None:
            continue
        value = _extract_value(item)
        if value is not None:
            parsed[key] = value
    return parsed


def _parse_player_detail_stats(details: list[dict]) -> dict:
    parsed = {}
    for item in details:
        type_id = item.get("type_id", 0)
        field_name = PLAYER_STAT_MAP.get(type_id)
        if field_name is None:
            continue
        value = _extract_value(item)
        if value is not None:
            parsed[field_name] = value
    return parsed


def _position_id_to_name(position_id: int) -> str:
    mapping = {
        24: "G", 25: "D", 26: "D", 27: "M", 28: "F", 29: "F",
        30: "D", 31: "M", 32: "F",
    }
    return mapping.get(position_id, "?")


def _parse_player_from_lineup(lu: dict) -> PlayerStats:
    player_id = lu.get("player_id", 0)
    player_name = lu.get("player_name", "")
    jersey_number = _safe_int(lu.get("jersey_number"), 0)
    position_id = lu.get("position_id", 0)
    type_id = lu.get("type_id", 11)
    is_substitute = type_id == 12
    formation_field = lu.get("formation_field", "")
    photo_url = lu.get("player", {}).get("image_path", "")

    parsed = _parse_player_detail_stats(lu.get("details", []))
    rating = parsed.get("rating")
    if rating is not None:
        rating = float(rating)

    passes_total = _safe_int(parsed.get("passes_total"))
    passes_acc = parsed.get("passes_accuracy", 0)
    if passes_acc > 100 and passes_total > 0:
        passes_acc = round(passes_acc / max(passes_total, 1) * 100, 1)

    return PlayerStats(
        id=player_id, name=player_name, number=jersey_number,
        position=_position_id_to_name(position_id),
        grid=formation_field if formation_field else None,
        is_substitute=is_substitute,
        minutes_played=_safe_int(parsed.get("minutes_played")),
        rating=rating, photo_url=photo_url,
        goals=_safe_int(parsed.get("goals")),
        assists=_safe_int(parsed.get("assists")),
        shots_total=_safe_int(parsed.get("shots_total")),
        shots_on=_safe_int(parsed.get("shots_on")),
        passes_total=passes_total,
        passes_key=_safe_int(parsed.get("passes_key")),
        passes_accuracy=_safe_float(passes_acc) if passes_acc <= 100 else 0,
        passes_final_third=_safe_int(parsed.get("passes_final_third")),
        tackles_total=_safe_int(parsed.get("tackles_total")),
        tackles_interceptions=_safe_int(parsed.get("tackles_interceptions")),
        tackles_won_pct=_safe_float(parsed.get("tackles_won_pct")),
        duels_total=_safe_int(parsed.get("duels_total")),
        duels_won=_safe_int(parsed.get("duels_won")),
        dribbles_attempts=_safe_int(parsed.get("dribbles_attempts")),
        dribbles_success=_safe_int(parsed.get("dribbles_success")),
        fouls_committed=_safe_int(parsed.get("fouls_committed")),
        fouls_drawn=_safe_int(parsed.get("fouls_drawn")),
        yellowcards=_safe_int(parsed.get("yellowcards")),
        redcards=_safe_int(parsed.get("redcards")),
        xg=_safe_float(parsed.get("xg")),
        xgot=_safe_float(parsed.get("xgot")),
        ball_recoveries=_safe_int(parsed.get("ball_recoveries")),
        possession_lost=_safe_int(parsed.get("possession_lost")),
        error_lead_to_goal=_safe_int(parsed.get("error_lead_to_goal")),
        shooting_performance=_safe_float(parsed.get("shooting_performance")),
        captain=bool(parsed.get("captain")),
        man_of_match=bool(parsed.get("man_of_match")),
        saves=_safe_int(parsed.get("saves")),
        penalties=_safe_int(parsed.get("penalties")),
        crosses=_safe_int(parsed.get("crosses")),
        blocked_shots=_safe_int(parsed.get("blocked_shots")),
        clearances=_safe_int(parsed.get("clearances")),
        touches=_safe_int(parsed.get("touches")),
    )


def _parse_events(events_raw: list[dict], home_team_id: int, away_team_id: int) -> list[MatchEvent]:
    event_type_map = {
        10: "VAR", 14: "Goal", 15: "Goal", 16: "Goal", 17: "Goal",
        18: "subst", 19: "Card", 20: "Card", 21: "Card",
        22: "Goal", 23: "Goal",
    }
    type_detail_map = {
        10: "var", 14: "goal", 15: "owngoal", 16: "goal_penalty",
        17: "missed_penalty", 18: "substitution", 19: "yellowcard",
        20: "redcard", 21: "yellowredcard",
        22: "pen_shootout_miss", 23: "pen_shootout_goal",
    }
    result = []
    for ev in sorted(events_raw, key=lambda e: e.get("sort_order", e.get("minute", 0))):
        type_id = ev.get("type_id", 0)
        ev_type = event_type_map.get(type_id, f"type_{type_id}")
        detail = type_detail_map.get(type_id, f"type_{type_id}")
        player_name = ev.get("player_name", "")
        related_name = ev.get("related_player_name", "")
        participant_id = ev.get("participant_id", 0)
        team_id = participant_id

        if ev_type == "subst":
            assist_name = player_name
            pname = related_name
        elif ev_type == "Goal":
            assist_name = related_name or None
            pname = player_name
        else:
            assist_name = None
            pname = player_name

        result.append(MatchEvent(
            time_elapsed=_safe_int(ev.get("minute")),
            time_extra=_safe_int(ev.get("extra_minute")) if ev.get("extra_minute") else None,
            period_id=_safe_int(ev.get("period_id")),
            team_id=team_id,
            team_name=ev.get("participant_name", ""),
            player_name=pname,
            assist_name=assist_name,
            event_type=ev_type,
            detail=detail,
            comments=ev.get("info") if ev.get("info") else None,
        ))
    return result


def _parse_scores(scores: list[dict], home_team_id: int, away_team_id: int) -> ScoreInfo:
    result = ScoreInfo(home=0, away=0, halftime_home=0, halftime_away=0)
    for s in scores:
        desc = s.get("description", "")
        score_data = s.get("score", {})
        participant_id = s.get("participant_id", 0)
        goals = _safe_int(score_data.get("goals", 0)) if isinstance(score_data, dict) else _safe_int(score_data)
        is_home = participant_id == home_team_id
        if desc == "CURRENT":
            if is_home: result.home = goals
            else: result.away = goals
        elif desc in ("HT", "HALFTIME"):
            if is_home: result.halftime_home = goals
            else: result.halftime_away = goals
        elif desc == "FT":
            if is_home: result.fulltime_home = goals
            else: result.fulltime_away = goals
        elif desc == "ET":
            if is_home: result.extratime_home = goals
            else: result.extratime_away = goals
        elif desc == "PEN":
            if is_home: result.penalty_home = goals
            else: result.penalty_away = goals
    return result


def _parse_period_scores(scores: list[dict]) -> list[PeriodScore]:
    result = []
    for s in scores:
        desc = s.get("description", "")
        score_data = s.get("score", {})
        goals = _safe_int(score_data.get("goals", 0)) if isinstance(score_data, dict) else _safe_int(score_data)
        sort_order = s.get("sort_order", 0)
        result.append(PeriodScore(description=desc, sort_order=sort_order, home_goals=goals, away_goals=goals))
    return result


def _parse_trends(trends_raw: list[dict]) -> dict:
    parsed = {}
    for t in trends_raw:
        participant_id = t.get("participant_id", 0)
        type_id = t.get("type_id", 0)
        period_id = t.get("period_id", 0)
        minute = t.get("minute", 0)
        value = _safe_float(t.get("value", 0))
        parsed.setdefault(participant_id, {}).setdefault(type_id, []).append(
            TrendPoint(minute=minute, value=value, period_id=period_id)
        )
    return parsed


# ============================================================
# 主数据获取函数
# ============================================================

def fetch_all(match_id: int, config: dict) -> RawMatchData:
    client = SportMonksClient(config)
    data = client.get_fixture_with_details(match_id)

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

    score_info = _parse_scores(data.get("scores", []), home_team.id, away_team.id)

    home_stats = {}
    away_stats = {}
    for item in data.get("statistics", []):
        type_id = item.get("type_id", 0)
        key = FIXTURE_STAT_MAP.get(type_id)
        if key is None:
            continue
        value = _extract_value(item)
        if value is None:
            continue
        target = home_stats if item.get("participant_id", 0) == home_team.id else away_stats
        target[key] = value

    lineups_data = data.get("lineups", [])
    home_players = []
    away_players = []
    for lu in lineups_data:
        team_id = lu.get("team_id", 0)
        player = _parse_player_from_lineup(lu)
        if not player.photo_url and player.id:
            player.photo_url = f"https://cdn.sportmonks.com/images/soccer/players/{player.id % 32}/{player.id}.png"
        if team_id == home_team.id:
            home_players.append(player)
        else:
            away_players.append(player)

    events = _parse_events(data.get("events", []), home_team.id, away_team.id)

    state_id = data.get("state_id", 5)
    status_map = {1:"NS",2:"LIVE",3:"HT",4:"BT",5:"FT",6:"AET",7:"PEN",8:"PST",9:"SUSP",10:"INT"}
    status = status_map.get(state_id, "FT")

    periods_raw = data.get("periods", [])
    periods = []
    for pr in periods_raw:
        period_stats = pr.get("statistics", [])
        period_events_raw = pr.get("events", [])
        home_ps = {}
        away_ps = {}
        for item in period_stats:
            key = FIXTURE_STAT_MAP.get(item.get("type_id", 0))
            if key is None:
                continue
            value = _extract_value(item)
            if value is None:
                continue
            target = home_ps if item.get("participant_id", 0) == home_team.id else away_ps
            target[key] = value
        periods.append(PeriodData(
            sort_order=pr.get("sort_order", 0),
            description=pr.get("description", ""),
            period_length=pr.get("period_length", 45),
            home_stats=home_ps,
            away_stats=away_ps,
            events=_parse_events(period_events_raw, home_team.id, away_team.id),
        ))

    trends = _parse_trends(data.get("trends", []))

    coaches_raw = data.get("coaches", [])
    home_coach = None
    away_coach = None
    for c in coaches_raw:
        ci = CoachInfo(
            id=c.get("id", 0),
            name=c.get("name", ""),
            photo_url=c.get("image_path", ""),
        )
        if c.get("participant_id", 0) == home_team.id:
            home_coach = ci
        else:
            away_coach = ci

    period_scores = _parse_period_scores(data.get("scores", []))

    raw = RawMatchData(
        match_id=match_id, fixture_id=match_id,
        home_team=home_team, away_team=away_team,
        home_coach=home_coach, away_coach=away_coach,
        score=score_info, period_scores=period_scores, status=status,
        home_stats=home_stats, away_stats=away_stats,
        home_players=home_players, away_players=away_players,
        events=events, periods=periods,
        trends=trends,
    )

    _save_raw_data(raw)
    return raw


def _save_raw_data(raw: RawMatchData):
    import dataclasses
    base = Path("data/raw") / str(raw.match_id)
    base.mkdir(parents=True, exist_ok=True)

    def _serialize(obj):
        if dataclasses.is_dataclass(obj):
            result = {"_type": type(obj).__name__}
            for f in dataclasses.fields(obj):
                val = getattr(obj, f.name)
                if isinstance(val, list):
                    result[f.name] = [_serialize(v) for v in val]
                elif isinstance(val, dict):
                    result[f.name] = {str(k): _serialize(v) for k, v in val.items()}
                elif dataclasses.is_dataclass(val):
                    result[f.name] = _serialize(val)
                else:
                    result[f.name] = val
            return result
        return obj

    data = _serialize(raw)
    with open(base / "raw_data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
