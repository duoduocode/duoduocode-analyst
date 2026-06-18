"""
球员人物特稿推荐 LLM Prompt 组装模块

将候选球员卡片 + 比赛上下文 + 新闻组装为 player_feature_recommend 提示词。
"""

from __future__ import annotations

from src.composer.prompt_loader import PromptLoader
from src.engine.player_feature_selector import PlayerCandidate


def build_player_feature_prompt(
    match_context: str,
    stage_info: str,
    tactical_summary: str,
    pressing_summary: str,
    candidates: list[PlayerCandidate],
    loader: PromptLoader | None = None,
    match_overview: str = "",
) -> tuple[str, str]:
    """返回 (system_prompt, user_prompt)。"""
    if loader is None:
        loader = PromptLoader()

    # 构建候选球员卡片数据
    cand_data = []
    for c in candidates:
        card = {
            "name": c.name,
            "team": c.team,
            "position": c.position,
            "minutes": c.minutes,
            "rating": c.rating,
            "is_substitute": c.is_substitute,
            "role_label": "替补登场" if c.is_substitute else "首发",
            "tags": c.tags,
            "events": c.events if c.events else ["-"],
            "key_stats": c.key_stats,
            "summary": c.summary or "暂无赛后点评",
            "news": c.news if c.news else [],
        }
        cand_data.append(card)

    return loader.render("player_feature_recommend",
                         match_context=match_context,
                         stage_info=stage_info,
                         tactical_summary=tactical_summary,
                         pressing_summary=pressing_summary,
                         candidates=cand_data,
                         match_overview=match_overview)
