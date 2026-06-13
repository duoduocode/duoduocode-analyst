"""
压迫分析 LLM Prompt 组装模块

将压迫图表底层数据构建为读者可理解的自然语言表格，
不暴露算法内部名称。
"""

from __future__ import annotations

from src.composer.prompt_loader import PromptLoader


def build_pressing_prompt(
    home_name: str,
    away_name: str,
    ppda_trend: dict,
    possession_trend: dict,
    shot_segments: dict,
    def_actions: dict,
    goal_events: list[dict],
    score_home: int,
    score_away: int,
    loader: PromptLoader | None = None,
) -> tuple[str, str]:
    """返回 (system_prompt, user_prompt)。"""
    if loader is None:
        loader = PromptLoader()

    h_ppda = ppda_trend.get("home", [0.0] * 6)
    a_ppda = ppda_trend.get("away", [0.0] * 6)
    h_poss = possession_trend.get("home", [0] * 6)
    a_poss = possession_trend.get("away", [0] * 6)
    h_xg = shot_segments.get("home_xg", [0.0] * 6)
    a_xg = shot_segments.get("away_xg", [0.0] * 6)
    h_on = shot_segments.get("home_on", [0] * 6)
    a_on = shot_segments.get("away_on", [0] * 6)
    h_off = shot_segments.get("home_off", [0] * 6)
    a_off = shot_segments.get("away_off", [0] * 6)

    h_da = def_actions.get("home", {})
    a_da = def_actions.get("away", {})
    h_tackles = h_da.get("tackles", [0] * 6)
    h_interceptions = h_da.get("interceptions", [0] * 6)
    h_fouls = h_da.get("fouls", [0] * 6)
    a_tackles = a_da.get("tackles", [0] * 6)
    a_interceptions = a_da.get("interceptions", [0] * 6)
    a_fouls = a_da.get("fouls", [0] * 6)

    # 模板变量：逐窗口展开
    kwargs = {"hn": home_name, "an": away_name}
    for i in range(6):
        kwargs[f"h_ppda_{i}"] = _fmt(h_ppda[i])
        kwargs[f"a_ppda_{i}"] = _fmt(a_ppda[i])
        kwargs[f"h_poss_{i}"] = str(h_poss[i]) if i < len(h_poss) else "-"
        kwargs[f"a_poss_{i}"] = str(a_poss[i]) if i < len(a_poss) else "-"
        kwargs[f"h_xg_{i}"] = f"{h_xg[i]:.2f}" if i < len(h_xg) else "-"
        kwargs[f"a_xg_{i}"] = f"{a_xg[i]:.2f}" if i < len(a_xg) else "-"
        # 射门(正) 格式: "5(3)"
        h_total = h_on[i] + h_off[i] if i < len(h_on) else 0
        a_total = a_on[i] + a_off[i] if i < len(a_on) else 0
        kwargs[f"h_shot_{i}"] = f"{h_total}({h_on[i]})" if h_total > 0 else "0(0)"
        kwargs[f"a_shot_{i}"] = f"{a_total}({a_on[i]})" if a_total > 0 else "0(0)"
        # 抢断+拦截
        kwargs[f"h_def_{i}"] = str(int(h_tackles[i] + h_interceptions[i])) if i < len(h_tackles) else "0"
        kwargs[f"a_def_{i}"] = str(int(a_tackles[i] + a_interceptions[i])) if i < len(a_tackles) else "0"
        kwargs[f"h_foul_{i}"] = str(int(h_fouls[i])) if i < len(h_fouls) else "0"
        kwargs[f"a_foul_{i}"] = str(int(a_fouls[i])) if i < len(a_fouls) else "0"

    # 全场累计
    h_xg_total = shot_segments.get("home_xg_total", 0)
    a_xg_total = shot_segments.get("away_xg_total", 0)
    h_shot_total = sum(h_on[i] + h_off[i] for i in range(6) if i < len(h_on))
    a_shot_total = sum(a_on[i] + a_off[i] for i in range(6) if i < len(a_on))
    h_on_total = sum(h_on[i] for i in range(6) if i < len(h_on))
    a_on_total = sum(a_on[i] for i in range(6) if i < len(a_on))
    h_def_total = sum(int(h_tackles[i] + h_interceptions[i]) for i in range(6) if i < len(h_tackles))
    a_def_total = sum(int(a_tackles[i] + a_interceptions[i]) for i in range(6) if i < len(a_tackles))
    h_foul_total = sum(int(h_fouls[i]) for i in range(6) if i < len(h_fouls))
    a_foul_total = sum(int(a_fouls[i]) for i in range(6) if i < len(a_fouls))

    h_avg_ppda = round(sum(h_ppda) / 6, 1) if h_ppda else 0
    a_avg_ppda = round(sum(a_ppda) / 6, 1) if a_ppda else 0

    full_parts = [
        f"全场汇总:",
        f"  {home_name} xG {h_xg_total:.2f} | 射门 {h_shot_total}({h_on_total}正) | 抢断+拦截 {h_def_total} | 犯规 {h_foul_total} | 平均压迫强度 {h_avg_ppda}",
        f"  {away_name} xG {a_xg_total:.2f} | 射门 {a_shot_total}({a_on_total}正) | 抢断+拦截 {a_def_total} | 犯规 {a_foul_total} | 平均压迫强度 {a_avg_ppda}",
    ]

    winner = home_name if score_home > score_away else (away_name if score_away > score_home else "双方")
    full_parts.append(f"  {home_name} {score_home} - {score_away} {away_name}，胜者：{winner}")

    kwargs["full_stats"] = "\n".join(full_parts)

    # 比赛上下文
    match_ctx = f"对阵：{home_name} vs {away_name}\n比分：{home_name} {score_home} - {score_away} {away_name}"
    if score_home > score_away:
        match_ctx += f"\n胜者：{home_name}"
    elif score_away > score_home:
        match_ctx += f"\n胜者：{away_name}"
    else:
        match_ctx += "\n结果：双方打平"
    kwargs["match_context"] = match_ctx

    # 进球事件
    if goal_events:
        goal_lines = []
        for g in goal_events:
            team_name = home_name if g.get("team") == "home" else away_name
            goal_lines.append(f"  {g['minute']}' {g.get('label', '')}（{team_name}）")
        kwargs["goal_text"] = "\n".join(goal_lines)
    else:
        kwargs["goal_text"] = "  本场无进球"

    return loader.render("pressing", **kwargs)


def _fmt(v: float) -> str:
    """格式化数值：整数不显 .0，浮点保留1位。"""
    if v == int(v):
        return str(int(v))
    return f"{v:.1f}"
