# AGENTS.md — AI 足球分析员 (Football Analyst)

> 本文档供 AI Agent 理解项目上下文、架构与常见问题，便于在新环境中快速上手调试。

---

## 1. 项目概述

**目标**：从 **SportMonks Football API V3** 获取比赛数据 → 计算自创指标 → 调用 DeepSeek LLM 生成分析文字 → mplsoccer 生成图表 → 拼装 Markdown 图文比赛报告，适配微信公众号发布。

**技术栈**：Python 3.11+ / requests / pyyaml / matplotlib / mplsoccer / numpy / scipy / markdown / jinja2

**LLM**：DeepSeek (`deepseek-chat` / `deepseek-v4-pro`)，OpenAI 兼容协议，支持两种调用方式：
- 优先尝试 `openai` SDK (Python 包)
- 后备：纯 `requests` HTTP POST 到 `/chat/completions`

**数据来源**：SportMonks V3 — 单次 API 请求获取全部数据（统计+事件+阵容+比分+球队信息）。

---

## 2. 快速启动

```bash
# 1. 安装依赖
pip install requests pyyaml matplotlib mplsoccer numpy scipy openai markdown jinja2

# 2. 配置 API Key（两种方式）
#    方式A: 写到 config.yaml（已配置则跳过）
#    方式B: 环境变量
set SPORTMONKS_API_TOKEN=你的token
set DEEPSEEK_API_KEY=你的key

# 3. 生成报告
python run.py --match 19683241                    # 单场完整报告 (PSG vs Arsenal)
python run.py --match 19683241 --dry-run           # 仅采集+计算，不调 LLM
python run.py --match 19683241 --no-images         # 跳过图表（matplotlib 不可用时）
python run.py --league 732 --date 2026-06-14       # 批量生成某日全部比赛
```

---

## 3. 项目结构

```
duoduocode-analyst/
├── config.yaml                          # SportMonks API Token + LLM 配置
├── config.example.yaml
├── run.py                               # 入口脚本
├── AGENTS.md                            # 本文档
├── prompts/                             # 9 个 Jinja2+YAML Prompt 模板
│   ├── cover.yaml / contrast.yaml / momentum.yaml / tactics.yaml
│   ├── mvp.yaml / hidden_mvp.yaml / black_hole.yaml
│   └── subs.yaml / replay.yaml
├── src/
│   ├── collector/
│   │   └── api_client.py               # SportMonks V3 客户端 + type_id 映射表
│   ├── engine/
│   │   ├── metrics.py                  # CI/TCR/PE + ComputedData + compute_all
│   │   ├── ratings.py                  # 球员贡献分 + MVP/隐性MVP/黑洞 分类
│   │   └── simulator.py                # 蒙特卡洛 xG 模拟 + LDI
│   ├── composer/
│   │   ├── prompt_loader.py            # YAML 加载 + Jinja2 渲染
│   │   └── data_builder.py             # 9 个模块的数据→Prompt 组装
│   ├── generator/
│   │   └── llm_client.py              # DeepSeek（openai SDK 优先，requests 后备）
│   ├── visualizer/
│   │   ├── __init__.py                 # 颜色常量 + matplotlib 中文字体配置
│   │   ├── shots.py                    # mplsoccer 射门分布图
│   │   ├── momentum.py                 # 动量曲线 + 事件标注
│   │   ├── pass_network.py             # mplsoccer 传球网络图
│   │   ├── radar.py                    # 球员雷达图 (7维度)
│   │   ├── subs.py                     # 换人对比柱状图
│   │   └── xg_hist.py                  # xG 模拟分布图
│   ├── reporter/
│   │   └── build_report.py            # Markdown + HTML 报告拼装（含队徽/头像/中文名）
│   └── player_names.py                # 球员中英文名映射表
├── design/                             # 产品文档
│   ├── SportMonks统计指标全集.md        # 全部可用的球队+球员+事件指标
│   └── SportMonks指标升级对比.md        # 套餐升级前后对比
├── data/
│   ├── raw/{match_id}/raw_data.json    # 解析后的结构化数据
│   └── computed/{match_id}.json        # 计算后指标
└── output/{match_id}_{HOME}_vs_{AWAY}/
    ├── images/*.png                    # 7 张图表
    ├── report.md                       # 完整图文报告
    └── report.html                     # HTML 版本
```

---

## 4. 核心架构与数据流

