"""Run player contribution detectors on a match and save results."""
import json, sys, os
sys.path.insert(0, '.')

from src.collector.api_client import PLAYER_STAT_MAP
from src.engine.player_insights import run_all_detectors

REVERSE_MAP = {v: k for k, v in PLAYER_STAT_MAP.items()}

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

def main(match_id):
    raw_path = f'data/raw/{match_id}/raw_data.json'
    RAW = json.load(open(raw_path, 'r', encoding='utf-8'))

    home_id = RAW['home_team']['id']
    away_id = RAW['away_team']['id']
    hname = RAW['home_team']['name']
    aname = RAW['away_team']['name']

    lineups = [player_to_lineup(p, home_id) for p in RAW['home_players']]
    lineups += [player_to_lineup(p, away_id) for p in RAW['away_players']]

    events = []
    for e in RAW['events']:
        events.append({
            'type_id': e.get('type_id', 0),
            'player_id': e.get('player_id', 0),
            'team_id': e.get('team_id', 0),
            'related_player_id': e.get('related_player_id', 0),
            'minute': e.get('time_elapsed', 0) or e.get('minute', 0),
            'period_id': e.get('period_id', 1),
            'event_type': e.get('event_type', ''),
            'detail': e.get('detail', ''),
            'player_name': e.get('player_name', ''),
            'related_player_name': e.get('related_player_name', ''),
        })

    end_min = 120 if RAW.get('score', {}).get('extratime_home') is not None else 90
    print(f'Lineups: {len(lineups)}, Events: {len(events)}, End: {end_min}min')

    results = run_all_detectors(
        lineups, home_id, away_id,
        RAW['score']['home'], RAW['score']['away'],
        events, end_min,
        home_name=hname, away_name=aname,
    )

    DETECTORS = [
        ('D1_progression', 'D1 推进价值 (Progression Value)'),
        ('D2_pressing', 'D2 压迫与反压迫 (Press & Counter-press)'),
        ('D3_gravity', 'D3 无球价值/Gravity (Off-ball Value)'),
        ('D4_tempo', 'D4 节奏控制/节拍器 (Tempo Control)'),
        ('D5_twoway', 'D5 双向负荷 (Two-way Load)'),
        ('D6_timing', 'D6 时机价值 (Timing Value)'),
        ('D7_efficiency', 'D7 效率与产量背离 (Efficiency vs Volume)'),
        ('D8_role_deviation', 'D8 角色偏离度 (Role Deviation)'),
        ('D9_connector', 'D9 连接器 (Connector)'),
        ('D10_finishing', 'D10 终结质量 (Finishing Quality)'),
        ('D11_xg_deviation', 'D11 xG背离度 (xG Deviation)'),
        ('D12_pure_finisher', 'D12 纯终结者 (Pure Finisher)'),
    ]

    print(f'\n{"="*60}')
    print(f'PLAYER CONTRIBUTION DETECTORS — {hname} vs {aname}')
    print(f'{"="*60}')

    output = {'match': f'{hname} vs {aname}', 'match_id': match_id,
              'end_minute': end_min, 'detectors': {}}

    for attr, label in DETECTORS:
        val = getattr(results, attr)
        print(f'\n--- {label} ---')
        det_result = {'label': label, 'rankings': []}

        if isinstance(val, dict):
            for team, plist in val.items():
                print(f'  [{team}]')
                for i, r in enumerate(plist[:3], 1):
                    ev = ', '.join(f'{k}={v}' for k, v in list(r.evidence.items())[:3])
                    print(f'    #{i} {r.name:22s} score={r.score:.3f}  [{ev}]')
                for i, r in enumerate(plist[:5], 1):
                    det_result['rankings'].append({
                        'rank': i, 'team': team,
                        'name': r.name, 'score': round(r.score, 3),
                        'evidence': {k: round(v, 4) if isinstance(v, float) else v
                                     for k, v in r.evidence.items()}
                    })
        elif isinstance(val, list):
            print(f'  [Combined cross-team]')
            for i, r in enumerate(val[:5], 1):
                ev = ', '.join(f'{k}={v}' for k, v in list(r.evidence.items())[:3])
                print(f'    #{i} {r.name:22s} score={r.score:.3f}  [{ev}]')
                det_result['rankings'].append({
                    'rank': i, 'team': 'combined',
                    'name': r.name, 'score': round(r.score, 3),
                    'evidence': {k: round(v, 4) if isinstance(v, float) else v
                                 for k, v in r.evidence.items()}
                })
        output['detectors'][attr] = det_result

    out_path = f'data/computed/{match_id}_player_insights.json'
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f'\nResults saved to {out_path}')
    print(f'{len(output["detectors"])} detectors processed.')
    return output

if __name__ == '__main__':
    match_id = int(sys.argv[1]) if len(sys.argv) > 1 else 19683241
    main(match_id)
