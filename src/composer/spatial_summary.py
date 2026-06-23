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


def _parse_primary_zone(output: str) -> int | None:
    """从视觉模型输出中提取热力活动最强的 18 区编号 (1-18)。"""
    if not output:
        return None
    # 1. "颜色最深的区(域)是X区" (multiline, may have period between)
    m = re.search(r'最深的区(?:域)?是[：:\s]*(\d{1,2})\s*(?:#|号)?区', output)
    if m:
        return int(m.group(1))
    # 2. "X区红色/橙色" followed by "颜色最深" within same zone description
    m = re.search(r'(\d{1,2})\s*#?区\s*(?:为\s*)?(?:红色|橙色)[^；。]*?颜色最深', output)
    if m:
        return int(m.group(1))
    # 3. "X区为红色" or "X区为橙色" (simple fallback, returns first match)
    m = re.search(r'(\d{1,2})\s*#?区\s*(?:为\s*)?红色', output)
    if m:
        return int(m.group(1))
    m = re.search(r'(\d{1,2})\s*#?区\s*(?:为\s*)?橙色', output)
    if m:
        return int(m.group(1))
    return None


def _parse_all_hot_zones(output: str, heatmap_path: str | None = None) -> list[int]:
    """提取球员的热力活动区。

    如果有 heatmap_path：全 18 区像素扫描，以像素真实热力为准。
    否则：从视觉模型输出文本中提取。
    返回去重后的区号列表，红色优先，橙色补充，最多6个。
    """
    if heatmap_path:
        return _parse_hot_zones_from_pixels(heatmap_path)

    # 回退：从模型文本提取
    if not output:
        return []
    red_zones = set()
    orange_zones = set()

    for m in re.finditer(r'(\d{1,2})\s*#?区\s*(?:为\s*)?红色', output):
        red_zones.add(int(m.group(1)))
    for m in re.finditer(r'(\d{1,2})\s*#?区\s*(?:为\s*)?橙色', output):
        z = int(m.group(1))
        if z not in red_zones:
            orange_zones.add(z)

    result = list(red_zones) + list(orange_zones)
    return result[:6]


def _parse_hot_zones_from_pixels(heatmap_path: str) -> list[int]:
    """全 18 区像素级扫描，返回真实热力活动区。

    红色区: R/G >= 1.05 的非白像素 >= 1.5%
    橙色区: R/G >= 1.02 的非白像素 >= 1.5%
    红色优先，橙色补充，最多 6 个。
    """
    red, orange = [], []
    for z in range(1, 19):
        if _validate_zone_heat(z, heatmap_path, "red"):
            red.append(z)
    for z in range(1, 19):
        if z not in red and _validate_zone_heat(z, heatmap_path, "orange"):
            orange.append(z)
    return (red + orange)[:6]


# ── 18 区 → 球场坐标 (像素验证用) ──
_ZONE_PITCH_COORDS = {
    1: (10, 12),  2: (10, 40),  3: (10, 68),
    4: (28, 12),  5: (28, 40),  6: (28, 68),
    7: (48, 12),  8: (48, 40),  9: (48, 68),
    10: (68, 12), 11: (68, 40), 12: (68, 68),
    13: (88, 12), 14: (88, 40), 15: (88, 68),
    16: (108, 12), 17: (108, 40), 18: (108, 68),
}


