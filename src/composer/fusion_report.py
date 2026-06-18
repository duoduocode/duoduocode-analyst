"""
融合比赛报道组装模块

将战术分析段落 + 压迫分析段落 + 关键事件时间线 + 新闻摘要
组装为 LLM prompt，生成战术+叙事融合的比赛报道文章。
"""

from __future__ import annotations

import re
from typing import Optional

from src.collector.api_client import RawMatchData, MatchEvent
from src.composer.prompt_loader import PromptLoader


# ═══════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════

def parse_narrative_sections(text: str) -> dict[str, str]:
    """解析 LLM 输出的【标签】分段文本。"""
    sections = {}
    for m in re.finditer(r"【(.+?)】\s*\n(.*?)(?=\n【|\Z)", text, re.DOTALL):
        sections[m.group(1).strip()] = m.group(2).strip()
    return sections


def _fmt_val(v) -> str:
    if isinstance(v, float):
        return f"{v:.3f}" if abs(v) < 1 else f"{v:.1f}"
    return str(v)


# ═══════════════════════════════════════════════
# 事件时间线 — 带可信度标记
# ═══════════════════════════════════════════════

def build_event_timeline_with_trust(raw: RawMatchData) -> str:
    """构建带可信度标记的关键事件时间线字符串。"""
    important_types = ("Goal", "Card", "subst", "VAR")
    events: list[MatchEvent] = [
        e for e in raw.events
        if e.event_type in important_types
        and e.detail not in ("pen_shootout_goal", "pen_shootout_miss")
    ]
    events.sort(key=lambda e: e.time_elapsed)

    lines = []
    for e in events:
        # 构建已知信息
        known = []
        team_name = raw.home_team.name if e.team_id == raw.home_team.id else raw.away_team.name
        known.append(f"分钟: 第{e.time_elapsed}分钟")
        known.append(f"球队: {team_name}")
        known.append(f"球员: {e.player_name or '未知'}")

        # 事件类型
        type_map = {"Goal": "进球", "Card": "纪律处罚", "subst": "换人", "VAR": "VAR介入"}
        event_cn = type_map.get(e.event_type, e.event_type)

        # 助攻（仅当数据中存在）
        if e.assist_name:
            known.append(f"助攻者: {e.assist_name}")

        # 进球方式（仅当 detail 指明）
        if e.detail == "owngoal":
            known.append("进球方式: 乌龙球")
        elif e.detail == "goal_penalty":
            known.append("进球方式: 点球")
        elif e.detail == "missed_penalty":
            known.append("结果: 点球罚失")
        elif e.event_type == "Goal" and e.detail not in ("owngoal", "goal_penalty", "missed_penalty"):
            # 普通进球，未注明方式 → 不可描述方式
            known.append("进球方式: 数据未提供（禁止脑补射门方式）")

        # 红黄牌
        if e.detail == "yellowcard":
            known.append("处罚: 黄牌")
        elif e.detail in ("redcard", "yellowredcard"):
            known.append("处罚: 红牌")

        # 组装描述指引
        desc_guide = _build_safe_description(e, team_name)

        lines.append(f"  [{event_cn}] 已知信息: {' | '.join(known)}")
        lines.append(f"    安全描述指引: {desc_guide}")
        lines.append("")

    if not lines:
        return "  （无关键事件）"

    return "\n".join(lines)


def _build_safe_description(e: MatchEvent, team_name: str) -> str:
    """根据已知数据构建安全的事件描述指引。"""
    player = e.player_name or "某球员"

    if e.event_type == "Goal":
        if e.detail == "owngoal":
            return f"你可以写：{team_name}的{player}打入乌龙球。"
        elif e.detail == "goal_penalty":
            if e.assist_name:
                return f"你可以写：{player}点球命中（{e.assist_name}制造点球）。"
            return f"你可以写：{player}点球命中。"
        elif e.detail == "missed_penalty":
            return f"你可以写：{player}点球罚失。"
        else:
            if e.assist_name:
                return f"你可以写：{player}破门得分（{e.assist_name}助攻）。禁止脑补射门方式（头球/推射/远射等），也禁止脑补传球路线。"
            else:
                return f"你可以写：{player}破门得分。禁止脑补助攻者、射门方式和配合细节。"

    elif e.event_type == "Card":
        card_type = "黄牌" if "yellow" in (e.detail or "") else "红牌"
        return f"你可以写：{player}吃到{card_type}。"

    elif e.event_type == "subst":
        return f"你可以写：{player}被换下/换上（换人事件）。"

    elif e.event_type == "VAR":
        return f"你可以写：VAR介入，涉及球员{player}。"

    return f"你可以描述为一次{e.event_type}事件。"


