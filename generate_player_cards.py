"""
Generate player contribution cards from fixture data.
Usage: python generate_player_cards.py 19683241 --player "Declan Rice"
       python generate_player_cards.py 19683241 --all
"""
import argparse, json, sys, os
sys.path.insert(0, '.')

from src.engine.player_insights import (
    run_all_detectors, DETECTOR_TAGS, classify_position,
)
from src.visualizer.player_card import plot_player_card, build_detector_sections
from src.collector.api_client import fetch_all, PLAYER_STAT_MAP
import yaml

REVERSE_MAP = {v: k for k, v in PLAYER_STAT_MAP.items()}

_POS_LABELS = {"G": "门将", "D": "后卫", "M": "中场", "F": "前锋"}


def player_to_lineup(p, team_id):
    details = []
    for field_name, value in p.items():
        type_id = REVERSE_MAP.get(field_name)
        if type_id and value is not None:
            details.append({'type_id': type_id, 'data': {'value': value}})
    return {
        'player_id': p['id'], 'player_name': p['name'],
        'team_id': team_id,
        'position_id': p.get('grid', p.get('position_id', 0)),
        'details': details,
        'player': {
            'image_path': p.get('photo_url', ''),
            'position_id': p.get('grid', p.get('position_id', 0)),
        }
    }


DETECTOR_ATTRS = {
    "D1": "D1_progression", "D2": "D2_pressing", "D3": "D3_gravity",
    "D4": "D4_tempo", "D5": "D5_twoway", "D7": "D7_efficiency",
    "D8": "D8_role_deviation", "D9": "D9_connector", "D10": "D10_finishing",
    "D13": "D13_prowess",
}


def load_or_fetch(match_id: int, force_fetch: bool = False) -> dict:
    raw_path = f'data/raw/{match_id}/raw_data.json'
    if force_fetch or not os.path.exists(raw_path):
        print(f"Fetching fixture {match_id}...")
        config = yaml.safe_load(open("config.yaml", encoding="utf-8"))
        raw = fetch_all(match_id, config["sportmonks"])
        # Save the raw dict to file
        import json as _json
        os.makedirs(os.path.dirname(raw_path), exist_ok=True)
        # fetch_all returns RawMatchData, need to serialize manually
        # We'll just use the raw JSON from the API
        from src.collector.api_client import SportMonksClient
        client = SportMonksClient(config["sportmonks"])
        raw_json = client.get_fixture_with_details(match_id)
        with open(raw_path, 'w', encoding='utf-8') as f:
            _json.dump(raw_json, f, ensure_ascii=False, indent=2)
        return raw_json
    else:
        with open(raw_path, 'r', encoding='utf-8') as f:
            return json.load(f)


def parse_lineups_events(RAW: dict):
    home_id = RAW['home_team']['id']
    away_id = RAW['away_team']['id']
    hname = RAW['home_team']['name']
    aname = RAW['away_team']['name']
    home_logo = RAW['home_team'].get('logo_url', '')
    away_logo = RAW['away_team'].get('logo_url', '')

    lineups = [player_to_lineup(p, home_id) for p in RAW['home_players']]
    lineups += [player_to_lineup(p, away_id) for p in RAW['away_players']]

    events = []
    for e in RAW.get('events', []):
        events.append({
            'type_id': e.get('type_id', 0),
            'player_id': e.get('player_id', 0),
            'participant_id': e.get('participant_id', 0),
            'related_player_id': e.get('related_player_id', 0),
            'minute': e.get('time_elapsed', 0) or e.get('minute', 0),
            'period_id': e.get('period_id', 1),
            'event_type': e.get('event_type', ''),
            'detail': e.get('detail', ''),
            'player_name': e.get('player_name', ''),
            'related_player_name': e.get('related_player_name', ''),
        })
    end_min = 120 if RAW.get('score', {}).get('extratime_home') is not None else 90
    return home_id, away_id, hname, aname, home_logo, away_logo, lineups, events, end_min


def build_player_index(lineups, home_id, away_id, hname, aname, home_logo, away_logo, raw_players):
    """Build player info dict. Uses raw_players for position field (SportMonks classification)."""
    # Build raw player lookup by id
    raw_by_id = {}
    for rp in raw_players:
        raw_by_id[rp.get('id')] = rp

    # Position mapping: SportMonks single-letter → Chinese
    _SM_POS = {"G": "门将", "D": "后卫", "M": "中场", "F": "前锋"}

    players = {}
    for lu in lineups:
        pid = lu.get('player_id')
        pname = lu.get('player_name', f"Player #{pid}")
        if not pid:
            continue
        tid = lu.get('team_id')

        rp = raw_by_id.get(pid, {})
        pos_code = rp.get('position', '?')  # SportMonks position: G/D/M/F
        if pos_code in _SM_POS:
            pos = _SM_POS[pos_code]
        else:
            # Fallback: try grid-based classification
            grid = rp.get('grid', '')
            if isinstance(grid, str) and grid:
                col = int(grid.split(':')[0]) if ':' in grid else 0
                pos = "门将" if col == 1 else "后卫" if col <= 4 else "中场" if col <= 6 else "前锋"
            else:
                pos = "?"
        photo_url = rp.get('photo_url', '')
        number = rp.get('number', '')
        minutes = rp.get('minutes_played', 0) or 0
        is_home = tid == home_id
        players[pname.lower()] = {
            'name': pname, 'photo_url': photo_url,
            'team': hname if is_home else aname,
            'team_logo': home_logo if is_home else away_logo,
            'position': _POS_LABELS.get(pos, pos),
            'is_home': is_home,
            'number': number,
            'minutes': int(minutes),
        }
    return players