def _validate_zone_heat(zone: int, heatmap_path: str, level: str = "red") -> bool:
    """像素级热区验证：在热力图 PNG 中采样指定 zone 区域，检查是否有真实的热力活动。

    先找到草坪绿色区域作为真实球场边界，再在球场内映射 zone 坐标。
     level: "red" 要求 R/G >= 1.05 的非白像素占比 >= 1%
            "orange" 要求 R/G >= 1.02 的非白像素占比 >= 1%

     Returns: True 表示该 zone 确实有对应级别的热力活动。
     """
    import numpy as np
    from PIL import Image

    coords = _ZONE_PITCH_COORDS.get(zone)
    if coords is None:
        return False

    try:
        img = Image.open(heatmap_path)
        arr = np.array(img)
    except Exception:
        return True  # 无法读取图片时保留原结果

    h, w = arr.shape[:2]
    R = arr[:, :, 0].astype(float)
    G = arr[:, :, 1].astype(float)

    # 1. 找到草坪区域边界（绿色像素：G明显高且不是纯黑/白）
    green_mask = (G > R * 1.08) & (G > 80) & (G < 253)
    green_rows, green_cols = np.where(green_mask)
    if len(green_rows) < 100:
        return True  # 草坪像素太少，信任模型

    gy0, gy1 = green_rows.min(), green_rows.max()
    gx0, gx1 = green_cols.min(), green_cols.max()

    # 2. zone 坐标映射到草坪区域内的像素
    zx, zy = coords
    px = int(gx0 + (zx / 120) * (gx1 - gx0))
    py = int(gy1 - (zy / 80) * (gy1 - gy0))  # y翻转: pitch y=0→img bottom

    # 3. 在更大区域采样（rad≈图像宽度 15%），排除纯白/纯黑像素
    radius = max(12, int(w * 0.15))
    yy, xx = np.ogrid[:h, :w]
    mask = (xx - px) ** 2 + (yy - py) ** 2 <= radius ** 2
    non_white = (arr[:, :, 0] < 252) | (arr[:, :, 1] < 252) | (arr[:, :, 2] < 252)
    non_black = (R + G) > 30
    valid_mask = mask & non_white & non_black

    if valid_mask.sum() < 30:
        return True

    rg = (R / G.clip(1))[valid_mask]

    # 阈值：低门槛只过滤完全绿色的zone（模型hallucination），保留有微弱热力的
    if level == "red":
        min_ratio = 1.05
        min_pct = 0.015
    else:
        min_ratio = 1.02
        min_pct = 0.015

    warm_pct = (rg >= min_ratio).sum() / valid_mask.sum()
    return warm_pct >= min_pct


def _build_heatmap_path(match_id: int, player_name: str) -> str:
    """构建球员热力图 PNG 文件路径。"""
    from pathlib import Path
    return str(Path(__file__).parent.parent.parent / "data" / str(match_id) / player_name / "heatmap.png")


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
        # 构建热力图路径用于像素级验证
        hp = _build_heatmap_path(match_id, name) if match_id else None
        entry = {
            "name": name,
            "pos": v.get("pos", "?"),
            "minutes": v.get("minutes", 0),
            "zscore": info.get("zscore", 0),
            "side": _extract_side_pattern(translated),
            "output": translated,
            "carry": _format_carry(info),
            "primary_zone": _parse_primary_zone(v.get("output", "")),
            "hot_zones": _parse_all_hot_zones(v.get("output", ""), hp),
        }
        if v.get("team") == "home":
            home_players.append(entry)
        else:
            away_players.append(entry)

    home_players.sort(key=lambda x: -x["zscore"])
    away_players.sort(key=lambda x: -x["zscore"])
    return home_players[:top_n], away_players[:top_n]


# ═══════════════════════════════════════════════
# TacticalSynthesis — 跨球员视觉数据合成
# ═══════════════════════════════════════════════

# ── 18区 → 球队语义映射 ──
# 球场网格: 6列×3行, x=0-120从左到右, y=0-80从下到上
# 画面下方(y=0-26): zones 1,4,7,10,13,16
# 画面中部(y=26-54): zones 2,5,8,11,14,17
# 画面上方(y=54-80): zones 3,6,9,12,15,18
# 主队(左→右攻,面朝右): 画面下=右路, 画面上=左路, zone1-6=防守半场, 13-18=进攻半场
# 客队(右→左攻,面朝左): 画面下=左路, 画面上=右路, zone1-6=进攻半场, 13-18=防守半场

# 每条通道的 zone 集合
_CHANNEL_ZONES = {
    "bottom": {1, 4, 7, 10, 13, 16},   # 画面下方
    "middle": {2, 5, 8, 11, 14, 17},   # 画面中部
    "top":    {3, 6, 9, 12, 15, 18},   # 画面上方
}

