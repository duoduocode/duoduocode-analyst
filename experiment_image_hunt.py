"""
多源图片猎手 — 针对获取大量比赛图片优化
==========================================
策略:
  1. 豆包搜索 → 专门搜图集/图片专题页 (非普通新闻)
  2. Bing Image Search → 直接搜图片URL
  3. 汇总去重下载

用法: python experiment_image_hunt.py 法国 塞内加尔
"""
import json, re, sys, time, logging
from pathlib import Path
from urllib.parse import urlparse, quote

import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

ARK_API_KEY = "ark-b3a3d353-b34b-4310-a789-8e88b3cd3269-51821"
ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
MODEL = "doubao-seed-2-0-pro-260215"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
OUTPUT_BASE = Path("output/doubao_experiment")

SKIP_DOMAINS = ("beacon", "tracking", "pixel", "doubleclick", "analytics")
SKIP_PATHS = ("logo", "icon", "avatar", "qr", "ewm", "share", "arrow", "btn",
              "button", "close", "motion", "weixin", "wechat", "code",
              "homepage", "default", "fileftp", "login", "blank", "placeholder")


# ═══════════════════════════════════════════════
# 1. 豆包搜索 — 专门搜图集URL
# ═══════════════════════════════════════════════

def doubao_search_images(home: str, away: str, year: str) -> list[str]:
    """让豆包专门搜索包含大量图片的图集专题页"""
    prompt = f"""请联网搜索{year}年美加墨世界杯{home}对{away}比赛的图片专题页面和图集。

搜索重点：
1. 以"高清大图""图片专题""图集""组图"为关键词的页面
2. 新华社图片频道、新浪体育图集、腾讯体育图集、央视网图集等
3. 越多图片的页面越好

要求：
- 只需要返回URL，不需要摘要
- 每条一行，格式：URL - 来源名称
- 至少返回15个包含大量图片的页面链接
- 优先返回图片多的图集页，不要返回纯文字新闻"""
    
    resp = requests.post(f"{ARK_BASE_URL}/responses",
        headers={"Authorization": f"Bearer {ARK_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": MODEL,
            "input": [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
            "tools": [{"type": "web_search"}],
            "max_output_tokens": 2048,
        }, timeout=120)
    resp.raise_for_status()
    data = resp.json()

    urls = []
    for item in data.get("output", []):
        if item.get("type") == "message":
            for part in item.get("content", []):
                if part.get("type") == "output_text":
                    # 从文本中提取URL
                    text = part["text"]
                    found = re.findall(r'https?://[^\s\n\'"]+', text)
                    urls.extend(found)
                for ann in part.get("annotations", []):
                    if ann.get("url"):
                        urls.append(ann["url"])
    
    urls = list(dict.fromkeys(urls))  # 去重保序
    logger.info(f"  豆包图片专题搜索: 找到 {len(urls)} 个URL")
    return urls


# ═══════════════════════════════════════════════
# 2. Bing Image Search — 直接搜图片
# ═══════════════════════════════════════════════

def bing_image_search(query: str, count: int = 30) -> list[str]:
    """直接搜Bing图片，返回图片URL"""
    url = f"https://www.bing.com/images/search?q={quote(query)}&count={count}&first=1"
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
        r.raise_for_status()
    except Exception as e:
        logger.warning(f"  Bing图片搜索失败: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    image_urls = []
    
    # 从 img 标签提取
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        if not src or not src.startswith("http"):
            continue
        src_l = src.lower()
        if not any(src_l.endswith(e) for e in (".jpg", ".jpeg", ".png", ".webp")):
            continue
        if any(k in src_l for k in SKIP_DOMAINS):
            continue
        if any(k in src_l for k in SKIP_PATHS):
            continue
        image_urls.append(src)

    # 从 murl 属性提取（Bing格式）
    for a in soup.find_all("a"):
        murl = a.get("m") or a.get("murl") or ""
        if murl and murl.startswith("http"):
            if any(murl.lower().endswith(e) for e in (".jpg", ".jpeg", ".png", ".webp")):
                image_urls.append(murl)

    result = list(dict.fromkeys(image_urls))[:count]
    logger.info(f"  Bing图片搜索 '{query[:30]}': {len(result)} 张")
    return result


# ═══════════════════════════════════════════════
# 3. 从文章页提取全部图片（去队名限制）
# ═══════════════════════════════════════════════

def extract_all_images_from_page(url: str, min_kb: int = 5) -> list[dict]:
    """从文章页提取所有大尺寸图片，不限制队名匹配"""
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT},
                        timeout=20, allow_redirects=True, verify=False)
        r.raise_for_status()
    except Exception:
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    container = soup.find("article") or soup.find("main") or soup.find("body")
    if not container:
        return []

    images = []
    seen = set()
    for img in container.find_all("img"):
        src = img.get("src") or img.get("data-src") or img.get("data-original") or img.get("data-lazy-src") or ""
        if not src:
            continue
        if src.startswith("//"):
            src = "https:" + src
        if not src.startswith("http") or src in seen:
            continue
        seen.add(src)
        src_l = src.lower()
        if any(k in src_l for k in SKIP_DOMAINS):
            continue
        if any(k in src_l for k in SKIP_PATHS):
            continue
        # 只收图片格式
        if not any(src_l.endswith(e) for e in (".jpg", ".jpeg", ".png", ".webp")):
            # 也收无后缀但带有图片特征的
            if "img" not in src_l and "image" not in src_l and "photo" not in src_l:
                continue
        
        alt = img.get("alt", "").strip()
        # 只过滤明显的小图标：URL中含尺寸参数且很小
        size_match = re.search(r'[_-](\d+)x(\d+)', src)
        if size_match:
            w, h = int(size_match.group(1)), int(size_match.group(2))
            if w < 100 or h < 100:
                continue

        images.append({"url": src, "alt": alt, "source_url": url})

    return images


