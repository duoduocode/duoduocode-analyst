"""
fetch_match_context.py (v3)

通过联网搜索获取指定比赛的赛前/战报/赛后新闻及图片。
使用 Bing News 搜索获取高质量中文新闻源，抓取正文并合并。

用法：
  python fetch_match_context.py 荷兰 日本                 # 输出到终端
  python fetch_match_context.py 荷兰 日本 --save output_dir  # 保存到目录
  python fetch_match_context.py 荷兰 日本 --mode pre     # 仅赛前
  python fetch_match_context.py 荷兰 日本 --mode post    # 仅赛后
  python fetch_match_context.py 荷兰 日本 --mode match   # 仅战报
  python fetch_match_context.py 荷兰 日本 --mode image   # 仅显示图片
"""

from __future__ import annotations

import re
import time
import logging
import json
from dataclasses import dataclass, field
from typing import List
from pathlib import Path

import requests
from bs4 import BeautifulSoup
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# 配置
# ──────────────────────────────────────────────
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)
BING_NEWS_URL = "https://www.bing.com/news/search"
MAX_SEARCH_RESULTS = 10
MAX_FETCH_ARTICLES = 3
FETCH_TIMEOUT = 15
REQUEST_DELAY = 1.2

# 优先域名（权威中文新闻源）
PREFERRED_DOMAINS = [
    "chinanews.com", "news.cn", "xinhuanet.com",
    "cctv.com", "sina.com.cn", "gmw.cn",
    "qzwb.com",
]

# 跳过域名（SSL 问题 / AI 农场）
SKIP_DOMAINS = [
    "sohu.com", "163.com", "toutiao.com", "baidu.com",
    "msn.com", "msn.cn",   # SSL 兼容问题
]


@dataclass
class MatchContext:
    """联网抓取的比赛上下文"""
    query: str = ""
    urls_used: List[str] = field(default_factory=list)
    titles_used: List[str] = field(default_factory=list)
    text: str = ""
    images: List[dict] = field(default_factory=list)
    success: bool = False
    error: str = ""


# ──────────────────────────────────────────────
# 1. Bing News 搜索
# ──────────────────────────────────────────────

def _domain_priority(url: str) -> int:
    from urllib.parse import urlparse
    domain = urlparse(url).netloc.lower()
    for skip in SKIP_DOMAINS:
        if skip in domain:
            return 999
    for i, pref in enumerate(PREFERRED_DOMAINS):
        if pref in domain:
            return i
    return 500


def search_news_bing(query: str, max_results: int = MAX_SEARCH_RESULTS) -> List[dict]:
    """通过 Bing News 搜索新闻。含重试"""
    for attempt in range(3):
        try:
            resp = requests.get(
                BING_NEWS_URL,
                params={"q": query},
                headers={"User-Agent": USER_AGENT},
                timeout=20,
            )
            resp.raise_for_status()
            break
        except Exception as e:
            if attempt < 2:
                logger.info(f"  Bing 重试 {attempt+1}/2: {e}")
                time.sleep(2)
            else:
                logger.warning(f"Bing News 搜索失败: {e}")
                return []

    soup = BeautifulSoup(resp.text, "html.parser")
    results = []
    seen_urls = set()

    for a in soup.select("a[href]"):
        href = a.get("href", "")
        title = a.get_text(strip=True)
        if not href.startswith("http") or "bing.com" in href:
            continue
        if not title or len(title) < 8:
            continue
        if href in seen_urls:
            continue
        seen_urls.add(href)
        results.append({"title": title, "url": href, "snippet": ""})
        if len(results) >= max_results:
            break

    logger.info(f"Bing News '{query}' -> {len(results)} results")
    results.sort(key=lambda r: _domain_priority(r["url"]))
    return results


