"""
球员空间摘要构建模块

从 vision_analyzer 缓存中读取球员视觉解析结果，结合球员 V6 数据，
构建可供 LLM prompt 使用的文本摘要。

产出三种摘要：
1. build_player_spatial_portrait() → 完整球员特写（含球队整体分析）
2. build_team_spatial_synthesis() → 球队级空间模式概要
3. build_pressing_spatial_context() → 压迫相关的空间上下文
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from src.utils.player_names import to_chinese as _cn

logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent.parent

# 坐标翻译表：画面坐标 → 足球语言
# 图表方向固定：左侧=主队球门，右侧=客队球门。X轴=球门方向，Y轴=边线方向。
# 主队从左→右攻，面朝右侧，画面上方=左路，画面下方=右路
# 客队从右→左攻，面朝左侧，画面上方=右路，画面下方=左路
_COORD_TRANSLATE = {
    "home": {
        # X轴（球门方向）：防守半场 vs 进攻半场
        "画面左半侧": "防守半场侧（靠近本方球门）", "画面右半侧": "进攻半场侧（靠近对方球门）",
        "画面左侧": "防守半场侧", "画面右侧": "进攻半场侧",
        "左侧": "防守半场侧", "右侧": "进攻半场侧",
        "左端": "防守半场端", "右端": "进攻半场端",
        # Y轴（边线方向）：画面上=左路，画面下=右路
        "画面上方": "左路（靠近上方边线）", "画面下方": "右路（靠近下方边线）",
        # 四象限
        "左上": "本方半场左路", "右上": "对方半场左路（进攻左路）",
        "左下": "本方半场右路", "右下": "对方半场右路（进攻右路）",
    },
    "away": {
        "画面左半侧": "进攻半场侧（靠近对方球门）", "画面右半侧": "防守半场侧（靠近本方球门）",
        "画面左侧": "进攻半场侧", "画面右侧": "防守半场侧",
        "左侧": "进攻半场侧", "右侧": "防守半场侧",
        "左端": "进攻半场端", "右端": "防守半场端",
        "画面上方": "右路（靠近上方边线）", "画面下方": "左路（靠近下方边线）",
        "左上": "对方半场右路（进攻右路）", "右上": "本方半场右路",
        "左下": "对方半场左路（进攻左路）", "右下": "本方半场左路",
    },
}


def _load_player_info(match_id: int) -> dict:
    """加载球员 V6 数据和 per-player JSON。"""
    v6_path = ROOT / "data" / "computed" / f"{match_id}_players_v6.json"
    data_dir = ROOT / "data" / str(match_id)

    player_info = {}
    if not v6_path.exists():
        return player_info

    with open(v6_path, encoding="utf-8") as f:
        v6 = json.load(f)

    for p in v6:
        info = {
            "team": p.get("team", "?"),
            "pos": p.get("pos", "?"),
            "minutes": p.get("minutes", 0),
            "is_sub": p.get("is_substitute", False),
            "zscore": round(p.get("contributions", {}).get("C1", {}).get("zscore", 0), 2),
        }
        # 防守数据
        dp = data_dir / p["name"] / "def_data.json"
        if dp.exists():
            with open(dp, encoding="utf-8") as f2:
                info["defense"] = json.load(f2)
        # 持球数据
        cp = data_dir / p["name"] / "carry_data.json"
        if cp.exists():
            with open(cp, encoding="utf-8") as f2:
                cd = json.load(f2)
                info["carry"] = cd
        player_info[p["name"]] = info

    return player_info


def _format_defense(info: dict) -> str:
    """格式化防守数据。"""
    d = info.get("defense", {})
    if not d:
        return ""
    items = []
    for k in ["Tackles (won)", "Interceptions", "Clearances", "Recoveries"]:
        if k in d:
            items.append(f"{k}: {d[k]}")
    return " / ".join(items) if items else ""


def _format_carry(info: dict) -> str:
    """格式化持球推进数据。"""
    d = info.get("carry", {})
    if not d:
        return ""
    items = []
    for k in ["Total carrying distance", "Progressive carrying distance",
               "Progressive carries", "Touches"]:
        if k in d:
            items.append(f"{k}: {d[k]}")
    return " / ".join(items) if items else ""


def build_player_spatial_portrait(
    match_id: int,
    vision_data: dict | None = None,
    top_n: int = 12,
) -> str:
    """构建完整球员空间行为特写文本（用于插入融合报告章节）。

    Args:
        match_id: 比赛 ID
        vision_data: 视觉解析结果，为 None 时自动加载缓存
        top_n: 每队取前多少名球员

    Returns:
        str: 格式化后的球员空间特写文本
    """
    if vision_data is None:
        from src.engine.vision_analyzer import load_vision_cache
        vision_data = load_vision_cache(match_id)
        if vision_data is None:
            return "（球员视觉解析数据不可用，请先运行 vision_analyzer）"

    player_info = _load_player_info(match_id)

    # 分组排序
    home_players = []
    away_players = []
    for name, v in vision_data.items():
        info = player_info.get(name, {})
        if not v.get("output", "").strip():
            continue  # 跳过无解析结果的
        entry = (name, v, info)
        if v.get("team") == "home":
            home_players.append(entry)
        else:
            away_players.append(entry)

    home_players.sort(key=lambda x: -x[2].get("zscore", 0))
    away_players.sort(key=lambda x: -x[2].get("zscore", 0))

    lines = []
    for team_label, team_name, team_players in [
        ("home", "Türkiye", home_players[:top_n]),
        ("away", "Paraguay", away_players[:top_n]),
    ]:
        lines.append(f"## {team_name}\n")
        for name, v, info in team_players:
            # 翻译坐标→足球语言
            raw_output = v['output']
            translated = _translate_output(raw_output, team_label)
            lines.append(f"### {_cn(name)}")
            lines.append(f"位置: {v.get('pos','?')} | 出场: {v.get('minutes','?')}分钟"
                         f"{' (替补)' if info.get('is_sub') else ''}"
                         f" | 贡献值 zscore: {info.get('zscore','?')}")
            carry_str = _format_carry(info)
            if carry_str:
                lines.append(f"推进: {carry_str}")
            def_str = _format_defense(info)
            if def_str:
                lines.append(f"防守: {def_str}")
            lines.append(f"\n{translated}\n")

        lines.append("")

    return "\n".join(lines)


def _translate_output(output: str, team: str) -> str:
    """将视觉模型的画面坐标输出翻译为足球语言。"""
    if not output:
        return ""
    result = output
    mapping = _COORD_TRANSLATE.get(team, _COORD_TRANSLATE["home"])
    for coord, football in mapping.items():
        result = result.replace(coord, football)
    return result


def _extract_side_pattern(translated_output: str) -> str:
    """从翻译后的足球语言输出中粗分球员的侧重区域。"""
    text = translated_output
    # 统计翻译后含"左路"/"右路"的出现次数
    left_hits = text.count("左路") + text.count("左侧") + text.count("左半")
    right_hits = text.count("右路") + text.count("右侧") + text.count("右半")
    if left_hits >= right_hits * 2:
        return "左路主导"
    elif right_hits >= left_hits * 2:
        return "右路主导"
    elif abs(left_hits - right_hits) <= 2:
        return "中路均衡"
    elif left_hits > right_hits:
        return "偏左"
    else:
        return "偏右"


def build_team_spatial_synthesis(
    match_id: int,
    vision_data: dict | None = None,
    left_team: str = "Türkiye",
    right_team: str = "Paraguay",
) -> str:
    """构建球队级空间模式概要 —— 从个体行为拼出整体战术图。

    按位置分组（后卫/中场/前锋），每队提炼出核心空间模式。
    """
    if vision_data is None:
        from src.engine.vision_analyzer import load_vision_cache
        vision_data = load_vision_cache(match_id)
        if vision_data is None:
            return ""

    player_info = _load_player_info(match_id)

    # 分组：home=left_team, away=right_team
    for team_label, team_name in [("home", left_team), ("away", right_team)]:
        pass  # just use team_label for filtering

    lines = []
    lines.append("## 球队空间行为总结\n")

    for team_label, team_name in [("home", left_team), ("away", right_team)]:
        team_players = []
        for name, v in vision_data.items():
            info = player_info.get(name, {})
            if v.get("team") != team_label:
                continue
            if not v.get("output", "").strip():
                continue
            # 翻译坐标→足球语言
            translated = _translate_output(v["output"], team_label)
            side = _extract_side_pattern(translated)
            team_players.append({
                "name": name, "pos": v.get("pos", "?"),
                "minutes": v.get("minutes", 0),
                "zscore": info.get("zscore", 0),
                "side": side, "output": translated,
                "carry": _format_carry(info),
            })

        if not team_players:
            continue

        # 分类统计
        side_counts = {"左路主导": 0, "偏左": 0, "中路均衡": 0, "偏右": 0, "右路主导": 0}
        for p in team_players:
            side_counts[p["side"]] = side_counts.get(p["side"], 0) + 1

        # 按贡献排序取前8
        team_players.sort(key=lambda x: -x["zscore"])

        lines.append(f"### {team_name} 空间形态\n")
        lines.append(f"全队空间分布: {side_counts}")
        lines.append(f"\n**贡献值前8球员的空间行为**:\n")

        for p in team_players[:8]:
            lines.append(f"- **{_cn(p['name'])}**（{p['pos']}，{p['minutes']}\"min，{p['side']}）")
            if p["carry"]:
                lines.append(f"  推进: {p['carry']}")
            # 取前两条描述
            desc_lines = [l.strip() for l in p["output"].split("\n") if l.strip()]
            short_desc = " ".join(desc_lines[:2])
            if len(short_desc) > 250:
                short_desc = short_desc[:250] + "..."
            lines.append(f"  {short_desc}")
            lines.append("")

        lines.append("")

    return "\n".join(lines)


def build_pressing_spatial_context(
    match_id: int,
    vision_data: dict | None = None,
) -> str:
    """构建压迫分析专用的空间上下文。

    提取两队进攻核心球员的活动区域特征，
    帮助 LLM 理解「压迫的空间效率」——不是 PPDA 数字高低，
    而是防守方只需在狭窄区域压迫即可。
    """
    if vision_data is None:
        from src.engine.vision_analyzer import load_vision_cache
        vision_data = load_vision_cache(match_id)
        if vision_data is None:
            return ""

    player_info = _load_player_info(match_id)

    # 选每队贡献值最高的前 5 人，取其空间特征
    home_players = []
    away_players = []
    for name, v in vision_data.items():
        info = player_info.get(name, {})
        if not v.get("output", "").strip():
            continue
        entry = (name, v, info)
        if v.get("team") == "home":
            home_players.append(entry)
        else:
            away_players.append(entry)

    home_players.sort(key=lambda x: -x[2].get("zscore", 0))
    away_players.sort(key=lambda x: -x[2].get("zscore", 0))

    lines = []
    lines.append("## 球员空间行为对压迫效率的影响\n")
    lines.append("以下是从球员视觉解析中提取的空间特征，请你在分析压迫时考虑这些事实：\n")

    lines.append(f"### Türkiye（进攻方）关键球员活动特征\n")
    for name, v, info in home_players[:5]:
        carry_str = _format_carry(info)
        translated = _translate_output(v['output'], "home")
        lines.append(f"- **{_cn(name)}**（{v.get('pos','?')}，{v.get('minutes','?')}分钟）：{translated[:200]}...")
        if carry_str:
            lines.append(f"  推进数据: {carry_str}")
        lines.append("")

    lines.append(f"### Paraguay（进攻方/防守方）关键球员活动特征\n")
    for name, v, info in away_players[:5]:
        carry_str = _format_carry(info)
        translated = _translate_output(v['output'], "away")
        lines.append(f"- **{_cn(name)}**（{v.get('pos','?')}，{v.get('minutes','?')}分钟）：{translated[:200]}...")
        if carry_str:
            lines.append(f"  推进数据: {carry_str}")
        lines.append("")

    lines.append("### 压迫分析的指引\n")
    lines.append("请在压迫分析中回答：")
    lines.append("- 土耳其的进攻主要集中在哪个区域（注意「对方半场左路」vs「对方半场右路」的区别）？")
    lines.append("- 这意味着巴拉圭的压迫只需覆盖多宽的区域？")
    lines.append("- 巴拉圭少打一人后，压迫强度为何剧烈下降——是主动放弃还是空间收缩的必然结果？")
    lines.append("- 土耳其的高压迫是否因为自身进攻宽度不足而被对手轻易化解？")

    return "\n".join(lines)


def get_team_structured_players(
    match_id: int,
    vision_data: dict | None = None,
    top_n: int = 8,
) -> tuple[list[dict], list[dict]]:
    """返回两队结构化球员空间数据，供战术速写图表使用。

    Returns:
        (home_players, away_players) 每个元素为 [{name, pos, minutes, zscore, side, output, carry}]
    """
    if vision_data is None:
        from src.engine.vision_analyzer import load_vision_cache
        vision_data = load_vision_cache(match_id)
        if vision_data is None:
            return [], []

    player_info = _load_player_info(match_id)

    home_players = []
    away_players = []
    for name, v in vision_data.items():
        info = player_info.get(name, {})
        if not v.get("output", "").strip():
            continue
        translated = _translate_output(v["output"], v.get("team", "home"))
        entry = {
            "name": name,
            "pos": v.get("pos", "?"),
            "minutes": v.get("minutes", 0),
            "zscore": info.get("zscore", 0),
            "side": _extract_side_pattern(translated),
            "output": translated,
            "carry": _format_carry(info),
        }
        if v.get("team") == "home":
            home_players.append(entry)
        else:
            away_players.append(entry)

    home_players.sort(key=lambda x: -x["zscore"])
    away_players.sort(key=lambda x: -x["zscore"])
    return home_players[:top_n], away_players[:top_n]
