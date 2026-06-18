"""
豆包联网搜索 + 图片抓取一体化实验
===================================
1. 调用豆包 Responses API（联网搜索）→ 生成新闻摘要 + 获取文章URL
2. 访问豆包推荐的文章页 → 提取图片 → 下载到本地
3. 输出结构化结果

用法: python experiment_search_and_images.py 法国 塞内加尔
"""
import json
import os
import re
import sys
import time
import logging
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════
ARK_API_KEY = "ark-b3a3d353-b34b-4310-a789-8e88b3cd3269-51821"
ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
MODEL = "doubao-seed-2-0-pro-260215"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
OUTPUT_BASE = Path("output/doubao_experiment")

_NAME_MAP = {
    "netherlands": "荷兰", "japan": "日本", "england": "英格兰", "france": "法国",
    "germany": "德国", "spain": "西班牙", "italy": "意大利", "portugal": "葡萄牙",
    "argentina": "阿根廷", "brazil": "巴西", "sweden": "瑞典", "tunisia": "突尼斯",
    "korea": "韩国", "south korea": "韩国",
}

SKIP_IMG_DOMAINS = ("beacon", "tracking", "pixel", "doubleclick", "analytics")
SKIP_IMG_PATHS = ("logo", "icon", "avatar", "qr", "ewm", "share", "arrow", "btn",
                  "button", "close", "motion", "weixin", "wechat", "code",
                  "homepage", "default", "fileftp", "login")


def to_chinese(name: str) -> str:
    return _NAME_MAP.get(name.strip().lower(), name)


# ═══════════════════════════════════════════════
# 1. 豆包联网搜索 → 摘要 + 文章URL
# ═══════════════════════════════════════════════