# ═══════════════════════════════════════════════
# 战术维度数据组装
# ═══════════════════════════════════════════════

def _build_dim_summary(tactical_data: dict, home_name: str, away_name: str) -> str:
    """组装战术维度对比表。"""
    hr = tactical_data["home"]["tactical_raw"]
    ar = tactical_data["away"]["tactical_raw"]

    dim_labels = [
        ("possession_pct",          "控球率",            "%"),
        ("pass_volume",             "总传球数",          "次"),
        ("long_ball_ratio",         "长传占比",          ""),
        ("cross_ratio",             "传中占比",          ""),
        ("final_third_pass_ratio",  "进攻三区传球占比",  ""),
        ("forward_ratio",           "向前传球比例",      ""),
        ("passes_per_shot",         "每射门所需传球数",  "次"),
        ("ppda",                    "压迫强度(越低越强)", ""),
        ("high_press_ratio",        "高位抢断比例",      ""),
        ("clearance_ratio",         "封堵/解围倾向",     ""),
    ]
    lines = []
    for key, label, unit in dim_labels:
        hv = hr.get(key, 0)
        av = ar.get(key, 0)
        lines.append(f"  {label:18s}  {home_name} {_fmt_val(hv)}{unit}  vs  {away_name} {_fmt_val(av)}{unit}")
    return "\n".join(lines)


def _build_possession_story(match_flow: dict, home_name: str, away_name: str) -> str:
    """组装控球率逐窗口变化描述。"""
    poss_trend = match_flow.get("possession_trend", {})
    h_poss = poss_trend.get("home", [])
    a_poss = poss_trend.get("away", [])
    if not h_poss:
        return "  （控球率逐窗口数据不可用）"

    windows = ["0-15'", "15-30'", "30-45'", "45-60'", "60-75'", "75-90'"]
    lines = []
    for i, wn in enumerate(windows):
        if i < len(h_poss):
            lines.append(f"  {wn}  {home_name} {h_poss[i]}% vs {away_name} {a_poss[i]}%")
    return "\n".join(lines)


def _build_shot_story(match_flow: dict, home_name: str, away_name: str) -> str:
    """组装射门逐窗口分布描述。"""
    shot_segs = match_flow.get("shot_segments", {})
    h_shots = shot_segs.get("home", [])
    a_shots = shot_segs.get("away", [])
    h_on = shot_segs.get("home_on", h_shots)
    a_on = shot_segs.get("away_on", a_shots)
    h_xg = shot_segs.get("home_xg", [])
    a_xg = shot_segs.get("away_xg", [])
    h_xgot = shot_segs.get("home_xgot", [])
    a_xgot = shot_segs.get("away_xgot", [])

    if not h_shots:
        return "  （射门逐窗口数据不可用）"

    windows = ["0-15'", "15-30'", "30-45'", "45-60'", "60-75'", "75-90'"]
    lines = []
    for i, wn in enumerate(windows):
        if i < len(h_shots):
            h_s = h_shots[i]
            a_s = a_shots[i]
            h_s_on = h_on[i] if i < len(h_on) else 0
            a_s_on = a_on[i] if i < len(a_on) else 0
            h_x = h_xg[i] if i < len(h_xg) else 0
            a_x = a_xg[i] if i < len(a_xg) else 0
            lines.append(f"  {wn}  {home_name} {h_s}射({h_s_on}正) xG {h_x:.3f}   vs   {away_name} {a_s}射({a_s_on}正) xG {a_x:.3f}")

    h_xg_total = shot_segs.get("home_xg_total", 0)
    a_xg_total = shot_segs.get("away_xg_total", 0)
    h_xgot_total = shot_segs.get("home_xgot_total", 0)
    a_xgot_total = shot_segs.get("away_xgot_total", 0)

    lines.append(f"\n  全场累计: {home_name} xG {h_xg_total:.2f} / xGOT {h_xgot_total:.2f};  {away_name} xG {a_xg_total:.2f} / xGOT {a_xgot_total:.2f}")

    if h_xgot_total > 0 and h_xg_total > 0:
        h_quality = "射门质量高" if h_xgot_total > h_xg_total * 0.9 else "射门质量偏低"
        lines.append(f"  ({home_name} {h_quality})")
    if a_xgot_total > 0 and a_xg_total > 0:
        a_quality = "射门质量高" if a_xgot_total > a_xg_total * 0.9 else "射门质量偏低"
        lines.append(f"  ({away_name} {a_quality})")

    return "\n".join(lines)