# 半场 zone 集合（画面 x 轴）
_HALF_ZONES = {
    "defensive_third": {1, 2, 3, 4, 5, 6},     # 画面左侧 1/3
    "middle_third":    {7, 8, 9, 10, 11, 12},  # 画面中间 1/3
    "attacking_third": {13, 14, 15, 16, 17, 18},  # 画面右侧 1/3
}

# 球员位置分组
_POS_GROUPS = {
    "GK": "门将",
    "D": "后卫", "DR": "后卫", "DL": "后卫", "DC": "后卫",
    "M": "中场", "MR": "中场", "ML": "中场", "MC": "中场",
    "DM": "中场", "AM": "中场",
    "F": "前锋", "FW": "前锋", "ST": "前锋",
    "RW": "前锋", "LW": "前锋", "CF": "前锋",
}


def _zone_to_channel_for_team(zone: int, team: str) -> dict:
    """将 18区区号映射为该队的进攻方向语义。

    Returns:
        {"channel": "进攻左路/中路/右路", "half": "防守/中场/进攻半场"}
    """
    side = None
    for s, zs in _CHANNEL_ZONES.items():
        if zone in zs:
            side = s
            break
    if side is None:
        return {"channel": "未知", "half": "未知"}

    half = None
    for h, zs in _HALF_ZONES.items():
        if zone in zs:
            half = h
            break

    if team == "home":
        channel_map = {"top": "进攻左路", "middle": "中路", "bottom": "进攻右路"}
        half_map = {"defensive_third": "防守半场", "middle_third": "中场", "attacking_third": "进攻半场"}
    else:
        channel_map = {"top": "进攻右路", "middle": "中路", "bottom": "进攻左路"}
        half_map = {"defensive_third": "进攻半场", "middle_third": "中场", "attacking_third": "防守半场"}

    return {"channel": channel_map.get(side, "未知"), "half": half_map.get(half, "未知")}


def _extract_vision_passing(output: str) -> dict:
    """从 vision output 中提取传球方向统计。"""
    result = {"forward": 0, "lateral": 0, "backward": 0, "short": 0, "long": 0}
    m = re.search(r'向前[传球\s]*共?(\d+)\s*次.*?横向[传球\s]*共?(\d+)\s*次.*?回传[共\s]*(\d+)\s*次', output)
    if m:
        result["forward"] = int(m.group(1))
        result["lateral"] = int(m.group(2))
        result["backward"] = int(m.group(3))
    m2 = re.search(r'短传[共\s]*(\d+)\s*次.*?长传[共\s]*(\d+)\s*次', output)
    if m2:
        result["short"] = int(m2.group(1))
        result["long"] = int(m2.group(2))
    return result


def _extract_vision_dribbling(output: str) -> dict:
    """从 vision output 中提取带球推进统计。"""
    result = {"forward": 0, "lateral": 0, "backward": 0}
    m = re.search(r'纵向向前[带球推进\s]*共?(\d+)\s*次.*?横向[带球推进\s]*共?(\d+)\s*次.*?后退[带球推进\s]*共?(\d+)\s*次', output)
    if m:
        result["forward"] = int(m.group(1))
        result["lateral"] = int(m.group(2))
        result["backward"] = int(m.group(3))
    return result


def _extract_vision_shooting(output: str) -> dict:
    """从 vision output 中提取射门统计。"""
    result = {"inside_box": 0, "outside_box": 0, "left": 0, "center": 0, "right": 0}
    m = re.search(r'禁区内[射门\s]*共?(\d+)\s*次.*?禁区外[射门\s]*共?(\d+)\s*次', output)
    if m:
        result["inside_box"] = int(m.group(1))
        result["outside_box"] = int(m.group(2))
    m2 = re.search(r'射门点在[画面]?左侧[共\s]*(\d+)\s*次.*?中间[共\s]*(\d+)\s*次.*?右侧[共\s]*(\d+)\s*次', output)
    if m2:
        result["left"] = int(m2.group(1))
        result["center"] = int(m2.group(2))
        result["right"] = int(m2.group(3))
    return result


