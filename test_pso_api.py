"""Check SportMonks penalty shootout event fields."""
import requests, json

url = 'https://api.sportmonks.com/v3/football/fixtures/19683241'
params = {
    'api_token': 'w6PU0YE99DrKPnOY43xonH5Bf7S279Ysvzzj6LZaAqnOKusDEIAUTbaNUzDr',
    'include': 'events;periods.events',
}
s = requests.Session()
s.trust_env = False
resp = s.get(url, params=params, timeout=30)
data = resp.json()
# Print top-level keys
print('Top-level keys:', list(data.keys()))
fixture = data if 'data' not in data else data['data']
print('Fixture keys:', list(fixture.keys()))

events = fixture.get('events', [])
pso_events = [e for e in events if e.get('detail') in ('pen_shootout_goal', 'pen_shootout_miss')]

if pso_events:
    print(f'Found {len(pso_events)} PSO events')
    # Check all keys
    all_keys = set()
    for e in pso_events:
        all_keys.update(e.keys())
    print('All available keys:', sorted(all_keys))
    print()
    for e in pso_events:
        print(json.dumps(e, indent=2, ensure_ascii=False))
        print()
else:
    print('No PSO events found in top-level events')
    # Check periods
    periods = fixture.get('periods', [])
    for p in periods:
        pe = p.get('events', [])
        pso_pe = [e for e in pe if 'pen_shootout' in str(e.get('detail', ''))]
        if pso_pe:
            print(f'Found in periods.sort_order={p.get("sort_order")}')
            print(json.dumps(pso_pe[0], indent=2, ensure_ascii=False))

# Also check player stats for any shootout-related type_ids
print('\n--- Checking player stats for shootout data ---')
lineups = fixture.get('lineups', [])
for lu in lineups[:1]:
    print(f'Lineup keys: {list(lu.keys())[:15]}')
