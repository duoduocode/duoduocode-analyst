"""
Sofascore Player Stats 采集工具
===============================
通过 Kimi WebBridge 控制浏览器，在 Sofascore 上定位指定比赛
并提取 Player Stats 球员统计数据。

依赖：Kimi WebBridge 守护进程运行在 localhost:10086

用法：
    python sofascore_player_stats.py <match_url>
    python sofascore_player_stats.py <match_url> --subtab Attacking
    python sofascore_player_stats.py <match_url> --all-subtabs --output result.json
    python sofascore_player_stats.py --search "PSG Arsenal" --tournament ucl
"""

import urllib.request, json, time, re, shutil, os, argparse, sys

# ============================================================
# Kimi WebBridge API 封装
# ============================================================

WEBBRIDGE_URL = "http://localhost:10086/command"
TIMEOUT = 30

def cmd(action, **params):
    """调用 WebBridge HTTP API"""
    body = {"action": action, **params}
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        WEBBRIDGE_URL,
        data=data,
        headers={"Content-Type": "application/json"}
    )
    resp = urllib.request.urlopen(req, timeout=TIMEOUT)
    return json.loads(resp.read())

def nav(url):
    """导航到指定 URL"""
    r = cmd("navigate", url=url)
    ok = r.get("ok") and r.get("data", {}).get("success")
    if not ok:
        print(f"[WARN] navigate failed: {r}")
    return ok

def js(code):
    """执行 JS 并返回字符串结果"""
    r = cmd("evaluate", code=code)
    if not r.get("ok"):
        raise RuntimeError(f"evaluate error: {r.get('error', {}).get('message')}")
    return r["data"]["value"]

def click(selector):
    """点击 CSS 选择器"""
    r = cmd("click", selector=selector)
    ok = r.get("ok") and r.get("data", {}).get("success")
    if not ok:
        print(f"[WARN] click '{selector}' failed: {r}")
    return ok

def screenshot():
    """截图并返回文件路径"""
    r = cmd("screenshot")
    if r.get("ok"):
        return r["data"]["path"]
    return None

def wait(seconds=3):
    """等待页面渲染"""
    time.sleep(seconds)

# ============================================================
# Sofascore 赛事 & 搜索
# ============================================================

# 已知赛事页面 URL
TOURNAMENT_URLS = {
    "ucl":      "https://www.sofascore.com/tournament/football/europe/uefa-champions-league/7",
    "uel":      "https://www.sofascore.com/tournament/football/europe/uefa-europa-league/17015",
    "premier":  "https://www.sofascore.com/tournament/football/england/premier-league/17",
    "laliga":   "https://www.sofascore.com/tournament/football/spain/laliga/8",
    "seriea":   "https://www.sofascore.com/tournament/football/italy/serie-a/23",
    "bundesliga":"https://www.sofascore.com/tournament/football/germany/bundesliga/35",
    "ligue1":   "https://www.sofascore.com/tournament/football/france/ligue-1/34",
    "worldcup": "https://www.sofascore.com/tournament/football/world/world-cup/16",
}

def find_match_on_page(keywords, tournament=None):
    """在赛事页面上搜索比赛链接"""
    if tournament and tournament.lower() in TOURNAMENT_URLS:
        nav(TOURNAMENT_URLS[tournament.lower()])
        wait(5)
    
    # JS 搜索匹配的比赛链接
    kw_list = [k.strip().lower() for k in keywords.split(",")]
    kw_js = json.dumps(kw_list)
    
    code = f"""
    (function() {{
        var keywords = {kw_js};
        var allLinks = document.querySelectorAll("a[href*='/match/']");
        var matches = [];
        allLinks.forEach(function(a) {{
            var href = a.href;
            var text = a.textContent.trim();
            var lower = (text + " " + href).toLowerCase();
            for (var i = 0; i < keywords.length; i++) {{
                if (lower.indexOf(keywords[i]) !== -1) {{
                    matches.push({{text: text.substring(0,80), href: href}});
                    break;
                }}
            }}
        }});
        return JSON.stringify(matches.slice(0, 20));
    }})()
    """
    result = js(code)
    matches = json.loads(result)
    
    if not matches:
        print("[WARN] 未找到匹配的比赛链接")
        return None
    
    # 优先选择包含 "final" 或所有关键词的链接
    for m in matches:
        if "final" in m.get("text", "").lower():
            return m["href"]
    return matches[0]["href"]

