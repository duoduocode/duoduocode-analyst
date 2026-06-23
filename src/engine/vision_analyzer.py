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

VISION_PROMPT_TEMPLATE = """你是足球数据分析师。请分析{player_name}（{team_name}队，位置{position}，出场{minutes}分钟）的数据，只描述你看到的图表事实，不推测战术意图。

已知他的持球推进数据：总推进距离 {total_carry}，渐进推进距离 {prog_carry}，渐进推进次数 {prog_carries}，总触球 {touches}。

{orientation}

**重要：描述必须是具体的、可量化的，而不是模糊概括。**

逐图回答：

1. 热力图 — 按画面6列×3行划分18个固定区域。

   **网格为画面绝对坐标**。列1永远是画面最左端的1/6，列6永远是画面最右端的1/6。编号从画面左下角1区开始，列内从下到上递增：

   列1（画面左 1/6）：1区 下 | 2区 中 | 3区 上
   列2（画面左 2/6）：4区 下 | 5区 中 | 6区 上
   列3（画面左 3/6）：7区 下 | 8区 中 | 9区 上
   列4（画面右 4/6）：10区 下 | 11区 中 | 12区 上
   列5（画面右 5/6）：13区 下 | 14区 中 | 15区 上
   列6（画面右 6/6）：16区 下 | 17区 中 | 18区 上

   注意：以上描述中"上=画面上方"、"下=画面下方"。请结合前面给出的球场方向，说明该区是处于本方半场/对方半场、以及禁区内/禁区外的具体位置。

   逐区描述：
   - 每个区是否有活动？（无活动/浅黄/深黄/橙色/红色）
   - 颜色最深的区是几号区？颜色等级是什么？
   - 该区处于画面哪端（左端/右端）？结合球队进攻方向判断是本方半场还是对方半场、禁区内还是禁区外、以及禁区内的子位置（球门区/点球点/大禁区角/边线附近）。
   - 有多少个区完全没有活动？列出区号。

2. 传球图 — 统计方向占比。
   - 向前___次 / 横向___次 / 回传___次
   - 短传___次 / 长传___次
   - 发起点在画面左半侧___个 / 中间___个 / 右半侧___个

3. 带球推进图 — 统计方向和区域。
   - 纵向向前___次 / 横向___次 / 后退___次
   - 起点在画面左半侧___次 / 右半侧___次
   - 终点位置描述：到达了什么区域（本方半场/中场/对方半场/禁区边缘/禁区内）？

4. 射门图 — 统计位置。
   - 禁区内___次 / 禁区外___次
   - 在画面的左侧___次 / 中间___次 / 右侧___次
   - 所有射门点的最靠前位置在哪？

**格式要求：每张图用4-6句话描述，尽量给出数值统计。**
**严格禁止：不得使用"试图""寻找""配合""组织""拉扯""策应"等意图词汇。只能描述位置、方向、颜色、次数。**"""


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
