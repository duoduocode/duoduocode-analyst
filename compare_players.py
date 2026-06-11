"""
球员贡献对比 — 入口脚本。

用法：
  python compare_players.py 19683241 "Declan Rice" "Vitinha"
  python compare_players.py 19683241 "Declan Rice" "Vitinha" --output compare.png
"""
import argparse
import json
import os
import sys
import yaml

sys.path.insert(0, ".")

from src.collector.api_client import fetch_all
from src.engine.player_insights import (
    run_all_detectors, DETECTOR_TAGS, classify_position, PlayerData,
)
from src.engine.key_events import detect_key_events
from src.visualizer.player_comparison import (
    plot_player_comparison, build_player_comparison_data, DIM_LABELS,
)

# ═══════════════════════════════════════
# 配置
# ═══════════════════════════════════════

def load_config():
    config_path = "config.yaml"
    if os.path.exists(config_path):
        with open(config_path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {"sportmonks": {"api_token": os.environ.get("SPORTMONKS_API_TOKEN", "")}}


def load_raw_data(match_id: int, config: dict):
    """加载或拉取比赛原始数据。"""
    cache_path = f"data/raw/{match_id}/raw_data.json"
    if os.path.exists(cache_path):
        print(f"  加载缓存: {cache_path}")
        with open(cache_path, "r", encoding="utf-8") as f:
            raw_dict = json.load(f)
        # 如果包含 _type 则为 RawMatchData 反序列化
        if raw_dict.get("_type") == "RawMatchData":
            return _deserialize_raw(raw_dict, match_id)
        # 否则通过 API 获取
        return fetch_all(match_id, config["sportmonks"])
    else:
        return fetch_all(match_id, config["sportmonks"])


def _deserialize_raw(d: dict, match_id: int):
    """从带有 _type 标记的 JSON 反序列化 RawMatchData。"""
    from src.collector.api_client import (
        RawMatchData, TeamInfo, CoachInfo, ScoreInfo, MatchEvent, PeriodData,
    )

    def _parse_event(e):
        if isinstance(e, dict):
            return MatchEvent(
                time_elapsed=e.get("time_elapsed", 0),
                time_extra=e.get("time_extra"),
                period_id=e.get("period_id", 0),
                team_id=e.get("team_id", 0),
                team_name=e.get("team_name", ""),
                player_name=e.get("player_name", ""),
                assist_name=e.get("assist_name"),
                event_type=e.get("event_type", ""),
                detail=e.get("detail", ""),
                comments=e.get("comments"),
            )
        return e

    home_team = TeamInfo(**{k: v for k, v in d["home_team"].items() if k != "_type"})
    away_team = TeamInfo(**{k: v for k, v in d["away_team"].items() if k != "_type"})

    sc = d.get("score", {})
    score = ScoreInfo(
        home=sc.get("home", 0), away=sc.get("away", 0),
        halftime_home=sc.get("halftime_home", 0), halftime_away=sc.get("halftime_away", 0),
        fulltime_home=sc.get("fulltime_home"), fulltime_away=sc.get("fulltime_away"),
        extratime_home=sc.get("extratime_home"), extratime_away=sc.get("extratime_away"),
        penalty_home=sc.get("penalty_home"), penalty_away=sc.get("penalty_away"),
    )

    home_coach = CoachInfo(**{k: v for k, v in d["home_coach"].items() if k != "_type"}) if d.get("home_coach") else None
    away_coach = CoachInfo(**{k: v for k, v in d["away_coach"].items() if k != "_type"}) if d.get("away_coach") else None

    events = [_parse_event(e) for e in d.get("events", []) if isinstance(e, (dict,))]

    periods = []
    for pd in d.get("periods", []):
        pev = [_parse_event(e) for e in pd.get("events", []) if isinstance(e, (dict,))]
        periods.append(PeriodData(
            sort_order=pd.get("sort_order", 0),
            description=pd.get("description", ""),
            period_length=pd.get("period_length", 45),
            home_stats=pd.get("home_stats", {}),
            away_stats=pd.get("away_stats", {}),
            events=pev,
        ))

    return RawMatchData(
        match_id=match_id, fixture_id=match_id,
        home_team=home_team, away_team=away_team,
        home_coach=home_coach, away_coach=away_coach,
        score=score,
        period_scores=d.get("period_scores", []),
        status=d.get("status", "FT"),
        home_stats=d.get("home_stats", {}),
        away_stats=d.get("away_stats", {}),
        home_players=d.get("home_players", []),
        away_players=d.get("away_players", []),
        events=events,
        periods=periods,
        trends=d.get("trends", {}),
        timeline=d.get("timeline", []),
        formations=d.get("formations", []),
        stage_info=d.get("stage_info"),
        venue_info=d.get("venue_info"),
    )


def _load_physical_data(match_id: int, player_name: str) -> tuple:
    """Try loading run/carry data. Returns (run_km, carry_km) or (None, None).

    兼容以下异常情况（均返回 None）：
    - data/{match_id}/ 目录不存在
    - data/{match_id}/{player_name}/ 目录不存在
    - run_data.json 或 carry_data.json 不存在/格式异常/缺失字段
    """
    data_dir = os.path.join("data", str(match_id), player_name)
    run_km = None
    carry_km = None

    run_path = os.path.join(data_dir, "run_data.json")
    if os.path.isfile(run_path):
        try:
            run = json.load(open(run_path, "r", encoding="utf-8"))
            run_km = 0.0
            for k in ("Walking + jogging", "Running", "High-speed running", "Sprinting"):
                val = run.get(k)
                if val is None:
                    continue
                run_km += float(str(val).split()[0])
        except (json.JSONDecodeError, FileNotFoundError, KeyError, ValueError, IndexError):
            pass

    carry_path = os.path.join(data_dir, "carry_data.json")
    if os.path.isfile(carry_path):
        try:
            carry = json.load(open(carry_path, "r", encoding="utf-8"))
            val = carry.get("Total carrying distance")
            if val is not None:
                carry_km = float(str(val).split()[0]) / 1000.0
        except (json.JSONDecodeError, FileNotFoundError, KeyError, ValueError, IndexError):
            pass

    return run_km, carry_km


def build_lineups_from_raw(raw):
    """从 RawMatchData 构建 lineups 格式。"""
    lineups = []
    home_id = raw.home_team.id
    away_id = raw.away_team.id

    REVERSE_MAP = {}
    from src.collector.api_client import PLAYER_STAT_MAP
    REVERSE_MAP = {v: k for k, v in PLAYER_STAT_MAP.items()}

    def _player_to_lineup(p, team_id):
        details = []
        if isinstance(p, dict):
            pid = p.get("id")
            for field_name, value in p.items():
                type_id = REVERSE_MAP.get(field_name)
                if type_id and value is not None:
                    details.append({"type_id": type_id, "data": {"value": value}})
            pos_id = p.get("position_id", p.get("grid", ""))
            photo_url = p.get("photo_url", "")
            player_name = p.get("name", "")
            number = p.get("number", "")
        else:
            pid = p.id
            for field_name in dir(p):
                if field_name.startswith("_"):
                    continue
                type_id = REVERSE_MAP.get(field_name)
                if type_id:
                    val = getattr(p, field_name)
                    if val is not None:
                        details.append({"type_id": type_id, "data": {"value": val}})
            pos_id = getattr(p, "position_id", getattr(p, "grid", ""))
            photo_url = getattr(p, "photo_url", "")
            player_name = p.name
            number = getattr(p, "number", "")

        player_obj = {}
        if photo_url:
            player_obj["image_path"] = photo_url
        if number:
            player_obj["number"] = number

        return {
            "player_id": pid,
            "player_name": player_name,
            "team_id": team_id,
            "position_id": pos_id,
            "player": player_obj,
            "details": details,
        }

    for p in raw.home_players:
        lineups.append(_player_to_lineup(p, home_id))
    for p in raw.away_players:
        lineups.append(_player_to_lineup(p, away_id))

    return lineups, home_id, away_id


def build_events_list(raw):
    """从 RawMatchData 构建事件列表。"""
    events = []
    for e in raw.events:
        info = {}
        if hasattr(e, "player_name"):
            info = {
                "player_name": e.player_name,
                "time_elapsed": e.time_elapsed,
                "period_id": e.period_id,
                "team_id": e.team_id,
                "event_type": e.event_type,
                "detail": e.detail or "",
                "assist_name": e.assist_name,
            }
        elif isinstance(e, dict):
            info = {
                "player_name": e.get("player_name", ""),
                "time_elapsed": e.get("time_elapsed", 0),
                "period_id": e.get("period_id", 0),
                "team_id": e.get("team_id", e.get("participant_id", 0)),
                "event_type": e.get("event_type", ""),
                "detail": e.get("detail", ""),
                "assist_name": e.get("assist_name"),
            }
        if info:
            events.append(info)
    return events


def build_key_events_for_player(raw, player_name: str) -> str:
    """为指定球员构建关键事件文本。"""
    labels = []

    home_id = raw.home_team.id
    away_id = raw.away_team.id
    events = build_events_list(raw)

    # 分离进球和换人
    goals = []
    subs = []
    for e in events:
        et = e.get("event_type", "")
        if et == "Goal" or et == "goal":
            goals.append(e)
        elif et == "subst" or et == "Subst":
            subs.append({
                "player_in": e.get("assist_name", ""),
                "player_out": e.get("player_name", ""),
                "minute": e.get("time_elapsed", 0),
            })

    try:
        periods_data = raw.periods if hasattr(raw, "periods") else []
        if hasattr(periods_data, "__iter__") and hasattr(periods_data, "__len__"):
            periods_list = []
            for p in periods_data:
                if hasattr(p, "sort_order"):
                    periods_list.append({"sort_order": p.sort_order})
                elif isinstance(p, dict):
                    periods_list.append(p)
        else:
            periods_list = []
    except Exception:
        periods_list = []

    key_result = detect_key_events(
        goals, subs, home_id, away_id,
        raw.score.home, raw.score.away,
        periods_list,
    )

    # 检查该球员命中的关键事件
    if player_name in key_result.first_goal_scorers:
        labels.append("首开记录")
    if key_result.late_winner_scorer == player_name:
        labels.append("绝杀")
    elif key_result.winning_goal_scorer == player_name:
        labels.append("制胜球")
    if key_result.equalizer_scorer == player_name:
        labels.append("绝平球")
    if player_name in key_result.super_sub_scorers:
        labels.append("超级替补")
    if player_name in key_result.penalty_scorers:
        labels.append("点球进球")
    if player_name in key_result.pen_shootout_scorers:
        labels.append("点球大战进球")
    if player_name in key_result.pen_shootout_missers:
        labels.append("点球大战射失")

    # 检查是否是制造点球 (assist_name 中有该球员且 detail 包含 penalty)
    for g in goals:
        if g.get("assist_name") == player_name or g.get("player_name") == player_name:
            detail = g.get("detail", "")
            if "penalty" in detail and g.get("assist_name") == player_name:
                if "赢得点球" not in labels:
                    labels.append("赢得点球")

    return "，".join(labels) if labels else "-"


def _build_full_score(score, raw) -> str:
    """构建全场最终比分展示（常规+加时+点球大战总和）。"""
    h = score.home
    a = score.away

    # 检测点球大战：从 penalty period 的 events 中统计 pen_shootout_goal
    ps_goals_home = 0
    ps_goals_away = 0
    home_id = getattr(raw.home_team, "id", 0)
    periods = getattr(raw, "periods", []) or []

    # 构建球员→队伍映射（penalty period events 没有 team_id，需通过球员列表匹配）
    player_team = {}
    for team_players, team_id in [
        (getattr(raw, "home_players", None) or [], home_id),
        (getattr(raw, "away_players", None) or [],
         getattr(raw.away_team, "id", 0)),
    ]:
        for p in team_players:
            pname = (p.get("name") or p.get("player_name") or "").strip()
            if pname:
                player_team[pname] = team_id

    for period in periods:
        desc = getattr(period, "description", "") if hasattr(period, "description") else period.get("description", "")
        if desc != "penalties":
            continue
        events = getattr(period, "events", None) or period.get("events", []) or []
        for ev in events:
            if not isinstance(ev, dict):
                detail = getattr(ev, "detail", "")
                ev_player = (getattr(ev, "player_name", None) or getattr(ev, "player", "") or "").strip()
            else:
                detail = ev.get("detail", "")
                ev_player = (ev.get("player_name") or ev.get("player") or "").strip()
            if detail != "pen_shootout_goal":
                continue
            tid = player_team.get(ev_player)
            if tid == home_id:
                ps_goals_home += 1
            elif tid:
                ps_goals_away += 1

    # 汇总（extratime_home/away 在 ScoreInfo 中有默认值 0）
    et_h = getattr(score, "extratime_home", 0) or 0
    et_a = getattr(score, "extratime_away", 0) or 0
    total_home = h + et_h + ps_goals_home
    total_away = a + et_a + ps_goals_away

    return f"{total_home} - {total_away}"


def main():
    parser = argparse.ArgumentParser(description="球员贡献对比")
    parser.add_argument("match_id", type=int, help="比赛 ID")
    parser.add_argument("player_a", type=str, help="球员 A 姓名")
    parser.add_argument("player_b", type=str, help="球员 B 姓名")
    parser.add_argument("--output", type=str, default=None, help="输出图片路径")
    args = parser.parse_args()

    print(f"对比: {args.player_a} vs {args.player_b}, 比赛 #{args.match_id}")

    # 加载数据
    config = load_config()
    raw = load_raw_data(args.match_id, config)

    home_name = raw.home_team.name
    away_name = raw.away_team.name
    score = raw.score
    print(f"  {home_name} {score.home} - {score.away} {away_name}")

    lineups, home_id, away_id = build_lineups_from_raw(raw)
    events = build_events_list(raw)

    # 收集所有球员（用于排名）
    end_min = 120 if getattr(score, "extratime_home", None) is not None else 90
    if getattr(score, "extratime_home", None) is not None:
        end_min = 120
    elif getattr(score, "fulltime_home", None) is not None:
        end_min = 120 if score.fulltime_home is not None else 90
    else:
        end_min = 90

    # 运行检测器
    results = run_all_detectors(
        lineups, home_id, away_id,
        score.home, score.away, events, end_min,
        home_name=home_name, away_name=away_name,
    )

    # 构建全体球员 PlayerData 列表（含内外场）
    all_players = []
    home_players_data = []
    away_players_data = []

    for p in raw.home_players:
        if isinstance(p, dict):
            pid = p.get("id")
            pname = p.get("name", "")
            stats = {}
            REVERSE_MAP = {}
            from src.collector.api_client import PLAYER_STAT_MAP
            REVERSE_MAP = {v: k for k, v in PLAYER_STAT_MAP.items()}
            for field_name, value in p.items():
                type_id = REVERSE_MAP.get(field_name)
                if type_id and value is not None:
                    stats[type_id] = value
            pos = p.get("position", "M")
            pos_id = classify_position(p.get("position_id", 0) if p.get("position_id") else
                                       {"G": 24, "D": 5, "M": 14, "F": 21}.get(pos, 14))
            photo_url = p.get("photo_url", "")
            pd = PlayerData(
                player_id=pid, name=pname,
                position_id=pos_id, pos=pos,
                team_name=home_name, stats=stats, photo_url=photo_url,
            )
        else:
            pd = PlayerData(
                player_id=p.id, name=p.name,
                position_id=getattr(p, "position_id", 0), pos=getattr(p, "pos", "M"),
                team_name=home_name, stats=getattr(p, "stats", {}),
                photo_url=getattr(p, "photo_url", ""),
            )
        home_players_data.append(pd)
        all_players.append(pd)

    for p in raw.away_players:
        if isinstance(p, dict):
            pid = p.get("id")
            pname = p.get("name", "")
            stats = {}
            REVERSE_MAP = {}
            from src.collector.api_client import PLAYER_STAT_MAP
            REVERSE_MAP = {v: k for k, v in PLAYER_STAT_MAP.items()}
            for field_name, value in p.items():
                type_id = REVERSE_MAP.get(field_name)
                if type_id and value is not None:
                    stats[type_id] = value
            pos = p.get("position", "M")
            pos_id = classify_position(p.get("position_id", 0) if p.get("position_id") else
                                       {"G": 24, "D": 5, "M": 14, "F": 21}.get(pos, 14))
            photo_url = p.get("photo_url", "")
            pd = PlayerData(
                player_id=pid, name=pname,
                position_id=pos_id, pos=pos,
                team_name=away_name, stats=stats, photo_url=photo_url,
            )
        else:
            pd = PlayerData(
                player_id=p.id, name=p.name,
                position_id=getattr(p, "position_id", 0), pos=getattr(p, "pos", "M"),
                team_name=away_name, stats=getattr(p, "stats", {}),
                photo_url=getattr(p, "photo_url", ""),
            )
        away_players_data.append(pd)
        all_players.append(pd)

    # 检查：是否为门将
    ap_check = next((p for p in all_players if p.name == args.player_a), None)
    bp_check = next((p for p in all_players if p.name == args.player_b), None)
    if ap_check and ap_check.pos == "G":
        print(f"  错误: {args.player_a} 是门将，不支持门将对比")
        sys.exit(1)
    if bp_check and bp_check.pos == "G":
        print(f"  错误: {args.player_b} 是门将，不支持门将对比")
        sys.exit(1)

    # 找出球员所在队伍
    a_in_home = any(p.name == args.player_a for p in home_players_data)
    b_in_home = any(p.name == args.player_b for p in home_players_data)

    a_team = home_name if a_in_home else away_name
    b_team = home_name if b_in_home else away_name

    a_team_list = home_players_data if a_in_home else away_players_data
    b_team_list = home_players_data if b_in_home else away_players_data

    # 构建检测器结果字典
    detector_results = {
        "D1": getattr(results, "D1_progression", {}),
        "D2": getattr(results, "D2_pressing", {}),
        "D3": getattr(results, "D3_gravity", {}),
        "D4": getattr(results, "D4_tempo", {}),
        "D5": getattr(results, "D5_twoway", {}),
    }

    # 关键事件
    key_a = build_key_events_for_player(raw, args.player_a)
    key_b = build_key_events_for_player(raw, args.player_b)
    print(f"  {args.player_a}: 关键事件 = {key_a}")
    print(f"  {args.player_b}: 关键事件 = {key_b}")

    # 加载跑动/推进数据
    run_a, carry_a = _load_physical_data(args.match_id, args.player_a)
    run_b, carry_b = _load_physical_data(args.match_id, args.player_b)
    if run_a is not None or carry_a is not None:
        print(f"  {args.player_a}: 跑动={run_a}, 推进={carry_a}")
    if run_b is not None or carry_b is not None:
        print(f"  {args.player_b}: 跑动={run_b}, 推进={carry_b}")

    # 构建对比数据
    player_a_data = build_player_comparison_data(
        a_team_list, detector_results, {args.player_a: key_a},
        args.player_a, a_team, all_players,
        run_km=run_a, carry_km=carry_a,
    )
    player_b_data = build_player_comparison_data(
        b_team_list, detector_results, {args.player_b: key_b},
        args.player_b, b_team, all_players,
        run_km=run_b, carry_km=carry_b,
    )

    if player_a_data is None:
        print(f"  错误: 找不到球员 {args.player_a}")
        sys.exit(1)
    if player_b_data is None:
        print(f"  错误: 找不到球员 {args.player_b}")
        sys.exit(1)

    # 重新设置 team 标志（用于配色）
    player_a_data["team"] = "home" if a_in_home else "away"
    player_b_data["team"] = "home" if b_in_home else "away"

    # 输出路径: output/{match_id}_{home_vs_away}/compare/
    safe_home = home_name.replace(" ", "_")
    safe_away = away_name.replace(" ", "_")
    match_dir = f"output/{args.match_id}_{safe_home}_vs_{safe_away}"
    compare_dir = f"{match_dir}/compare"
    safe_a = args.player_a.replace(" ", "_")
    safe_b = args.player_b.replace(" ", "_")
    output_path = args.output or f"{compare_dir}/{safe_a}_vs_{safe_b}.png"

    # ── 构建全场最终比分（含加时/点球） ──
    full_score = _build_full_score(score, raw)

    match_title = f"{home_name}  {full_score}  {away_name}"

    print(f"  生成对比图: {output_path}")
    plot_player_comparison(
        match_title=match_title,
        home_name=home_name,
        away_name=away_name,
        player_a=player_a_data,
        player_b=player_b_data,
        output_path=output_path,
    )
    print(f"  完成!")


if __name__ == "__main__":
    main()