# ═══════════════════════════════════════════════
# 4. 下载
# ═══════════════════════════════════════════════

def download_images(image_list: list[dict], img_dir: Path, min_kb: int = 5) -> list[dict]:
    img_dir.mkdir(parents=True, exist_ok=True)
    downloaded = []
    seen_urls = set()

    for img in image_list:
        url = img["url"]
        if url in seen_urls:
            continue
        seen_urls.add(url)

        try:
            r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20, verify=False)
            r.raise_for_status()
        except Exception:
            continue

        if len(r.content) < min_kb * 1024:
            continue  # 太小，可能是占位图

        ext = ".jpg"
        for e in (".jpg", ".jpeg", ".png", ".webp"):
            if e in url.lower():
                ext = e; break

        fname = f"img_{len(downloaded)+1:03d}{ext}"
        fpath = img_dir / fname
        with open(fpath, "wb") as f:
            f.write(r.content)
        downloaded.append({
            "filename": fname, "url": url,
            "alt": img.get("alt", ""), "source_url": img.get("source_url", ""),
            "size_kb": len(r.content) // 1024,
        })
        logger.info(f"  ✓ {fname} ({len(r.content)//1024}KB) ← {urlparse(url).netloc}")
        time.sleep(0.2)

        if len(downloaded) >= 40:  # 够了就停
            break

    return downloaded


# ═══════════════════════════════════════════════
# 5. 主流程
# ═══════════════════════════════════════════════

