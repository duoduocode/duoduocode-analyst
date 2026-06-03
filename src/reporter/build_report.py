from pathlib import Path

from src.collector.api_client import RawMatchData
from src.engine.metrics import ComputedData, _stat


def build_report(
    raw: RawMatchData,
    computed: ComputedData,
    ai_texts: dict,
    image_paths: dict,
    output_dir: str,
) -> str:
    hs = raw.home_stats
    aws = raw.away_stats

    home_poss = int(float(_stat(hs, "Ball Possession", "Ball Possession", default=50)))
    away_poss = int(float(_stat(aws, "Ball Possession", "Ball Possession", default=50)))
    home_xg = float(_stat(hs, "Expected Goals", "expected_goals", default=0))
    away_xg = float(_stat(aws, "Expected Goals", "expected_goals", default=0))
    home_shots = int(float(_stat(hs, "Total Shots", "Total Shots", default=0)))
    away_shots = int(float(_stat(aws, "Total Shots", "Total Shots", default=0)))
    home_so = int(float(_stat(hs, "Shots on Goal", "Shots on Goal", default=0)))
    away_so = int(float(_stat(aws, "Shots on Goal", "Shots on Goal", default=0)))
    home_bc = int(float(_stat(hs, "Big Chances Created", "Big Chances Created", default=0)))
    away_bc = int(float(_stat(aws, "Big Chances Created", "Big Chances Created", default=0)))
    home_shots_ib = int(float(_stat(hs, "Shots insidebox", "Shots insidebox", default=0)))
    away_shots_ib = int(float(_stat(aws, "Shots insidebox", "Shots insidebox", default=0)))
    home_pass_acc = int(float(_stat(hs, "Passes %", "Passes %", default=75)))
    away_pass_acc = int(float(_stat(aws, "Passes %", "Passes %", default=75)))
    home_tackles = int(float(_stat(hs, "Tackles", "Tackles", default=0)))
    away_tackles = int(float(_stat(aws, "Tackles", "Tackles", default=0)))
    home_rec = int(float(_stat(hs, "Ball Recoveries", "Ball Recoveries", default=0)))
    away_rec = int(float(_stat(aws, "Ball Recoveries", "Ball Recoveries", default=0)))
    home_crosses = int(float(_stat(hs, "Crosses", "Crosses", default=0)))
    away_crosses = int(float(_stat(aws, "Crosses", "Crosses", default=0)))
    home_offsides = int(float(_stat(hs, "Offsides", "Offsides", default=0)))
    away_offsides = int(float(_stat(aws, "Offsides", "Offsides", default=0)))

    md = f"# {raw.home_team.name} {raw.score.home}-{raw.score.away} {raw.away_team.name}\n\n"
    md += f"> *{ai_texts.get('cover', '')}*\n\n---\n\n"

    md += "## 核心数据面板\n\n"
    md += f"|  | {raw.home_team.name} | {raw.away_team.name} |\n"
    md += "|---|---|---|\n"
    md += f"| 控球率 | {home_poss}% | {away_poss}% |\n"
    md += f"| 预期进球 (xG) | {home_xg} | {away_xg} |\n"
    md += f"| 射门 (射正) | {home_shots}({home_so}) | {away_shots}({away_so}) |\n"
    md += f"| 绝佳机会 | {home_bc} | {away_bc} |\n"
    md += f"| 禁区内射门 | {home_shots_ib} | {away_shots_ib} |\n"
    md += f"| 传球成功率 | {home_pass_acc}% | {away_pass_acc}% |\n"
    md += f"| 抢断 | {home_tackles} | {away_tackles} |\n"
    md += f"| 球权回收 | {home_rec} | {away_rec} |\n"
    md += "\n"

    md += f"| 自创指标 | {raw.home_team.name} | {raw.away_team.name} |\n"
    md += "|---|---|---|\n"
    md += f"| 控制指数 CI | {computed.home_ci} | {computed.away_ci} |\n"
    md += f"| 威胁转化率 TCR | {computed.home_tcr} | {computed.away_tcr} |\n"
    md += f"| 压迫效率 PE% | {computed.home_pe} | {computed.away_pe} |\n"
    ld = computed.ldi_result
    md += f"| 运气偏离 LDI | {ld.get('ldi', '-')} ({ld.get('interpretation', '')}) | — |\n"
    md += "\n"

    if ai_texts.get("contrast"):
        md += f"> {ai_texts['contrast']}\n\n---\n\n"

    md += "## 比赛走势\n\n"
    if ai_texts.get("momentum"):
        md += f"{ai_texts['momentum']}\n\n"
    md += f"![动量曲线]({image_paths.get('momentum', 'images/02_momentum.png')})\n\n---\n\n"

    md += "## 战术兑现度\n\n"
    if ai_texts.get("tactics"):
        md += f"{ai_texts['tactics']}\n\n"
    md += f"![传球网络 - {raw.home_team.name}]({image_paths.get('pass_home', 'images/03a_pass_home.png')})\n\n"
    md += f"![传球网络 - {raw.away_team.name}]({image_paths.get('pass_away', 'images/03b_pass_away.png')})\n\n"
    md += "---\n\n"

    md += "## 球员点评\n\n"
    md += f"### 账面 MVP：{computed.home_mvp.name if computed.home_mvp else '无'}\n\n"
    if ai_texts.get("mvp"):
        md += f"{ai_texts['mvp']}\n\n"
    md += f"![射门分布]({image_paths.get('shots', 'images/01_shots.png')})\n\n"

    md += f"### 隐性 MVP：{computed.home_hidden_mvp.name if computed.home_hidden_mvp else '无'}\n\n"
    if ai_texts.get("hidden_mvp"):
        md += f"{ai_texts['hidden_mvp']}\n\n"
    md += f"![隐性MVP雷达]({image_paths.get('radar_hidden', 'images/04b_radar_hidden.png')})\n\n"

    md += f"### 黑洞球员：{computed.home_black_hole.name if computed.home_black_hole else '无'}\n\n"
    if ai_texts.get("black_hole"):
        md += f"{ai_texts['black_hole']}\n\n"

    md += "---\n\n"

    md += "## 换人效果\n\n"
    if ai_texts.get("subs"):
        md += f"{ai_texts['subs']}\n\n"
    md += f"![换人对比]({image_paths.get('subs_home', 'images/05_subs.png')})\n\n---\n\n"

    md += "## 如果重踢 100 次\n\n"
    if ai_texts.get("replay"):
        md += f"{ai_texts['replay']}\n\n"
    md += f"![xG模拟]({image_paths.get('xg_hist', 'images/06_xg_hist.png')})\n\n---\n\n"

    md += "*报告由 AI 足球分析员自动生成 | 数据来源：API-Football*\n"

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    report_path = out_dir / "report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(md)

    html_path = out_dir / "report.html"
    try:
        import markdown
        html_content = markdown.markdown(md, extensions=["tables", "fenced_code"])
        html_wrapper = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
body {{ font-family: sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; line-height: 1.8; }}
img {{ max-width: 100%; }}
table {{ border-collapse: collapse; width: 100%; }}
td, th {{ border: 1px solid #ddd; padding: 8px; text-align: center; }}
th {{ background: #f5f5f5; }}
blockquote {{ border-left: 4px solid #2ecc71; padding-left: 16px; color: #555; }}
</style></head><body>{html_content}</body></html>"""
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_wrapper)
    except Exception:
        pass

    return report_path