def _extract_v6_raw_stats(v6_player: dict) -> dict:
    """从 players_v6.json 的单个球员数据中提取关键原始值。"""
    stats = {}
    contribs = v6_player.get("contributions", {})

    # C1 进攻
    c1 = contribs.get("C1", {}).get("raw_metrics", {})
    for k in ["goals", "assists", "xg", "shots_total", "shots_on", "xgot"]:
        if k in c1:
            stats[k] = c1[k]["raw"]

    # C2 传球
    c2 = contribs.get("C2", {}).get("raw_metrics", {})
    for k in ["passes_total", "pass_accuracy", "key_passes", "crosses_total",
               "long_balls", "long_balls_won", "passes_forward", "passes_final_third"]:
        if k in c2:
            stats[k] = c2[k]["raw"]

    # C3 推进
    c3 = contribs.get("C3", {}).get("raw_metrics", {})
    for k in ["dribbles_total", "dribbles_success", "progressive_runs"]:
        if k in c3:
            stats[k] = c3[k]["raw"]

    # C4 防守
    c4 = contribs.get("C4", {}).get("raw_metrics", {})
    for k in ["tackles_total", "tackles_won", "tackles_interceptions",
               "blocked_shots", "clearances"]:
        if k in c4:
            stats[k] = c4[k]["raw"]

    # C5 对抗
    c5 = contribs.get("C5", {}).get("raw_metrics", {})
    for k in ["duels_total", "duels_won", "duels_won_pct", "aerials_won",
               "ball_recoveries", "fouls_drawn", "fouls_committed"]:
        if k in c5:
            stats[k] = c5[k]["raw"]

    return stats


def _enrich_players(match_id: int, team: str, vision_data: dict) -> list[dict]:
    """为指定球队构建 enriched player 列表，融合像素热区 + vision 方向 + v6 原始值 + carry/defense。

    Returns:
        [{name, cn_name, pos, pos_group, minutes, zscore, hot_zones,
          hot_channels, primary_zone, primary_channel, team,
          passing, dribbling, shooting, carry, defense, v6_stats}]
    """
    v6_path = ROOT / "data" / "computed" / f"{match_id}_players_v6.json"
    v6_all = {}
    if v6_path.exists():
        with open(v6_path, encoding="utf-8") as f:
            for p in json.load(f):
                v6_all[p["name"]] = p

    data_dir = ROOT / "data" / str(match_id)
    players = []

    for name, v in vision_data.items():
        if v.get("team") != team:
            continue
        if not v.get("output", "").strip():
            continue

        v6 = v6_all.get(name, {})
        # 像素热区
        hp = _build_heatmap_path(match_id, name) if match_id else None
        hot_zones = _parse_all_hot_zones(v.get("output", ""), hp)

        # 热区映射到通道
        channels = set()
        halfs = set()
        for z in hot_zones:
            ci = _zone_to_channel_for_team(z, team)
            channels.add(ci["channel"])
            halfs.add(ci["half"])

        primary_zone = _parse_primary_zone(v.get("output", ""))
        primary_channel = _zone_to_channel_for_team(primary_zone, team) if primary_zone else {}

        # Vision 方向统计
        passing = _extract_vision_passing(v["output"])
        dribbling = _extract_vision_dribbling(v["output"])
        shooting = _extract_vision_shooting(v["output"])

        # carry / defense
        carry = {}
        cp = data_dir / name / "carry_data.json"
        if cp.exists():
            with open(cp, encoding="utf-8") as f2:
                carry = json.load(f2)

        defense = {}
        dp = data_dir / name / "def_data.json"
        if dp.exists():
            with open(dp, encoding="utf-8") as f2:
                defense = json.load(f2)

        pos = v.get("pos", "?")
        pos_group = _POS_GROUPS.get(pos, "其他")

        zscore = 0.0
        if v6:
            zscore = round(v6.get("contributions", {}).get("C1", {}).get("zscore", 0), 2)

        players.append({
            "name": name,
            "cn_name": _cn(name),
            "pos": pos,
            "pos_group": pos_group,
            "minutes": v.get("minutes", 0),
            "zscore": zscore,
            "hot_zones": hot_zones,
            "hot_channels": sorted(channels),
            "primary_zone": primary_zone,
            "primary_channel": primary_channel,
            "team": team,
            "passing": passing,
            "dribbling": dribbling,
            "shooting": shooting,
            "carry": carry,
            "defense": defense,
            "v6_stats": _extract_v6_raw_stats(v6) if v6 else {},
        })

    players.sort(key=lambda x: -x["zscore"])
    return players