def _build_event_impact_text(match_flow: dict) -> str:
    """组装事件冲击窗口描述。"""
    impact_windows = match_flow.get("event_impact_windows", [])
    if not impact_windows:
        return "  （无进球事件冲击数据）"

    lines = []
    for iw in impact_windows:
        mi = iw["minute"]
        player = iw["player"]
        etype = iw["event_type"]

        gt = "goal_team"
        op = "opponent"
        poss = iw["possession"]
        sht = iw["shots"]
        xg = iw["xg_approx"]

        g_poss_delta = poss[gt]["after"] - poss[gt]["before"]
        o_poss_delta = poss[op]["after"] - poss[op]["before"]
        g_poss_dir = "上升" if g_poss_delta > 2 else "下降" if g_poss_delta < -2 else "持平"
        o_poss_dir = "上升" if o_poss_delta > 2 else "下降" if o_poss_delta < -2 else "持平"

        g_shot_delta = sht[gt]["after"] - sht[gt]["before"]
        o_shot_delta = sht[op]["after"] - sht[op]["before"]

        lines.append(f"  {mi}' {etype}（{player}）前后窗口对比:")
        lines.append(f"    进球方控球率: {poss[gt]['before']}% → {poss[gt]['after']}%（{g_poss_dir}{abs(g_poss_delta):.1f}%）")
        lines.append(f"    对方控球率:   {poss[op]['before']}% → {poss[op]['after']}%（{o_poss_dir}{abs(o_poss_delta):.1f}%）")
        lines.append(f"    进球方射门:   {sht[gt]['before']} → {sht[gt]['after']}（{'+' if g_shot_delta > 0 else ''}{g_shot_delta}）")
        lines.append(f"    对方射门:     {sht[op]['before']} → {sht[op]['after']}（{'+' if o_shot_delta > 0 else ''}{o_shot_delta}）")
        lines.append(f"    进球方xG近似: {xg[gt]['before']} → {xg[gt]['after']}（{'+' if xg[gt]['after'] - xg[gt]['before'] > 0 else ''}{xg[gt]['after'] - xg[gt]['before']:.3f}）")
        lines.append(f"    对方xG近似:   {xg[op]['before']} → {xg[op]['after']}（{'+' if xg[op]['after'] - xg[op]['before'] > 0 else ''}{xg[op]['after'] - xg[op]['before']:.3f}）")
        lines.append("")

    return "\n".join(lines)