def search_news_bing_with_fallback(query: str, fallback_query: str = "",
                                   max_results: int = MAX_SEARCH_RESULTS) -> List[dict]:
    """搜索，如果 0 结果则换备选搜索词重试"""
    results = search_news_bing(query, max_results)
    if not results and fallback_query:
        logger.info(f"  0 结果，换备选搜索词: {fallback_query}")
        time.sleep(2)
        results = search_news_bing(fallback_query, max_results)
    return results


# ──────────────────────────────────────────────
# 2. 正文 & 图片提取
# ──────────────────────────────────────────────

def _extract_text_from_html(html: str) -> str:
    """从 HTML 中提取正文纯文本"""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside",
                     "noscript", "iframe", "form", "button"]):
        tag.decompose()
    container = soup.find("article") or soup.find("main") or soup.find("body")
    if not container:
        return soup.get_text(separator="\n", strip=True)
    noise_patterns = (
        "nav", "sidebar", "related", "recommend", "footer", "header",
        "share", "comment", "pagination", "ad", "banner",
    )
    for cls in noise_patterns:
        for el in container.find_all(class_=re.compile(cls, re.I)):
            el.decompose()
    text = container.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text[:8000]


def _extract_images_from_html(html: str, source_url: str = "",
                              home: str = "", away: str = "") -> List[dict]:
    """提取比赛相关图片（优先 alt 队名匹配，兜底 URL 年份匹配）"""
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        return []

    container = soup.find("article") or soup.find("main") or soup.find("body")
    if not container:
        return images

    skip_domains = ("beacon", "tracking", "pixel", "doubleclick", "analytics")
    skip_paths = ("logo", "icon", "avatar", "qr", "ewm", "share", "arrow", "btn",
                  "button", "close", "motion", "weixin", "wechat", "code",
                  "homepage", "default", "fileftp", "login")

    team_keywords = set()
    for name in (home, away):
        n = name.lower().strip()
        if n:
            team_keywords.add(n)
        cn = to_chinese_name(name)
        if cn and cn != name:
            team_keywords.add(cn)

    # Primary: alt 含队名 → 比赛照片
    primary = []
    seen = set()
    for img in container.find_all("img"):
        src = img.get("src", "") or img.get("data-src", "") or img.get("data-original", "")
        if not src:
            continue
        if src.startswith("//"):
            src = "https:" + src
        if not src.startswith("http"):
            continue
        if src in seen:
            continue
        seen.add(src)
        src_lower = src.lower()
        if any(k in src_lower for k in skip_domains):
            continue
        if any(k in src_lower for k in skip_paths):
            continue
        if not any(ext in src_lower for ext in (".jpg", ".jpeg", ".png", ".webp")):
            continue
        alt = img.get("alt", "").strip()
        alt_lower = alt.lower()
        alt_matches = any(kw in alt_lower for kw in team_keywords) if team_keywords else False
        if alt_matches:
            primary.append({"url": src, "alt": alt, "source_url": source_url})

    # Fallback: 如果 alt 匹配为 0，用 URL 年份 + 父元素文本检测
    if not primary:
        seen.clear()
        for img in container.find_all("img"):
            src = img.get("src", "") or img.get("data-src", "") or img.get("data-original", "")
            if not src:
                continue
            if src.startswith("//"):
                src = "https:" + src
            if not src.startswith("http"):
                continue
            if src in seen:
                continue
            seen.add(src)
            src_lower = src.lower()
            if any(k in src_lower for k in skip_domains):
                continue
            if any(k in src_lower for k in skip_paths):
                continue
            if not any(ext in src_lower for ext in (".jpg", ".jpeg", ".png", ".webp")):
                continue
            if "2026" not in src:
                continue
            # 检查父元素文本是否含队名关键词
            parent_text = ""
            for parent in img.parents:
                txt = parent.get_text(strip=True)
                if len(txt) > 10:
                    parent_text = txt
                    break
            if not parent_text or not team_keywords:
                continue
            parent_lower = parent_text.lower()
            if not any(kw in parent_lower for kw in team_keywords):
                continue
            alt = img.get("alt", "").strip()
            primary.append({"url": src, "alt": alt, "source_url": source_url})

    return primary[:20]


