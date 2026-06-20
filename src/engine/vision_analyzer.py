"""
球员视觉解析模块

通过豆包视觉模型对球员热力图、传球图、带球推进图、射门图进行解析，
结果缓存到 data/computed/{match_id}_vision_analysis.json。

固定 prompt 模板，保证每次解析的一致性。
"""

from __future__ import annotations

import base64
import json
import logging
import os
import sys
import time
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════
# 固定 Prompt 模板
# ═══════════════════════════════════════════════

VISION_PROMPT_TEMPLATE = """你是足球数据分析师。请分析{player_name}（{team_name}队，位置{position}，出场{minutes}分钟）的数据，只描述你看到的事实，不推测战术角色或意图。

已知他的持球推进数据：总推进距离 {total_carry}，渐进推进距离 {prog_carry}，渐进推进次数 {prog_carries}，总触球 {touches}。

{orientation}

逐图回答，每条2-3句话：
1. 热力图：分别描述画面左上、右上、左下、右下四块区域的活动密度。哪块最密集？是否进入禁区（画面左端/右端的矩形区域）？
2. 传球图：传球方向以什么为主（向前/横向/回传）？短传还是长传？发起点集中在画面的左半侧还是右半侧？
3. 带球推进图：带球方向（纵向向前/横向/后退）？起点在画面的左半侧还是右半侧？终点在哪？
4. 射门图：射门位置在禁区内还是禁区外？在画面的左侧/中间/右侧？

**禁止事项**
禁止描述意图（如"试图组织""寻找传球线路"）。
禁止描述配合（如"撞墙配合""分给队友"）。只能描述：他在哪、往哪个方向传、往哪个方向带、在哪射门。"""


# ═══════════════════════════════════════════════
# 图表类型映射
# ═══════════════════════════════════════════════

CHART_TYPES = [
    ("heatmap", "heatmap.png"),
    ("pass", "pass_chart.png"),
    ("dribble", "dribble_chart.png"),
    ("shot", "shot_chart.png"),
]


