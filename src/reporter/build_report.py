from __future__ import annotations

from pathlib import Path

from src.collector.api_client import PlayerStats, RawMatchData
from src.engine.metrics import ComputedData, _stat
from src.player_names import get_cn_name


def _sum_player_tackles(players: list[PlayerStats]) -> int:
    return sum(p.tackles_total for p in players)


def _player_photo_html(photo_url: str, size: int = 40) -> str:
    if not photo_url:
        return ""
    return f'<img src="{photo_url}" width="{size}" height="{size}" style="border-radius:50%;vertical-align:middle;margin-right:6px;" />'


def _team_logo_html(logo_url: str, size: int = 24) -> str:
    if not logo_url:
        return ""
    return f'<img src="{logo_url}" width="{size}" height="{size}" style="vertical-align:middle;margin-right:4px;" />'


def build_report(
    raw: RawMatchData,
    computed: ComputedData,
    ai_texts: dict,
    image_paths: dict,
    output_dir: str,
) -> str:
    hs = raw.home_stats
    aws = raw.away_stats

    home_logo = _team_logo_html(raw.home_team.logo_url)
    away_logo = _team_logo_html(raw.away_team.logo_url)

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

    # 从球员数据汇总抢断（API-Sports 免费版不返回球队级 Tackles）
    home_tackles = _sum_player_tackles(raw.home_players)
    away_tackles = _sum_player_tackles(raw.away_players)
    tackles_str = f"| 抢断 | {home_tackles} | {away_tackles} |\n"

    home_rec = int(float(_stat(hs, "Ball Recoveries", "Ball Recoveries", default=0)))
    away_rec = int(float(_stat(aws, "Ball Recoveries", "Ball Recoveries", default=0)))
    if home_rec == 0 and away_rec == 0:
        rec_str = "| 球权回收 | 无数据 | 无数据 |\n"
    else:
        rec_str = f"| 球权回收 | {home_rec} | {away_rec} |\n"

    home_crosses = int(float(_stat(hs, "Crosses", "Crosses", default=0)))
    away_crosses = int(float(_stat(aws, "Crosses", "Crosses", default=0)))
    home_offsides = int(float(_stat(hs, "Offsides", "Offsides", default=0)))
    away_offsides = int(float(_stat(aws, "Offsides", "Offsides", default=0)))

    # 标题行：队徽 + 队名
    md = f"# {home_logo} {raw.home_team.name} {raw.score.home}-{raw.score.away} {raw.away_team.name} {away_logo}\n\n"
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
    md += tackles_str
    md += rec_str
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

    # 账面 MVP
    mvp = computed.home_mvp
    mvp_photo = _player_photo_html(mvp.photo_url) if mvp else ""
    mvp_cn = get_cn_name(mvp.name) if mvp else ""
    mvp_display = f"{mvp.name} ({mvp_cn})" if mvp and mvp_cn != mvp.name else (mvp.name if mvp else "无")
    md += f"### 账面 MVP：{mvp_photo} {mvp_display}\n\n"
    if ai_texts.get("mvp"):
        md += f"{ai_texts['mvp']}\n\n"
    md += f"![射门分布]({image_paths.get('shots', 'images/01_shots.png')})\n\n"

    # 隐性 MVP
    hidden = computed.home_hidden_mvp
    hidden_photo = _player_photo_html(hidden.photo_url) if hidden else ""
    hidden_cn = get_cn_name(hidden.name) if hidden else ""
    hidden_display = f"{hidden.name} ({hidden_cn})" if hidden and hidden_cn != hidden.name else (hidden.name if hidden else "无")
    md += f"### 隐性 MVP：{hidden_photo} {hidden_display}\n\n"
    if ai_texts.get("hidden_mvp"):
        md += f"{ai_texts['hidden_mvp']}\n\n"
    md += f"![隐性MVP雷达]({image_paths.get('radar_hidden', 'images/04b_radar_hidden.png')})\n\n"

    # 黑洞球员
    bh = computed.home_black_hole
    bh_photo = _player_photo_html(bh.photo_url) if bh else ""
    bh_cn = get_cn_name(bh.name) if bh else ""
    bh_display = f"{bh.name} ({bh_cn})" if bh and bh_cn != bh.name else (bh.name if bh else "无")
    md += f"### 黑洞球员：{bh_photo} {bh_display}\n\n"
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
body {{ font-family: 'Microsoft YaHei', 'PingFang SC', sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; line-height: 1.8; }}
img {{ max-width: 100%; }}
table {{ border-collapse: collapse; width: 100%; }}
td, th {{ border: 1px solid #ddd; padding: 8px; text-align: center; }}
th {{ background: #f5f5f5; }}
blockquote {{ border-left: 4px solid #2ecc71; padding-left: 16px; color: #555; }}
h1 img, h3 img {{ border-radius: 50%; vertical-align: middle; }}
</style></head><body>{html_content}</body></html>"""
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_wrapper)
    except Exception:
        pass

    return report_path