def _fetch_article_raw(url: str, home: str = "", away: str = "") -> dict | None:
    """抓取文章，返回 {text, html, images}。含 AI 过滤"""
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=FETCH_TIMEOUT,
            allow_redirects=True,
        )
        resp.raise_for_status()
        if resp.encoding and resp.encoding.lower() != "utf-8":
            resp.encoding = resp.apparent_encoding or "utf-8"
        html = resp.text
        text = _extract_text_from_html(html)
        if not text or len(text) < 80:
            return None
        ai_markers = [
            "虚构", "纯属虚构", "以上内容由AI生成",
            "OpenAI", "ChatGPT", "GPT生成", "AI 生成",
        ]
        for marker in ai_markers:
            if marker in text[:500]:
                logger.info(f"  跳过(AI标记: {marker}): {url[:80]}")
                return None
        images = _extract_images_from_html(html, url, home, away)
        return {"text": text, "html": html, "images": images}
    except Exception as e:
        logger.warning(f"  抓取失败: {url[:80]}... {e}")
        return None


# ──────────────────────────────────────────────
# 3. 文本清洗
# ──────────────────────────────────────────────

def _clean_text(text: str, home: str, away: str, mode: str = "match") -> str:
    """只保留与主客队相关的行，去除无关内容。
    
    Args:
        mode: "match"（含外来队名排除）/ "pre" / "post"
    """
    h_cn = to_chinese_name(home)
    a_cn = to_chinese_name(away)
    keywords = {home.lower(), away.lower(), h_cn, a_cn}
    keywords.discard("")
    for kw in list(keywords):
        keywords.add(kw + "队")
        keywords.add(kw + "人")

    skip_markers = ("返回", "首页", "上一篇", "下一篇", "编辑", "责编",
                    "来源", "更多精彩", "分享到", "缩小字体", "放大字体",
                    "收藏", "微博", "微信", "原标题")
    # 广告/无关内容关键词
    ad_keywords = ("便宜一半", "机车", "航空自卫队", "金价大跌", "新浪财经",
                   "阅读下一篇", "查看热榜", "相关推荐", "推荐阅读",
                   "特别声明", "VIP课程", "开户", "债券")

    # 外来队名 + 比分上下文：match 模式下排除（文章常是多场汇总，如"德国7-1库拉索，日本2-2荷兰"）    
    foreign_score_patterns = (
        "德国队成世界杯",          # "德国队成世界杯历史进球最多队伍"
        "恩梅查", "施洛特贝克",   # 德国球员
        "哈弗茨", "穆西亚拉", "温达夫", "布朗",
        "科梅嫩西亚", "库拉索",   # Curacao
        "欧非对话",                # 瑞典 vs 突尼斯
    )

    lines = text.split("\n")
    kept = []
    for line in lines:
        stripped = line.strip()
        if not stripped or len(stripped) < 8:
            continue
        if any(stripped.startswith(m) for m in skip_markers):
            continue
        if any(ak in stripped for ak in ad_keywords):
            continue
            
        # match 模式：排除以外来队名为主体的行
        if mode == "match":
            if any(fp in stripped for fp in foreign_score_patterns):
                continue

        line_lower = stripped.lower()
        relevant = any(kw.lower() in line_lower for kw in keywords)
        if relevant:
            kept.append(stripped)

    if len(kept) < 3:
        return text[:1500]
    return "\n".join(kept)


# ──────────────────────────────────────────────
# 4. 查询构造
# ──────────────────────────────────────────────

_NAME_MAP = {
    "netherlands": "荷兰", "japan": "日本",
    "england": "英格兰", "france": "法国",
    "germany": "德国", "spain": "西班牙",
    "italy": "意大利", "portugal": "葡萄牙",
    "argentina": "阿根廷", "brazil": "巴西",
    "sweden": "瑞典", "tunisia": "突尼斯",
    "korea": "韩国", "south korea": "韩国",
}


