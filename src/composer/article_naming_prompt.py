"""
战术文章命名 LLM Prompt 组装模块

将战术分析 / 压迫分析 / 关键事件组装为 article_naming 提示词。
"""

from __future__ import annotations

from src.composer.prompt_loader import PromptLoader


def build_article_naming_prompt(
    match_context: str,
    tactical_summary: str,
    pressing_summary: str,
    key_events: str,
    loader: PromptLoader | None = None,
    match_overview: str = "",
) -> tuple[str, str]:
    """返回 (system_prompt, user_prompt)。"""
    if loader is None:
        loader = PromptLoader()
    return loader.render("article_naming",
                         match_context=match_context,
                         tactical_summary=tactical_summary,
                         pressing_summary=pressing_summary,
                         key_events=key_events,
                         match_overview=match_overview)


def parse_article_titles(text: str) -> list[dict]:
    """解析 LLM 输出的文章标题文本为结构化列表。

    输入格式：
      【战术向】
      《标题一》— 理由简述
      ...

    Returns: [{"angle": "战术向", "title": "标题一", "reason": "理由简述"}, ...]
    """
    titles = []
    current_angle = "自由角度"

    angle_map = {
        "战术向": "战术向", "战术": "战术向",
        "人物向": "人物向", "人物": "人物向",
        "数据向": "数据向", "数据": "数据向",
        "自由角度": "自由角度", "自由": "自由角度",
    }

    for line in text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue

        # 检测角度标题
        if line.startswith("【") and "】" in line:
            angle_key = line.split("【")[1].split("】")[0].strip()
            current_angle = angle_map.get(angle_key, angle_key)
            continue

        # 检测标题行：《标题》— 理由
        if "《" in line and "》" in line:
            try:
                title_part = line.split("《")[1].split("》")[0].strip()
                reason = ""
                # Handle both em-dash and regular dash separators
                if "—" in line:
                    reason = line.split("—", 1)[1].strip()
                elif "——" in line:
                    reason = line.split("——", 1)[1].strip()
                elif "--" in line:
                    reason = line.split("--", 1)[1].strip()
                elif " - " in line:
                    reason = line.split(" - ", 1)[1].strip()
                titles.append({
                    "angle": current_angle,
                    "title": title_part,
                    "reason": reason,
                })
            except (IndexError, ValueError):
                continue

    return titles
