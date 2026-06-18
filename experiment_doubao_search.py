"""
豆包联网搜索实验脚本 (v1)
使用火山引擎 Ark Responses API + web_search 工具，
一次请求同时完成联网搜索 + LLM 生成。

用法:
  python experiment_doubao_search.py

前提:
  - 已在火山引擎控制台开通 doubao-seed-2.0-pro 模型
  - 设置环境变量 ARK_API_KEY，或直接在脚本中填入

产出:
  output/doubao_experiment_france_senegal.md  — 完整新闻+摘要
"""

import json
import os
import sys
import time
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════
ARK_API_KEY = os.environ.get("ARK_API_KEY", "ark-b3a3d353-b34b-4310-a789-8e88b3cd3269-51821")
ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
MODEL = os.environ.get("ARK_MODEL", "doubao-seed-2-0-pro-260215")

HOME = "法国"
AWAY = "塞内加尔"
YEAR = "2026"

OUTPUT_DIR = Path("output/doubao_experiment")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

if ARK_API_KEY.startswith("在此"):
    logger.error("请先设置 ARK_API_KEY 环境变量，或在脚本中填入你的火山引擎 API KEY")
    logger.error("获取方式: 火山引擎控制台 → 模型推理 → API KEY管理")
    sys.exit(1)


# ═══════════════════════════════════════════════
# 豆包 Ark Responses API 调用（联网搜索）
# ═══════════════════════════════════════════════

def call_doubao_with_search(prompt: str, temperature: float = 0.7, max_output_tokens: int = 4096) -> dict:
    """
    调用火山引擎 Ark Responses API，开启联网搜索。
    返回 {"content": str, "usage": dict, "annotations": list}
    """
    import requests

    url = f"{ARK_BASE_URL}/responses"
    headers = {
        "Authorization": f"Bearer {ARK_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "input": [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
        "tools": [{"type": "web_search"}],
        "temperature": temperature,
        "max_output_tokens": max_output_tokens,
    }

    logger.info(f"调用豆包 Responses API (联网搜索)... prompt_len={len(prompt)}")
    t0 = time.time()
    resp = requests.post(url, headers=headers, json=payload, timeout=120)
    elapsed = time.time() - t0

    if resp.status_code != 200:
        logger.error(f"API 返回错误: {resp.status_code}\n{resp.text}")
        raise RuntimeError(f"API error: {resp.status_code}")

    data = resp.json()
    output = data.get("output", [])

    content_parts = []
    annotations = []
    for item in output:
        if item.get("type") == "message":
            for part in item.get("content", []):
                if part.get("type") == "output_text":
                    content_parts.append(part["text"])
                if "annotations" in part:
                    annotations.extend(part["annotations"])
        elif item.get("type") == "web_search_call":
            # 搜索过程记录
            pass

    usage = data.get("usage", {})
    logger.info(f"完成! 耗时 {elapsed:.1f}s | input_tokens={usage.get('input_tokens','?')} "
                f"output_tokens={usage.get('output_tokens','?')}")

    return {
        "content": "\n".join(content_parts),
        "usage": usage,
        "annotations": annotations,
    }


# ═══════════════════════════════════════════════
# 三个搜索 Prompt
# ═══════════════════════════════════════════════

PROMTS = {
    "pre": f"""请联网搜索{YEAR}年美加墨世界杯{HOME}对{AWAY}的赛前新闻。

要求：
1. 整理10条赛前相关新闻
2. 每条新闻包含：标题、来源、核心内容
3. 最后对以上10条新闻写一段160-300字的赛前新闻摘要，包含核心事实、关键人物、数据亮点、看点分析
4. 新闻标题用中文格式：《标题》
5. 来源注明具体媒体名称（如：新华社、央视网、体坛周报等）

请按以下格式输出：

## 赛前新闻列表
1. 《标题》— 来源：XX — 内容简述
2. 《标题》— 来源：XX — 内容简述
...

## 赛前新闻摘要
（160-300字）""",

    "match": f"""请联网搜索{YEAR}年美加墨世界杯{HOME}对{AWAY}的比赛战报、赛况新闻。

要求：
1. 整理完整比赛过程，包括首发阵容、关键事件（进球、黄牌、红牌、换人）、战术亮点
2. 最后写一段380-500字的比赛赛况新闻摘要，以新闻战报风格叙述，按时间线展开
3. 摘要需包含：比赛基本信息、关键事件时间线、比分变化、球员表现亮点、教练评价、数据亮点

请按以下格式输出：

## 比赛基本信息
- 赛事：
- 时间：
- 场地：
- 比分：

## 关键事件时间线
（按时间顺序列出）

## 双方首发阵容
**{HOME}**：
**{AWAY}**：

## 比赛赛况摘要
（380-500字新闻战报）""",

    "post": f"""请联网搜索{YEAR}年美加墨世界杯{HOME}对{AWAY}的赛后新闻。

要求：
1. 整理10条赛后相关新闻
2. 每条新闻包含：标题、来源、核心内容
3. 最后对以上10条新闻写一段160-300字的赛后新闻摘要，包含赛后评价、纪录亮点、出线形势分析
4. 新闻标题用中文格式：《标题》

请按以下格式输出：

## 赛后新闻列表
1. 《标题》— 来源：XX — 内容简述
2. 《标题》— 来源：XX — 内容简述
...

## 赛后新闻摘要
（160-300字）""",
}