def _compute_attack_channels(players: list[dict]) -> dict:
    """聚合全队热区到 3 条通道，输出每条通道的球员列表 + 覆盖 zones。"""
    channels = {"进攻左路": [], "中路": [], "进攻右路": []}
    for p in players:
        hot = p.get("hot_zones", [])
        if not hot:
            continue
        # 给球员分配主要通道（热区最多的通道）
        ch_counts = {"进攻左路": 0, "中路": 0, "进攻右路": 0}
        for z in hot:
            ci = _zone_to_channel_for_team(z, p["team"])
            ch_counts[ci["channel"]] += 1
        main_ch = max(ch_counts, key=ch_counts.get)
        # 同时记录所有覆盖到的通道
        for ch in ch_counts:
            if ch_counts[ch] > 0:
                channels[ch].append({
                    "name": p["cn_name"],
                    "zones": hot,
                    "is_main": ch == main_ch,
                })

    # 生成文本
    result = {}
    for ch, members in channels.items():
        if not members:
            result[ch] = {"count": 0, "desc": "无球员覆盖"}
            continue
        # 去重球员（一个球员可能出现在多个通道）
        member_names = sorted(set(m["name"] for m in members))
        # 所有 member 的 zone 合集
        all_zones = set()
        for m in members:
            all_zones.update(m["zones"])

        # 统计半场分布
        half_dist = {"防守半场": 0, "中场": 0, "进攻半场": 0}
        for z in all_zones:
            ci = _zone_to_channel_for_team(z, players[0]["team"])
            half_dist[ci["half"]] += 1

        result[ch] = {
            "count": len(member_names),
            "players": member_names,
            "zones": sorted(all_zones),
            "half_distribution": half_dist,
            "desc": "",
        }
    return result


def _compute_zone_overlap(players: list[dict]) -> list[dict]:
    """统计每个 zone 的球员重叠数，返回重叠 >=2 的区域。"""
    zone_players = {z: [] for z in range(1, 19)}
    for p in players:
        for z in p.get("hot_zones", []):
            zone_players[z].append(p["cn_name"])

    overlaps = []
    for z in range(1, 19):
        if len(zone_players[z]) >= 2:
            ci = _zone_to_channel_for_team(z, players[0]["team"])
            overlaps.append({
                "zone": z,
                "count": len(zone_players[z]),
                "players": zone_players[z],
                "channel": ci["channel"],
                "half": ci["half"],
            })

    overlaps.sort(key=lambda x: -x["count"])
    return overlaps


