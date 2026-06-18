"""
央视网新闻抓取工具 (v2) — 基于 Kimi WebBridge /command API
==========================================================
专用于 cctv.com 搜索，处理 search.cctv.com 的 link_p.php 包装链接，
提取正文并调用 LLM 生成 160-300 字摘要。

用法: python cctv_news_fetcher.py 西班牙 佛得角
"""
import urllib.request, json, time, re, argparse, logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import List
from urllib.parse import unquote, parse_qs, urlparse

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

WB_URL = "http://localhost:10086/command"

# ═══════════════════════════════════════════════
# WebBridge 封装
# ═══════════════════════════════════════════════

def wb(action: str, **params) -> dict:
    body = json.dumps({"action": action, **params}).encode()
    req = urllib.request.Request(WB_URL, data=body,
        headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=90).read())

def nav(url: str) -> bool:
    r = wb("navigate", url=url)
    return r.get("ok") and r.get("data", {}).get("success")

def js(code: str) -> str:
    r = wb("evaluate", code=code)
    if not r.get("ok"):
        raise RuntimeError(f"evaluate: {r.get('error')}")
    return r["data"]["value"]

# ═══════════════════════════════════════════════
# 央视网搜索
# ═══════════════════════════════════════════════

def _parse_cctv_url(wrapped_url: str) -> str:
    """解析 search.cctv.com/link_p.php?targetpage=... 获取真实 URL"""
    if "link_p.php" not in wrapped_url:
        return wrapped_url
    try:
        qs = parse_qs(urlparse(wrapped_url).query)
        target = qs.get("targetpage", [""])[0]
        return unquote(target)
    except:
        return wrapped_url

def search_cctv(query: str, max_results: int = 10) -> List[dict]:
    """搜索央视网，获取多页结果，只保留 2026 年体育频道文章"""
    import urllib.parse
    all_articles = []
    
    for page in [1, 2]:
        url = f"https://search.cctv.com/search.php?qtext={urllib.parse.quote(query)}&type=web&sort=relevance&vtime=&datepid=1&channel=&page={page}"
        logger.info(f"  CCTV搜索 page{page}: {query}")
        nav(url)
        time.sleep(5)

        code = """(()=>{
            const r=[]; const seen=new Set();
            document.querySelectorAll('a').forEach(a=>{
                const h=a.href||''; const t=(a.textContent||'').trim().replace(/\\s+/g,' ');
                if((h.includes('sports.cctv.com')||h.includes('search.cctv.com/link_p')) && t.length>10 && !seen.has(h)){
                    seen.add(h);
                    r.push({title:t.substring(0,120), url:h});
                }
            });
            return JSON.stringify(r.slice(0,""" + str(max_results) + """));
        })()"""
        
        raw = json.loads(js(code))
        for a in raw:
            real_url = _parse_cctv_url(a["url"])
            if "sports.cctv.com/2026/" not in real_url:
                continue
            all_articles.append({"title": a["title"], "url": real_url})
        
        if len(all_articles) >= max_results:
            break
    
    logger.info(f"  共找到 {len(all_articles)} 条")
    return all_articles

def extract_content(url: str) -> str:
    """打开文章页，提取正文"""
    nav(url)
    time.sleep(4)
    
    code = """(()=>{
        // sports.cctv.com 正文容器：优先用 id 选择器
        const selectors = [
            '#content_area', '#article_area', '#text_area', 
            '[id*=content_area]', '[id*=article_area]',
            '.TRS_Editor', '.cnt_content', '.article_content',
            '[class*=article-body]', '[class*=article_content]',
            '.article-content', '.text_content',
            'article',
        ];
        let art = null;
        for (const s of selectors) {
            const el = document.querySelector(s);
            if (el && el.innerText.length > 50) {
                art = el; break;
            }
        }
        if (!art) { art = document.body; }
        
        let text = art.innerText || '';
        const lines = text.split('\\n').filter(l => {
            const t = l.trim();
            if (t.length < 6) return false;
            // 过滤纯元数据行（非正文内容）
            if (/^(返回|首页|导航|上一篇|下一篇|编辑|责编|来源|分享|扫描|扫一扫|二维码|©|Copyright|法律声明|京ICP|京公网|中央广播|总台|违法和不良|信息网络传播|控制面板)\s*$/i.test(t)) return false;
            return true;
        });
        return lines.join('\\n').substring(0, 5000);
    })()"""
    return js(code)

# ═══════════════════════════════════════════════
# LLM 摘要
# ═══════════════════════════════════════════════

@dataclass
class ArticleSummary:
    title: str
    url: str
    summary: str = ""

@dataclass
class NewsReport:
    home: str; away: str
    pre: List[ArticleSummary] = field(default_factory=list)
    match: List[ArticleSummary] = field(default_factory=list)
    post: List[ArticleSummary] = field(default_factory=list)

