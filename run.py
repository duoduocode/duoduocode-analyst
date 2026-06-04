import argparse
import json
import logging
import os
from pathlib import Path

import yaml

from src.collector.api_client import SportMonksClient, fetch_all
from src.engine.metrics import compute_all

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    for key, value in os.environ.items():
        placeholder = "${" + key + "}"
        raw = raw.replace(placeholder, value)
    return yaml.safe_load(raw)


def generate_narrative(
    raw, computed, signals, trend_analysis, llm_config: dict
) -> str:
    from src.composer.data_builder import build_narrative
    from src.composer.prompt_loader import PromptLoader
    from src.generator.llm_client import LLMClient

    llm = LLMClient(llm_config)
    pl = PromptLoader("prompts")

    logger.info("Building narrative prompt...")
    sys_p, user_p = build_narrative(raw, computed, signals, trend_analysis, pl)

    logger.info("Calling LLM for narrative...")
    text = llm.generate(sys_p, user_p)
    return text


def generate_all_visuals(raw, computed, visual_config: dict, output_dir: str) -> dict:
    from src.engine.metrics import _stat
    from src.engine.ratings import get_player_radar_values, get_team_average_radar
    from src.visualizer.momentum import plot_momentum_curve
    from src.visualizer.pass_network import plot_pass_network
    from src.visualizer.radar import plot_player_radar
    from src.visualizer.shots import build_shot_data_from_players, plot_shot_map
    from src.visualizer.subs import plot_subs_comparison
    from src.visualizer.xg_hist import plot_xg_histogram

    dpi = visual_config.get("dpi", 150)
    images_dir = Path(output_dir) / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    result = {}

    hs = raw.home_stats
    aws = raw.away_stats
    home_xg = sum(p.xg for p in raw.home_players) if raw.home_players else float(_stat(hs, "Expected Goals", default=0))
    away_xg = sum(p.xg for p in raw.away_players) if raw.away_players else float(_stat(aws, "Expected Goals", default=0))

    home_shots_data = build_shot_data_from_players(raw.home_players, raw.home_team.id)
    away_shots_data = build_shot_data_from_players(raw.away_players, raw.away_team.id)

    result["shots"] = plot_shot_map(
        home_shots_data, away_shots_data,
        home_xg, away_xg,
        raw.home_team.name, raw.away_team.name,
        str(images_dir / "01_shots.png"),
        dpi=dpi,
    )

    result["momentum"] = plot_momentum_curve(
        computed.momentum["segments"],
        computed.momentum["key_events"],
        raw.home_team.name, raw.away_team.name,
        str(images_dir / "02_momentum.png"),
        dpi=dpi,
    )

    if raw.home_lineup:
        result["pass_home"] = plot_pass_network(
            raw.home_lineup.players,
            raw.home_players,
            raw.home_lineup.formation,
            raw.home_team.name,
            str(images_dir / "03a_pass_home.png"),
            dpi=dpi,
        )
    else:
        result["pass_home"] = ""

    if raw.away_lineup:
        result["pass_away"] = plot_pass_network(
            raw.away_lineup.players,
            raw.away_players,
            raw.away_lineup.formation,
            raw.away_team.name,
            str(images_dir / "03b_pass_away.png"),
            dpi=dpi,
        )
    else:
        result["pass_away"] = ""

    if computed.home_hidden_mvp:
        hidden = computed.home_hidden_mvp
        player_vals = get_player_radar_values(hidden)
        comp_vals = get_team_average_radar(raw.home_players)
        result["radar_hidden"] = plot_player_radar(
            player_vals, comp_vals,
            hidden.name, f"{raw.home_team.name} 全队平均",
            str(images_dir / "04b_radar_hidden.png"),
            dpi=dpi,
            is_hidden_mvp=True,
        )
    else:
        result["radar_hidden"] = ""

    result["subs_home"] = plot_subs_comparison(
        computed.home_subs_effect,
        raw.home_team.name,
        str(images_dir / "05_subs.png"),
        dpi=dpi,
    )

    result["xg_hist"] = plot_xg_histogram(
        computed.ldi_result,
        raw.score.home, raw.score.away,
        raw.home_team.name, raw.away_team.name,
        str(images_dir / "06_xg_hist.png"),
        dpi=dpi,
    )

    rel = {}
    for k, v in result.items():
        if v:
            rel[k] = str(Path(v).relative_to(output_dir)).replace("\\", "/")
        else:
            rel[k] = ""
    return rel