def _load_config() -> dict:
    """加载配置。"""
    import yaml
    root = Path(__file__).parent.parent.parent
    with open(root / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _get_team_names(match_id: int, root: Path) -> tuple[str, str]:
    """从 output 目录获取比赛双方队名（左_vs_右）。

    Returns:
        (left_team_name, right_team_name)
    """
    output_dir = root / "output"
    if output_dir.exists():
        for d in output_dir.iterdir():
            if d.is_dir() and d.name.startswith(f"{match_id}_"):
                parts = d.name.split("_vs_")
                if len(parts) == 2:
                    return parts[0].replace(f"{match_id}_", ""), parts[1]
    return "Home", "Away"


def _build_orientation(team: str, left_team: str, right_team: str) -> str:
    """根据球员所属球队构建方向说明。

    关键事实：所有图表方向一致——
    左侧 = left_team 球门，右侧 = right_team 球门。
    """
    if team == "home":
        return (
            f"**球场方向**\n"
            f"此图表中，{left_team}的球门在画面左侧，{right_team}的球门在画面右侧。\n"
            f"此球员的球队（{left_team}）从左向右进攻。\n"
            f"面向对方球门（画面右侧）时：画面上方=左路，画面下方=右路。"
        )
    else:
        return (
            f"**球场方向**\n"
            f"此图表中，{left_team}的球门在画面左侧，{right_team}的球门在画面右侧。\n"
            f"此球员的球队（{right_team}）从右向左进攻。\n"
            f"面向对方球门（画面左侧）时：画面上方=右路，画面下方=左路。"
        )


def _get_player_team(data_dir: Path, player_name: str) -> str:
    """从 players_v6.json 获取球员所属队伍。"""
    match_id = data_dir.parent.name  # data/19609173 -> 19609173
    computed_dir = data_dir.parent.parent / "computed"
    v6_path = computed_dir / f"{match_id}_players_v6.json"
    if v6_path.exists():
        with open(v6_path, encoding="utf-8") as f:
            v6 = json.load(f)
        for p in v6:
            if p["name"] == player_name:
                return p.get("team", "?")
    return "?"


def run_vision_analysis(
    match_id: int,
    config: dict | None = None,
    force: bool = False,
) -> dict:
    """对一场比赛的全部球员执行视觉解析。

    Args:
        match_id: 比赛 ID
        config: 配置字典，为 None 时自动加载
        force: 是否强制重新解析（即使缓存存在）

    Returns:
        dict: {player_name: {team, pos, minutes, carry, prog_carry, touches, output, tokens_in, tokens_out, charts}}
    """
    if config is None:
        config = _load_config()

    root = Path(__file__).parent.parent.parent
    data_dir = root / "data" / str(match_id)
    computed_dir = root / "data" / "computed"
    cache_path = computed_dir / f"{match_id}_vision_analysis.json"

    # ── 检查缓存 ──
    if not force and cache_path.exists():
        with open(cache_path, encoding="utf-8") as f:
            cached = json.load(f)
        # 检查缓存是否有效（至少有一个 player 有 output）
        has_output = any(v.get("output", "").strip() for v in cached.values())
        if has_output:
            logger.info(f"Vision: loaded {len(cached)} players from cache")
            return cached
        logger.info("Vision: cache exists but empty outputs, re-running")

    # ── 加载球员元信息 ──
    computed_dir.mkdir(parents=True, exist_ok=True)
    v6_path = computed_dir / f"{match_id}_players_v6.json"
    player_info = {}
    if v6_path.exists():
        with open(v6_path, encoding="utf-8") as f:
            v6 = json.load(f)
        for p in v6:
            info = {
                "team": p.get("team", "?"),
                "pos": p.get("pos", "?"),
                "minutes": p.get("minutes", 0),
                "is_sub": p.get("is_substitute", False),
            }
            # 加载 carray_data.json
            cp = data_dir / p["name"] / "carry_data.json"
            if cp.exists():
                with open(cp, encoding="utf-8") as f2:
                    cd = json.load(f2)
                    info["carry"] = cd.get("Total carrying distance", "?")
                    info["prog_carry"] = cd.get("Progressive carrying distance", "?")
                    info["prog_carries"] = cd.get("Progressive carries", "?")
                    info["touches"] = cd.get("Touches", "?")
            # 加载 def_data.json
            dp = data_dir / p["name"] / "def_data.json"
            if dp.exists():
                with open(dp, encoding="utf-8") as f2:
                    info["defense"] = json.load(f2)
            player_info[p["name"]] = info

    # ── 收集所有球员 ──
    players = sorted([d for d in os.listdir(data_dir) if os.path.isdir(data_dir / d)])

    doubao_key = config["doubao"]["api_key"]
    doubao_url = config["doubao"]["base_url"]
    doubao_model = config["doubao"]["model"]

    vision_results = {}
    total_in = 0
    total_out = 0
    n = len(players)

    logger.info(f"Vision: analyzing {n} players for match {match_id}")
    print(f"\nStarting vision analysis: {n} players\n", flush=True)

    # 获取比赛双方队名
    left_team, right_team = _get_team_names(match_id, root)

    for i, pname in enumerate(players):
        pd = data_dir / pname
        info = player_info.get(pname, {})
        team = info.get("team", "?")
        team_name = "Türkiye" if team == "home" else ("Paraguay" if team == "away" else "未知")
        pos = info.get("pos", "?")
        minutes = info.get("minutes", 0)
        carry = info.get("carry", "?")
        prog_carry = info.get("prog_carry", "?")
        prog_carries = info.get("prog_carries", "?")
        touches = info.get("touches", "?")

        # 收集图表
        images = {}
        for ct, fname in CHART_TYPES:
            fp = pd / fname
            if fp.exists():
                with open(fp, "rb") as f_img:
                    images[ct] = base64.b64encode(f_img.read()).decode("utf-8")

        if len(images) == 0:
            logger.debug(f"[{i+1:2d}/{n}] {pname:28s} — no charts, skip")
            vision_results[pname] = {
                "team": team, "pos": pos, "minutes": minutes,
                "carry": carry, "prog_carry": prog_carry, "touches": touches,
                "output": "", "tokens_in": 0, "tokens_out": 0, "charts": 0,
            }
            continue

        # 构建 prompt
        orientation = _build_orientation(team, left_team, right_team)
        prompt = VISION_PROMPT_TEMPLATE.format(
            player_name=pname, team_name=team_name,
            position=pos, minutes=minutes,
            total_carry=carry, prog_carry=prog_carry,
            prog_carries=prog_carries, touches=touches,
            orientation=orientation,
        )

        content = [{"type": "input_text", "text": prompt}]
        for ct in ["heatmap", "pass", "dribble", "shot"]:
            if ct in images:
                content.append({"type": "input_image", "image_url": f"data:image/png;base64,{images[ct]}"})

        # 调用豆包
        t0 = time.time()
        output_text = ""
        tin = tout = 0

        for attempt in range(3):
            try:
                resp = requests.post(
                    f"{doubao_url}/responses",
                    headers={"Authorization": f"Bearer {doubao_key}", "Content-Type": "application/json"},
                    json={
                        "model": doubao_model,
                        "input": [{"role": "user", "content": content}],
                        "temperature": 0.4,
                        "max_output_tokens": 800,
                        "thinking": {"type": "disabled"},
                    },
                    timeout=180,
                    proxies={"http": None, "https": None},
                )
                if resp.status_code == 200:
                    break
                logger.warning(f"  {pname} retry {attempt+1}: HTTP {resp.status_code}")
                time.sleep(3)
            except Exception as e:
                logger.warning(f"  {pname} retry {attempt+1}: {e}")
                time.sleep(3)
        else:
            logger.error(f"  {pname} FAILED after 3 retries")
            vision_results[pname] = {
                "team": team, "pos": pos, "minutes": minutes,
                "carry": carry, "prog_carry": prog_carry, "touches": touches,
                "output": "", "tokens_in": 0, "tokens_out": 0, "charts": len(images),
            }
            continue

        elapsed = time.time() - t0
        data = resp.json()

        for item in data.get("output", []):
            if item.get("type") == "message":
                for part in item.get("content", []):
                    if part.get("type") == "output_text":
                        output_text += part.get("text", "")

        usage = data.get("usage", {})
        tin = usage.get("input_tokens", 0)
        tout = usage.get("output_tokens", 0)
        total_in += tin
        total_out += tout

        vision_results[pname] = {
            "team": team, "pos": pos, "minutes": minutes,
            "carry": carry, "prog_carry": prog_carry, "touches": touches,
            "output": output_text.strip(),
            "tokens_in": tin, "tokens_out": tout, "charts": len(images),
        }

        logger.info(f"[{i+1:2d}/{n}] {pname:28s} {team:5s} {pos:3s} "
                     f"charts={len(images)} carry={carry}  "
                     f"{tin}/{tout}t  {elapsed:.0f}s")
        # 即时输出进度到控制台
        print(f"  [{i+1:2d}/{n}] {pname}  {tin}/{tout}t  {elapsed:.0f}s", flush=True)

    # ── 保存缓存 ──
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(vision_results, f, ensure_ascii=False, indent=2)

    cost = total_in / 1000000 * 0.12 + total_out / 1000000 * 0.96
    logger.info(f"Vision done: {total_in}in/{total_out}out tokens, ~${cost:.3f} USD")
    logger.info(f"Saved: {cache_path}")
    print(f"\nVision complete: {total_in}/{total_out} tokens, ~${cost:.3f}", flush=True)

    return vision_results


def load_vision_cache(match_id: int) -> dict | None:
    """加载已缓存的视觉解析结果。"""
    root = Path(__file__).parent.parent.parent
    cache_path = root / "data" / "computed" / f"{match_id}_vision_analysis.json"
    if not cache_path.exists():
        logger.warning(f"No vision cache: {cache_path}")
        return None
    with open(cache_path, encoding="utf-8") as f:
        return json.load(f)