def _build_exec_narrative(td: dict, hn: str, an: str) -> str:
    """战术执行效果 — 自然语言描述。"""
    dim_names = {
        "possession": "传控渗透", "long_ball": "长传冲击", "crossing": "传中抢点",
        "penetration": "三区穿插", "directness": "向前推进",
        "press_intensity": "压迫限制", "high_press": "高位抢断",
        "deep_block": "落位防守", "interception": "线路拦截",
    }

    parts = []
    for tkey, tname in [("home", hn), ("away", an)]:
        ex = td[tkey]["execution"]
        lines = [f"{tname}:"]

        ad = ex["attack"]["dimensions"]
        if ad:
            pos_dims = [d for d in ad if d["score"] > 0]
            neg_dims = [d for d in ad if d["score"] <= 0]
            if pos_dims:
                names = [dim_names.get(d["dim"], d["dim"]) for d in pos_dims]
                lines.append(f"  进攻做得好的方面: {'、'.join(names)}")
            if neg_dims:
                names = [dim_names.get(d["dim"], d["dim"]) for d in neg_dims]
                lines.append(f"  进攻效率偏低的方面: {'、'.join(names)}")
        else:
            lines.append("  进攻无明确的优势维度")

        dd = ex["defense"]["dimensions"]
        if dd:
            pos_dims = [d for d in dd if d["score"] > 0]
            neg_dims = [d for d in dd if d["score"] <= 0]
            if pos_dims:
                names = [dim_names.get(d["dim"], d["dim"]) for d in pos_dims]
                lines.append(f"  防守做得好的方面: {'、'.join(names)}")
            if neg_dims:
                names = [dim_names.get(d["dim"], d["dim"]) for d in neg_dims]
                lines.append(f"  防守存在漏洞的方面: {'、'.join(names)}")
        else:
            lines.append("  防守无明确的优势维度")

        parts.append("\n".join(lines))

    return "\n\n".join(parts)


def _build_coaching_narrative(coaching: dict, hn: str, an: str) -> str:
    """教练博弈 — 自然语言描述。"""
    style_labels = {
        "possession_vs_counter": f"传控对防守反击 — {hn}更倾向于控球组织，{an}更依赖快速转换",
        "possession_dominant": f"单方控球主导 — 一方完全掌控球权，另一方被动应对",
        "long_ball_vs_press": "长传冲击对高位压迫 — 双方在纵向空间上互相考验",
        "direct_duel": "双方均依赖长传快攻 — 比赛在快速转换中展开",
        "mirror_match": "镜像对决 — 双方战术风格高度相似",
        "mixed_styles": "混合风格 — 双方战术特征没有形成清晰的对抗轴",
    }
    clash = style_labels.get(coaching.get("style_clash", ""), "混合风格")

    pairs = coaching.get("mismatch_pairs", [])
    dim_names = {
        "possession": "传控渗透", "long_ball": "长传冲击", "crossing": "传中抢点",
        "penetration": "三区穿插", "directness": "向前推进",
        "press_intensity": "压迫限制", "high_press": "高位抢断",
        "deep_block": "落位防守", "interception": "线路拦截",
    }

    pair_lines = []
    for p in pairs:
        ot = hn if p.get("off_team") == "home" else an
        off_label = dim_names.get(p["off_dim"], p["off_dim"])
        def_label = dim_names.get(p["def_dim"], p["def_dim"])
        r = p.get("result", 0)
        if r > 0:
            pair_lines.append(f"  {ot} 的 {off_label} 成功打破了对方的 {def_label}")
        else:
            pair_lines.append(f"  {ot} 的 {off_label} 被对方的 {def_label} 有效限制")

    coaching_story = f"风格碰撞: {clash}\n"
    if pair_lines:
        coaching_story += "战术对位:\n" + "\n".join(pair_lines)

    return coaching_story


def _interpret_ppda_value(val) -> str:
    """将 PPDA 数值转为自然语言描述（不用PPDA这个词）。"""
    if val is None or val == 0:
        return "数据不可用"
    v = float(val)
    if v < 5:
        return f"压迫极强——对手每推进{v:.1f}脚传球就被抢断或拦截"
    elif v < 8:
        return f"压迫较紧——对手每{v:.1f}脚传球遭遇一次有效防守"
    elif v < 12:
        return f"压迫适中——对手每{v:.1f}脚传球才遇到一次防守干扰"
    elif v < 18:
        return f"压迫偏松——对手每{v:.1f}脚传球才被有效干扰一次"
    else:
        return f"压迫很松——对手每{v:.1f}脚传球才遇到一次防守动作"


