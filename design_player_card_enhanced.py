# -*- coding: utf-8 -*-
"""生成增强版球员贡献卡片设计预览 (Vitinha / 19683241)"""
import json, os, argparse


def build_preview(match_id, player_name):
    # ── load v6 data ──
    v6_path = f"data/computed/{match_id}_players_v6.json"
    raw_path = f"data/raw/{match_id}/raw_data.json"
    v6_data = json.load(open(v6_path, "r", encoding="utf-8"))
    raw = json.load(open(raw_path, "r", encoding="utf-8"))

    p = next((x for x in v6_data if x["name"] == player_name), None)
    if not p:
        print(f"Player '{player_name}' not found")
        return

    # ── run / carry data ──
    data_dir = f"data/{match_id}/{player_name}"
    carry = json.load(open(os.path.join(data_dir, "carry_data.json"), "r", encoding="utf-8"))
    run = json.load(open(os.path.join(data_dir, "run_data.json"), "r", encoding="utf-8"))

    # Parse run distances
    def _parse_km(s):
        """'10.48 km (85%)' → 10.48"""
        return float(s.split()[0])

    run_total = sum(_parse_km(run[k]) for k in ("Walking + jogging", "Running", "High-speed running", "Sprinting"))

    # Parse carry
    carry_total_str = carry["Total carrying distance"]          # "539.2 m"
    carry_total_km = float(carry_total_str.split()[0]) / 1000.0

    # ── player photo / logo ──
    all_rp = raw.get("home_players", []) + raw.get("away_players", [])
    photo_map = {rp["name"]: rp.get("photo_url", "") for rp in all_rp}
    photo_url = photo_map.get(player_name, "")
    logo_url = raw["home_team"].get("logo_url", "")

    # ── build dim cards data ──
    DIM_SHORT = {"C1": "进攻", "C2": "推进", "C3": "控制", "C4": "防守", "C5": "对抗"}
    METRIC_NAMES = {
        "goals": "进球", "assists": "助攻", "xg": "xG", "shots_total": "射门",
        "shots_on": "射正", "chances_created": "创造机会", "passes_key": "关键传球",
        "passes_final_third": "进攻三区传球", "dribbles_attempts": "尝试过人",
        "dribbles_success": "成功过人", "long_balls": "长传", "long_balls_won": "成功长传",
        "long_balls_won_pct": "长传成功率", "penalties_won": "制造点球",
        "passes_total": "总传球", "passes_accurate": "准确传球",
        "passes_accuracy": "传球成功率", "touches": "触球",
        "tackles_total": "抢断", "tackles_interceptions": "拦截",
        "tackles_won_pct": "抢断成功率", "clearances": "解围",
        "blocked_shots": "封堵射门", "ball_recoveries": "球权回收",
        "duels_total": "对抗总数", "duels_won": "赢得对抗",
        "duels_won_pct": "对抗成功率", "aerials": "空中对抗",
        "aerials_won": "赢得空中", "aerials_won_pct": "空中成功率",
        "fouls_committed": "犯规", "fouls_drawn": "被犯规",
    }
    _RATIO = {"passes_accuracy", "crosses_accuracy", "long_balls_won_pct", "tackles_won_pct", "duels_won_pct", "aerials_won_pct"}

    def _fmt(v, key=""):
        if v is None: return "0"
        try: fv = float(v)
        except: return str(v)
        if key in _RATIO: return f"{fv:.1f}%" if fv >= 1 else f"{fv:.3f}"
        if fv == int(fv): return str(int(fv))
        return f"{fv:.1f}"

    dim_cards = []
    for dk in ["C1", "C2", "C3", "C4", "C5"]:
        c = p["contributions"].get(dk)
        if not c or c.get("zscore", -99) <= -99:
            continue
        raw_m = c.get("raw_metrics", {})
        sorted_m = sorted(raw_m.items(), key=lambda x: -abs(x[1].get("contrib", 0)))
        metrics = []
        for mkey, md in sorted_m[:6]:
            raw_val = md.get("raw", 0)
            tr = md.get("_team_rank", "-")
            mr = md.get("_match_rank", "-")
            hl = (isinstance(tr, int) and tr <= 5) or (isinstance(mr, int) and mr <= 5)
            metrics.append({"name": METRIC_NAMES.get(mkey, mkey), "raw": raw_val, "key": mkey, "tr": tr, "mr": mr, "hl": hl})
        dim_cards.append({"key": dk, "name": DIM_SHORT[dk], "metrics": metrics})

    is_key = any(c.get("rank", 99) <= 5 and c.get("zscore", 0) > 0 for c in p["contributions"].values())

    # ════════════════════════════════
    # BUILD HTML
    # ════════════════════════════════
    dim_colors = {"C1": "#f78166", "C2": "#58a6ff", "C3": "#3fb950", "C4": "#bc8cff", "C5": "#d2991d"}

    cards_html = ""
    for dc in dim_cards:
        color = dim_colors.get(dc["key"], "#58a6ff")
        rows = ""
        for m in dc["metrics"]:
            hl_class = " hl" if m.get("hl") else ""
            rows += (
                f'<tr class="{hl_class}">'
                f'<td class="mn">{m["name"]}</td>'
                f'<td class="mv">{_fmt(m["raw"], m.get("key",""))}</td>'
                f'<td class="mr">{m.get("tr","-")}</td>'
                f'<td class="mo">{m.get("mr","-")}</td>'
                f'</tr>'
            )
        cards_html += f"""
    <div class="dc">
      <div class="dc-hd" style="border-bottom:1px solid {color}33">
        <span class="dc-tag" style="color:{color}">{dc["name"]}贡献</span>
        <span class="dc-sub">队排第{p['contributions'].get(dc['key'],{}).get('rank','?')}名</span>
      </div>
      <table class="mt">
        <thead><tr><th>指标</th><th>数值</th><th>队排</th><th>场排</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>"""

    key_html = '<span class="key-badge">关键球员</span>' if is_key else ""

    html = f"""<!DOCTYPE html>
<html lang="zh">
<head><meta charset="UTF-8">
<title>Vitinha — 增强版球员贡献卡片</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:"Microsoft YaHei","PingFang SC",sans-serif;background:#0a0e1a;color:#c9d1d9;display:flex;justify-content:center;padding:30px 0}}
.card{{width:960px;background:#0d1117;border-radius:12px;overflow:hidden;box-shadow:0 8px 40px rgba(0,0,0,.5)}}

/* ── SECTION ── */
.sec{{padding:20px 24px}}
.sec-hd{{display:flex;align-items:center;gap:10px;margin-bottom:14px}}
.sec-hd .ico{{font-size:18px}}
.sec-hd .tt{{font-size:15px;font-weight:800;color:#f0f6fc;letter-spacing:.5px}}
.sec-hd .sub{{font-size:11px;color:#8b949e;margin-left:8px}}

/* ── HEADER ── */
.hd{{display:flex;align-items:center;gap:18px;padding:24px 24px 16px;background:linear-gradient(180deg,#161b22 0%,#0d1117 100%);border-bottom:1px solid #21262d}}
.pw{{width:72px;height:72px;border-radius:50%;overflow:hidden;flex-shrink:0;border:3px solid #58a6ff;background:#21262d;display:flex;align-items:center;justify-content:center;font-size:28px;color:#58a6ff;font-weight:bold}}
.pw img{{width:100%;height:100%;object-fit:cover}}
.hi{{flex:1;min-width:0}}
.pn{{font-size:26px;font-weight:800;color:#f0f6fc;letter-spacing:.4px}}
.pm{{display:flex;gap:8px;margin-top:6px;font-size:13px;align-items:center;flex-wrap:wrap}}
.chip{{background:#161b22;padding:3px 10px;border-radius:4px;border:1px solid #30363d;color:#8b949e;font-weight:600}}
.key-badge{{background:#1f6feb;color:#fff;font-size:11px;padding:3px 8px;border-radius:3px;font-weight:700;margin-left:6px}}
.su{{font-size:13px;color:#8b949e;margin-top:8px;line-height:1.6;font-weight:600}}
.run-chip{{color:#3fb950 !important;border-color:#3fb95044 !important}}
.carry-chip{{color:#d2991d !important;border-color:#d2991d44 !important}}

/* ── DIM CARDS (reuse existing style) ── */
.dim-grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}}
.dc{{background:#161b22;border-radius:8px;overflow:hidden;border:1px solid #21262d}}
.dc-hd{{display:flex;align-items:center;padding:9px 14px;gap:8px;background:#161b22}}
.dc-tag{{font-size:15px;font-weight:800;letter-spacing:.3px}}
.dc-sub{{font-size:11px;color:#8b949e;font-weight:600;margin-left:4px}}
.mt{{width:100%;border-collapse:collapse}}
.mt th{{font-size:11px;color:#8b949e;text-align:left;padding:5px 10px 5px 14px;font-weight:600;border-bottom:1px solid #21262d;background:#0d111744}}
.mt th:nth-child(2){{text-align:center;width:56px}}
.mt th:nth-child(3),.mt th:nth-child(4){{text-align:center;width:36px}}
.mt td{{font-size:12px;padding:5px 10px 5px 14px;border-top:1px solid #1a1f2b}}
.mn{{color:#b0b8c4;font-weight:600}}
.mv{{color:#f0f6fc;text-align:center;font-weight:700}}
.mr{{text-align:center;color:#8b949e;font-size:12px;font-weight:600}}
.mo{{text-align:center;color:#58a6ff;font-weight:700;font-size:12px}}
tr.hl{{background:#3d290022}}
tr.hl td.mn{{color:#d2991d}}
tr.hl td.mv{{color:#d2991d;font-weight:800}}
tr.hl td.mr,tr.hl td.mo{{color:#d2991d;font-weight:700}}

/* ── FOOTER ── */
.ft{{display:flex;align-items:center;justify-content:space-between;padding:14px 24px;border-top:1px solid #21262d;background:#0d1117;font-size:11px;color:#484f58}}
</style></head>
<body>
<div class="card">

  <!-- HEADER -->
  <div class="hd">
    <div class="pw">{'<img src="' + photo_url + '" />' if photo_url else 'V'}</div>
    <div class="hi">
      <div class="pn">{player_name} {key_html}</div>
      <div class="pm">
        <span class="chip">#{p['number']}</span>
        <span class="chip">MF · {p['minutes']}&prime;</span>
        <span class="chip" style="color:#58a6ff">Paris Saint Germain</span>
        <span class="chip run-chip">跑动距离 {run_total:.1f} km</span>
        <span class="chip carry-chip">带球推进 {carry_total_km:.2f} km</span>
      </div>
      <div class="su">{p.get('llm_summary','')}</div>
    </div>
  </div>

  <!-- DIM CONTRIBUTION -->
  <div class="sec">
    <div class="sec-hd"><span class="ico">&#x1F3AF;</span><span class="tt">贡献维度</span><span class="sub">Contribution Breakdown</span></div>
    <div class="dim-grid">{cards_html}</div>
  </div>

  <!-- FOOTER -->
  <div class="ft">
    <div>Paris Saint Germain</div>
    <div>队排 = 队内排名 &nbsp; 场排 = 全场排名 &nbsp; 黄色标记 = 队排/场排 Top 5</div>
  </div>

</div>
</body></html>"""

    out_dir = f"design"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "player_card_enhanced_preview.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Preview saved: {out_path}")
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("match_id", type=int, default=19683241, nargs="?")
    parser.add_argument("--player", default="Vitinha")
    args = parser.parse_args()
    build_preview(args.match_id, args.player)