# ============================================================
# Player Stats 提取
# ============================================================

# 子分类 tab 映射
SUBTAB_MAP = {
    "general":     "tab-summaryGroup",
    "attacking":   "tab-attackGroup",
    "defending":   "tab-defenceGroup",
    "passing":     "tab-passingGroup",
    "duels":       "tab-duelsGroup",
    "goalkeeping": "tab-goalkeeperGroup",
}

def click_player_stats():
    """点击 Player stats 标签"""
    # 方法1: 用 data-testid 点击
    if click("[data-testid=tab-2]"):
        wait(3)
        return True
    
    # 方法2: 用 ref 点击（通过 snapshot）
    r = cmd("snapshot")
    tree = json.dumps(r.get("data", {}).get("tree", []))
    for m in re.finditer(r'"name":"Player stats"', tree):
        snippet = tree[max(0, m.start()-60):m.start()+150]
        refs = re.findall(r'"ref":"(@\w+)"', snippet)
        if refs:
            if click(refs[0]):
                wait(3)
                return True
    return False

def click_subtab(name):
    """点击子分类 tab"""
    testid = SUBTAB_MAP.get(name.lower().replace(" ", ""))
    if not testid:
        print(f"[WARN] 未知子分类: {name}, 可用: {list(SUBTAB_MAP.keys())}")
        return False
    if click(f"[data-testid={testid}]"):
        wait(2)
        return True
    return False

def extract_table():
    """提取当前表格数据"""
    code = """
    (function() {
        var tbl = document.querySelector("table");
        if (!tbl) return JSON.stringify({error: "no table found"});
        var rows = [];
        tbl.querySelectorAll("tr").forEach(function(tr) {
            var cells = [];
            tr.querySelectorAll("td, th").forEach(function(td) {
                cells.push(td.textContent.trim());
            });
            if (cells.length > 0) rows.push(cells);
        });
        return JSON.stringify(rows);
    })()
    """
    result = js(code)
    return json.loads(result)

def table_to_dict(rows):
    """将二维数组转为 dict 列表，第一行为表头"""
    if not rows or len(rows) < 2:
        return rows
    headers = rows[0]
    records = []
    for row in rows[1:]:
        rec = {}
        for i, h in enumerate(headers):
            rec[h] = row[i] if i < len(row) else ""
        records.append(rec)
    return records

# ============================================================
# 主流程
# ============================================================