# ═══════════════════════════════════════════════
# 主入口：组装融合 Prompt
# ═══════════════════════════════════════════════

def build_fusion_prompt(
    raw: RawMatchData,
    tactical_data: dict,
    tactical_narrative: str,
    pressing_narrative: str,
    pre_news: str = "",
    match_news: str = "",
    post_news: str = "",
    loader: PromptLoader | None = None,
    match_overview: str = "",
) -> tuple[str, str]:
    """组装融合比赛报道的 LLM prompt。

    Returns:
        (system_prompt, user_prompt)
    """
    if loader is None:
        loader = PromptLoader("prompts")

    home_name = raw.home_team.name
    away_name = raw.away_team.name
    score = raw.score
    total_home, total_away = _compute_full_score(raw)[:2]

    mf = tactical_data["match_flow"]
    coaching = tactical_data["coaching"]

    # ── 解析现有叙述段落 ──
    tac_sections = parse_narrative_sections(tactical_narrative)
    prs_sections = parse_narrative_sections(pressing_narrative)

    # ── 比赛上下文 ──
    stage_name = ""
    venue_name = ""
    if raw.stage_info:
        stage_name = raw.stage_info.get("name", "")
    if raw.venue_info:
        venue_name = raw.venue_info.get("name", "")

    match_ctx_lines = []
    if stage_name:
        match_ctx_lines.append(f"赛事：{stage_name}")
    if venue_name:
        match_ctx_lines.append(f"场地：{venue_name}")
    match_ctx_lines.append(f"对阵：{home_name} vs {away_name}")
    match_ctx_lines.append(f"全场比分：{home_name} {total_home} - {total_away} {away_name}")
    match_ctx_lines.append(f"半场比分：{score.halftime_home} - {score.halftime_away}")
    if score.home > score.away:
        match_ctx_lines.append(f"胜者：{home_name}")
    elif score.away > score.home:
        match_ctx_lines.append(f"胜者：{away_name}")
    else:
        match_ctx_lines.append("结果：双方打平")

    match_context = "\n".join(match_ctx_lines)

    # ── 组装素材 ──
    dim_summary = _build_dim_summary(tactical_data, home_name, away_name)
    possession_story = _build_possession_story(mf, home_name, away_name)
    shot_story = _build_shot_story(mf, home_name, away_name)
    event_timeline = build_event_timeline_with_trust(raw)
    event_impact_text = _build_event_impact_text(mf)
    exec_story = _build_exec_narrative(tactical_data, home_name, away_name)
    coaching_story = _build_coaching_narrative(coaching, home_name, away_name)

    # PPDA
    ppda_h = mf.get("ppda", {}).get("home", {})
    ppda_a = mf.get("ppda", {}).get("away", {})
    ppda_hv = ppda_h.get("full_match", 0)
    ppda_av = ppda_a.get("full_match", 0)

    return loader.render(
        "fusion_report",
        match_context=match_context,
        pre_news=pre_news,
        match_news=match_news,
        post_news=post_news,
        dim_summary=dim_summary,
        possession_story=possession_story,
        shot_story=shot_story,
        home_name=home_name,
        away_name=away_name,
        ppda_home_label=_interpret_ppda_value(ppda_hv),
        ppda_away_label=_interpret_ppda_value(ppda_av),
        event_timeline=event_timeline,
        event_impact_text=event_impact_text,
        tactical_portrait=tac_sections.get("战术画像", "（无）"),
        tactical_deduction=tac_sections.get("战术演绎", "（无）"),
        tactical_verification=tac_sections.get("战术验证", "（无）"),
        tactical_game=tac_sections.get("战术博弈", "（无）"),
        tactical_verdict=tac_sections.get("战术定论", "（无）"),
        tactical_oneline=tac_sections.get("一句话总结", "（无）"),
        pressing_layout=prs_sections.get("压迫布局", "（无）"),
        pressing_return=prs_sections.get("压迫回报", "（无）"),
        pressing_cost=prs_sections.get("压迫代价", "（无）"),
        exec_story=exec_story,
        coaching_story=coaching_story,
    )


