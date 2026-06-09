"""
单独生成战术分析板块报告 — fixture 19683241
用法: python run_tactical_only.py
"""

import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def load_config():
    import os
    import yaml
    with open("config.yaml", "r", encoding="utf-8") as f:
        raw = f.read()
    for key, value in os.environ.items():
        raw = raw.replace("${" + key + "}", value)
    return yaml.safe_load(raw)


def main():
    import sys
    match_ids = [19683240, 19683238, 19683235, 18452325]
    # Allow override via command line
    if len(sys.argv) > 1:
        match_ids = [int(arg) for arg in sys.argv[1:]]

    config = load_config()

    for midx, match_id in enumerate(match_ids):
        logger.info(f"{'='*40}\n处理比赛 #{match_id} ({midx+1}/{len(match_ids)})")

        # ── 1. 加载数据 ──
        logger.info(f"加载缓存数据 #{match_id}")
        from src.collector.api_client import load_cached_raw
        raw = load_cached_raw(match_id)
        home_name = raw.home_team.name
        away_name = raw.away_team.name
        score = raw.score

        # ── 计算含点球大战的总比分 ──
        pen_home = pen_away = 0
        for e in raw.events:
            if e.event_type == "Goal" and e.detail in ("pen_shootout_goal",):
                if e.team_id == raw.home_team.id:
                    pen_home += 1
                else:
                    pen_away += 1
        total_home = score.home + pen_home
        total_away = score.away + pen_away
        has_penalties = (pen_home > 0 or pen_away > 0)

        logger.info(f"  {home_name} {total_home} - {total_away} {away_name}"
                    f"{' (含点球 '+str(pen_home)+'-'+str(pen_away)+')' if has_penalties else ''}")

        # ── 2. 计算战术分析 ──
        logger.info("计算战术分析 (四层因果模型)...")
        from src.engine.tactical_insights import compute_tactical_analysis
        tactical_data = compute_tactical_analysis(raw)
        logger.info(f"  风格碰撞: {tactical_data['coaching']['style_clash']}")
        logger.info(f"  主场执行: 攻={tactical_data['home']['execution']['attack']['verdict']} "
                    f"防={tactical_data['home']['execution']['defense']['verdict']}")
        logger.info(f"  客场执行: 攻={tactical_data['away']['execution']['attack']['verdict']} "
                    f"防={tactical_data['away']['execution']['defense']['verdict']}")

        # ── 3. LLM 战术叙事 ──
        logger.info("调用 LLM 生成战术叙事...")
        from src.composer.tactical_prompt import build_tactical_system_and_user
        from src.generator.llm_client import LLMClient

        llm = LLMClient(config["llm"])
        stage_name = (raw.stage_info or {}).get("name", "")
        tactical_system, tactical_user_prompt = build_tactical_system_and_user(
            tactical_data, home_name, away_name,
            total_home, total_away,
            pen_home=pen_home, pen_away=pen_away, stage_name=stage_name,
        )
        tactical_narrative = llm.generate(tactical_system, tactical_user_prompt)
        logger.info(f"  叙事长度: {len(tactical_narrative)} 字符")

        # ── 3b. 提取「一句话总结」─
        one_liner = ""
        import re
        ol_match = re.search(r'【一句话总结】\s*\n(.*?)(?=\n【|\Z)', tactical_narrative, re.DOTALL)
        if ol_match:
            one_liner = ol_match.group(1).strip()
            # Remove from narrative so it doesn't show twice in sections
            tactical_narrative = tactical_narrative.replace(ol_match.group(0), "").strip()
        if not one_liner:
            stage_name = (raw.stage_info or {}).get("name", "")
            one_liner = f"{home_name} {total_home}-{total_away} {away_name} — {stage_name}"

        # ── 4. 图表生成 ──
        output_dir = Path("output") / f"{match_id}_{home_name.replace(' ', '_')}_vs_{away_name.replace(' ', '_')}"
        images_dir = output_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)

        logger.info("生成战术图表...")
        from src.visualizer.tactical_charts import generate_all_tactical_charts
        dpi = config.get("visual", {}).get("dpi", 150)
        tactical_image_paths_raw = generate_all_tactical_charts(
            tactical_data, home_name, away_name,
            str(images_dir), dpi=dpi,
        )
        tactical_image_paths = {}
        for k, v in tactical_image_paths_raw.items():
            tactical_image_paths[k] = str(Path(v).relative_to(output_dir)).replace("\\", "/")
        logger.info(f"  已生成: {list(tactical_image_paths.keys())}")

        # ── 4b. 全场事件时间轴 (HTML + PNG 导出) ──
        from src.visualizer.tactical_charts import generate_event_timeline_html, save_timeline_png
        timeline_html = generate_event_timeline_html(raw, home_name, away_name)
        logger.info(f"  事件时间轴 HTML: {len(timeline_html)} 字符")

        timeline_png_rel = None
        try:
            timeline_png_path = str(images_dir / "timeline.png")
            save_timeline_png(raw, home_name, away_name, timeline_png_path)
            timeline_png_rel = str(Path(timeline_png_path).relative_to(output_dir)).replace("\\", "/")
            logger.info(f"  事件时间轴 PNG: {timeline_png_rel}")
        except Exception as e:
            logger.warning(f"  事件时间轴PNG导出失败: {e}")

        # ── 4c. 阵容图（HTML 内嵌 + PNG 导出） ──
        from src.visualizer.lineup import generate_lineup_html, save_lineup_png
        try:
            lineup_html = generate_lineup_html(raw)
            logger.info(f"  阵容图 HTML: {len(lineup_html)} 字符")
        except Exception as e:
            logger.warning(f"  阵容图生成失败: {e}")
            lineup_html = ""
        try:
            lineup_png_path = str(images_dir / "lineup.png")
            save_lineup_png(raw, lineup_png_path)
            logger.info(f"  阵容图 PNG: {lineup_png_path}")
        except Exception as e:
            logger.warning(f"  阵容图PNG导出失败: {e}")

        # ── 5. 保存 JSON ──
        json_path = output_dir / "tactical_analysis.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(tactical_data, f, ensure_ascii=False, indent=2, default=str)
        logger.info(f"  JSON: {json_path}")

        # ── 6. 保存 Excel ──
        from run import _save_tactical_excel
        xlsx_path = output_dir / "tactical_analysis.xlsx"
        _save_tactical_excel(tactical_data, tactical_narrative, home_name, away_name, str(xlsx_path))
        logger.info(f"  Excel: {xlsx_path}")

        # ── 7. 组装独立 HTML 战术报告 ──
        _build_standalone_tactical_html(
            tactical_data, tactical_narrative, tactical_image_paths,
            home_name, away_name, score, str(output_dir), timeline_html,
            timeline_png_rel, one_liner, "", lineup_html, raw,
            total_home, total_away, pen_home, pen_away, has_penalties,
        )
        logger.info(f"  HTML 报告: {output_dir / 'tactical_report.html'}")

        logger.info(f"\n完成！输出目录: {output_dir}")

    logger.info(f"\n{'='*40}\n全部 {len(match_ids)} 场比赛处理完成")