def build_detector_data(results, hname, aname):
    """Extract raw results + top3 per detector per team."""
    raw_by_detector = {}
    top3_by_detector = {}
    for dname, attr in DETECTOR_ATTRS.items():
        d = getattr(results, attr)
        raw_by_detector[dname] = d
        top3_by_detector[dname] = {
            "team_results": {
                team: [{"name": r.name, "score": r.score} for r in rlist[:3]]
                for team, rlist in d.items()
            }
        }
    return raw_by_detector, top3_by_detector


def generate_card_for_player(match_id: int, player_query: str, force_fetch: bool = False):
    RAW = load_or_fetch(match_id, force_fetch)
    home_id, away_id, hname, aname, home_logo, away_logo, lineups, events, end_min = \
        parse_lineups_events(RAW)

    results = run_all_detectors(
        lineups, home_id, away_id,
        RAW['score']['home'], RAW['score']['away'],
        events, end_min,
        home_name=hname, away_name=aname,
    )

    all_players = build_player_index(lineups, home_id, away_id, hname, aname, home_logo, away_logo, RAW.get('home_players', []) + RAW.get('away_players', []))
    raw_by_detector, top3_by_detector = build_detector_data(results, hname, aname)

    # Find player
    pq = player_query.strip().lower()
    matched = None
    for key, info in all_players.items():
        if pq in key:
            matched = info
            break
    if not matched:
        print(f"Player '{player_query}' not found. Available:")
        for name in sorted(all_players.keys()):
            print(f"  {name}")
        return

    sections = build_detector_sections(
        raw_by_detector, top3_by_detector,
        matched['name'], matched['team'],
    )

    if not sections:
        print(f"{matched['name']} ({matched['team']}) has no top-3 detector hits.")
        return

    output_dir = f"output/{match_id}_{hname}_vs_{aname}/player_cards"
    output_path = f"{output_dir}/{matched['name']}_card.png"

    print(f"\n{matched['name']} | {matched['team']} | {matched['position']}")
    print(f"Tags: {', '.join(s['tag'] for s in sections)}")
    for s in sections:
        print(f"  [{s['tag']}] score={s['score']}  metrics: {[m[0] for m in s['metrics']]}")

    plot_player_card(
        player_name=matched['name'],
        photo_url=matched['photo_url'],
        team_name=matched['team'],
        team_logo_url=matched['team_logo'],
        position=matched['position'],
        sections=sections,
        output_path=output_path,
        jersey_number=str(matched.get('number', '')),
        minutes=matched.get('minutes', 0),
    )
    print(f"→ Saved: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate player contribution cards")
    parser.add_argument("match_id", type=int, help="Fixture ID")
    parser.add_argument("--player", type=str, help="Player name (partial match)")
    parser.add_argument("--all", action="store_true", help="Generate for all eligible players")
    parser.add_argument("--fetch", action="store_true", help="Force re-fetch data")
    args = parser.parse_args()

    if args.player:
        generate_card_for_player(args.match_id, args.player, force_fetch=args.fetch)
    elif args.all:
        RAW = load_or_fetch(args.match_id, args.fetch)
        home_id, away_id, hname, aname, home_logo, away_logo, lineups, events, end_min = \
            parse_lineups_events(RAW)
        results = run_all_detectors(
            lineups, home_id, away_id,
            RAW['score']['home'], RAW['score']['away'],
            events, end_min,
            home_name=hname, away_name=aname,
        )
        all_players = build_player_index(lineups, home_id, away_id, hname, aname, home_logo, away_logo, RAW.get('home_players', []) + RAW.get('away_players', []))
        raw_by_detector, top3_by_detector = build_detector_data(results, hname, aname)
        output_dir = f"output/{match_id}_{hname}_vs_{aname}/player_cards"

        count = 0
        for key, info in all_players.items():
            sections = build_detector_sections(
                raw_by_detector, top3_by_detector, info['name'], info['team'],
            )
            if not sections:
                continue
            output_path = f"{output_dir}/{info['name']}_card.png"
            plot_player_card(
                player_name=info['name'],
                photo_url=info['photo_url'],
                team_name=info['team'],
                team_logo_url=info['team_logo'],
                position=info['position'],
                sections=sections,
                output_path=output_path,
                jersey_number=str(info.get('number', '')),
                minutes=info.get('minutes', 0),
            )
            count += 1
            print(f"[{count}] {info['name']} → {', '.join(s['tag'] for s in sections)}")
        print(f"\nDone: {count} cards in {output_dir}/")
    else:
        print("Use --player <name> or --all")
