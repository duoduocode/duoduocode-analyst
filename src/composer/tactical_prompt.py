"""
战术分析 LLM Prompt 组装模块

核心原则：传给 LLM 的所有数据必须是读者可理解的自然语言，
绝不暴露算法内部名称（penetration、deep_block、Gap、ROI、克制分 等）。
"""

from __future__ import annotations

from src.composer.prompt_loader import PromptLoader


def build_tactical_prompt(
    tactical_data: dict,
    home_name: str, away_name: str,
    score_home: int, score_away: int,
    loader: PromptLoader | None = None,
) -> str:
    """向后兼容。"""
    _, user = build_tactical_system_and_user(
        tactical_data, home_name, away_name, score_home, score_away, loader,
    )
    return user


def build_tactical_system_and_user(
    tactical_data: dict,
    home_name: str, away_name: str,
    score_home: int, score_away: int,
    loader: PromptLoader | None = None,
) -> tuple[str, str]:
    if loader is None:
        loader = PromptLoader()

    hr = tactical_data["home"]["tactical_raw"]
    ar = tactical_data["away"]["tactical_raw"]
    mf = tactical_data["match_flow"]
    coaching = tactical_data["coaching"]

    # ── 维度对比表（纯指标，无算法名） ──
    dim_labels = [
        ("possession_pct",     "控球率",         "%"),
        ("pass_volume",         "总传球数",       "次"),
        ("long_ball_ratio",     "长传占比",       ""),
        ("cross_ratio",         "传中占比",       ""),
        ("final_third_pass_ratio","进攻三区传球占比",""),
        ("forward_ratio",       "向前传球比例",   ""),
        ("passes_per_shot",     "每射门所需传球数","次"),
        ("ppda",                "压迫强度（越低越强）",""),
        ("high_press_ratio",    "高位抢断比例",   ""),
        ("clearance_ratio",     "封堵/解围倾向",  ""),
    ]
    dim_lines = []
    for key, label, unit in dim_labels:
        hv = hr.get(key, 0)
        av = ar.get(key, 0)
        dim_lines.append(f"  {label:18s}  {home_name} {_fmt_val(hv)}{unit}  vs  {away_name} {_fmt_val(av)}{unit}")

    # ── 比赛走势 ──
    rhythm = mf.get("rhythm", {})
    rhythm_labels = {
        "volatile": "大起大落，双方交替主导",
        "stabilized": "主动权稳固，节奏变化有限",
        "one_sided": "单边主导，一方完全控制比赛",
        "stalemate": "均势拉锯，无人真正掌控",
    }
    rhythm_text = rhythm_labels.get(rhythm.get("verdict"), "不明")

    ppda_h = mf.get("ppda", {}).get("home", {})
    ppda_a = mf.get("ppda", {}).get("away", {})
    ppda_hv = ppda_h.get("full_match", "-")
    ppda_av = ppda_a.get("full_match", "-")

    # 控球率逐窗口
    poss_trend = mf.get("possession_trend", {})
    h_poss = poss_trend.get("home", [])
    a_poss = poss_trend.get("away", [])
    poss_story = ""
    if h_poss:
        windows_names = ["0-15'", "15-30'", "30-45'", "45-60'", "60-75'", "75-90'"]
        poss_story = "控球率逐窗口变化:\n"
        for i, wn in enumerate(windows_names):
            if i < len(h_poss):
                poss_story += f"  {wn}  {home_name} {h_poss[i]}% vs {away_name} {a_poss[i]}%\n"

    # 射门逐窗口
    shot_segs = mf.get("shot_segments", {})
    h_shots = shot_segs.get("home", [])
    a_shots = shot_segs.get("away", [])
    shot_story = ""
    if h_shots:
        shot_story = "射门逐窗口分布:\n"
        for i, wn in enumerate(windows_names):
            if i < len(h_shots):
                shot_story += f"  {wn}  {home_name} {h_shots[i]}次射门  vs  {away_name} {a_shots[i]}次射门\n"

    key_events_text = ""
    for ev in mf.get("key_event_impacts", []):
        key_events_text += f"  - {ev.get('context', '')}\n"
    if not key_events_text.strip():
        key_events_text = "  （无关键事件）"

    # ── 战术执行效果（自然语言描述，不暴分） ──
    exec_text = _build_exec_narrative(tactical_data, home_name, away_name)

    # ── 克制链（自然语言，不暴数字） ──
    clash_text = _build_coaching_narrative(coaching, home_name, away_name)

    return loader.render("tactical",
                         home_name=home_name, away_name=away_name,
                         score_home=score_home, score_away=score_away,
                         dim_summary="\n".join(dim_lines),
                         rhythm_text=rhythm_text,
                         swings=rhythm.get("swings", 0),
                         ppda_home_val=ppda_hv,
                         ppda_away_val=ppda_av,
                         key_events_text=key_events_text,
                         possession_story=poss_story,
                         shot_story=shot_story,
                         exec_story=exec_text,
                         coaching_story=clash_text,
                         )


def _build_exec_narrative(td: dict, hn: str, an: str) -> str:
    """将执行效果数据转写为自然语言段落，不暴露评分和算法名。"""
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

        # 进攻
        ad = ex["attack"]["dimensions"]
        if ad:
            pos_dims = [d for d in ad if d["score"] > 0]
            neg_dims = [d for d in ad if d["score"] <= 0]
            if pos_dims:
                names = [dim_names.get(d["dim"], d["dim"]) for d in pos_dims]
                lines.append(f"  进攻层面做得好的方面: {'、'.join(names)}")
            if neg_dims:
                names = [dim_names.get(d["dim"], d["dim"]) for d in neg_dims]
                lines.append(f"  进攻层面效率偏低的方面: {'、'.join(names)}")
        else:
            lines.append("  进攻层面未显示出明确的优势维度")

        # 防守
        dd = ex["defense"]["dimensions"]
        if dd:
            pos_dims = [d for d in dd if d["score"] > 0]
            neg_dims = [d for d in dd if d["score"] <= 0]
            if pos_dims:
                names = [dim_names.get(d["dim"], d["dim"]) for d in pos_dims]
                lines.append(f"  防守层面做得好的方面: {'、'.join(names)}")
            if neg_dims:
                names = [dim_names.get(d["dim"], d["dim"]) for d in neg_dims]
                lines.append(f"  防守层面存在漏洞的方面: {'、'.join(names)}")
        else:
            lines.append("  防守层面未显示出明确的优势维度")

        parts.append("\n".join(lines))

    return "\n\n".join(parts)


def _build_coaching_narrative(coaching: dict, hn: str, an: str) -> str:
    """将教练博弈数据转写为自然语言。"""
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


def _fmt_val(v) -> str:
    if isinstance(v, float):
        return f"{v:.3f}" if abs(v) < 1 else f"{v:.1f}"
    return str(v)