def summarize(articles: List[dict], category: str, llm_client, max_n: int = 5) -> List[ArticleSummary]:
    """LLM 摘要"""
    from jinja2 import Template
    import yaml
    tpl = yaml.safe_load(open("prompts/news_summarize.yaml", "r", encoding="utf-8"))
    sys_p, user_tpl = tpl["system"], Template(tpl["user"])

    results = []
    for i, a in enumerate(articles[:max_n]):
        logger.info(f"  [{category}] {a['title'][:50]}...")
        body = extract_content(a["url"])
        if not body or len(body) < 80:
            logger.warning(f"    内容过短({len(body)}字)")
            results.append(ArticleSummary(a["title"], a["url"]))
            continue
        
        summary = ""
        if llm_client:
            prompt = user_tpl.render(title=a["title"], body=body[:3000])
            for att in range(3):
                try:
                    s = llm_client.generate(sys_p, prompt, max_tokens=600)
                    if s and len(s) >= 80:
                        summary = s.strip(); break
                except: pass
                time.sleep(1)
        
        results.append(ArticleSummary(a["title"], a["url"], summary))
        cn = sum(1 for c in summary if '\u4e00' <= c <= '\u9fff')
        logger.info(f"    摘要: {cn}字" if summary else "    摘要: 未生成")
        time.sleep(1)
    
    return results

# ═══════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════

SEARCH_QUERIES = {
    "pre": "{home} {away} 世界杯 前瞻",
    "match": "{home} {away} 世界杯 战报",
    "post": "{home} {away} 世界杯 赛后",  
}

def _classify_article(title: str, url: str) -> str:
    """根据标题关键词分类文章"""
    t = title.lower()
    # 赛后相关
    if any(kw in t for kw in ['赛后', '最佳', '当选', '评分', '总结', '复盘', '分析', '点评']):
        return "post"
    # 战报相关
    if any(kw in t for kw in ['战报', '逼平', '爆冷', '险胜', '绝杀', '完胜', '告负', '取胜', 
                               '获胜', '晋级', '淘汰', '比分', '实录', '直击', '战平']):
        return "match"
    # 前瞻相关
    if any(kw in t for kw in ['前瞻', '预测', '预告', '赔率', '前瞻', '首轮', '小组赛',
                               '执法', '裁判', '名单', '首发', '阵容', '公布']):
        return "pre"
    return "match"  # default to match

def fetch(home: str, away: str, llm_client=None) -> NewsReport:
    """全局收集→去重→分类→摘要"""
    report = NewsReport(home, away)
    
    # Step 1: 全局收集所有文章
    all_arts = {}
    for key, q_tpl in [("pre","赛前"),("match","战报"),("post","赛后")]:
        q = SEARCH_QUERIES[key].format(home=home, away=away)
        logger.info(f"  搜索 {q_tpl}: {q}")
        for a in search_cctv(q, max_results=8):
            if a["url"] not in all_arts:
                all_arts[a["url"]] = {"title": a["title"], "url": a["url"]}
    
    articles = list(all_arts.values())
    logger.info(f"  去重后共 {len(articles)} 篇")
    
    # Step 2: 按标题分类
    classified = {"pre": [], "match": [], "post": []}
    for a in articles:
        cat = _classify_article(a["title"], a["url"])
        classified[cat].append(a)
    
    # Step 3: 各层取前5篇生成摘要
    for key, label in [("pre","赛前"),("match","战报"),("post","赛后")]:
        arts = classified[key][:5]
        logger.info(f"\n── {label}新闻: {len(arts)}篇 ──")
        if not arts:
            continue
        s = summarize(arts, label, llm_client)
        setattr(report, key, s)
    
    return report

def save_md(report: NewsReport, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = [f"# 央视网·2026美加墨世界杯 {report.home}vs{report.away} 新闻合集", ""]
    
    sections = [("一、赛前前瞻新闻", report.pre), ("二、全场实时赛况战报新闻", report.match), ("三、赛后复盘新闻", report.post)]
    for title, arts in sections:
        lines.extend([f"## {title}", ""])
        for i, a in enumerate(arts, 1):
            lines.append(f"### {i}.《{a.title}》")
            if a.url: lines.append(f"URL: `{a.url}`")
            if a.summary:
                cn = sum(1 for c in a.summary if '\u4e00' <= c <= '\u9fff')
                lines.append(f"摘要：{a.summary}（{cn}字）")
            else:
                lines.append("摘要：（未生成）")
            lines.extend(["", ""])
    
    p = out_dir / "structured_news.md"
    p.write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"\n报告: {p}")
    return p

if __name__ == "__main__":
    import yaml, sys
    from src.generator.llm_client import LLMClient

    p = argparse.ArgumentParser()
    p.add_argument("home"); p.add_argument("away")
    p.add_argument("--output","-o",default="")
    p.add_argument("--no-llm",action="store_true")
    args = p.parse_args()

    llm = None
    if not args.no_llm:
        llm = LLMClient(yaml.safe_load(open("config.yaml","r",encoding="utf-8"))["llm"])

    out = Path(args.output) if args.output else Path(f"output/_cctv_{args.home}_{args.away}")
    report = fetch(args.home, args.away, llm_client=llm)
    save_md(report, out)
    
    t = len(report.pre)+len(report.match)+len(report.post)
    print(f"\n完成: {len(report.pre)}赛前/{len(report.match)}战报/{len(report.post)}赛后 = {t}篇")
