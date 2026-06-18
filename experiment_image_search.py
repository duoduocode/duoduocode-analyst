"""豆包联网搜索图片获取实验"""
import requests, json, time

KEY = "ark-b3a3d353-b34b-4310-a789-8e88b3cd3269-51821"
HEADERS = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
BASE = "https://ark.cn-beijing.volces.com/api/v3"
MODEL = "doubao-seed-2-0-pro-260215"

prompt = """请联网搜索2026年美加墨世界杯法国对塞内加尔比赛的现场图片和进球瞬间图片，需要包含：
1. 比赛现场全景图
2. 姆巴佩进球庆祝瞬间
3. 双方首发阵容合影

请直接给出你能获取到的图片URL链接，每条单独一行，标注图片描述。如果没有获取到图片，请如实告诉我。"""

print("调用豆包 Responses API (联网搜索 索图)...")
t0 = time.time()

resp = requests.post(f"{BASE}/responses", headers=HEADERS, json={
    "model": MODEL,
    "input": [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
    "tools": [{"type": "web_search"}],
    "max_output_tokens": 2048,
}, timeout=120)

elapsed = time.time() - t0
data = resp.json()

print(f"status={resp.status_code} 耗时 {elapsed:.1f}s")

# 打印完整的 output 结构，看有没有图片相关字段
output = data.get("output", [])
for i, item in enumerate(output):
    print(f"\n--- output[{i}] type={item.get('type', '?')} ---")
    if item.get("type") == "message":
        for j, part in enumerate(item.get("content", [])):
            ptype = part.get("type", "?")
            print(f"  content[{j}] type={ptype}")
            if ptype == "output_text":
                print(f"    text: {part['text'][:600]}")
            elif ptype in ("image", "input_image"):
                print(f"    image_url: {part.get('image_url', '?')[:200]}")
            # 看有没有 annotations
            if "annotations" in part:
                print(f"    annotations: {json.dumps(part['annotations'], ensure_ascii=False)[:500]}")
    elif item.get("type") == "web_search_call":
        print(f"  search results count: {len(item.get('results', []))}")
        for r in item.get("results", [])[:3]:
            print(f"    title: {r.get('title', '')[:80]}")
            print(f"    url: {r.get('url', '')[:150]}")

# 打印 usage
usage = data.get("usage", {})
print(f"\nusage: {usage}")

# 全量 JSON 保存以便详细分析
with open("output/doubao_experiment/image_test_raw.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print(f"\n完整响应已保存到 output/doubao_experiment/image_test_raw.json")
