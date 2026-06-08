"""
Generate player contribution cards (PNG) from v6 JSON data via Playwright.

Reads from data/computed/{match_id}_players_v6.json (output of run_player_v6.py).

Usage:
  python generate_cards_v6.py 19683241                          # all players
  python generate_cards_v6.py 19683241 --player "Declan Rice"    # specific player
  python generate_cards_v6.py 19683241 --key-only                # key players only
"""

import argparse, json, os, sys, base64

import requests

THIS_DIR = os.path.dirname(os.path.abspath(__file__))


# ═══════════════════════════════════════════════════════════════
# Image helpers (base64 data URI)
# ═══════════════════════════════════════════════════════════════

def _img_to_data_uri(url: str) -> str:
    if not url:
        return ""
    try:
        session = requests.Session()
        session.trust_env = False
        resp = session.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        resp.raise_for_status()
        ct = resp.headers.get("Content-Type", "image/png")
        b64 = base64.b64encode(resp.content).decode("ascii")
        return f"data:{ct};base64,{b64}"
    except Exception:
        return ""


# ═══════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════

# Dim names without "贡献" suffix
DIM_SHORT = {"C1": "进攻", "C2": "推进", "C3": "控制", "C4": "防守", "C5": "对抗"}

# Subtitles from design doc §2.0
DIM_SUBTITLES = {
    "C1": "创造机会，转化进球",
    "C2": "构建攻势，推进阵地",
    "C3": "掌控节奏，寻找机会",
    "C4": "抢断拦截，阻止得分",
    "C5": "积极拼抢，拿下球权",
}

# Full Chinese metric names (for card display)
METRIC_FULL_NAMES = {
    # C1
    "goals": "进球", "assists": "助攻", "xg": "xG(预期进球)",
    "penalties_scored": "点球进球", "shots_total": "射门", "shots_on": "射正",
    "xgot": "xGOT(射正预期进球)", "shooting_performance": "射门表现",
    "hit_woodwork": "中框", "big_chances_created": "创造绝佳机会",
    "chances_created": "创造机会", "passes_key": "关键传球",
    "shots_off": "射偏", "shots_blocked": "被封堵射门",
    "big_chances_missed": "错失绝佳机会",
    # C2
    "passes_final_third": "进攻三区传球", "dribbles_success": "成功过人",
    "dribbles_attempts": "尝试过人", "crosses": "传中",
    "crosses_accurate": "精准传中", "crosses_accuracy": "传中成功率",
    "long_balls": "长传", "long_balls_won": "成功长传",
    "long_balls_won_pct": "长传成功率", "penalties_won": "制造点球",
    "fouls_drawn": "被犯规", "offsides": "越位",
    # C3
    "passes_total": "总传球", "passes_accurate": "准确传球",
    "passes_accuracy": "传球成功率", "touches": "触球",
    "back_passes": "回传", "possession_lost": "丢失球权",
    "dispossessed": "被夺球权", "minutes_played": "出场时间",
    # C4
    "tackles_total": "抢断", "tackles_won": "抢断成功",
    "tackles_interceptions": "拦截", "tackles_won_pct": "抢断成功率",
    "clearances": "解围", "blocked_shots": "封堵射门",
    "dribbled_past": "被过人", "penalties_committed": "送点",
    "error_lead_to_goal": "失误导致丢球", "error_lead_to_shot": "失误导致射门",
    "ball_recoveries": "球权回收",
    # C5
    "duels_total": "对抗总数", "duels_won": "赢得对抗",
    "duels_lost": "对抗失败", "duels_won_pct": "对抗成功率",
    "aerials": "空中对抗", "aerials_won": "赢得空中",
    "aerials_lost": "空中失败", "aerials_won_pct": "空中成功率",
    "fouls_committed": "犯规", "fouls_drawn": "被犯规",
    "yellowcards": "黄牌", "redcards": "红牌",
    # C7 Goalkeeper
    "saves": "扑救",
    "saves_inside_box": "禁区扑救",
    "goalkeeper_goals_conceded": "失球",
    "good_high_claim": "摘高球",
    "punches": "击球",
    "error_lead_to_goal": "致命失误",
}

