"""Find UCL 25-26 knockout fixtures — date-range approach."""
import json, os, requests
from collections import defaultdict

TOKEN = "w6PU0YE99DrKPnOY43xonH5Bf7S279Ysvzzj6LZaAqnOKusDEIAUTbaNUzDr"
s = requests.Session()
s.trust_env = False
ap = {"api_token": TOKEN}

# UCL knockout match days (typical dates)
DATE_RANGES = [
    # Playoffs (Feb)
    ("2026-02-10", "2026-02-13"),
    ("2026-02-17", "2026-02-20"),
    # R16 (March)
    ("2026-03-03", "2026-03-06"),
    ("2026-03-10", "2026-03-13"),
    # QF (April)
    ("2026-04-07", "2026-04-10"),
    ("2026-04-14", "2026-04-17"),
    # SF (April-May)
    ("2026-04-28", "2026-05-01"),
    ("2026-05-05", "2026-05-08"),
    # Final (May-June)
    ("2026-05-30", "2026-06-02"),
]

seen_ids = set()
all_fixtures = []

for d1, d2 in DATE_RANGES:
    resp = s.get(
        f"https://api.sportmonks.com/v3/football/fixtures/between/{d1}/{d2}",
        params={**ap, "include": "participants;stage;scores;league"}
    )
    data = resp.json()
    fixtures = data.get("data", [])
    
    for fx in fixtures:
        league = fx.get("league", {})
        if league.get("id") != 2:
            continue
        # Also skip qualifiers
        stage = fx.get("stage", {})
        stage_name = stage.get("name", "")
        skip_keywords = ["qualification", "qualifying", "league stage"]
        if any(kw in stage_name.lower() for kw in skip_keywords):
            continue
        
        fid = fx["id"]
        if fid in seen_ids:
            continue
        seen_ids.add(fid)
        
        home = fx.get("participants", [{}])[0] if fx.get("participants") else {}
        away = fx.get("participants", [{}])[1] if len(fx.get("participants", [])) > 1 else {}
        scores_info = fx.get("scores", [])
        sh = scores_info[0].get("score", {}).get("goals", "?") if scores_info else "?"
        sa = scores_info[1].get("score", {}).get("goals", "?") if len(scores_info) > 1 else "?"
        
        entry = {
            "fixture_id": fid,
            "stage": stage_name,
            "stage_id": stage.get("id"),
            "home": home.get("name", "?"),
            "away": away.get("name", "?"),
            "home_id": home.get("id"),
            "away_id": away.get("id"),
            "score_home": sh,
            "score_away": sa,
            "starting_at": fx.get("starting_at"),
        }
        all_fixtures.append(entry)

os.makedirs("data", exist_ok=True)
with open("data/ucl_knockout_fixtures.json", "w", encoding="utf-8") as f:
    json.dump(all_fixtures, f, ensure_ascii=False, indent=2)

# Summary
by_stage = defaultdict(list)
for fx in all_fixtures:
    by_stage[fx["stage"]].append(fx)

order = ["Knockout Round Play-offs", "8th Finals", "Quarter-finals", "Semi-finals", "Final"]
for stage in order:
    fxs = by_stage.get(stage, [])
    if not fxs:
        continue
    print(f"\n{'='*60}")
    print(f"  {stage} ({len(fxs)} matches)")
    print(f"{'='*60}")
    for fx in sorted(fxs, key=lambda x: x.get("starting_at", "")):
        dt = fx['starting_at'][:10] if fx.get('starting_at') else '?'
        print(f"  {fx['fixture_id']:>8}  {fx['home']:>25s}  {fx['score_home']}-{fx['score_away']}  {fx['away']:<25s}  {dt}")

print(f"\n{'='*60}")
print(f"Total: {len(all_fixtures)} knockout fixtures saved to data/ucl_knockout_fixtures.json")

# Print ID list for easy copying
print(f"\nFixture IDs: {[fx['fixture_id'] for fx in all_fixtures]}")
