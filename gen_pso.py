"""Generate 19683241 Excel with pen_shootout support."""
import json, sys, os, importlib.util
sys.path.insert(0, '.')

spec = importlib.util.spec_from_file_location('src.engine.player_insights_v6', 'src/engine/player_insights_v6.py')
pi6 = importlib.util.module_from_spec(spec)
sys.modules['src.engine.player_insights_v6'] = pi6
spec.loader.exec_module(pi6)

spec2 = importlib.util.spec_from_file_location('src.reporter.player_excel', 'src/reporter/player_excel.py')
pex = importlib.util.module_from_spec(spec2)
sys.modules['src.reporter.player_excel'] = pex
spec2.loader.exec_module(pex)

raw = json.load(open('data/raw/19683241/raw_data.json', 'r', encoding='utf-8'))
insights = pi6.run_v6(raw)

out = 'data/computed/19683241_v6_ps.xlsx'
pex.export_match_excel(insights, '19683241', 'Paris Saint Germain vs Arsenal', '1:1', out)
print(f'DONE -> {out}')

# Verify pen_shootout data
print('\n--- PSO Events Detected ---')
for pi in insights:
    eb = pi.event_bonus
    if eb and (eb.pen_shootout_goal or eb.pen_shootout_miss):
        events = []
        if eb.pen_shootout_goal: events.append('PK战进球')
        if eb.pen_shootout_miss: events.append('PK战射失')
        print(f'{pi.name}: {events} C6={eb.compute_score():.1f} label={eb.c6_label()}')