def _compute_full_score(raw) -> tuple:
    """计算全场比分（含加时+点球）。"""
    score = raw.score
    home_id = raw.home_team.id
    pen_home = pen_away = 0
    for e in raw.events:
        if e.event_type == "Goal" and e.detail == "pen_shootout_goal":
            if e.team_id == home_id:
                pen_home += 1
            else:
                pen_away += 1
    total_home = score.home + (score.extratime_home or 0) + pen_home
    total_away = score.away + (score.extratime_away or 0) + pen_away
    return total_home, total_away, pen_home, pen_away


# ═══════════════════════════════════════════════
# HTML 渲染
# ═══════════════════════════════════════════════

def _md_to_html_sections(md_text: str, images_dir_rel: str = "images") -> str:
    """将 LLM 输出的 Markdown 转换为 HTML sections。

    LLM 输出格式预期：
      # 标题
      ## 段落名
      正文...
      > **[配图N]** path
      > **读图**：说明
    """
    import html as html_mod

    lines = md_text.strip().split("\n")
    result = []
    in_paragraph = False
    in_blockquote = False
    para_lines = []
    bq_lines = []

    def flush_para():
        nonlocal in_paragraph, para_lines
        if para_lines:
            text = " ".join(para_lines).strip()
            if text:
                result.append(f"<p>{text}</p>")
            para_lines = []
        in_paragraph = False

    def flush_bq():
        nonlocal in_blockquote, bq_lines
        if bq_lines:
            text = "\n".join(bq_lines)
            # 检查是否为配图引用
            if "**配图" in text or "**读图**" in text:
                # 将配图块渲染为图片+说明卡片
                img_match = re.search(r"\*\*\[配图\d+\]\*\*\s*(.+?)(?:\n|$)", text)
                caption_match = re.search(r"\*\*读图\*\*[：:]\s*(.+)", text, re.DOTALL)

                img_path = ""
                if img_match:
                    img_path = img_match.group(1).strip()
                    # 清理可能的 markdown 链接格式
                    img_path = re.sub(r"^[`\"]+|[`\"]+$", "", img_path)

                caption = ""
                if caption_match:
                    caption = caption_match.group(1).strip()

                if img_path:
                    # 提取文件名
                    fname = img_path.split("/")[-1]
                    result.append(
                        '<div style="margin:20px 0;text-align:center">'
                        f'<img src="{images_dir_rel}/{fname}" alt="配图" '
                        f'style="max-width:100%;border-radius:8px;border:1px solid #1e3a4d">'
                    )
                    if caption:
                        result.append(
                            f'<p style="font-size:12px;color:#8ab4d6;margin:8px 0 0;'
                            f'line-height:1.6;text-align:left">{html_mod.escape(caption)}</p>'
                        )
                    result.append('</div>')
            else:
                result.append(
                    f'<blockquote style="border-left:3px solid #f1c40f;padding:8px 14px;'
                    f'margin:12px 0;color:#c0d6e4;background:rgba(241,196,15,0.06);border-radius:0 6px 6px 0">'
                    f'{html_mod.escape(text)}</blockquote>'
                )
            bq_lines = []
        in_blockquote = False

    for line in lines:
        stripped = line.strip()

        # 一级标题 → 文章大标题
        if stripped.startswith("# ") and not stripped.startswith("## "):
            flush_para()
            flush_bq()
            result.append(f'<h2 style="color:#fff;font-size:20px;text-align:center;margin:8px 0 20px">{html_mod.escape(stripped[2:])}</h2>')
            continue

        # 二级标题
        if stripped.startswith("## "):
            flush_para()
            flush_bq()
            result.append(
                f'<h3 style="color:#2ecc71;font-size:17px;border-bottom:1px solid #1e3a4d;'
                f'padding-bottom:6px;margin:24px 0 12px">{html_mod.escape(stripped[3:])}</h3>'
            )
            continue

        # 空行
        if not stripped:
            flush_para()
            flush_bq()
            continue

        # 引用块
        if stripped.startswith(">"):
            if in_blockquote:
                bq_lines.append(stripped[1:].strip())
            else:
                flush_para()
                in_blockquote = True
                bq_lines = [stripped[1:].strip()]
            continue

        # 普通段落
        if in_blockquote:
            flush_bq()
        in_paragraph = True
        para_lines.append(stripped)

    flush_para()
    flush_bq()

    return "\n".join(result)


