import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import requests


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


class APIFootballClient:
    def __init__(self, config: dict):
        raw_key = config.get("api_key", "")
        if raw_key.startswith("${"):
            env_key = raw_key.strip("${").strip("}")
            raw_key = os.environ.get(env_key, "")
        self.api_key = os.environ.get("API_FOOTBALL_KEY", raw_key)

        self.base_url = config["base_url"]
        self.api_host = config.get("api_host", "api-football-v1.p.rapidapi.com")

        if "api-sports.io" in self.api_host:
            self.headers = {"x-apisports-key": self.api_key}
        else:
            self.headers = {
                "X-RapidAPI-Key": self.api_key,
                "X-RapidAPI-Host": self.api_host,
            }

    def _get(self, endpoint: str, params: dict) -> dict:
        url = f"{self.base_url}{endpoint}"
        resp = requests.get(url, headers=self.headers, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if data.get("errors"):
            raise RuntimeError(f"API error: {data['errors']}")
        return data

    def get_fixtures_by_date(self, league_id: int, season: int, date: str) -> list[dict]:
        params = {"league": league_id, "season": season, "date": date}
        result = self._get("/fixtures", params)
        return result.get("response", [])

    def get_fixture(self, match_id: int) -> dict:
        params = {"id": match_id}
        result = self._get("/fixtures", params)
        fixtures = result.get("response", [])
        if not fixtures:
            raise ValueError(f"Fixture not found: {match_id}")
        return fixtures[0]

    def get_statistics(self, fixture_id: int) -> dict:
        params = {"fixture": fixture_id}
        result = self._get("/fixtures/statistics", params)
        return result.get("response", [])

    def get_players(self, fixture_id: int) -> dict:
        params = {"fixture": fixture_id}
        result = self._get("/fixtures/players", params)
        return result.get("response", [])

    def get_events(self, fixture_id: int) -> dict:
        params = {"fixture": fixture_id}
        result = self._get("/fixtures/events", params)
        return result.get("response", [])

    def get_lineups(self, fixture_id: int) -> dict:
        params = {"fixture": fixture_id}
        result = self._get("/fixtures/lineups", params)
        return result.get("response", [])


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


def _parse_stats(statistics_list: list[dict]) -> dict:
    parsed = {}
    for item in statistics_list:
        key = item["type"]
        value = item.get("value")
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


def _parse_player_stats(player_data: dict) -> PlayerStats:
    stat = player_data.get("statistics", [{}])[0]
    games = stat.get("games", {})
    goals_data = stat.get("goals", {})
    shots = stat.get("shots", {})
    passes = stat.get("passes", {})
    tackles = stat.get("tackles", {})
    duels = stat.get("duels", {})
    dribbles = stat.get("dribbles", {})
    fouls = stat.get("fouls", {})

    rating_val = games.get("rating")
    if rating_val is not None:
        try:
            rating_val = float(rating_val)
        except (ValueError, TypeError):
            rating_val = None

    passes_total_val = _safe_int(passes.get("total"))
    passes_accurate_count = _safe_int(passes.get("accuracy"))
    passes_accuracy_pct = round(passes_accurate_count / max(passes_total_val, 1) * 100, 1)

    return PlayerStats(
        id=player_data["player"]["id"],
        name=player_data["player"]["name"],
        number=_safe_int(player_data["player"].get("number"), 0),
        position=_safe_str(games.get("position", "")),
        grid=player_data.get("statistics", [{}])[0].get("games", {}).get("grid"),
        is_substitute=(
            player_data.get("statistics", [{}])[0]
            .get("games", {})
            .get("substitute", False)
        ),
        minutes_played=_safe_int(games.get("minutes")),
        rating=rating_val,
        goals=_safe_int(goals_data.get("total")),
        assists=_safe_int(goals_data.get("assists")),
        shots_total=_safe_int(shots.get("total")),
        shots_on=_safe_int(shots.get("on")),
        passes_total=passes_total_val,
        passes_key=_safe_int(passes.get("key")),
        passes_accuracy=passes_accuracy_pct,
        tackles_total=_safe_int(tackles.get("total")),
        tackles_interceptions=_safe_int(tackles.get("interceptions")),
        duels_total=_safe_int(duels.get("total")),
        duels_won=_safe_int(duels.get("won")),
        dribbles_attempts=_safe_int(dribbles.get("attempts")),
        dribbles_success=_safe_int(dribbles.get("success")),
        fouls_committed=_safe_int(fouls.get("committed")),
        fouls_drawn=_safe_int(fouls.get("drawn")),
    )


def fetch_all(match_id: int, config: dict) -> RawMatchData:
    client = APIFootballClient(config)
    fixture = client.get_fixture(match_id)
    fixture_data = fixture["fixture"]
    fixture_id = fixture_data["id"]
    league = fixture["league"]
    teams = fixture["teams"]
    goals = fixture["goals"]
    score = fixture["score"]

    def _fetch_stats():
        return client.get_statistics(fixture_id)

    def _fetch_players():
        return client.get_players(fixture_id)

    def _fetch_events():
        return client.get_events(fixture_id)

    def _fetch_lineups():
        return client.get_lineups(fixture_id)

    with ThreadPoolExecutor(max_workers=4) as executor:
        future_stats = executor.submit(_fetch_stats)
        future_players = executor.submit(_fetch_players)
        future_events = executor.submit(_fetch_events)
        future_lineups = executor.submit(_fetch_lineups)

        stats_raw = future_stats.result()
        players_raw = future_players.result()
        events_raw = future_events.result()
        lineups_raw = future_lineups.result()

    home_stats = {}
    away_stats = {}
    for team_stats in stats_raw:
        team_id = team_stats["team"]["id"]
        parsed = _parse_stats(team_stats.get("statistics", []))
        if team_id == teams["home"]["id"]:
            home_stats = parsed
        else:
            away_stats = parsed

    home_players = []
    away_players = []
    for team_players in players_raw:
        team_id = team_players["team"]["id"]
        for p in team_players.get("players", []):
            ps = _parse_player_stats(p)
            if team_id == teams["home"]["id"]:
                home_players.append(ps)
            else:
                away_players.append(ps)

    events = []
    for ev in events_raw:
        events.append(
            MatchEvent(
                time_elapsed=ev["time"]["elapsed"],
                time_extra=ev["time"].get("extra"),
                team_id=ev["team"]["id"],
                team_name=ev["team"]["name"],
                player_name=ev["player"]["name"] if ev.get("player") else "",
                assist_name=(
                    ev["assist"]["name"] if ev.get("assist") and ev["assist"].get("name") else None
                ),
                event_type=ev["type"],
                detail=ev.get("detail", ""),
                comments=ev.get("comments"),
            )
        )

    def _parse_lineup(lineup_data: dict) -> LineupInfo:
        players = []
        for p in lineup_data.get("startXI", []):
            p_info = p.get("player", {})
            players.append(
                LineupPlayer(
                    id=p_info.get("id", 0),
                    name=p_info.get("name", ""),
                    number=p_info.get("number", 0),
                    position=p_info.get("pos", ""),
                    grid=p.get("grid"),
                )
            )
        return LineupInfo(
            formation=lineup_data.get("formation", ""),
            players=players,
        )

    home_lineup = None
    away_lineup = None
    for lu in lineups_raw:
        if lu["team"]["id"] == teams["home"]["id"]:
            home_lineup = _parse_lineup(lu)
        else:
            away_lineup = _parse_lineup(lu)

    score_info = ScoreInfo(
        home=goals["home"] or 0,
        away=goals["away"] or 0,
        halftime_home=score["halftime"]["home"] or 0,
        halftime_away=score["halftime"]["away"] or 0,
        fulltime_home=score.get("fulltime", {}).get("home"),
        fulltime_away=score.get("fulltime", {}).get("away"),
        extratime_home=score.get("extratime", {}).get("home"),
        extratime_away=score.get("extratime", {}).get("away"),
        penalty_home=score.get("penalty", {}).get("home"),
        penalty_away=score.get("penalty", {}).get("away"),
    )

    status = fixture_data.get("status", {}).get("short", "FT")

    raw = RawMatchData(
        match_id=match_id,
        fixture_id=fixture_id,
        home_team=TeamInfo(
            id=teams["home"]["id"],
            name=teams["home"]["name"],
            logo_url=teams["home"].get("logo", ""),
        ),
        away_team=TeamInfo(
            id=teams["away"]["id"],
            name=teams["away"]["name"],
            logo_url=teams["away"].get("logo", ""),
        ),
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


def _save_raw_data(raw: RawMatchData):
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