def _compute_formation_clues(players: list[dict]) -> dict:
    """从热区分布推断阵型线索。"""
    clues = {
        "high_line": False,         # 防线是否压过半场
        "fullback_attack": False,   # 边后卫是否参与进攻
        "midfield_wide": False,     # 中场覆盖面
        "striker_deep": False,      # 前锋是否回撤
        "width_bias": "均衡",       # 进攻宽度偏向
    }

    defenders = [p for p in players if p["pos_group"] == "后卫"]
    midfielders = [p for p in players if p["pos_group"] == "中场"]
    forwards = [p for p in players if p["pos_group"] == "前锋"]

    # 防线高度：后卫热区是否越过中线（zone 10-18）
    def_zones_in_attack = set()
    for d in defenders:
        for z in d.get("hot_zones", []):
            ci = _zone_to_channel_for_team(z, d["team"])
            if ci["half"] == "进攻半场":
                def_zones_in_attack.add(z)
    clues["high_line"] = len(def_zones_in_attack) > 0
    clues["def_zones_in_attack"] = sorted(def_zones_in_attack)

    # 边后卫进攻参与度：是否有后卫热区偏向边路
    fb_wing_count = 0
    for d in defenders:
        for z in d.get("hot_zones", []):
            ci = _zone_to_channel_for_team(z, d["team"])
            if ci["channel"] in ("进攻左路", "进攻右路"):
                fb_wing_count += 1
    clues["fullback_attack"] = fb_wing_count > 0
    clues["fullback_wing_touches"] = fb_wing_count

    # 中场覆盖宽度
    mf_zones = set()
    for m in midfielders:
        mf_zones.update(m.get("hot_zones", []))
    clues["midfield_zones_count"] = len(mf_zones)
    clues["midfield_wide"] = len(mf_zones) >= 6

    # 前锋是否回撤（热区在防守半场/中场）
    fw_deep_zones = set()
    for f in forwards:
        for z in f.get("hot_zones", []):
            ci = _zone_to_channel_for_team(z, f["team"])
            if ci["half"] in ("防守半场", "中场"):
                fw_deep_zones.add(z)
    clues["striker_deep"] = len(fw_deep_zones) > 0
    clues["fw_deep_zones"] = sorted(fw_deep_zones)

    # 进攻宽度偏向
    left_count = 0
    right_count = 0
    center_count = 0
    for p in players:
        for z in p.get("hot_zones", []):
            ci = _zone_to_channel_for_team(z, p["team"])
            ch = ci["channel"]
            if ch == "进攻左路":
                left_count += 1
            elif ch == "进攻右路":
                right_count += 1
            else:
                center_count += 1

    if left_count > right_count * 1.5:
        clues["width_bias"] = "偏左"
    elif right_count > left_count * 1.5:
        clues["width_bias"] = "偏右"
    else:
        clues["width_bias"] = "均衡"
    clues["width_counts"] = {"左路": left_count, "中路": center_count, "右路": right_count}

    return clues


def _compute_passing_profile(players: list[dict]) -> dict:
    """聚合全队 vision 传球方向统计。"""
    total = {"forward": 0, "lateral": 0, "backward": 0, "short": 0, "long": 0}
    for p in players:
        pas = p.get("passing", {})
        total["forward"] += pas.get("forward", 0)
        total["lateral"] += pas.get("lateral", 0)
        total["backward"] += pas.get("backward", 0)
        total["short"] += pas.get("short", 0)
        total["long"] += pas.get("long", 0)

    all_passes = total["forward"] + total["lateral"] + total["backward"]
    if all_passes > 0:
        return {
            "total": all_passes,
            "forward_pct": round(total["forward"] / all_passes * 100),
            "lateral_pct": round(total["lateral"] / all_passes * 100),
            "backward_pct": round(total["backward"] / all_passes * 100),
            "short": total["short"],
            "long": total["long"],
        }
    return {"total": 0, "forward_pct": 0, "lateral_pct": 0, "backward_pct": 0, "short": 0, "long": 0}


def _format_key_stat(v6_stats: dict, key: str, label: str) -> str | None:
    """格式化单个关键统计，“哈兰德进球2/预期进球0.71”。"""
    val = v6_stats.get(key)
    if val is None:
        return None
    if isinstance(val, float):
        return f"{label}{val:.1f}" if val >= 1 else f"{label}{val:.2f}"
    return f"{label}{val}"


def _format_player_key_stats(player: dict, top_n: int = 5) -> str:
    """为一个球员输出最多 top_n 条关键统计。"""
    v6 = player.get("v6_stats", {})
    carry = player.get("carry", {})
    defense = player.get("defense", {})

    stat_defs = [
        ("goals", "进球"), ("xg", "预期进球"), ("shots_total", "射门"), ("shots_on", "射正"),
        ("key_passes", "关键传球"), ("passes_total", "传球"), ("pass_accuracy", "传球成功率"),
        ("crosses_total", "传中"), ("long_balls_won", "长传成功"),
        ("dribbles_total", "过人尝试"), ("dribbles_success", "过人成功"),
        ("tackles_total", "抢断"), ("interceptions", "拦截"), ("clearances", "解围"),
        ("ball_recoveries", "恢复球权"), ("duels_won_pct", "对抗成功率"),
    ]

    items = []
    for key, label in stat_defs:
        s = _format_key_stat(v6, key, label)
        if s:
            items.append(s)
        if len(items) >= top_n:
            break

    # 补充 carry
    if carry and len(items) < top_n:
        cd = carry.get("Total carrying distance", "")
        if cd:
            items.append(f"推进{cd}")

    return " / ".join(items) if items else ""