def generate_fusion_html(
    fusion_md: str,
    home_name: str,
    away_name: str,
    score_home: int,
    score_away: int,
    output_dir: str,
    stage_name: str = "",
    venue_name: str = "",
) -> str:
    """生成融合报道的独立 HTML 文件。

    Returns:
        HTML 文件路径
    """
    import os
    from pathlib import Path

    BG = "#0f1923"
    FG = "#d0d8e0"
    GREEN = "#2ecc71"
    CARD_BG = "#162a38"
    BORDER = "#1e3a4d"
    GOLD = "#f1c40f"

    H = []
    H.append('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">')
    H.append('<meta name="viewport" content="width=device-width, initial-scale=1.0">')
    H.append(f'<title>融合比赛报道 — {home_name} vs {away_name}</title>')
    H.append('<style>')
    H.append(f'*{{margin:0;padding:0;box-sizing:border-box}}')
    H.append(f'body{{font-family:"Microsoft YaHei","PingFang SC",sans-serif;background:{BG};color:{FG};line-height:1.9;font-size:15px}}')
    H.append(f'.container{{max-width:860px;margin:0 auto;padding:20px 24px}}')
    H.append(f'img{{max-width:100%;border-radius:6px}}')
    H.append(f'a{{color:{GREEN};text-decoration:none}}')
    H.append(f'p{{margin:0 0 10px;text-align:justify}}')
    H.append(f'.scoreboard{{text-align:center;margin:20px 0 30px}}')
    H.append(f'.scoreboard .teams{{font-size:18px;color:#c0d6e4}}')
    H.append(f'.scoreboard .score{{font-size:42px;font-weight:bold;color:{GREEN};margin:0 20px}}')
    H.append(f'.match-meta{{text-align:center;font-size:13px;color:#7a9ab4;margin:10px 0 20px}}')
    H.append(f'.footer{{text-align:center;color:#4a6a80;font-size:12px;margin:30px 0 10px;border-top:1px solid {BORDER};padding-top:16px}}')
    H.append(f'.lineup-section{{margin:16px 0 24px}}')
    H.append(f'.lineup-section img{{display:block;margin:0 auto;max-width:100%}}')
    H.append('</style></head><body><div class="container">')

    # ── 比赛信息头部 ──
    H.append('<div class="scoreboard">')
    H.append(f'<span class="teams">{home_name}</span>')
    H.append(f'<span class="score">{score_home} - {score_away}</span>')
    H.append(f'<span class="teams">{away_name}</span>')
    H.append('</div>')

    if stage_name or venue_name:
        meta_parts = []
        if stage_name:
            meta_parts.append(stage_name)
        if venue_name:
            meta_parts.append(venue_name)
        H.append(f'<div class="match-meta">{" · ".join(meta_parts)}</div>')

    # ── 首发阵容图 ──
    lineup_path = os.path.join(output_dir, "images", "lineup.png")
    if os.path.exists(lineup_path):
        H.append('<div class="lineup-section">')
        H.append('<img src="images/lineup.png" alt="双方首发阵容">')
        H.append('</div>')

    # ── 正文 Markdown → HTML ──
    body_html = _md_to_html_sections(fusion_md, "images")
    H.append(body_html)

    # ── 页脚 ──
    H.append('<div class="footer">融合比赛报道由 AI 自动生成 | 数据来源：SportMonks API + 网络新闻</div>')
    H.append('</div></body></html>')

    html_path = os.path.join(output_dir, "fusion_report.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write("\n".join(H))

    return html_path