def main():
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    if len(sys.argv) < 3:
        print("用法: python experiment_image_hunt.py 法国 塞内加尔")
        sys.exit(1)

    home, away = sys.argv[1], sys.argv[2]
    year = "2026"
    out_dir = OUTPUT_BASE / f"{home}_vs_{away}_images"
    img_dir = out_dir / "images"
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── 策略A: 豆包搜图集专题页 ──
    logger.info("=" * 60)
    logger.info("【策略A】豆包搜索图片专题/图集页面")
    logger.info("=" * 60)
    gallery_urls = doubao_search_images(home, away, year)
    
    page_images = []
    for i, url in enumerate(gallery_urls):
        logger.info(f"  [{i+1}/{len(gallery_urls)}] {urlparse(url).netloc} {urlparse(url).path[:50]}")
        imgs = extract_all_images_from_page(url)
        logger.info(f"    → 提取 {len(imgs)} 张")
        page_images.extend(imgs)
        if len(page_images) >= 100:
            break
        time.sleep(0.8)

    # ── 策略B: Bing图片直接搜索 ──
    logger.info("\n" + "=" * 60)
    logger.info("【策略B】Bing图片直搜")
    logger.info("=" * 60)

    bing_queries = [
        f"{home} {away} 2026 世界杯 高清",
        f"{home} {away} 2026 World Cup",
        f"{home} vs {away} 世界杯 进球 庆祝",
        f"姆巴佩 {away} 2026 世界杯",
    ]
    bing_images = []
    for q in bing_queries:
        urls = bing_image_search(q, count=15)
        for u in urls:
            bing_images.append({"url": u, "alt": q, "source_url": "bing_image_search"})
        time.sleep(1)

    # ── 策略C: 再追加一轮豆包新闻搜索（普通新闻页也能抓图）──
    logger.info("\n" + "=" * 60)
    logger.info("【策略C】豆包新闻搜索补充（扩大URL池）")
    logger.info("=" * 60)
    news_prompt = f"""请联网搜索{year}年美加墨世界杯{home}对{away}比赛的相关新闻，
尽量多返回带图片的页面URL（赛前、赛况、赛后都要），返回20条以上，每条一行。"""
    
    try:
        resp = requests.post(f"{ARK_BASE_URL}/responses",
            headers={"Authorization": f"Bearer {ARK_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": MODEL,
                "input": [{"role": "user", "content": [{"type": "input_text", "text": news_prompt}]}],
                "tools": [{"type": "web_search"}],
                "max_output_tokens": 3072,
            }, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        
        extra_urls = []
        for item in data.get("output", []):
            if item.get("type") == "message":
                for part in item.get("content", []):
                    if part.get("type") == "output_text":
                        extra_urls.extend(re.findall(r'https?://[^\s\n\'"]+', part["text"]))
                    for ann in part.get("annotations", []):
                        if ann.get("url"):
                            extra_urls.append(ann["url"])
        
        extra_urls = [u for u in list(dict.fromkeys(extra_urls)) if u not in gallery_urls]
        logger.info(f"  额外找到 {len(extra_urls)} 个URL")
        
        for i, url in enumerate(extra_urls):
            logger.info(f"  [{i+1}/{len(extra_urls)}] {urlparse(url).netloc}")
            imgs = extract_all_images_from_page(url)
            logger.info(f"    → 提取 {len(imgs)} 张")
            page_images.extend(imgs)
            if len(page_images) >= 150:
                break
            time.sleep(0.5)
    except Exception as e:
        logger.warning(f"  策略C失败: {e}")

    # ── 汇总去重 ──
    logger.info("\n" + "=" * 60)
    logger.info("【汇总去重】")
    all_images = page_images + bing_images
    seen_urls = set()
    unique = []
    for img in all_images:
        if img["url"] not in seen_urls:
            seen_urls.add(img["url"])
            unique.append(img)
    logger.info(f"  策略A(图集页): {len(page_images)}  → ")
    logger.info(f"  策略B(Bing直搜): {len(bing_images)}  → ")
    logger.info(f"  去重后总计: {len(unique)} 张")
    
    # ── 下载 ──
    logger.info("\n" + "=" * 60)
    logger.info("【下载图片】")
    downloaded = download_images(unique, img_dir, min_kb=5)
    
    # ── 保存索引 ──
    index_path = out_dir / "images.json"
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump({"match": f"{home} vs {away}", "total": len(downloaded),
                   "images": downloaded}, f, ensure_ascii=False, indent=2)
    
    logger.info(f"\n{'='*60}")
    logger.info(f"【完成】共下载 {len(downloaded)} 张图片")
    logger.info(f"  目录: {img_dir}")
    logger.info(f"  索引: {index_path}")
    logger.info(f"  总大小: {sum(d['size_kb'] for d in downloaded) // 1024} MB")


if __name__ == "__main__":
    main()
