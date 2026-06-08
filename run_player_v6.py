"""
Quick runner for player contribution v6 analysis.
Usage:
  python run_player_v6.py
  python run_player_v6.py 19683241
"""

import importlib.util
import json
import os
import sys
import yaml

# Load player_insights_v6 directly (avoid visualizer/__init__.py matplotlib import)
spec = importlib.util.spec_from_file_location(
    "src.engine.player_insights_v6", "src/engine/player_insights_v6.py"
)
pi6 = importlib.util.module_from_spec(spec)
sys.modules["src.engine.player_insights_v6"] = pi6
spec.loader.exec_module(pi6)
run_v6 = pi6.run_v6

# Load excel exporter
spec3 = importlib.util.spec_from_file_location(
    "src.reporter.player_excel", "src/reporter/player_excel.py"
)
pex = importlib.util.module_from_spec(spec3)
sys.modules["src.reporter.player_excel"] = pex
spec3.loader.exec_module(pex)
export_match_excel = pex.export_match_excel
export_cross_match_role_summary = pex.export_cross_match_role_summary

# Load LLM client
from src.generator.llm_client import LLMClient


def _save_insights_json(insights, path):
    """Serialize PlayerInsightV6 list to JSON for downstream reuse."""
    data = []
    for pi in insights:
        contribs = {}
        for k, c in pi.contributions.items():
            raw_metrics_serializable = {}
            for mk, mv in c.raw_metrics.items():
                if isinstance(mv, dict):
                    raw_metrics_serializable[mk] = {kk: vv for kk, vv in mv.items()}
                else:
                    raw_metrics_serializable[mk] = {"value": mv}
            contribs[k] = {
                "zscore": c.zscore, "rank": c.rank, "percentile": c.percentile,
                "label": c.label, "raw_metrics": raw_metrics_serializable,
            }
        role = None
        if pi.role:
            role = {"name": pi.role.name, "confidence": pi.role.confidence,
                    "narrative": pi.role.narrative}
        eb = pi.event_bonus
        data.append({
            "name": pi.name, "player_id": pi.player_id, "number": pi.number,
            "pos": pi.pos, "team": pi.team, "team_name": pi.team_name,
            "minutes": pi.minutes, "is_substitute": pi.is_substitute,
            "contributions": contribs, "role": role, "llm_summary": pi.llm_summary,
            "events": eb.labels() if eb else [],
            "c6_label": eb.c6_label() if eb else "",
            "c6_score": eb.compute_score() if eb else 0,
        })
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    match_ids = [19683241, 19683240, 19683238]

    if len(sys.argv) > 1:
        match_ids = [int(a) for a in sys.argv[1:] if a.isdigit()]

    # Load config for LLM
    config = yaml.safe_load(open("config.yaml", encoding="utf-8"))
    llm_client = None
    try:
        llm_client = LLMClient(config["llm"])
        print(f"LLM client ready: model={config['llm']['model']}")
    except Exception as e:
        print(f"[WARN] LLM not available: {e}. Falling back to cosine-similarity role inference.")

    all_results = {}
    os.makedirs("data/computed", exist_ok=True)

    for mid in match_ids:
        path = f"data/raw/{mid}/raw_data.json"
        try:
            raw = json.load(open(path, "r", encoding="utf-8"))
        except FileNotFoundError:
            print(f"[SKIP] No data for match {mid}")
            continue

        home_name = raw["home_team"]["name"]
        away_name = raw["away_team"]["name"]
        score_h = raw["score"]["home"]
        score_a = raw["score"]["away"]
        match_name = f"{home_name} vs {away_name}"
        score_str = f"{score_h}:{score_a}"

        print(f"Analyzing {match_name} ({mid})...")
        insights = run_v6(raw, llm_client=llm_client)
        all_results[str(mid)] = insights

        # Export JSON first (independent of Excel)
        json_path = f"data/computed/{mid}_players_v6.json"
        _save_insights_json(insights, json_path)
        print(f"  -> JSON saved to {json_path}")

        # Export Excel (may fail if file is locked by Excel app)
        xlsx_path = f"data/computed/{mid}_players_v6.xlsx"
        try:
            export_match_excel(insights, str(mid), match_name, score_str, xlsx_path)
            print(f"  -> Excel saved to {xlsx_path}")
        except PermissionError as pe:
            print(f"  [WARN] Excel skipped: file is locked ({xlsx_path}). Close Excel and re-run.")
        except Exception as exc:
            print(f"  [WARN] Excel export failed: {exc}")

        # Quick summary
        roles = set(pi.role.name for pi in insights if pi.role)
        llm_count = sum(1 for pi in insights if pi.llm_summary)
        print(f"  Players: {len(insights)} | LLM analyzed: {llm_count} | Roles: {len(roles)}")
        print()

    # Cross-match Excel
    if len(all_results) >= 2:
        cross_path = "data/computed/cross_match_roles_v6.xlsx"
        try:
            export_cross_match_role_summary(all_results, cross_path)
            print(f"Cross-match role summary -> {cross_path}")
        except PermissionError:
            print(f"[WARN] Cross-match Excel skipped: file is locked ({cross_path})")
        except Exception as exc:
            print(f"[WARN] Cross-match Excel failed: {exc}")

    print("Done!")


if __name__ == "__main__":
    main()