# Metrics that are ratios (percentages / small decimals)
_RATIO_METRICS = {
    "passes_accuracy", "crosses_accuracy", "long_balls_won_pct",
    "tackles_won_pct", "duels_won_pct", "aerials_won_pct",
}

def _fmt_val(v, mname=""):
    if v is None:
        return "0"
    try:
        fv = float(v)
    except (ValueError, TypeError):
        return str(v)
    if mname in _RATIO_METRICS:
        return f"{fv:.1f}%" if fv >= 1 else f"{fv:.3f}"
    if fv == int(fv):
        return str(int(fv))
    return f"{fv:.1f}"


# ═══════════════════════════════════════════════════════════════
# Card style
# ═══════════════════════════════════════════════════════════════

STYLE = {
    "bg": "#0d1117",
    "card_bg": "#161b22",
    "primary": "#58a6ff",
    "accent": "#79c0ff",
    "text": "#c9d1d9",
    "dim": "#8b949e",
    "tag_bg": "#1f6feb",
    "highlight_bg": "#3d2900",
    "highlight_text": "#d2991d",
    "border": "#30363d",
    "divider": "#21262d",
    "white": "#f0f6fc",
}

DIM_COLORS = {
    "C1": "#f78166", "C2": "#58a6ff", "C3": "#3fb950",
    "C4": "#bc8cff", "C5": "#d2991d",
}

POS_EMOJI = {"G": "GK", "D": "DF", "M": "MF", "F": "FW"}


# ═══════════════════════════════════════════════════════════════
# HTML builder
# ═══════════════════════════════════════════════════════════════

def build_card_html(
    player_name: str, jersey: str, pos: str, team_name: str,
    minutes: int, photo_data: str, logo_data: str,
    llm_summary: str, is_key: bool,
    dim_cards: list[dict],
    events: list[str],
) -> str:
    s = STYLE

    ph = f'<img src="{photo_data}" alt="" />' if photo_data else ""
    lo = f'<img src="{logo_data}" alt="" />' if logo_data else ""

    # Events row
    ev_html = ""
    if events and events != ["-"]:
        ev_tags = "".join(f'<span class="evt">{ev}</span>' for ev in events)
        ev_html = f'<div class="ev-row">{ev_tags}</div>'

    # LLM summary
    sum_text = llm_summary if (llm_summary and len(llm_summary) > 5) else "暂无分析"

    # Key badge
    key_badge = '<span class="key-badge">关键球员</span>' if is_key else ""

    # Build dim cards
    cards_html = ""
    for dc in dim_cards:
        dim_key = dc["dim_key"]
        color = DIM_COLORS.get(dim_key, "#58a6ff")
        dim_name = dc["dim_name"]
        subtitle = dc.get("subtitle", "")

        # Header: dim name + subtitle, no scores/rank
        header = (
            f'<div class="dc-hd" style="background:{color}15;border-bottom:1px solid {color}33">'
            f'<span class="dc-tag" style="color:{color}">{dim_name}</span>'
        )
        if subtitle:
            header += f'<span class="dc-sub">{subtitle}</span>'
        header += "</div>"

        # Metrics table
        max_rows = 6
        has_rankings = any(m.get("tr") != "" or m.get("mr") != "" for m in dc["metrics"])
        if has_rankings:
            rows = ""
            for m in dc["metrics"][:max_rows]:
                hl_class = " hl" if m.get("hl") else ""
                rows += (
                    f'<tr class="{hl_class}">'
                    f'<td class="mn">{m["name"]}</td>'
                    f'<td class="mv">{_fmt_val(m["raw"], m.get("key",""))}</td>'
                    f'<td class="mr">{m.get("tr","-")}</td>'
                    f'<td class="mo">{m.get("mr","-")}</td>'
                    f'</tr>'
                )
            cards_html += (
                f'<div class="dc">'
                f'{header}'
                f'<table class="mt">'
                f'<thead><tr><th>指标</th><th>数值</th><th>队排</th><th>场排</th></tr></thead>'
                f'<tbody>{rows}</tbody>'
                f'</table>'
                f'</div>'
            )
        else:
            # GK / no ranking columns
            rows = ""
            for m in dc["metrics"][:max_rows]:
                rows += (
                    f'<tr>'
                    f'<td class="mn">{m["name"]}</td>'
                    f'<td class="mv">{_fmt_val(m["raw"], m.get("key",""))}</td>'
                    f'</tr>'
                )
            cards_html += (
                f'<div class="dc">'
                f'{header}'
                f'<table class="mt">'
                f'<thead><tr><th>指标</th><th>数值</th></tr></thead>'
                f'<tbody>{rows}</tbody>'
                f'</table>'
                f'</div>'
            )

    pos_label = POS_EMOJI.get(pos, pos)

    html = f"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="UTF-8"><style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:780px;font-family:"Microsoft YaHei","PingFang SC",sans-serif;background:{s["bg"]};color:{s["text"]};-webkit-font-smoothing:antialiased}}