def to_chinese_name(name: str) -> str:
    return _NAME_MAP.get(name.strip().lower(), name)


def build_query(home: str, away: str) -> str:
    h = to_chinese_name(home); a = to_chinese_name(away)
    return f"{h} {a} 战报" if h != a else f"{home} {away} 世界杯 战报"


def build_query_fallback(home: str, away: str) -> str:
    h = to_chinese_name(home); a = to_chinese_name(away)
    return f"{h} {a} 世界杯 比分" if h != a else f"{home} {away} 比分"


def build_pre_match_query(home: str, away: str) -> str:
    h = to_chinese_name(home); a = to_chinese_name(away)
    return f"世界杯 {h} {a} 前瞻 首发 阵容"


def build_post_match_query(home: str, away: str) -> str:
    h = to_chinese_name(home); a = to_chinese_name(away)
    return f"{h} {a} 世界杯 全场比赛"


# ──────────────────────────────────────────────
# 5. 核心抓取逻辑
# ──────────────────────────────────────────────

def _fetch_with_query(home: str, away: str, query: str,
                      max_fetch: int = MAX_FETCH_ARTICLES,
                      fallback_query: str = "",
                      mode: str = "match") -> MatchContext:
    """内部：按指定搜索词抓取并清洗"""
    ctx = MatchContext()
    ctx.query = query
    articles = search_news_bing_with_fallback(query, fallback_query)
    if not articles:
        ctx.error = "搜索无结果"
        return ctx

    texts = []
    all_images = []
    for i, art in enumerate(articles[:max_fetch]):
        title = art["title"]
        url = art["url"]
        logger.info(f"  抓取 [{i+1}/{max_fetch}]: {title[:50]}...")
        time.sleep(REQUEST_DELAY)
        result = _fetch_article_raw(url, home, away)
        if not result:
            continue
        raw = result["text"]
        if len(raw) < 80:
            continue
        cleaned = _clean_text(raw, home, away, mode=mode)
        if len(cleaned) < 30:
            continue
        ctx.urls_used.append(url)
        ctx.titles_used.append(title)
        texts.append(f"【{title}】\n{cleaned}")
        for img in result.get("images", []):
            img["source_title"] = title
            all_images.append(img)

    ctx.images = all_images[:30]
    if not texts:
        ctx.error = "所有文章抓取后内容过短"
        return ctx

    ctx.text = "\n\n---\n\n".join(texts)
    ctx.success = True
    logger.info(f"  完成: {len(texts)} 篇, 共 {len(ctx.text)} 字符")
    return ctx


def fetch_match_context(home: str, away: str, query: str = "",
                        max_fetch: int = MAX_FETCH_ARTICLES) -> MatchContext:
    if not query:
        query = build_query(home, away)
    return _fetch_with_query(home, away, query, max_fetch,
                             fallback_query=build_query_fallback(home, away),
                             mode="match")


def fetch_pre_match_context(home: str, away: str, query: str = "",
                            max_fetch: int = MAX_FETCH_ARTICLES) -> MatchContext:
    if not query:
        query = build_pre_match_query(home, away)
    return _fetch_with_query(home, away, query, max_fetch, mode="pre")


def fetch_post_match_context(home: str, away: str, query: str = "",
                             max_fetch: int = MAX_FETCH_ARTICLES) -> MatchContext:
    if not query:
        query = build_post_match_query(home, away)
    return _fetch_with_query(home, away, query, max_fetch, mode="post")