def call_doubao(prompt: str, max_tokens: int = 4096) -> dict:
    """调用豆包 Responses API，返回 {content, annotations, article_urls}"""
    resp = requests.post(f"{ARK_BASE_URL}/responses",
        headers={"Authorization": f"Bearer {ARK_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": MODEL,
            "input": [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
            "tools": [{"type": "web_search"}],
            "max_output_tokens": max_tokens,
        }, timeout=120)
    resp.raise_for_status()
    data = resp.json()

    content_text = ""
    annotations = []
    article_urls = []

    for item in data.get("output", []):
        if item.get("type") == "message":
            for part in item.get("content", []):
                if part.get("type") == "output_text":
                    content_text += part["text"]
                for ann in part.get("annotations", []):
                    annotations.append(ann)
                    if ann.get("type") == "url_citation" and ann.get("url"):
                        article_urls.append(ann["url"])

    usage = data.get("usage", {})
    return {
        "content": content_text,
        "annotations": annotations,
        "article_urls": list(dict.fromkeys(article_urls)),  # 去重保持顺序
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
    }


# ═══════════════════════════════════════════════
# 2. 从文章页提取图片
# ═══════════════════════════════════════════════

def fetch_article_images(url: str, home: str, away: str) -> list[dict]:
    """访问文章页，提取比赛相关图片"""
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20, allow_redirects=True)
        r.raise_for_status()
        if r.encoding and r.encoding.lower() != "utf-8":
            r.encoding = r.apparent_encoding or "utf-8"
    except Exception as e:
        logger.warning(f"  访问失败: {url[:80]}... {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    container = soup.find("article") or soup.find("main") or soup.find("body")
    if not container:
        return []

    team_keywords = set()
    for name in (home, away):
        n = name.lower().strip()
        if n:
            team_keywords.add(n)
        cn = to_chinese(name)
        if cn and cn != name:
            team_keywords.add(cn)

    primary = []
    seen = set()

    for img in container.find_all("img"):
        src = img.get("src") or img.get("data-src") or img.get("data-original") or ""
        if not src:
            continue
        if src.startswith("//"):
            src = "https:" + src
        if not src.startswith("http") or src in seen:
            continue
        seen.add(src)
        src_l = src.lower()
        if any(k in src_l for k in SKIP_IMG_DOMAINS):
            continue
        if any(k in src_l for k in SKIP_IMG_PATHS):
            continue
        if not any(src_l.endswith(e) for e in (".jpg", ".jpeg", ".png", ".webp")):
            continue

        alt = img.get("alt", "").strip()
        alt_l = alt.lower()
        alt_match = team_keywords and any(kw in alt_l for kw in team_keywords)
        if alt_match:
            primary.append({"url": src, "alt": alt, "source_url": url})

    # Fallback: URL含年份 + 父元素含队名
    if not primary:
        seen.clear()
        for img in container.find_all("img"):
            src = img.get("src") or img.get("data-src") or img.get("data-original") or ""
            if not src or src.startswith("//"):
                src = "https:" + src if src.startswith("//") else src
            if not src.startswith("http") or src in seen:
                continue
            seen.add(src)
            src_l = src.lower()
            if any(k in src_l for k in SKIP_IMG_DOMAINS):
                continue
            if any(k in src_l for k in SKIP_IMG_PATHS):
                continue
            if not any(src_l.endswith(e) for e in (".jpg", ".jpeg", ".png", ".webp")):
                continue
            if "2026" not in src:
                continue
            parent_text = ""
            for p in img.parents:
                txt = p.get_text(strip=True)
                if len(txt) > 10:
                    parent_text = txt; break
            if not parent_text or not team_keywords:
                continue
            if not any(kw in parent_text.lower() for kw in team_keywords):
                continue
            primary.append({"url": src, "alt": img.get("alt", "").strip(), "source_url": url})

    return primary[:20]


def download_images(images: list[dict], img_dir: Path) -> list[dict]:
    """下载图片到指定目录，返回下载结果列表"""
    img_dir.mkdir(parents=True, exist_ok=True)
    downloaded = []

    for i, img in enumerate(images):
        url = img["url"]
        try:
            r = None
            for verify_flag in (True, False):
                try:
                    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20, verify=verify_flag)
                    r.raise_for_status()
                    break
                except requests.exceptions.SSLError:
                    if not verify_flag:
                        raise
                    continue
            if r is None:
                continue
            ext = ".jpg"
            for e in (".jpg", ".jpeg", ".png", ".webp"):
                if e in url.lower():
                    ext = e; break
            fname = f"img_{i+1:03d}{ext}"
            fpath = img_dir / fname
            with open(fpath, "wb") as f:
                f.write(r.content)
            downloaded.append({
                "filename": fname, "url": url,
                "alt": img.get("alt", ""), "source_url": img.get("source_url", ""),
            })
            logger.info(f"    ✓ {fname} ({len(r.content) // 1024}KB)")
        except Exception as e:
            logger.warning(f"    ✗ {url[:70]}... {e}")
        time.sleep(0.3)

    return downloaded


# ═══════════════════════════════════════════════
# 3. 主流程
# ═══════════════════════════════════════════════