.card{{padding:28px 24px 20px}}
/* Header */
.hd{{display:flex;align-items:center;gap:16px;margin-bottom:18px}}
.pw{{width:78px;height:78px;border-radius:50%;overflow:hidden;flex-shrink:0;border:3px solid {s["primary"]};box-shadow:0 0 20px {s["primary"]}22}}
.pw img{{width:100%;height:100%;object-fit:cover}}
.hi{{flex:1;min-width:0}}
.pn{{font-size:24px;font-weight:800;color:{s["white"]};letter-spacing:.4px}}
.pm{{display:flex;gap:8px;margin-top:6px;font-size:14px;align-items:center}}
.pm .chip{{background:{s["card_bg"]};padding:3px 10px;border-radius:4px;border:1px solid {s["border"]};color:{s["dim"]};font-weight:600}}
.key-badge{{background:{s["tag_bg"]};color:#fff;font-size:12px;padding:3px 9px;border-radius:3px;font-weight:700;margin-left:4px}}
/* Summary */
.su{{font-size:14px;color:{s["dim"]};margin-top:7px;line-height:1.55;font-weight:700;max-width:95%}}
/* Events */
.ev-row{{display:flex;gap:7px;margin-top:6px}}
.evt{{background:{s["primary"]}18;color:{s["accent"]};font-size:12px;padding:3px 9px;border-radius:3px;border:1px solid {s["primary"]}33;font-weight:600}}
/* Divider */
.dv{{height:1px;background:linear-gradient(90deg,{s["primary"]}44,{s["accent"]}22,transparent);margin:16px 0;border:none}}
/* Grid */
.grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}}
/* Dim card */
.dc{{background:{s["card_bg"]};border-radius:8px;overflow:hidden;border:1px solid {s["divider"]}}}
.dc-hd{{display:flex;align-items:center;padding:9px 14px;gap:8px;flex-wrap:wrap}}
.dc-tag{{font-size:15px;font-weight:800;letter-spacing:.3px}}
.dc-sub{{font-size:12px;color:{s["dim"]};font-weight:700;margin-left:2px}}
.mt{{width:100%;border-collapse:collapse}}
.mt th{{font-size:11px;color:{s["dim"]};text-align:left;padding:4px 10px 4px 14px;font-weight:600;border-bottom:1px solid {s["divider"]};background:{s["bg"]}55}}
.mt th:nth-child(2){{text-align:center;width:56px}}
.mt th:nth-child(3),.mt th:nth-child(4){{text-align:center;width:34px}}
.mt td{{font-size:12px;padding:5px 10px 5px 14px;border-top:1px solid {s["divider"]}}}
.mn{{color:#b0b8c4;font-weight:600}}
.mv{{color:{s["white"]};text-align:center;font-weight:700}}
.mr{{text-align:center;color:{s["dim"]};font-size:12px;font-weight:600}}
.mo{{text-align:center;color:{s["accent"]};font-weight:700;font-size:12px}}
/* Highlight rows */
tr.hl{{background:{s["highlight_bg"]}44}}
tr.hl td.mn{{color:{s["highlight_text"]}}}
tr.hl td.mv{{color:{s["highlight_text"]};font-weight:800}}
tr.hl td.mr,tr.hl td.mo{{color:{s["highlight_text"]};font-weight:700}}
/* Footer */
.ft{{display:flex;align-items:center;justify-content:space-between;margin-top:14px;padding-top:12px;border-top:1px solid {s["divider"]}}}
.fl{{display:flex;align-items:center;gap:8px;font-size:13px;color:{s["dim"]}}}
.fl img{{width:22px;height:22px;object-fit:contain}}
.fn{{font-size:11px;color:#30363d}}
</style></head><body><div class="card">

<div class="hd">
  <div class="pw">{ph}</div>
  <div class="hi">
    <div class="pn">{player_name} {key_badge}</div>
    <div class="pm">
      <span class="chip">#{jersey}</span>
      <span class="chip">{pos_label} · {minutes}&prime;</span>
    </div>
    {ev_html}
    <div class="su">{sum_text}</div>
  </div>
</div>

<hr class="dv">

<div class="grid">{cards_html}</div>

<div class="ft">
  <div class="fl">{lo}{team_name}</div>
  <div class="fn">队排 = 队内排名 · 场排 = 全场排名 · 黄色 = 队排&le;5 或 场排&le;5</div>
</div>

</div></body></html>"""

    return html


# ═══════════════════════════════════════════════════════════════
# Data builder from JSON
# ═══════════════════════════════════════════════════════════════

def build_cards_from_json(json_path: str, raw_path: str) -> list[dict]:
    """Read v6 JSON + raw data and build card data dicts."""
    data = json.load(open(json_path, "r", encoding="utf-8"))
    raw = json.load(open(raw_path, "r", encoding="utf-8"))

    # Team logos from raw data
    home_name = raw["home_team"]["name"]
    away_name = raw["away_team"]["name"]
    home_logo = raw["home_team"].get("logo_url", "")
    away_logo = raw["away_team"].get("logo_url", "")

    # Player photo index
    all_raw_players = raw.get("home_players", []) + raw.get("away_players", [])
    photo_map = {}
    for rp in all_raw_players:
        photo_map[rp["name"]] = rp.get("photo_url", "")

    results = []
    for pi in data:
        if pi["minutes"] < 15:
            continue

        name = pi["name"]
        team_name = pi["team_name"]
        logo_url = home_logo if team_name == home_name else away_logo
        photo_url = photo_map.get(name, "")

        # Determine if key player (any C1-C5 rank <= 5 and zscore > 0)
        is_key = False
        for dim_key in ["C1", "C2", "C3", "C4", "C5"]:
            c = pi["contributions"].get(dim_key)
            if c and c.get("rank", 99) <= 5 and c.get("zscore", 0) > 0:
                is_key = True
                break

        # Build dim cards
        dim_cards = []
        if pi["pos"] == "G":
            # Goalkeeper: use C7 metrics instead of C1-C5
            c7 = pi["contributions"].get("C7", {})
            if c7 and c7.get("zscore", -99) > -99:
                gk_raw = c7.get("raw_metrics", {})
                # Ordered GK metric keys (user-specified, no possession_lost)
                gk_order = ["saves", "saves_inside_box", "goalkeeper_goals_conceded",
                           "good_high_claim", "punches", "passes_accuracy",
                           "long_balls_won", "long_balls_won_pct",
                           "error_lead_to_goal"]
                gk_metrics = []
                for mkey in gk_order:
                    if mkey not in gk_raw:
                        continue
                    mv = gk_raw[mkey]
                    raw_val = mv if isinstance(mv, (int, float)) else mv.get("value", 0)
                    disp_name = METRIC_FULL_NAMES.get(mkey, mkey)
                    gk_metrics.append({
                        "name": disp_name, "key": mkey,
                        "raw": raw_val if raw_val is not None else 0,
                        "tr": "", "mr": "", "hl": False,
                    })
                dim_cards.append({
                    "dim_key": "C7", "dim_name": "门将表现",
                    "subtitle": c7.get("label", ""),
                    "metrics": gk_metrics,
                })
        else:
            for dim_key in ["C1", "C2", "C3", "C4", "C5"]:
                c = pi["contributions"].get(dim_key)
                if c is None:
                    continue
                if c.get("zscore", 0) <= -99:
                    continue

                # For key players, only show positive dims (rank <= 5, zscore > 0)
                if is_key and (c.get("zscore", 0) <= 0 or c.get("rank", 99) > 5):
                    continue

                dim_name = DIM_SHORT.get(dim_key, dim_key)
                subtitle = DIM_SUBTITLES.get(dim_key, "")

                raw_metrics = c.get("raw_metrics", {})
                # Sort by abs(contrib)
                sorted_metrics = sorted(
                    raw_metrics.items(),
                    key=lambda x: -abs(x[1].get("contrib", 0))
                )

                metrics = []
                for mkey, mdata in sorted_metrics:
                    raw_val = mdata.get("raw", 0)
                    tr = mdata.get("_team_rank", "")
                    mr = mdata.get("_match_rank", "")
                    hl = (isinstance(tr, int) and tr <= 5) or (isinstance(mr, int) and mr <= 5)
                    disp_name = METRIC_FULL_NAMES.get(mkey, mkey)
                    metrics.append({
                        "name": disp_name, "key": mkey, "raw": raw_val,
                        "tr": tr, "mr": mr, "hl": hl,
                    })

                dim_cards.append({
                    "dim_key": dim_key, "dim_name": dim_name,
                    "subtitle": subtitle,
                    "metrics": metrics,
                })

        events = pi.get("events", [])

        results.append({
            "name": name, "jersey": str(pi.get("number", "")),
            "pos": pi["pos"], "team_name": team_name,
            "minutes": pi["minutes"],
            "photo_url": photo_url, "logo_url": logo_url,
            "llm_summary": pi.get("llm_summary", ""),
            "is_key": is_key, "dim_cards": dim_cards, "events": events,
        })

    return results


# ═══════════════════════════════════════════════════════════════
# Render via Playwright
# ═══════════════════════════════════════════════════════════════

def render_card_png(card_data: dict, output_path: str):
    from playwright.sync_api import sync_playwright

    photo_data = _img_to_data_uri(card_data["photo_url"])
    logo_data = _img_to_data_uri(card_data["logo_url"])

    html = build_card_html(
        player_name=card_data["name"], jersey=card_data["jersey"],
        pos=card_data["pos"], team_name=card_data["team_name"],
        minutes=card_data["minutes"], photo_data=photo_data,
        logo_data=logo_data, llm_summary=card_data["llm_summary"],
        is_key=card_data["is_key"], dim_cards=card_data["dim_cards"],
        events=card_data["events"],
    )

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 800, "height": 1000})
        page.set_content(html, wait_until="commit", timeout=30000)
        h = page.evaluate("document.body.scrollHeight")
        page.set_viewport_size({"width": 800, "height": h + 10})
        page.screenshot(path=output_path, full_page=True)
        browser.close()

    print(f"  -> {output_path}")


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Generate v6 player cards as PNG")
    parser.add_argument("match_id", type=int, help="Match ID")
    parser.add_argument("--player", type=str, default=None, help="Specific player name")
    parser.add_argument("--key-only", action="store_true", help="Only key players")
    args = parser.parse_args()

    match_id = args.match_id

    json_path = f"data/computed/{match_id}_players_v6.json"
    raw_path = f"data/raw/{match_id}/raw_data.json"

    if not os.path.exists(json_path):
        print(f"[ERROR] v6 JSON not found: {json_path}")
        print(f"  Run `python run_player_v6.py {match_id}` first to generate it.")
        sys.exit(1)
    if not os.path.exists(raw_path):
        print(f"[ERROR] Raw data not found: {raw_path}")
        sys.exit(1)

    cards = build_cards_from_json(json_path, raw_path)

    # Filter
    if args.player:
        cards = [c for c in cards if c["name"] == args.player]
        if not cards:
            print(f"[ERROR] Player '{args.player}' not found")
            sys.exit(1)
    elif args.key_only:
        cards = [c for c in cards if c["is_key"]]

    raw = json.load(open(raw_path, "r", encoding="utf-8"))
    home = raw["home_team"]["name"].replace(" ", "_")
    away = raw["away_team"]["name"].replace(" ", "_")
    out_dir = f"output/{match_id}_{home}_vs_{away}/cards"
    os.makedirs(out_dir, exist_ok=True)

    print(f"Reading from: {json_path}")
    print(f"Generating {len(cards)} card(s) to {out_dir}/ ...")
    for cd in cards:
        filename = cd["name"].replace(" ", "_").replace("'", "").replace("(", "").replace(")", "")
        out_path = os.path.join(out_dir, f"{filename}.png")
        render_card_png(cd, out_path)

    print("Done!")


if __name__ == "__main__":
    main()
