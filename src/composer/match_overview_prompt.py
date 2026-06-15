"""
比赛过程概述 LLM Prompt 组装模块 (v3)

基于 web 抓取的真实新闻文本 + 结构化事件数据作为锚定（防止幻觉），
LLM 只做润色和整合。
"""

from __future__ import annotations

from src.composer.prompt_loader import PromptLoader


def build_match_overview_prompt(
    match_context: str,
    key_events_text: str,
    news_text: str = "",
    loader: PromptLoader | None = None,
) -> tuple[str, str]:
    """返回 (system_prompt, user_prompt)。

    Args:
        match_context: 比赛信息，如 "2026年世界杯F组小组赛 荷兰对日本 2-2"
        key_events_text: 关键事件时间线文本（数据锚定，用于校准）
        news_text: web 抓取的真实新闻战报（主要素材）
    """
    if loader is None:
        loader = PromptLoader()
    return loader.render("match_overview",
                         match_context=match_context,
                         key_events_text=key_events_text,
                         news_text=news_text)