def fetch_all_context(home: str, away: str,
                      max_fetch: int = MAX_FETCH_ARTICLES) -> dict:
    """返回 {"pre": ctx, "match": ctx, "post": ctx}"""
    results = {}
    logger.info("── 赛前新闻 ──")
    results["pre"] = fetch_pre_match_context(home, away, max_fetch=max_fetch)
    logger.info("── 比赛战报 ──")
    results["match"] = fetch_match_context(home, away, max_fetch=max_fetch)
    logger.info("── 赛后新闻 ──")
    results["post"] = fetch_post_match_context(home, away, max_fetch=max_fetch)
    return results


# ──────────────────────────────────────────────
# 6. 保存到目录
# ──────────────────────────────────────────────

def save_context_to_dir(
    results: dict,
    output_dir: str | Path,
    match_id: int = 0,
    home: str = "",
    away: str = "",
) -> dict:
    """
    将 fetch_all_context 的结果保存到指定目录。

    产出: output_dir/{pre.txt, match.txt, post.txt, images.json, images/}
    返回: {"pre_lines": N, "match_lines": N, "post_lines": N, "images_downloaded": N}
    """
    out_dir = Path(output_dir)
    img_dir = out_dir / "images"
    img_dir.mkdir(parents=True, exist_ok=True)

    stats = {}
    for key, ctx in results.items():
        if not ctx.success:
            stats[key] = 0
            continue
        txt_path = out_dir / f"{key}.txt"
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(f"搜索词: {ctx.query}\n来源:\n")
            for i, (t, u) in enumerate(zip(ctx.titles_used, ctx.urls_used)):
                f.write(f"  [{i+1}] {t}\n      {u}\n")
            f.write(f"\n{'─'*60}\n\n")
            f.write(ctx.text)
        stats[key] = ctx.text.count("\n") + 1
        logger.info(f"  {key}.txt: {stats[key]} 行")

    # 图片去重 + 下载
    all_imgs = []
    for ctx in results.values():
        if ctx.success:
            all_imgs.extend(ctx.images)

    seen = set()
    unique_imgs = []
    for img in all_imgs:
        if img["url"] not in seen:
            seen.add(img["url"])
            unique_imgs.append(img)

    downloaded = []
    for i, img in enumerate(unique_imgs):
        url = img["url"]
        try:
            # sina CDN SSL 兼容：先尝试 verify=True，失败则 verify=False
            r = None
            for verify_flag in (True, False):
                try:
                    r = requests.get(url, headers={"User-Agent": USER_AGENT},
                                     timeout=20, verify=verify_flag)
                    r.raise_for_status()
                    break
                except requests.exceptions.SSLError:
                    if not verify_flag:
                        raise
                    continue
            if r is None:
                raise Exception("download failed")
            ext = ".jpg"
            for e in (".jpg", ".jpeg", ".png", ".webp"):
                if e in url.lower():
                    ext = e; break
            fname = f"img_{i+1:03d}{ext}"
            fpath = img_dir / fname
            with open(fpath, "wb") as f:
                f.write(r.content)
            downloaded.append({
                "index": i + 1, "filename": fname, "url": url,
                "alt": img.get("alt", ""),
                "source_url": img.get("source_url", ""),
                "source_title": img.get("source_title", ""),
            })
        except Exception as e:
            logger.warning(f"  图片下载失败: {url[:80]}... {e}")
        time.sleep(0.3)

    img_index = out_dir / "images.json"
    with open(img_index, "w", encoding="utf-8") as f:
        json.dump({
            "match": f"{home} vs {away}",
            "match_id": match_id,
            "total": len(downloaded),
            "images": downloaded,
        }, f, ensure_ascii=False, indent=2)

    stats["images_downloaded"] = len(downloaded)
    logger.info(f"  图片: {len(downloaded)}/{len(unique_imgs)} 张")
    return stats