def _describe_zones(zones: list, team: str) -> str:
    """将zone编号列表转为自然语言描述（LLM友好，不暴露数字）。

    Args:
        zones: zone编号列表 e.g. [14, 17, 18]
        team: "home" 或 "away"

    Returns:
        自然语言描述 e.g. "前场右路(2处)" 或 "后场中路、中场左路"
    """
    if not zones:
        return "无"
    from collections import defaultdict
    # 紧凑标签
    half_compact = {"防守半场": "后场", "中场": "中场", "进攻半场": "前场"}
    ch_compact = {"进攻左路": "左路", "中路": "中路", "进攻右路": "右路"}
    groups: dict = defaultdict(list)
    for z in zones:
        ci = _zone_to_channel_for_team(z, team)
        key = (ci["channel"], ci["half"])
        groups[key].append(z)
    parts = []
    for (ch, hf), zs in groups.items():
        hf_c = half_compact.get(hf, hf)
        ch_c = ch_compact.get(ch, ch)
        if len(zs) == 1:
            parts.append(f"{hf_c}{ch_c}")
        else:
            parts.append(f"{hf_c}{ch_c}({len(zs)}处)")
    return "、".join(parts)


def build_team_tactical_synthesis(match_id: int) -> str:
    """主入口：为一场比赛生成两队跨球员战术合成文本，供 LLM 消费。

    Returns:
        str: 结构化中文文本块，直接插入 fusion_report prompt 的「战术速写」章节。
    """
    from src.engine.vision_analyzer import load_vision_cache

    vision_data = load_vision_cache(match_id)
    if vision_data is None:
        return "（视觉解析数据不可用）"

    # 获取队名
    output_dir = ROOT / "output"
    home_name = "主队"
    away_name = "客队"
    for d in output_dir.iterdir():
        if d.is_dir() and d.name.startswith(f"{match_id}_"):
            parts = d.name.split("_vs_")
            if len(parts) == 2:
                home_name = parts[0].replace(f"{match_id}_", "")
                away_name = parts[1]
                break

    lines = []
    for team, team_name in [("home", home_name), ("away", away_name)]:
        players = _enrich_players(match_id, team, vision_data)
        if not players:
            lines.append(f"【{team_name} 进攻体系合成】\n数据不可用\n")
            continue

        # 只取热区非空且有意义的球员（GK 除外）
        active_players = [p for p in players if p["hot_zones"] and p["pos"] != "GK"]

        channels = _compute_attack_channels(active_players)
        overlaps = _compute_zone_overlap(active_players)
        formation = _compute_formation_clues(active_players)
        passing = _compute_passing_profile(active_players)

        attack_dir = "从左→右" if team == "home" else "从右→左"

        lines.append(f"【{team_name} 进攻体系合成】")
        lines.append(f"攻击方向: {attack_dir}")

        # ── 传球整体倾向 ──
        if passing["total"] > 0:
            lines.append(f"全队传球倾向: 向前{passing['forward_pct']}% / "
                         f"横向{passing['lateral_pct']}% / 回传{passing['backward_pct']}% "
                         f"(短传{passing['short']} / 长传{passing['long']})")

        # ── 宽度偏向 ──
        wc = formation.get("width_counts", {})
        left_c = wc.get('左路', 0)
        center_c = wc.get('中路', 0)
        right_c = wc.get('右路', 0)
        if center_c >= left_c and center_c >= right_c:
            width_desc = "进攻重心在中路"
        elif left_c >= right_c:
            width_desc = "进攻重心偏左路"
        else:
            width_desc = "进攻重心偏右路"
        lines.append(f"进攻倾向: {width_desc}")

        # ── 3 条通道（倾向描述，不暴露人数）──
        # 计算各通道占比来确定倾向等级
        ch_total = sum(channels.get(ch, {}).get("count", 0) for ch in ["进攻左路", "中路", "进攻右路"]) or 1
        for ch in ["进攻左路", "中路", "进攻右路"]:
            ch_info = channels.get(ch, {})
            count = ch_info.get("count", 0)
            if count == 0:
                continue
            ratio = count / ch_total
            if ratio >= 0.40:
                level = "主力方向"
            elif ratio >= 0.25:
                level = "辅助通道"
            else:
                level = "次要通道"

            player_list = ch_info.get("players", [])
            zone_list = ch_info.get("zones", [])
            zone_desc = _describe_zones(zone_list, team)
            show_names = player_list[:4]
            show_str = '、'.join(show_names)
            lines.append(f"◆ {ch}: {level} — {show_str}")
            lines.append(f"   覆盖: {zone_desc}")

        # ── 热区重叠（精简为枢纽描述）──
        if overlaps and overlaps[0]["count"] >= 3:
            o = overlaps[0]
            zdesc = _describe_zones([o['zone']], team)
            show_names = o['players'][:4]
            show_str = '、'.join(show_names)
            lines.append(f"控制枢纽: {zdesc} — {show_str} 在此区域反复接球组织")

        # ── 阵型线索 ──
        lines.append("阵型线索:")
        if formation["high_line"]:
            def_zones = formation.get('def_zones_in_attack', [])
            def_desc = _describe_zones(def_zones, team) if def_zones else ""
            lines.append(f"  ● 防线高位: 后卫热区前压至{def_desc}")
        else:
            lines.append(f"  ● 防线保持在本方半场，后卫未过半场")
        if formation["fullback_attack"]:
            lines.append(f"  ● 边后卫参与进攻: {formation.get('fullback_wing_touches', 0)}次边路区域覆盖")
        else:
            lines.append(f"  ● 边后卫未明显参与边路进攻")
        lines.append(f"  ● 中场覆盖: {formation.get('midfield_zones_count', 0)}个区域"
                     f"{'（覆盖面广）' if formation['midfield_wide'] else ''}")
        if formation["striker_deep"]:
            fw_zones = formation.get('fw_deep_zones', [])
            fw_desc = _describe_zones(fw_zones, team) if fw_zones else ""
            lines.append(f"  ● 前锋回撤: 热区延伸到中场/后场 — {fw_desc}")
        else:
            lines.append(f"  ● 前锋基本不参与回撤，主要活动在进攻半场")

        # ── 关键球员数据卡 Top 8 ──
        lines.append("")
        lines.append(f"【{team_name} 关键球员数据卡】")
        for p in players[:8]:
            hot = p.get("hot_zones", [])
            primary = p.get("primary_zone")
            hot_desc = _describe_zones(hot, team)
            hot_str = f"活动区域: {hot_desc}"
            if primary:
                primary_desc = _describe_zones([primary], team)
                hot_str += f"（核心: {primary_desc}）"
            pass_str = ""
            pas = p.get("passing", {})
            if pas.get("forward", 0) + pas.get("lateral", 0) > 0:
                pass_str = f"传球:前{pas.get('forward',0)}/横{pas.get('lateral',0)}/回{pas.get('backward',0)}"
            carry_str = ""
            carry = p.get("carry", {})
            if carry:
                cd = carry.get("Total carrying distance", "")
                ct = carry.get("Touches", "")
                if cd or ct:
                    carry_str = f"推进{cd} 触球{ct}"
            key_stats = _format_player_key_stats(p, top_n=4)
            lines.append(f"◆ {p['cn_name']} ({p['pos']}, {p['minutes']}min, z={p['zscore']})")
            lines.append(f"   {hot_str}")
            if pass_str:
                lines.append(f"   {pass_str}")
            if carry_str:
                lines.append(f"   {carry_str}")
            if key_stats:
                lines.append(f"   v6: {key_stats}")

        lines.append("")

    return "\n".join(lines)