# ═══════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════

def main():
    logger.info(f"豆包联网搜索实验: {YEAR}年世界杯 {HOME} vs {AWAY}")
    logger.info(f"模型: {MODEL}")
    logger.info("=" * 60)

    all_results = {}

    for mode in ["pre", "match", "post"]:
        mode_label = {"pre": "赛前新闻+摘要", "match": "赛况新闻+摘要", "post": "赛后新闻+摘要"}
        logger.info(f"\n{'=' * 60}")
        logger.info(f"阶段 {mode_label[mode]}")
        logger.info(f"{'=' * 60}")

        try:
            result = call_doubao_with_search(PROMTS[mode], max_output_tokens=4096)
            all_results[mode] = result
            # 打印前500字符预览
            preview = result["content"][:500]
            logger.info(f"--- 结果预览 (前500字符) ---")
            print(preview + ("..." if len(result["content"]) > 500 else ""))
            logger.info(f"--- 总长度: {len(result['content'])} 字符 ---")

            # 短暂间隔，避免触发限流
            time.sleep(2)

        except Exception as e:
            logger.error(f"失败: {e}")
            all_results[mode] = {"content": f"【错误】{e}", "usage": {}, "annotations": []}

    # ── 保存完整结果 ──
    output_path = OUTPUT_DIR / "france_senegal_news.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# {YEAR}年美加墨世界杯 {HOME} vs {AWAY} 新闻合集\n\n")
        f.write(f"> 生成工具: 豆包联网搜索 ({MODEL})\n")
        f.write(f"> 生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        for mode, label in [("pre", "赛前新闻"), ("match", "赛况战报"), ("post", "赛后新闻")]:
            f.write(f"---\n\n")
            f.write(f"## {label}\n\n")
            f.write(all_results.get(mode, {}).get("content", "(无内容)") + "\n\n")

        # 引用来源附录
        f.write("---\n\n")
        f.write("## 联网搜索引用来源\n\n")
        for mode, label in [("pre", "赛前"), ("match", "赛况"), ("post", "赛后")]:
            anns = all_results.get(mode, {}).get("annotations", [])
            if anns:
                f.write(f"### {label}\n")
                for i, ann in enumerate(anns, 1):
                    title = ann.get("title", "")
                    url = ann.get("url_citation", ann.get("url", ""))
                    if url:
                        f.write(f"{i}. [{title}]({url})\n")
                    else:
                        f.write(f"{i}. {title}\n")
                f.write("\n")

    logger.info(f"\n{'=' * 60}")
    logger.info(f"结果已保存到: {output_path}")
    logger.info(f"文件大小: {output_path.stat().st_size / 1024:.1f} KB")

    # ── 统计总 Token ──
    total_in = sum(r.get("usage", {}).get("input_tokens", 0) for r in all_results.values())
    total_out = sum(r.get("usage", {}).get("output_tokens", 0) for r in all_results.values())
    logger.info(f"总 Token: 输入 {total_in} | 输出 {total_out}")
    # 豆包2.0pro 定价: $0.514/M输入, $2.57/M输出
    cost = total_in / 1e6 * 0.514 + total_out / 1e6 * 2.57
    logger.info(f"预估费用: ${cost:.6f} (约 ¥{cost * 7.2:.4f})")


if __name__ == "__main__":
    main()