```
run.py
  ├─ 1. load_config() → 读取 config.yaml，替换 ${ENV_VAR} 占位符
  ├─ 2. fetch_all(match_id) → SportMonks 单次请求
  │      GET /fixtures/{id}?include=statistics;lineups.details;events;participants;scores
  │      ├─ statistics[] → type_id 转换 → home_stats / away_stats (dict, 40 项)
  │      ├─ lineups.details[] → type_id 转换 → home_players / away_players (PlayerStats)
  │      ├─ events[] → type_id 转换 → events (MatchEvent)
  │      ├─ participants[] → TeamInfo (id, name, logo_url)
  │      └─ scores[] → ScoreInfo
  ├─ 3. compute_all() → 计算 CI/TCR/PE/LDI/动量/球员分类/标签
  ├─ 4. generate_all_texts() → 9 次 LLM 调用
  ├─ 5. generate_all_visuals() → 7 张 mplsoccer 图表 (可选)
  └─ 6. build_report() → Markdown + HTML 输出
```

---

## 5. 关键适配：SportMonks type_id 体系

⚠️ **SportMonks 用整数 `type_id` 编码所有统计和事件，不使用字段名。** 映射表集中在 `src/collector/api_client.py`。

### 5.1 球队统计映射 (`FIXTURE_STAT_MAP`)

40 项球队级指标，完整列表见 `design/SportMonks统计指标全集.md`。

```python
FIXTURE_STAT_MAP: dict[int, str] = {
    34: "Corner Kicks",      45: "Ball Possession",
    42: "Total Shots",       86: "Shots on Goal",
    41: "Shots off Goal",    58: "Blocked Shots",
    49: "Shots insidebox",   50: "Shots outsidebox",
    64: "Hit Woodwork",      580: "Big Chances Created",
    581: "Big Chances Missed", 80: "Total passes",
    81: "Successful Passes", 82: "Passes %",
    117: "Key Passes",       78: "Tackles",
    100: "Interceptions",    56: "Fouls",
    106: "Duels Won",        108: "Dribbles Attempts",
    109: "Successful Dribbles", 65: "Successful Headers",
    98: "Crosses",           99: "Accurate Crosses",
    43: "Attacks",           44: "Dangerous Attacks",
    52: "Goals",             79: "Assists",
    59: "Substitutions",     87: "Injuries",
    # ... 等共 40 项
}
```

### 5.2 球员统计映射 (`PLAYER_STAT_MAP`)

25 项球员级指标，含高阶数据：

```python
PLAYER_STAT_MAP: dict[int, str] = {
    118: "rating",           119: "minutes_played",
    52: "goals",             79: "assists",
    42: "shots_total",       86: "shots_on",
    80: "passes_total",      117: "passes_key",
    1584: "passes_accuracy", 78: "tackles_total",
    100: "tackles_interceptions", 105: "duels_total",
    106: "duels_won",        108: "dribbles_attempts",
    109: "dribbles_success", 56: "fouls_committed",
    96: "fouls_drawn",       98: "crosses",
    57: "saves",
    # 高阶 (需套餐支持)
    5304: "xg",              5305: "xgot",
    27271: "ball_recoveries",
}
```

### 5.3 事件类型映射 (`_parse_events`)

基于 fixture 19683241 (PSG vs Arsenal 含加时+点球大战) 实测验证：

| type_id | 含义 | event_type | detail |
|--------:|------|:---:|------|
| 10 | 点球判罚 | Info | penalty_awarded |
| 14 | 运动战进球 | Goal | goal |
| 15 | 射门尝试 | Shot | shot_attempt |
| 16 | 点球进球 | Goal | goal_penalty |
| 17 | 点球罚失 | Goal | missed_penalty |
| 18 | 换人 | subst | substitution |
| 19 | 黄牌 | Card | yellowcard |
| 20 | 两黄变红 | Card | yellowredcard |
| 21 | 直红 | Card | redcard |
| 22 | 点球大战罚失/被扑 | Goal | pen_shootout_miss |
| 23 | 点球大战进球 | Goal | pen_shootout_goal |
| 55 | VAR | VAR | var |

⚠️ 换人事件：`player_name` = 换上球员 → `assist_name`；`related_player_name` = 换下球员 → `player_name`（与 API-Football 相反）。
⚠️ 进球事件：`related_player_name` = 助攻者 → `assist_name`。

### 5.4 认证方式

```python
# SportMonks: api_token 作为 query param
requests.get(url, params={"api_token": token, "include": "..."})
```

---

## 6. 自创指标速查