def main():
    if len(sys.argv) < 3:
        print("用法: python experiment_search_and_images.py 法国 塞内加尔")
        sys.exit(1)
    home = sys.argv[1]
    away = sys.argv[2]
    year = "2026"

    out_dir = OUTPUT_BASE / f"{home}_vs_{away}"
    out_dir.mkdir(parents=True, exist_ok=True)
    img_dir = out_dir / "images"
    img_dir.mkdir(parents=True, exist_ok=True)

    # ── Prompt 模板 ──
    prompts = {
        "pre": f"""请联网搜索{year}年美加墨世界杯{home}对{away}的赛前新闻（赛前阵容、伤病、前瞻、历史交锋等）。
按以下格式输出：
## 赛前新闻列表
1. 《标题》— 来源：XX
...

## 赛前新闻摘要
（160-300字）""",

        "match": f"""请联网搜索{year}年美加墨世界杯{home}对{away}的比赛战报（首发、进球事件、关键数据、赛后评价）。
按以下格式输出：
## 比赛基本信息 + 关键事件时间线 + 双方首发阵容

## 比赛赛况摘要
（380-500字新闻战报）""",

        "post": f"""请联网搜索{year}年美加墨世界杯{home}对{away}的赛后新闻（球员评价、纪录、出线形势、赛后反应等）。
按以下格式输出：
## 赛后新闻列表
1. 《标题》— 来源：XX
...

## 赛后新闻摘要
（160-300字）""",
    }

    all_results = {}
    all_article_urls = []

    for mode, label in [("pre", "赛前"), ("match", "赛况"), ("post", "赛后")]:
        logger.info(f"\n{'='*60}")
        logger.info(f"【{label}】豆包联网搜索 + 摘要生成")
        logger.info(f"{'='*60}")

        try:
            t0 = time.time()
            result = call_doubao(prompts[mode])
            elapsed = time.time() - t0
            logger.info(f"  完成 {elapsed:.1f}s | tokens: in={result['input_tokens']} out={result['output_tokens']}")
            logger.info(f"  摘要长度: {len(result['content'])} 字符")
            logger.info(f"  引用的文章URL: {len(result['article_urls'])} 条")
            all_results[mode] = result
            all_article_urls.extend(result["article_urls"])
        except Exception as e:
            logger.error(f"  失败: {e}")
            all_results[mode] = {"content": str(e), "annotations": [], "article_urls": [], "input_tokens": 0, "output_tokens": 0}

        time.sleep(3)

    # ── 去重文章URL ──
    unique_urls = list(dict.fromkeys(all_article_urls))
    logger.info(f"\n{'='*60}")
    logger.info(f"【图片抓取】去重后共 {len(unique_urls)} 篇文章")
    logger.info(f"{'='*60}")

    all_images = []
    for i, url in enumerate(unique_urls):
        logger.info(f"  [{i+1}/{len(unique_urls)}] {urlparse(url).netloc} ...")
        imgs = fetch_article_images(url, home, away)
        logger.info(f"    提取到 {len(imgs)} 张相关图片")
        all_images.extend(imgs)
        time.sleep(1)

    # 对图片URL去重
    seen_urls = set()
    unique_imgs = []
    for img in all_images:
        if img["url"] not in seen_urls:
            seen_urls.add(img["url"])
            unique_imgs.append(img)

    logger.info(f"\n  总计: {len(all_images)} 张原始 → {len(unique_imgs)} 张去重后")

    # ── 下载图片 ──
    downloaded = download_images(unique_imgs, img_dir)
    logger.info(f"  成功下载: {len(downloaded)} 张")

    # ── 保存汇总 ──
    # 1. 新闻摘要 Markdown
    md_path = out_dir / "news_summary.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# {year}年美加墨世界杯 {home} vs {away} 新闻合集\n\n")
        f.write(f"> 生成方式: 豆包联网搜索 (doubao-seed-2-0-pro) + HTML图片提取\n")
        f.write(f"> 时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        for mode, label in [("pre", "赛前新闻"), ("match", "赛况战报"), ("post", "赛后新闻")]:
            f.write(f"---\n\n## {label}\n\n")
            f.write(all_results[mode]["content"] + "\n\n")

    # 2. 图片索引 JSON
    img_index_path = out_dir / "images.json"
    with open(img_index_path, "w", encoding="utf-8") as f:
        json.dump({
            "match": f"{home} vs {away}",
            "total": len(downloaded),
            "images": downloaded,
            "source_articles": unique_urls,
        }, f, ensure_ascii=False, indent=2)

    # 3. 统计
    total_in = sum(r["input_tokens"] for r in all_results.values())
    total_out = sum(r["output_tokens"] for r in all_results.values())
    cost = total_in / 1e6 * 0.514 + total_out / 1e6 * 2.57

    logger.info(f"\n{'='*60}")
    logger.info(f"【完成】")
    logger.info(f"  新闻摘要: {md_path} ({md_path.stat().st_size / 1024:.1f} KB)")
    logger.info(f"  图片数量: {len(downloaded)} 张 → {img_dir}")
    logger.info(f"  图片索引: {img_index_path}")
    logger.info(f"  总Token: in={total_in} out={total_out}")
    logger.info(f"  LLM费用: ${cost:.4f} (约 ¥{cost * 7.2:.3f})")


if __name__ == "__main__":
    main()