def _build_standalone_tactical_html(
    tactical_data: dict,
    tactical_narrative: str,
    tactical_image_paths: dict,
    home_name: str, away_name: str,
    score,
    output_dir: str,
    timeline_html: str = "",
    timeline_png: str = "",
    one_liner: str = "",
    lineup_img: str = "",
    lineup_html: str = "",
    raw=None,
    total_home: int = 0,
    total_away: int = 0,
    pen_home: int = 0,
    pen_away: int = 0,
    has_penalties: bool = False,
):
    """组装独立战术分析 HTML 报告。"""
    import re

    def _parse_sections(text: str) -> dict:
        sections = {}
        pattern = r"【(.+?)】\s*\n(.*?)(?=\n【|\Z)"
        matches = re.findall(pattern, text, re.DOTALL)
        for title, content in matches:
            sections[title.strip()] = content.strip()
        return sections

    tac_sections = _parse_sections(tactical_narrative)

    BG = "#0f1923"
    FG = "#d0d8e0"
    GREEN = "#2ecc71"
    BLUE = "#3498db"
    RED = "#e74c3c"
    GOLD = "#f1c40f"
    CARD_BG = "#162a38"
    BORDER = "#1e3a4d"

    H = []
    H.append('<!DOCTYPE html>')
    H.append('<html lang="zh-CN"><head><meta charset="utf-8">')
    H.append('<meta name="viewport" content="width=device-width, initial-scale=1.0">')
    H.append(f'<title>战术分析 — {home_name} vs {away_name}</title>')
    H.append('<style>')
    H.append(f'*{{margin:0;padding:0;box-sizing:border-box}}')
    H.append(f'body{{font-family:"Microsoft YaHei","PingFang SC",sans-serif;background:{BG};color:{FG};line-height:1.8}}')
    H.append(f'.container{{max-width:960px;margin:0 auto;padding:20px}}')
    H.append(f'img{{max-width:100%;border-radius:6px}}')
    H.append(f'h2{{color:#e0e8f0;font-size:22px;border-bottom:2px solid {GREEN};padding-bottom:8px;margin:28px 0 14px}}')
    H.append(f'h3{{color:#c0d0e0;font-size:16px;margin:18px 0 8px}}')
    H.append(f'h4{{color:{BLUE};font-size:14px;margin:14px 0 6px}}')
    H.append(f'.scoreboard{{text-align:center;margin:20px 0 30px}}')
    H.append(f'.scoreboard .teams{{font-size:20px;color:#fff}}')
    H.append(f'.scoreboard .score{{font-size:44px;font-weight:bold;color:{GREEN};margin:0 20px}}')
    H.append(f'.insight-box{{background:{CARD_BG};border-radius:8px;padding:14px 18px;margin:12px 0;border-left:3px solid {GREEN}}}')
    H.append(f'.insight-box.gold{{border-left-color:{GOLD}}}')
    H.append(f'.insight-box h4{{color:{GREEN};margin:0 0 6px;font-size:14px}}')
    H.append(f'.insight-box p{{font-size:14px;line-height:1.9}}')
    H.append(f'.charts-grid{{display:flex;gap:12px;flex-wrap:wrap;justify-content:center;margin:16px 0}}')
    H.append(f'.charts-grid .chart-item{{flex:1;min-width:300px;background:{CARD_BG};border-radius:8px;padding:8px}}')
    H.append(f'.tactical-cards{{margin:16px 0}}')
    H.append(f'.score-card{{flex:1;min-width:260px;background:{CARD_BG};border-radius:10px;padding:14px;border-top:3px solid}}')
    H.append(f'.score-card .verdict-box{{flex:1;text-align:center;background:{BG};border-radius:6px;padding:8px}}')
    H.append(f'table{{width:100%;border-collapse:collapse;font-size:11px}}')
    H.append(f'th{{text-align:left;color:#95a5a6;font-size:10px;padding:2px 4px}}')
    H.append(f'td{{padding:3px 4px;border-bottom:1px solid {BORDER}}}')
    H.append(f'.footer{{text-align:center;color:#4a6a80;font-size:12px;margin:30px 0 10px;border-top:1px solid {BORDER};padding-top:16px}}')
    H.append('</style></head><body><div class="container">')

    # Header — use one-liner as report title
    if one_liner:
        H.append(f'<div style="text-align:center;color:#fff;font-size:20px;font-weight:bold;'
                 f'line-height:1.8;padding:16px 20px;margin-bottom:8px;'
                 f'background:linear-gradient(135deg,#1a2a3a,#0f1923);border-radius:10px">'
                 f'{one_liner}</div>')
    else:
        H.append(f'<h1 style="text-align:center;color:#fff;font-size:24px">{home_name} vs {away_name} 战术分析报告</h1>')
    H.append(f'<div class="scoreboard">')
    H.append(f'<span class="teams">{home_name}</span>')
    H.append(f'<span class="score">{total_home} - {total_away}</span>')
    H.append(f'<span class="teams">{away_name}</span>')
    if has_penalties:
        H.append(f'<p style="text-align:center;font-size:12px;color:#95a5a6;margin-top:6px">'
                 f'常规+加时 {score.home}-{score.away}  |  点球 {pen_home}-{pen_away}</p>')
    H.append(f'</div>')

    # ═══════════════════════════════════════════════
    # ── 比赛概览 ──
    # ═══════════════════════════════════════════════

    # CSS for overview elements
    H.append('<style>')
    H.append('.match-bg{font-size:13px;color:#8ab4d6;margin:10px 0;text-align:center;line-height:2}')
    H.append('.match-bg .stage-name{font-weight:bold;color:#f1c40f;font-size:15px}')
    H.append('.match-bg .venue-name{color:#c0d6e4}')
    H.append('.match-bg .score-detail{font-size:12px;color:#7a9ab4;margin-top:4px}')
    H.append('</style>')

    # 1. 一句话总结 — now used as report title above, but keep a subtle subtitle
    if one_liner:
        H.append(f'<div style="font-size:12px;color:#5a7a90;text-align:center;margin:4px 0 12px">'
                 f'─ 比赛概要 ─</div>')

    # 2. 比赛背景
    stage_name = ""
    venue_name = ""
    et_home = et_away = pk_home = pk_away = None
    if raw is not None:
        si = raw.stage_info or {}
        vi = raw.venue_info or {}
        stage_name = si.get("name", "")
        venue_name = vi.get("name", "")
        city = vi.get("city_name", "")
        capacity = vi.get("capacity", "")
        et_home = raw.score.extratime_home
        et_away = raw.score.extratime_away
        pk_home = raw.score.penalty_home
        pk_away = raw.score.penalty_away

    if stage_name or venue_name:
        bg_lines = []
        if stage_name:
            bg_lines.append(f'<span class="stage-name">{stage_name}</span>')
        if venue_name:
            cap_str = f" · 容量 {capacity:,}" if capacity else ""
            bg_lines.append(f'<span class="venue-name">{venue_name}{cap_str}</span>')

        # Score breakdown
        score_parts = [f'常规时间 {score.home}-{score.away}']
        if score.halftime_home is not None:
            score_parts.append(f'半场 {score.halftime_home}-{score.halftime_away}')
        if et_home is not None and et_away is not None:
            score_parts.append(f'加时 {et_home}-{et_away}')
        if has_penalties:
            score_parts.append(f'点球 {pen_home}-{pen_away}')
        bg_lines.append(f'<div class="score-detail">{"  |  ".join(score_parts)}</div>')

        H.append(f'<div class="match-bg">{"<br>".join(bg_lines)}</div>')

    # 3. 阵容图（内嵌 HTML）
    if lineup_html:
        H.append(lineup_html)

    # Section 1: 战术画像 + 雷达图
    profile = tac_sections.get("战术画像", "")
    if profile:
        H.append('<div class="insight-box">')
        H.append(f'<h4>战术画像</h4><p>{profile}</p>')
        H.append('</div>')
        if tactical_image_paths.get("tactical_radar"):
            H.append(f'<p style="text-align:center;margin:16px 0"><img src="{tactical_image_paths["tactical_radar"]}" alt="战术雷达图"></p>')

    # Section 2: 战术演绎 + 控球率图 + 射门图（上下堆叠，各占全宽）
    deduction = tac_sections.get("战术演绎", "")
    if deduction:
        H.append(f'<div class="insight-box" style="border-left-color:{BLUE}">')
        H.append(f'<h4 style="color:{BLUE}">战术演绎</h4><p>{deduction}</p>')
        H.append('</div>')
        # 控球率摇摆图 — 全宽
        if tactical_image_paths.get("tactical_possession"):
            H.append(f'<p style="text-align:center;margin:10px 0 4px;font-size:12px;color:#95a5a6">▼ 控球率逐段变化</p>')
            H.append(f'<p style="text-align:center;margin:0 0 16px"><img src="{tactical_image_paths["tactical_possession"]}" alt="控球摇摆" style="width:100%"></p>')
        # 射门柱状图 — 全宽
        if tactical_image_paths.get("tactical_shots"):
            H.append(f'<p style="text-align:center;margin:10px 0 4px;font-size:12px;color:#95a5a6">▼ 时段射门分布</p>')
            H.append(f'<p style="text-align:center;margin:0 0 16px"><img src="{tactical_image_paths["tactical_shots"]}" alt="时段射门" style="width:100%"></p>')

    # Section 3: 战术验证 + 执行效果卡
    verification = tac_sections.get("战术验证", "")
    if verification:
        H.append(f'<div class="insight-box" style="border-left-color:{GREEN}">')
        H.append(f'<h4 style="color:{GREEN}">战术验证</h4><p>{verification}</p>')
        H.append('</div>')

    # 执行效果卡（HTML inline）
    try:
        from src.visualizer.tactical_charts import generate_tactical_html_cards
        cards = generate_tactical_html_cards(tactical_data, home_name, away_name)
        H.append(cards)
    except Exception as e:
        H.append(f'<!-- cards error: {e} -->')

    # Section 4: 战术博弈 + PPDA 图表
    game = tac_sections.get("战术博弈", "")
    if game:
        H.append(f'<div class="insight-box" style="border-left-color:{RED}">')
        H.append(f'<h4 style="color:{RED}">战术博弈</h4><p>{game}</p>')
        H.append('</div>')
        if tactical_image_paths.get("tactical_ppda"):
            H.append(f'<p style="text-align:center;margin:10px 0 4px;font-size:12px;color:#95a5a6">▼ 全场压迫强度对比</p>')
            H.append(f'<p style="text-align:center;margin:0 0 16px"><img src="{tactical_image_paths["tactical_ppda"]}" alt="PPDA对比" style="width:100%"></p>')

    # Section 5: 战术定论
    conclusion = tac_sections.get("战术定论", "")
    if conclusion:
        H.append(f'<div class="insight-box gold"><p style="font-size:16px;font-weight:bold;margin:0">{conclusion}</p></div>')

    # ── 全场事件时间轴 ──
    if timeline_html:
        H.append(f'<h2 style="color:#e0e8f0;font-size:22px;border-bottom:2px solid {GREEN};padding-bottom:8px;margin:28px 0 14px">全场事件时间轴</h2>')
        H.append(timeline_html)
        if timeline_png:
            H.append(f'<p style="text-align:center;margin:16px 0 4px;font-size:12px;color:#95a5a6">▼ 时间轴图片版（可右键保存）</p>')
            H.append(f'<p style="text-align:center;margin:0 0 16px"><img src="{timeline_png}" alt="事件时间轴" style="width:100%"></p>')

    H.append('<div class="footer">战术分析报告由 AI 自动生成 | 数据来源：SportMonks API</div>')
    H.append('</div></body></html>')

    html_content = "\n".join(H)
    html_path = Path(output_dir) / "tactical_report.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)


if __name__ == "__main__":
    main()