# ──────────────────────────────────────────────
# 命令行入口
# ──────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    # 参数解析
    args = sys.argv[1:]
    mode = "all"
    save_dir = ""
    positional = []
    valid_modes = ("match", "pre", "post", "all", "image")

    i = 0
    while i < len(args):
        a = args[i]
        if a == "--mode" and i + 1 < len(args):
            mode = args[i + 1]; i += 2
        elif a == "--save" and i + 1 < len(args):
            save_dir = args[i + 1]; i += 2
        elif a in valid_modes:
            i += 1  # skip mode values not preceded by --mode
        else:
            positional.append(a); i += 1

    home = positional[0] if len(positional) >= 1 else "荷兰"
    away = positional[1] if len(positional) >= 2 else "日本"

    # 从 raw_data 推断队名（如果给了 match_id）
    match_id = 0
    if positional and positional[0].isdigit():
        match_id = int(positional[0])
        raw_path = Path(f"data/raw/{match_id}/raw_data.json")
        if raw_path.exists():
            with open(raw_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            home = raw.get("home_team", {}).get("name", home)
            away = raw.get("away_team", {}).get("name", away)
            # 默认 save 到 output/{match_id}_{home}_vs_{away}/web_context/
            if not save_dir:
                save_dir = str(Path(f"output/{match_id}_{home}_vs_{away}/web_context"))

    print(f"\n{'='*60}")
    print(f"联网搜索: {home} vs {away}  [mode={mode}]")
    print(f"{'='*60}")

    if mode == "pre":
        ctx = fetch_pre_match_context(home, away)
    elif mode == "post":
        ctx = fetch_post_match_context(home, away)
    elif mode == "match":
        ctx = fetch_match_context(home, away)
    elif mode == "image":
        ctx = fetch_match_context(home, away, max_fetch=3)
    else:
        results = fetch_all_context(home, away)
        if save_dir:
            stats = save_context_to_dir(results, save_dir, match_id, home, away)
            print(f"\n保存完成: {save_dir}")
            for k, v in stats.items():
                print(f"  {k}: {v}")
            sys.exit(0)
        # else: print all
        def _print_ctx(label, ctx):
            print(f"\n{'─'*40}")
            print(f"  [{label}] {ctx.query}")
            if not ctx.success:
                print(f"  [{label}] 失败: {ctx.error}"); return
            for i, (t, u) in enumerate(zip(ctx.titles_used, ctx.urls_used)):
                print(f"  [{i+1}] {t[:60]}\n      {u[:100]}")
            print(ctx.text[:2500])
            if ctx.images:
                print(f"\n  ── 图片 ({len(ctx.images)} 张) ──")
                for img in ctx.images[:10]:
                    alt = img.get("alt", "")[:30]
                    print(f"  {img['url'][:100]}")
                    if alt: print(f"    alt: {alt}")
        _print_ctx("赛前", results["pre"])
        _print_ctx("战报", results["match"])
        _print_ctx("赛后", results["post"])
        sys.exit(0)

    # 单个 mode 处理
    if save_dir:
        results = {"match": ctx} if mode in ("match", "image") else {mode: ctx}
        stats = save_context_to_dir(results, save_dir, match_id, home, away)
        print(f"\n保存完成: {save_dir}")
        for k, v in stats.items():
            print(f"  {k}: {v}")
    else:
        _print_ctx_single = lambda label, ctx: (
            print(f"\n{'─'*40}\n  [{label}] {ctx.query}\n  {ctx.text[:3000]}")
            or (print(f"\n  ── 图片 ({len(ctx.images)} 张) ──")
                if ctx.images else None)
            or [print(f"  {img['url'][:120]}") for img in ctx.images[:10]]
        )
        label_map = {"pre": "赛前", "post": "赛后", "match": "战报", "image": "图片"}
        label = label_map.get(mode, mode)
        if mode == "image":
            ctx = fetch_match_context(home, away, max_fetch=3)
            print(f"\n  [图片] 共 {len(ctx.images)} 张")
            for img in ctx.images:
                print(f"  {img['url']}")
        else:
            _print_ctx_single(label, ctx)

    print(f"\n{'─'*40}\n{'='*60}")