| 指标 | 公式（核心） | 范围 | 数据源 |
|---|---|---|---|
| **CI** 控制指数 | 0.35×控球 + 0.25×传球 + 0.25×区域 + 0.15×回收 | 0-100 (两队之和=100) | Possession%, Pass%, Shots insidebox, Corners, Ball Recoveries |
| **TCR** 威胁转化率 | 100×(xG+0.3×绝佳机会)/(射门+0.3×角球) | 通常 2-35 | xG, Big Chances, Total Shots, Corners |
| **PE%** 压迫效率 | 100×(回收/(犯规+1)) / 双方之和 | 0-100 | Ball Recoveries, Fouls |
| **LDI** 运气偏离 | P(实际比分)/P(最可能比分) | 0-1+ | xG + 蒙特卡洛模拟 |

指标解读区间见 `src/engine/metrics.py`。

---

## 7. 降级策略

| 场景 | 策略 |
|---|---|
| `scipy` 未安装 | → 尝试 `numpy.random.poisson` |
| `numpy` 未安装 | → 纯 Python Knuth 算法，模拟次数降至 2000 |
| `matplotlib` / `mplsoccer` 未安装 | → `--no-images` 跳过图表 |
| `openai` SDK 未安装 | → LLMClient 自动降级为 `requests` HTTP POST |
| xG 无球队级 | → 从球员 xG(5304) 汇总 |
| Ball Recoveries 无球队级 | → 从球员 ball_recoveries(27271) 汇总 |
| 中文方框 | → `src/visualizer/__init__.py` 已配置 SimHei / Microsoft YaHei |

---

## 8. 调试建议

### 8.1 先 dry-run
```bash
python run.py --match 19683241 --dry-run
```
只拉数据 + 算指标，不调 LLM。检查 `data/raw/{id}/raw_data.json` 确认字段是否正确。

### 8.2 查看当前可用指标
```bash
python -c "import json; d=json.load(open('data/raw/19683241/raw_data.json','utf-8')); print(list(d['home_stats'].keys()))"
```

### 8.3 检查 LLM 是否可用
```bash
python -c "from src.generator.llm_client import LLMClient; import yaml; c=LLMClient(yaml.safe_load(open('config.yaml'))['llm']); print(c.generate('你是翻译','将hello翻译成中文'))"
```

### 8.4 单模块重跑
```python
from src.collector.api_client import fetch_all
import yaml
config = yaml.safe_load(open("config.yaml"))
raw = fetch_all(19683241, config["sportmonks"])

from src.engine.metrics import compute_all
computed = compute_all(raw)

# 验证 xG 采集
home_xg = sum(p.xg for p in raw.home_players)
away_xg = sum(p.xg for p in raw.away_players)
print(f"PSG xG: {home_xg:.4f}, Arsenal xG: {away_xg:.4f}")
```

### 8.5 查看球队级 xG / Recoveries（从球员汇总）
```python
import json
raw = json.load(open("data/raw/19683241/raw_data.json", "r", encoding="utf-8"))
home_xg = sum(p.get("xg", 0) or 0 for p in raw["home_players"])
home_rec = sum(p.get("ball_recoveries", 0) or 0 for p in raw["home_players"])
print(f"xG: {home_xg:.4f}  Recoveries: {home_rec}")
```

---

## 9. 已知问题与待办

- [x] ~~API-Football 抢断/球权回收缺失~~ → SportMonks 已解决
- [x] ~~球场Logo未显示~~ → SportMonks 提供 `image_path`
- [x] ~~图表中文方框~~ → 已配置中文字体 SimHei/YaHei
- [x] ~~换人方向搞反~~ → 已修正 (player_name=换上, related_player_name=换下)
- [x] ~~事件类型映射错误 (22/23 = VAR/OwnGoal)~~ → 实测修正为点球大战
- [x] ~~xG 不可用~~ → 球员级 5304/5305 已接入
- [ ] Shot Map 坐标 — SportMonks events 不返回射门 (x,y) 坐标
- [ ] PPDA (压迫强度) — 无直接数据，需自定义计算
- [ ] Pass Network 数据 — 当前 `home_lineup.players` 为空，传球网络图数据不足
- [ ] 15+ 个未识别球员级 type_id (111/114/115/571/584 等)

---

## 10. 多环境迁移清单

1. `git clone` 本项目
2. `pip install requests pyyaml matplotlib mplsoccer numpy scipy openai markdown jinja2`
3. 设置环境变量 `SPORTMONKS_API_TOKEN` 和 `DEEPSEEK_API_KEY`（或直接写入 config.yaml）
4. `python -c "from src.collector.api_client import SportMonksClient; print('OK')"` → 验证导入
5. `python run.py --match 19683241 --dry-run` → 验证数据管线
6. `python run.py --match 19683241` → 完整生成