def fetch_player_stats(match_url=None, keywords=None, tournament=None,
                       subtabs=None, all_subtabs=False, output=None):
    """
    主入口：获取比赛球员统计
    
    参数:
        match_url:   比赛页面 URL
        keywords:    搜索关键词（如 "PSG,Arsenal"）
        tournament:  赛事代码（如 "ucl"）
        subtabs:     要提取的子分类列表
        all_subtabs: 是否提取所有子分类
        output:      JSON 输出文件路径
    """
    result = {
        "source": match_url,
        "player_stats": {}
    }
    
    # Step 1: 定位比赛
    if match_url:
        print(f"[1/5] 导航到比赛页面: {match_url}")
        nav(match_url)
    elif keywords:
        print(f"[1/5] 搜索比赛: {keywords}")
        if tournament:
            print(f"      赛事: {tournament}")
        match_url = find_match_on_page(keywords, tournament)
        if not match_url:
            print("[ERROR] 未找到比赛")
            return None
        print(f"      找到: {match_url}")
        nav(match_url)
    else:
        print("[ERROR] 请提供 match_url 或 --search 关键词")
        return None
    
    wait(5)
    
    # 验证页面
    title_url = js("(function(){return document.title + ' ||| ' + window.location.href;})()")
    print(f"      页面: {title_url[:120]}")
    result["source"] = title_url.split(" ||| ")[1] if " ||| " in title_url else match_url
    
    # Step 2: 点击 Player stats
    print("[2/5] 点击 Player stats 标签...")
    if not click_player_stats():
        print("[ERROR] 无法点击 Player stats 标签")
        return result
    
    # Step 3: 确定要提取的子分类
    if all_subtabs:
        subtabs = list(SUBTAB_MAP.keys())
    elif subtabs is None:
        subtabs = ["general"]  # 默认只提取 General
    
    # Step 4: 逐个子分类提取
    for i, name in enumerate(subtabs):
        label = name.capitalize()
        print(f"[3/5] [{i+1}/{len(subtabs)}] 提取 {label}...")
        
        if name.lower() != "general":
            if not click_subtab(name):
                print(f"      [WARN] 无法切换到 {label}")
                continue
        else:
            # General 默认激活，无需切换
            pass
        
        wait(2)
        rows = extract_table()
        if isinstance(rows, dict) and "error" in rows:
            print(f"      [WARN] {rows['error']}")
            continue
        
        records = table_to_dict(rows)
        result["player_stats"][label] = {
            "headers": rows[0] if rows else [],
            "players": records
        }
        print(f"      {len(records)} 名球员")
    
    # Step 5: 保存结果
    print("[4/5] 保存结果...")
    if output:
        os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
        with open(output, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"      已保存: {output}")
    
    # 截图
    print("[5/5] 截图...")
    screenshot_path = screenshot()
    if screenshot_path:
        print(f"      截图: {screenshot_path}")
        # 复制到 output 目录
        dst_dir = r"d:\football-data\output"
        os.makedirs(dst_dir, exist_ok=True)
        dst = os.path.join(dst_dir, "sofascore_player_stats.png")
        shutil.copy(screenshot_path, dst)
        print(f"      已复制到: {dst}")
    
    return result

# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Sofascore Player Stats 采集工具（通过 Kimi WebBridge）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python sofascore_player_stats.py https://www.sofascore.com/football/match/paris-saint-germain-arsenal/RsUH
  python sofascore_player_stats.py --search "PSG,Arsenal" --tournament ucl
  python sofascore_player_stats.py <url> --all-subtabs --output result.json
  python sofascore_player_stats.py <url> --subtab General --subtab Attacking
        """
    )
    parser.add_argument("url", nargs="?", help="Sofascore 比赛页面 URL")
    parser.add_argument("--search", "-s", help="搜索关键词，逗号分隔，如 'PSG,Arsenal'")
    parser.add_argument("--tournament", "-t", choices=list(TOURNAMENT_URLS.keys()),
                        help="赛事代码: ucl, premier, laliga 等")
    parser.add_argument("--subtab", action="append", dest="subtabs",
                        choices=list(SUBTAB_MAP.keys()),
                        help="要提取的子分类（可重复使用）")
    parser.add_argument("--all-subtabs", action="store_true",
                        help="提取所有子分类")
    parser.add_argument("--output", "-o", help="JSON 输出路径")
    
    args = parser.parse_args()
    
    result = fetch_player_stats(
        match_url=args.url,
        keywords=args.search,
        tournament=args.tournament,
        subtabs=args.subtabs,
        all_subtabs=args.all_subtabs,
        output=args.output
    )
    
    if result and result.get("player_stats"):
        # 打印摘要
        print("\n" + "=" * 60)
        for tab_name, tab_data in result["player_stats"].items():
            print(f"\n--- {tab_name} ---")
            players = tab_data.get("players", [])
            for p in players[:5]:  # 显示前5名
                name = p.get("", p.get("+", p.get(list(p.keys())[0] if p else "", "")))
                if name and not name.startswith("+"):
                    rating = p.get("Sofascore Rating", "")
                    goals = p.get("Goals", "")
                    pos = p.get("Position", "")
                    print(f"  {name:<22s} {pos:<3s} G:{goals:<3s} Rating:{rating}")
            if len(players) > 5:
                print(f"  ... 共 {len(players)} 名球员")
    else:
        print("\n[WARN] 未提取到数据")
        sys.exit(1)

if __name__ == "__main__":
    main()
