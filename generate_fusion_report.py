"""
融合比赛报道生成器

将战术分析段落 + 压迫分析段落 + 关键事件 + 新闻摘要
融合为一篇战术+叙事综合比赛报道（HTML）。

用法:
  python generate_fusion_report.py 19609143
  python generate_fusion_report.py 19609143 --no-news
  python generate_fusion_report.py 19609143 --no-html
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
from pathlib import Path

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, THIS_DIR)

from src.utils.player_names import to_chinese as _cn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════
# 配置加载
# ═══════════════════════════════════════════════

def load_config(path: str = "config.yaml") -> dict:
    import yaml
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    for key, value in os.environ.items():
        raw = raw.replace("${" + key + "}", value)
    cfg = yaml.safe_load(raw)
    return cfg


# ═══════════════════════════════════════════════
# 数据加载
# ═══════════════════════════════════════════════

def load_raw_data(match_id: int) -> dict:
    """一次性加载 raw_data.json 并返回反序列化的 RawMatchData。"""
    from src.collector.api_client import load_cached_raw as _load_cached
    try:
        logger.info(f"加载缓存数据: data/raw/{match_id}/raw_data.json")
        return _load_cached(match_id)
    except FileNotFoundError:
        logger.error(f"缓存不存在: data/raw/{match_id}/raw_data.json")
        logger.error("请先运行 generate_match_report.py {match_id} 生成缓存")
        sys.exit(1)


# ═══════════════════════════════════════════════
# 战术分析 + LLM 叙事生成
# ═══════════════════════════════════════════════

def generate_tactical_narrative(raw, tactical_data: dict, config: dict) -> str:
    """生成六段战术叙事（复用现有 tactical prompt）。"""
    from src.composer.tactical_prompt import build_tactical_system_and_user
    from src.composer.prompt_loader import PromptLoader
    from src.generator.llm_client import LLMClient

    llm = LLMClient(config["llm"])
    loader = PromptLoader("prompts")

    home_name = raw.home_team.name
    away_name = raw.away_team.name
    score = raw.score
    pen_home = pen_away = 0
    for e in raw.events:
        if e.event_type == "Goal" and e.detail == "pen_shootout_goal":
            if e.team_id == raw.home_team.id:
                pen_home += 1
            else:
                pen_away += 1

    total_home = score.home + (score.extratime_home or 0) + pen_home
    total_away = score.away + (score.extratime_away or 0) + pen_away

    stage_name = (raw.stage_info or {}).get("name", "")

    logger.info("生成战术分析叙事 (LLM)...")
    sys_p, user_p = build_tactical_system_and_user(
        tactical_data, home_name, away_name,
        total_home, total_away, loader,
        pen_home=pen_home, pen_away=pen_away,
        stage_name=stage_name,
    )
    return llm.generate(sys_p, user_p)


def generate_pressing_narrative(raw, tactical_data: dict, config: dict,
                                spatial_context: str = "") -> str:
    """生成压迫分析叙事（复用现有 pressing prompt）。"""
    from src.composer.pressing_prompt import build_pressing_prompt
    from src.composer.prompt_loader import PromptLoader
    from src.generator.llm_client import LLMClient

    llm = LLMClient(config["llm"])
    loader = PromptLoader("prompts")

    home_name = raw.home_team.name
    away_name = raw.away_team.name
    score = raw.score

    mf = tactical_data["match_flow"]
    ppda_trend = mf.get("ppda_trend", {"home": [], "away": []})
    possession_trend = mf.get("possession_trend", {"home": [], "away": []})
    shot_segments = mf.get("shot_segments", {})

    # 构建防守动作数据
    def_actions = _build_def_actions(raw)
    goal_events = _build_goal_events(raw)

    logger.info("生成压迫分析叙事 (LLM)...")
    sys_p, user_p = build_pressing_prompt(
        home_name, away_name,
        ppda_trend, possession_trend, shot_segments,
        def_actions, goal_events,
        score.home, score.away, loader,
        spatial_context=spatial_context,
    )
    return llm.generate(sys_p, user_p)


def _build_def_actions(raw) -> dict:
    """构建每窗口防守动作数据。"""
    windows = [(0, 15), (15, 30), (30, 45), (45, 60), (60, 75), (75, 90)]

    def _cum_at(pts, minute):
        val = 0.0
        for p in sorted(pts, key=lambda x: x.minute):
            if p.minute <= minute:
                val = p.value
            else:
                break
        return val

    def _window_actions(own_team_id: str) -> dict:
        result = {"tackles": [], "interceptions": [], "fouls": []}
        for metric, tid in [("tackles", "78"), ("interceptions", "100"), ("fouls", "56")]:
            pts = raw.trends.get(own_team_id, {}).get(tid, [])
            for start, end in windows:
                delta = _cum_at(pts, end) - _cum_at(pts, start)
                result[metric].append(round(delta, 1))
        return result

    return {
        "home": _window_actions(str(raw.home_team.id)),
        "away": _window_actions(str(raw.away_team.id)),
    }


def _build_goal_events(raw) -> list[dict]:
    """构建进球事件列表。"""
    goals = []
    for e in raw.events:
        if e.event_type == "Goal" and e.detail not in ("pen_shootout_goal", "pen_shootout_miss"):
            team_label = "home" if e.team_id == raw.home_team.id else "away"
            goals.append({
                "minute": e.time_elapsed,
                "label": _cn(e.player_name) or "",
                "team": team_label,
            })
    return goals


# ═══════════════════════════════════════════════
# 新闻素材加载
# ═══════════════════════════════════════════════

def load_news(output_dir: Path) -> tuple[str, str, str]:
    """加载 web_context 中的赛前/赛况/赛后新闻。"""
    web_dir = output_dir / "web_context"
    pre_news = match_news = post_news = ""

    for mode, label in [("pre", "赛前"), ("match", "赛况"), ("post", "赛后")]:
        path = web_dir / f"{mode}.txt"
        if path.exists():
            text = path.read_text(encoding="utf-8")
            # 只取摘要部分（跳过元信息头部）
            # 查找"新闻摘要"之后的正文
            lines = text.split("\n")
            content_start = 0
            for i, line in enumerate(lines):
                if "新闻摘要" in line and ("##" in line or "摘要" in line):
                    content_start = i + 1
                    break
            body = "\n".join(lines[content_start:]).strip()
            if not body:
                body = text.strip()
            if mode == "pre":
                pre_news = body[:2000]
            elif mode == "match":
                match_news = body[:3000]
            else:
                post_news = body[:2000]
            logger.info(f"  加载{label}新闻: {len(body)} 字符")

    return pre_news, match_news, post_news


# ═══════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════

def generate_fusion_report(
    match_id: int,
    skip_news: bool = False,
    skip_html: bool = False,
):
    """主入口：生成融合比赛报道。"""
    config = load_config()

    # 1. 加载数据
    raw = load_raw_data(match_id)
    home_name = raw.home_team.name
    away_name = raw.away_team.name
    score = raw.score

    safe_home = home_name.replace(" ", "_")
    safe_away = away_name.replace(" ", "_")
    output_dir = Path("output") / f"{match_id}_{safe_home}_vs_{safe_away}"

    if not output_dir.exists():
        logger.error(f"输出目录不存在: {output_dir}")
        logger.error("请先运行 generate_match_report.py {match_id}")
        sys.exit(1)

    logger.info(f"{'='*60}")
    logger.info(f"比赛: {home_name} {score.home} - {score.away} {away_name}  (#{match_id})")
    logger.info(f"输出: {output_dir}")

    # 2. 计算战术分析
    from src.engine.tactical_insights import compute_tactical_analysis
    logger.info("计算战术分析 (四层因果模型)...")
    tactical_data = compute_tactical_analysis(raw)
    logger.info(f"  风格碰撞: {tactical_data['coaching']['style_clash']}")

    # 3. 生成战术叙事
    tactical_narrative = generate_tactical_narrative(raw, tactical_data, config)
    logger.info(f"  战术叙事: {len(tactical_narrative)} 字符")

    # 3.5. 加载球员空间行为数据（视觉AI解析缓存）
    from src.engine.vision_analyzer import load_vision_cache, run_vision_analysis
    from src.composer.spatial_summary import (
        build_player_spatial_portrait,
        build_team_spatial_synthesis,
        build_pressing_spatial_context,
        build_team_tactical_synthesis,
    )

    vision_data = load_vision_cache(match_id)
    if vision_data is None:
        logger.info("  视觉解析缓存不存在，自动触发豆包视觉模型逐人读图...")
        vision_data = run_vision_analysis(match_id, config=config, force=False)
        if vision_data is None:
            logger.warning("  视觉解析失败，跳过球员空间行为章节。")
        else:
            logger.info(f"  视觉解析完成: {len(vision_data)} 人")

    player_spatial_portrait = ""
    team_spatial_synthesis = ""
    pressing_spatial_context = ""
    tactical_synthesis = ""
    if vision_data:
        player_spatial_portrait = build_player_spatial_portrait(
            match_id, vision_data=vision_data, top_n=12
        )
        team_spatial_synthesis = build_team_spatial_synthesis(
            match_id, vision_data=vision_data,
            left_team=home_name, right_team=away_name,
        )
        pressing_spatial_context = build_pressing_spatial_context(
            match_id, vision_data=vision_data
        )
        tactical_synthesis = build_team_tactical_synthesis(match_id)
        logger.info(f"  球员空间行为: {len(player_spatial_portrait)} 字符")
        logger.info(f"  球队空间合成: {len(team_spatial_synthesis)} 字符")
        logger.info(f"  战术合成: {len(tactical_synthesis)} 字符")

        # 3.6. 生成战术合成图
        tactical_synthesis_path = ""
        try:
            from src.visualizer.tactical_sketch import plot_tactical_synthesis
            images_dir = output_dir / "images"
            images_dir.mkdir(parents=True, exist_ok=True)
            match_score_str = f"{score.home} - {score.away}"
            plot_tactical_synthesis(
                match_id, home_name, away_name,
                str(images_dir), dpi=150, match_score=match_score_str,
                vision_data=vision_data,
            )
            tactical_synthesis_path = "images/tactical_synthesis.png"
            logger.info(f"  战术合成图: {tactical_synthesis_path}")
        except Exception as e:
            logger.warning(f"  战术合成图生成跳过: {e}")

    # 4. 生成压迫叙事
    pressing_narrative = generate_pressing_narrative(
        raw, tactical_data, config, spatial_context=pressing_spatial_context
    )
    logger.info(f"  压迫叙事: {len(pressing_narrative)} 字符")

    # 5. 加载新闻素材
    pre_news = match_news = post_news = ""
    if not skip_news:
        pre_news, match_news, post_news = load_news(output_dir)

    # 6. 组装融合 Prompt
    from src.composer.fusion_report import build_fusion_prompt
    from src.composer.prompt_loader import PromptLoader
    from src.generator.llm_client import LLMClient

    loader = PromptLoader("prompts")
    llm = LLMClient(config["llm"])

    logger.info("组装融合报道 Prompt...")
    sys_p, user_p = build_fusion_prompt(
        raw, tactical_data, tactical_narrative, pressing_narrative,
        pre_news=pre_news, match_news=match_news, post_news=post_news,
        loader=loader,
        player_spatial_portrait=player_spatial_portrait,
        team_spatial_synthesis=team_spatial_synthesis,
        tactical_synthesis=tactical_synthesis,
    )

    # 7. LLM 生成融合文章
    logger.info("LLM 生成融合报道...")
    # 融合文章需要更多 tokens
    fusion_md = llm.generate(sys_p, user_p, max_tokens=4000)
    logger.info(f"  融合报道: {len(fusion_md)} 字符")

    # 保存 Markdown
    md_path = output_dir / "fusion_report.md"
    md_path.write_text(fusion_md, encoding="utf-8")
    logger.info(f"  Markdown: {md_path}")

    # 8. 生成 HTML
    if not skip_html:
        from src.composer.fusion_report import generate_fusion_html

        stage_name = (raw.stage_info or {}).get("name", "")
        venue_name = (raw.venue_info or {}).get("name", "")

        html_path = generate_fusion_html(
            fusion_md, home_name, away_name,
            score.home, score.away,
            str(output_dir),
            stage_name=stage_name,
            venue_name=venue_name,
        )
        logger.info(f"  HTML: {html_path}")

    # 9. 也保存中间产物供调试
    narrative_dir = output_dir / "fusion_intermediates"
    narrative_dir.mkdir(exist_ok=True)
    (narrative_dir / "tactical_narrative.txt").write_text(tactical_narrative, encoding="utf-8")
    (narrative_dir / "pressing_narrative.txt").write_text(pressing_narrative, encoding="utf-8")
    (narrative_dir / "fusion_user_prompt.txt").write_text(user_p, encoding="utf-8")

    logger.info(f"\n{'='*60}")
    logger.info("完成! 生成文件:")
    logger.info(f"  fusion_report.md   — 融合报道 Markdown")
    if not skip_html:
        logger.info(f"  fusion_report.html — 融合报道 HTML")
    logger.info(f"  fusion_intermediates/ — 中间产物 (调试用)")

    return fusion_md


def main():
    parser = argparse.ArgumentParser(
        description="融合比赛报道生成器 — 战术分析 + 赛况叙事",
    )
    parser.add_argument("match_id", type=int, nargs="+", help="比赛 ID")
    parser.add_argument("--no-news", action="store_true", help="不加载新闻素材")
    parser.add_argument("--no-html", action="store_true", help="不生成 HTML")
    args = parser.parse_args()

    for mid in args.match_id:
        generate_fusion_report(
            mid,
            skip_news=args.no_news,
            skip_html=args.no_html,
        )


if __name__ == "__main__":
    main()