def main():
    parser = argparse.ArgumentParser(description="AI 足球比赛分析报告生成")
    parser.add_argument("--match", type=int, help="比赛 ID (fixture id)")
    parser.add_argument("--league", type=int, default=1, help="联赛 ID (默认: 1=世界杯)")
    parser.add_argument("--date", type=str, help="日期 YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true", help="仅采集数据并计算指标")
    parser.add_argument("--no-images", action="store_true", help="跳过图表生成")
    parser.add_argument("--config", type=str, default="config.yaml", help="配置文件路径")
    args = parser.parse_args()

    config = load_config(args.config)

    if args.league and args.date:
        client = SportMonksClient(config["sportmonks"])
        fixtures = client.get_fixtures_by_date(
            args.league,
            config.get("competition", {}).get("season", 2026),
            args.date,
        )
        match_ids = [f["fixture"]["id"] for f in fixtures if f["fixture"]["id"]]
        logger.info(f"找到 {len(match_ids)} 场比赛: {args.date}")
    elif args.match:
        match_ids = [args.match]
    else:
        parser.error("请指定 --match 或 (--league + --date)")

    for match_id in match_ids:
        logger.info(f"{'='*60}")
        logger.info(f"处理比赛 #{match_id}...")

        try:
            raw = fetch_all(match_id, config["sportmonks"])
        except Exception as e:
            logger.error(f"数据采集失败 #{match_id}: {e}")
            continue

        computed = compute_all(raw)

        logger.info("Analyzing trends...")
        from src.engine.trends import analyze_trends
        trend_analysis = analyze_trends(raw)

        logger.info("Detecting signals...")
        from src.engine.signals import detect_all, get_top_signals
        all_signals = detect_all(raw, None, trend_analysis)
        top_signals = get_top_signals(all_signals, top_n=6)

        signal_names = [s.name for s in top_signals]
        logger.info(f"Top signals: {signal_names}")
        logger.info(f"  ({len(all_signals)} total signals detected, top 6 selected for LLM)")

        computed_path = Path("data/computed") / f"{match_id}.json"
        computed_path.parent.mkdir(parents=True, exist_ok=True)
        import dataclasses

        computed_dict = dataclasses.asdict(computed)
        # Save ALL detected signals (not just top 6)
        computed_dict["signals"] = [
            {"name": s.name, "category": s.category, "strength": s.strength,
             "narrative_hint": s.narrative_hint, "evidence": s.evidence}
            for s in all_signals
        ]
        computed_dict["top_signals"] = signal_names
        with open(computed_path, "w", encoding="utf-8") as f:
            json.dump(computed_dict, f, ensure_ascii=False, indent=2, default=str)

        logger.info(
            f"指标: CI({computed.home_ci}/{computed.away_ci}) "
            f"TCR({computed.home_tcr}/{computed.away_tcr}) "
            f"PE({computed.home_pe}/{computed.away_pe}) "
            f"标签: {computed.tags}"
        )

        if args.dry_run:
            logger.info(f"Dry-run 完成，数据已保存至 data/raw/{match_id}/ 和 data/computed/")
            continue

        safe_home = "".join(c if c.isalnum() or c in "-_" else "_" for c in raw.home_team.name)
        safe_away = "".join(c if c.isalnum() or c in "-_" else "_" for c in raw.away_team.name)
        output_dir = Path("output") / f"{match_id}_{safe_home}_vs_{safe_away}"

        narrative_text = generate_narrative(raw, computed, top_signals, trend_analysis, config["llm"])
        logger.info("Narrative generated.")

        if not args.no_images:
            image_paths = generate_all_visuals(raw, computed, config["visual"], str(output_dir))
            logger.info(f"图表已生成: {len(image_paths)} 张")
        else:
            image_paths = {}

        from src.reporter.build_report import build_report
        report_path = build_report(raw, computed, narrative_text, all_signals, image_paths, str(output_dir))
        logger.info(f"报告已生成: {report_path}")

    logger.info(f"\n完成！共处理 {len(match_ids)} 场比赛。")


if __name__ == "__main__":
    main()
