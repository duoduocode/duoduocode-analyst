# AGENTS.md — AI 足球分析员 (Football Analyst)

> 本文档供 AI Agent 理解项目上下文、架构与常见问题，便于在新环境中快速上手调试。

---

## 1. 项目概述

**目标**：从 **SportMonks Football API V3** 获取比赛全量数据 → 趋势分析 + **36 个信号检测器**自动识别比赛看点 → 调用 DeepSeek LLM 生成动态叙事 → mplsoccer 生成图表 → 拼装 Markdown 图文报告，适配微信公众号发布。

**核心理念**：不再用固定模板套每场比赛，而是通过**信号驱动**自动发现每场比赛最值得分析的独特角度。

**技术栈**：Python 3.11+ / requests / pyyaml / matplotlib / mplsoccer / numpy / scipy / markdown / jinja2

**LLM**：DeepSeek (`deepseek-chat` / `deepseek-v4-pro`)，OpenAI 兼容协议，支持两种调用方式：
- 优先尝试 `openai` SDK (Python 包)
- 后备：纯 `requests` HTTP POST 到 `/chat/completions`

**数据来源**：SportMonks V3 — 单次 API 请求（含 `periods.statistics`, `periods.events`, `trends`, `coaches` 等全量 include）获取 ~1700 条趋势记录 + 分时段统计 + 球员/球队/事件/比分数据。

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
python generate_match_report.py 19683241           # ★ 统一入口：战术 V2 + 球员 V6 一次性生成
python generate_match_report.py 19683241 --no-llm  # 跳过 LLM（仅数据 + 图表）
python generate_match_report.py 19683241 --tactical-only  # 仅战术报告
python generate_match_report.py 19683241 --cards-only    # 仅球员卡片
python run.py --match 19683241                    # 旧版报告（信号驱动六段叙事）
python run.py --league 732 --date 2026-06-14       # 批量生成某日全部比赛
```

---

## 3. 项目结构

```
duoduocode-analyst/
├── config.yaml                          # SportMonks API Token + LLM 配置
├── config.example.yaml
├── generate_match_report.py             # ★★ 统一报告入口（战术 V2 + 球员 V6）
├── run.py                               # 旧版入口（信号驱动六段叙事）
├── run_player_v6.py                     # v6 球员贡献独立入口（Excel + JSON + LLM分析）
├── run_tactical_only.py                 # 战术报告独立入口
├── compare_players.py                   # 球员对比图生成
├── generate_cards_v6.py                 # v6 球员贡献卡片生成（Playwright → PNG）
├── AGENTS.md                            # 本文档
├── prompts/                             # Prompt 模板 (Jinja2+YAML)
│   ├── narrative.yaml                   # ★ 信号驱动叙事模板（替代旧9模块）
│   ├── player_analysis.yaml            # ★ v6 球员分析提示词（张佳玮+内德风格）
│   ├── player_summary.yaml            # 旧版张佳玮短评模板（已停用）
│   ├── momentum.yaml / tactics.yaml / mvp.yaml
│   ├── hidden_mvp.yaml / black_hole.yaml
│   └── subs.yaml / replay.yaml / contrast.yaml / cover.yaml
├── src/
│   ├── collector/
│   │   └── api_client.py               # SportMonks V3 客户端 + type_id 映射 + 全量数据解析
│   ├── engine/
│   │   ├── metrics.py                  # CI/TCR/PE/LDI 自创指标 + ComputedData
│   │   ├── ratings.py                  # 球员贡献分 + MVP/隐性MVP/黑洞分类
│   │   ├── simulator.py                # 蒙特卡洛 xG 模拟
│   │   ├── trends.py                   # ★ 趋势分析：增量计算/窗口聚合/斜率/转折点
│   │   ├── signals.py                  # ★ 36 个信号检测器 + Top N 筛选
│   │   ├── key_events.py               # ★ 统一关键事件判定（首开/绝杀/制胜/点球大战等）
│   │   ├── player_insights_v6.py       # ★ v6 球员贡献检测引擎（七维模型 + LLM分析）
│   │   ├── tactical_insights.py        # ★ 战术分析引擎（四层因果模型）
│   │   ├── cross_insights.py           # 交叉洞察（控球有效性等硬事实）
│   │   └── sub_impact.py               # 换人影响分析
│   ├── composer/
│   │   ├── prompt_loader.py            # YAML 加载 + Jinja2 渲染（不变）
│   │   ├── data_builder.py             # ★ 信号驱动叙事组装（替代旧9模块builder）
│   │   └── tactical_prompt.py          # ★ 战术叙事 Prompt 构建
│   ├── generator/
│   │   └── llm_client.py              # DeepSeek（openai SDK 优先，requests 后备）
│   ├── visualizer/
│   │   ├── __init__.py                 # 颜色常量 + matplotlib 中文字体配置
│   │   ├── shots.py                    # mplsoccer 射门分布图
│   │   ├── momentum.py                 # 动量曲线 + 事件标注
│   │   ├── pass_network.py             # mplsoccer 传球网络图
│   │   ├── radar.py                    # 球员雷达图 (7维度)
│   │   ├── subs.py                     # 换人对比柱状图
│   │   ├── xg_hist.py                  # xG 模拟分布图
│   │   ├── tactical_charts.py          # ★ 战术图表（雷达/控球/射门/PPDA/时间轴）
│   │   ├── player_comparison.py        # ★ 球员对比图（双面板 + 雷达图）
│   │   ├── player_card.py              # ★ 球员贡献卡片
│   │   ├── lineup.py                   # ★ 阵容图（HTML + PNG）
│   │   ├── efficiency.py               # 效率对比图
│   │   └── player_tables.py            # 球员数据表
│   ├── reporter/
│   │   ├── build_report.py            # ★ 动态章节报告拼装（基于LLM输出+信号）
│   │   └── player_excel.py            # ★ v6 球员贡献 Excel 9-sheet 导出
│   └── player_names.py                # 球员中英文名映射表
├── design/                             # 产品文档
│   ├── 比赛报告架构v3.md                # v3 报告架构（三层洞察 × 六段叙事）
│   ├── 战术分析板块设计-v2.md            # ★ v2 战术分析板块（四层因果模型）
│   ├── 球员贡献检测器方案-v6.md          # ★ v6 两层叙事模型设计文档
│   ├── 球员贡献检测器方案-v5.md          # v5 七维贡献模型设计文档
│   ├── 球员贡献检测器方案.md             # v3 13检测器设计文档
│   ├── 关键事件判定方案.md               # 统一关键事件判定规则
│   ├── 比赛概览模块设计.md               # 比赛概览模块设计
│   ├── SportMonks统计指标全集.md         # 全部可用的球队+球员+事件指标 (type_id映射)
│   └── SportMonks_Fixture_Include全集.md # SportMonks 全部 include 参数说明
├── data/
│   ├── raw/{match_id}/raw_data.json    # 解析后的结构化数据（含 trends/periods/coaches）
│   └── computed/{match_id}.json        # 计算后指标 + 检测到的信号
│   └── computed/{match_id}_players_v6.json # ★ v6 球员贡献 JSON
│   └── computed/{match_id}_players_v6.xlsx # ★ v6 球员贡献 Excel (9 sheets)
└── output/{match_id}_{HOME}_vs_{AWAY}/
    ├── tactical_report.html            # ★ 战术分析报告 V2 (HTML)
    ├── tactical_analysis.json          # 战术原始数据
    ├── tactical_analysis.xlsx          # 战术 Excel
    ├── report_v3.html                  # 旧版 v3 报告
    ├── compare/                        # 球员对比图
    │   └── PlayerA_vs_PlayerB.png
    ├── player_cards/                   # 球员贡献卡片 (PNG)
    ├── images/                         # 图表
    │   ├── tactical_radar.png          # 战术雷达图
    │   ├── tactical_shots.png          # 时段射门分布
    │   ├── tactical_ppda.png           # 压迫强度对比
    │   ├── tactical_ppda_timeline.png  # 压迫强度时间曲线
    │   ├── pressing_effectiveness.png  # 压迫效果图
    │   ├── pressing_efficiency.png     # 压迫效率图
    │   ├── tactical_possession.png     # 控球摇摆图
    │   ├── lineup.png                 # 阵容图
    │   └── timeline.png               # 事件时间轴
    └── ...
```

---

## 4. 统一报告生成管线 (generate_match_report.py)

**一次命令生成战术报告 + 球员贡献数据**。

```bash
python generate_match_report.py 19683241           # 完整生成（战术 + 球员）
python generate_match_report.py 19683241 --cards-only   # 只生成球员卡片
python generate_match_report.py 19683241 --tactical-only # 只生成战术报告
python compare_players.py 19683241 "PlayerA" "PlayerB"  # 球员对比（独立脚本）
```

---

### 4.1 步骤 → 依赖 → 产出

#### 第一步：拉取/加载原始数据

| 项 | 内容 |
|------|------|
| **命令** | 内嵌在 `generate_match_report.py` 中，无需单独执行 |
| **依赖** | `config.yaml`（API Token） |
| **产出** | `data/raw/{id}/raw_data.json`（~800KB，全量 SportMonks V3 数据） |
| **说明** | 首次从 API 拉取，后续读缓存；含 team/player/stats/events/trends/periods/coaches |

#### 第二步：生成战术分析报告（管道 A）

| 步骤 | 动作 | 依赖文件 | 产出文件 | 代码位置 |
|------|------|---------|---------|---------|
| A1 | 四层因果模型计算 | `data/raw/{id}/raw_data.json` | 内存中的 tactical_data dict | `src/engine/tactical_insights.py` |
| A2 | LLM 五段战术叙事 | `prompts/tactical.yaml`, tactical_data | 叙事文本（~3700 tokens） | `src/composer/tactical_prompt.py` |
| A3 | 战术图表生成 | tactical_data | `output/.../images/tactical_radar.png`<br>`output/.../images/tactical_possession.png`<br>`output/.../images/tactical_shots.png`<br>`output/.../images/tactical_ppda.png`<br>`output/.../images/tactical_ppda_timeline.png`<br>`output/.../images/pressing_effectiveness.png`<br>`output/.../images/pressing_efficiency.png` | `src/visualizer/tactical_charts.py` |
| A4 | 事件时间轴 | `raw_data.json` | `output/.../images/timeline.png` | `src/visualizer/tactical_charts.py` |
| A5 | 阵容图 | `raw_data.json` | `output/.../images/lineup.png` | `src/visualizer/lineup.py` |
| A6 | 保存战术数据 | tactical_data | `output/.../tactical_analysis.json`<br>`output/.../tactical_analysis.xlsx` | `generate_match_report.py` |
| A7 | 组装 HTML 报告 | 以上全部产物 | `output/.../tactical_report.html` ★ | `generate_match_report.py` |

#### 第三步：生成球员贡献数据（管道 B，与管道 A 并行）

| 步骤 | 动作 | 依赖文件 | 产出文件 | 代码位置 |
|------|------|---------|---------|---------|
| B1 | 五维贡献计算 | `data/raw/{id}/raw_data.json` | C1-C5 z-score + 队内/全场排名 | `src/engine/player_insights_v6.py` |
| B2 | 角色分类 | B1 结果 | 角色标签（控场/推进/射手…） | `src/engine/player_insights_v6.py` |
| B3 | 关键事件判定 | `raw_data.json` | 首开/绝杀/制胜/点球等标签 | `src/engine/key_events.py` |
| B4 | LLM 球员叙事（31人） | `prompts/player_analysis.yaml`, B1+B2+B3 | 每人 ~80-120 字叙事 | `src/generator/llm_client.py` |
| B5 | 保存 JSON | B1+B2+B3+B4 | `data/computed/{id}_players_v6.json`（~600KB） | `generate_match_report.py` |
| B6 | 保存 Excel | B1+B2+B3+B4 | `data/computed/{id}_players_v6.xlsx`（9 sheets） | `src/reporter/player_excel.py` |

> **JSON 文件字段**：name / player_id / number / pos / team / team_name / minutes / contributions{C1-C5} / role / llm_summary / events  
> **Excel 9 sheets**：概要 / C1进攻 / C2推进 / C3控制 / C4防守 / C5对抗 / C6事件 / C7门将 / 角色叙事

#### 第四步：生成球员贡献卡片（管道 C，需 `--cards-only` 触发）

| 步骤 | 动作 | 依赖文件 | 产出文件 | 代码位置 |
|------|------|---------|---------|---------|
| C1 | 读取 JSON | `data/computed/{id}_players_v6.json` | 球员卡片数据 dict | `generate_cards_v6.py` |
| C2 | 加载物理数据 | `data/{id}/{PlayerName}/run_data.json`（可选）<br>`data/{id}/{PlayerName}/carry_data.json`（可选） | 跑动距离(km) / 带球推进(km) | `generate_cards_v6.py` |
| C3 | 构建卡片 HTML | C1 + C2 | HTML 字符串 | `generate_cards_v6.py` |
| C4 | Playwright 渲染 | C3（HTML） | `output/.../player_cards/{Name}.png` | `generate_cards_v6.py` |

> `run_data.json` / `carry_data.json` 缺失时不报错，卡片中不显示跑动/推进 chip。

#### 第五步：球员对比（管道 D，独立运行 `compare_players.py`）

| 步骤 | 动作 | 依赖文件 | 产出文件 | 代码位置 |
|------|------|---------|---------|---------|
| D1 | 加载比赛数据 | `data/raw/{id}/raw_data.json` | lineups + events | `compare_players.py` |
| D2 | 五维检测器运行 | D1 | C1-C5 指标 + 队内/全场排名 | `src/engine/player_insights.py` |
| D3 | 关键事件 | D1 | 首开/绝杀/制胜等标签 | `src/engine/key_events.py` |
| D4 | 物理数据加载 | `data/{id}/{PlayerName}/run_data.json`（可选）<br>`data/{id}/{PlayerName}/carry_data.json`（可选） | 跑动距离 / 带球推进 | `compare_players.py` |
| D5 | 加载 LLM 叙事 | `data/computed/{id}_players_v6.json` | 两名球员的叙事文本 | `compare_players.py` |
| D6 | 绘制对比图 | D1+D2+D3+D4+D5 | `output/.../compare/{A}_vs_{B}.png` | `src/visualizer/player_comparison.py` |

---

### 4.2 完整文件清单

```
外部输入（只读）
  config.yaml                   # API Token + LLM 配置
  prompts/tactical.yaml         # 战术叙事 Prompt 模板
  prompts/player_analysis.yaml  # 球员叙事 Prompt 模板

                     ┌─ 管道 A ─────────────────────────────────────
                     │
  data/raw/          │   output/{id}_{HOME}_vs_{AWAY}/
  {id}/raw_data.json─┤   ├── tactical_report.html ★ 主力产品
      (唯一数据源)    │   ├── tactical_analysis.json / .xlsx
                     │   ├── images/
                     │   │   ├── tactical_radar.png
                     │   │   ├── tactical_possession.png
                     │   │   ├── tactical_shots.png
                     │   │   ├── tactical_ppda.png
                     │   │   ├── tactical_ppda_timeline.png
                     │   │   ├── pressing_effectiveness.png
                     │   │   ├── pressing_efficiency.png
                     │   │   ├── lineup.png
                     │   │   └── timeline.png
                     │
                     └─ 管道 B ── data/computed/{id}_players_v6.json
                           │                    └─ .xlsx (9 sheets)
                           │
                           ├─ 管道 C ── output/.../player_cards/{Name}.png
                           │            (依赖: run_data.json / carry_data.json, 可选)
                           │
                           └─ 管道 D ── output/.../compare/{A}_vs_{B}.png
                                        (依赖: raw_data.json + _players_v6.json
                                               + run_data.json / carry_data.json, 可选)
```

---

### 4.3 执行顺序规则

| 管道 | 触发 | 前置条件 | 可并行? |
|------|------|---------|--------|
| A 战术报告 | 默认执行 | `raw_data.json` 存在 | 与 B 并行 |
| B 球员贡献 | 默认执行 | `raw_data.json` 存在 | 与 A 并行 |
| C 球员卡片 | `--cards-only` | 管道 B 完成（`_players_v6.json` 存在） | 不可与 B 并行 |
| D 球员对比 | `compare_players.py` | 管道 B 完成 + `raw_data.json` 存在 | 可在 C 之后任意时刻 |

---

### 4.4 首次运行示例

```bash
# 第一步：生成完整报告（产出 raw_data.json + tactical_report.html + _players_v6.json/.xlsx）
python generate_match_report.py 19683241

# 第二步：生成球员卡片 PNG（依赖第一步的 _players_v6.json）
python generate_match_report.py 19683241 --cards-only

# 第三步（可选）：生成球员对比图
python compare_players.py 19683241 "Declan Rice" "Vitinha"
```

---

## 5. 旧版管线：核心架构与数据流（信号驱动）

```
run.py
  ├─ 1. load_config() → 读取 config.yaml，替换 ${ENV_VAR} 占位符
  │
  ├─ 2. fetch_all(match_id) → SportMonks 单次请求
  │      GET /fixtures/{id}?include=
  │        statistics;periods.statistics;periods.events;trends;
  │        lineups.details;events;participants;scores;coaches;referees
  │      ├─ statistics[] → home_stats / away_stats (dict, 40 项)
  │      ├─ lineups.details[] → home_players / away_players (PlayerStats, 30+ 字段)
  │      ├─ events[] → events (MatchEvent, 含 period_id)
  │      ├─ periods[] → PeriodData (分时段统计+事件)
  │      ├─ trends[] → {participant_id: {type_id: [TrendPoint]}} (~1700 条)
  │      ├─ coaches[] → home_coach / away_coach (CoachInfo)
  │      ├─ participants[] → TeamInfo (id, name, logo_url)
  │      └─ scores[] → ScoreInfo + period_scores
  │
  ├─ 3. compute_all(raw) → CI/TCR/PE/LDI/动量/球员分类/标签
  │
  ├─ 4. analyze_trends(raw) → 增量计算 / 窗口聚合 / 转折点 / 对抗衰减 / 压迫衰减 / 风格转变
  │
  ├─ 5. detect_all(raw, computed, trend_analysis)
  │      → 36 个检测器并行运行，输出 SignalResult[] 按强度排序
  │      → get_top_signals() 取 Top 6（跨类别去重）
  │
  ├─ 6. build_narrative() + LLM → 单次 LLM 调用生成完整叙事
  │      Prompt 包含：核心数据面板 + 关键事件 + 分时段 + 信号列表 + 趋势发现 + 球员亮点
  │
  ├─ 7. generate_all_visuals() → 7 张 mplsoccer 图表 (可选)
  │
  └─ 8. build_report(narrative, signals) → 解析 LLM 输出的【标题】【导语】等章节
        + 核心数据面板 + 图表 + 信号面板 + 分期段对比 + 事件时间线 + 球员评分表
        → Markdown + HTML 双输出
```

---

## 6. 关键适配：SportMonks type_id 体系

⚠️ **SportMonks 用整数 `type_id` 编码所有统计和事件，不使用字段名。** 映射表集中在 `src/collector/api_client.py`。

### 6.1 球队统计映射 (`FIXTURE_STAT_MAP`)

40 项球队级指标，完整列表见 `design/SportMonks统计指标全集.md`。

### 6.2 球员统计映射 (`PLAYER_STAT_MAP`)

已从 25 项扩展到 **49 项**，含高阶数据：

```python
PLAYER_STAT_MAP: dict[int, str] = {
    # 基础
    118: "rating",           119: "minutes_played",
    40: "captain",           1490: "man_of_match",
    120: "touches",
    # 射门/进球
    52: "goals",             79: "assists",
    42: "shots_total",       86: "shots_on",
    47: "penalties",
    # 传球
    80: "passes_total",      117: "passes_key",
    1584: "passes_accuracy", 27269: "passes_final_third",
    98: "crosses",
    # 防守
    78: "tackles_total",     100: "tackles_interceptions",
    27268: "tackles_won_pct", 97: "blocked_shots",
    101: "clearances",       27271: "ball_recoveries",
    57: "saves",
    # 对抗
    105: "duels_total",      106: "duels_won",
    # 盘带
    108: "dribbles_attempts", 109: "dribbles_success",
    # 犯规
    56: "fouls_committed",   96: "fouls_drawn",
    84: "yellowcards",       83: "redcards",
    # 失误
    571: "error_lead_to_goal", 27273: "possession_lost",
    # 高阶 (需套餐支持)
    5304: "xg",              5305: "xgot",
    9685: "shooting_performance",
}
```

### 6.3 事件类型映射 (`_parse_events`)

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
| 55 | VAR 介入 | VAR | var |

⚠️ **换人事件**：SportMonks 中 `player_name` = 换上球员，`related_player_name` = 换下球员（与 API-Football 相反）。
⚠️ **进球事件**：`related_player_name` = 助攻者 → `assist_name`。
⚠️ **MatchEvent 含 `period_id`**：区分常规时间(1-2)、加时赛(3-4)、点球大战(5)。

### 6.4 趋势数据 (`trends`) 结构

API 返回 ~1500-1700 条逐分钟累积记录。解析后结构：
```python
trends: dict[int, dict[int, list[TrendPoint]]]
#         participant_id → type_id → [TrendPoint(minute, value, period_id), ...]
```

常出现的 type_id：80(传球), 43(进攻), 106(赢得对抗), 45(控球), 98(传中), 42(射门), 44(威胁进攻), 27271(球权回收) 等。

### 7.5 认证方式

```python
# SportMonks: api_token 作为 query param
requests.get(url, params={"api_token": token, "include": "..."})
```

---

## 7. 信号检测系统

36 个检测器分 7 大类，每个返回 `SignalResult(name, category, strength, evidence, narrative_hint)`。

### 7.1 A. 比分背离 (Score Deviation) — 6 个

| 检测器 | 触发条件 |
|--------|---------|
| `xg_upset` | xG 劣势方赢了比赛 (xG gap > 0.3) |
| `conversion_anomaly` | 射门转化率异常高或异常低 |
| `penalty_decided` | 点球进球数 ≥ 分差 |
| `red_card_turning` | 红牌后比分走势逆转 |
| `own_goal_impact` | 乌龙球直接决定了比赛结果 |
| `late_winner` | 75 分钟后进球改变了胜者 |

### 7.2 B. 效率撕裂 (Efficiency Tear) — 6 个

| 检测器 | 触发条件 |
|--------|---------|
| `possession_waste` | 高控球但低 xG（控球无效） |
| `counter_attack_efficiency` | 低控球但每次射门 xG 极高 |
| `pass_efficiency_gap` | 双方关键传球率差距 > 3% |
| `shot_quality_gap` | 双方 xG/shot 差距 ≥ 2 倍 |
| `corner_efficiency` | 角球直接/间接进球 ≥ 2 个 |
| `big_chance_conversion` | 绝佳机会错失率 > 60% |

### 7.3 C. 个人英雄/罪人 (Individual) — 6 个

| 检测器 | 触发条件 |
|--------|---------|
| `one_man_team` | 单人包办全队 ≥ 75% 进球 |
| `gk_hero` | 门将扑救 ≥ 5 次 |
| `gk_disaster` | 丢球 3+ 且扑救成功率 < 50% |
| `super_sub` | 替补出场贡献球+助 ≥ 3 分 |
| `fatal_error` | `error_lead_to_goal` > 0 |
| `rating_paradox` | 高分但基础数据差 |

### 7.4 D. 结构性问题 (Structural) — 6 个

| 检测器 | 触发条件 |
|--------|---------|
| `wing_domination` | 传中次数差距 ≥ 2.5 倍 |
| `attack_channel_bias` | 单路进攻占比 > 50% |
| `aerial_domination` | 成功头球差距 ≥ 2 倍 |
| `tactical_fouls` | 犯规多但黄牌少（聪明的战术犯规） |
| `sub_timing_impact` | 早期换人 (< 30') 或拖延时间换人 (≥ 85') |
| `formation_mismatch` | 禁区外射门 > 禁区内 ×1.5 |

### 7.5 E. 叙事钩子 (Narrative) — 6 个

| 检测器 | 触发条件 |
|--------|---------|
| `mirror_match` | 5 项指标双方差距 < 25% |
| `high_scoring` | 总进球 ≥ 5 |
| `clean_sheet` | 一方零封 |
| `comeback` | 先落后再逆转 |
| `draw_drama` | 平局但 xG 差大 |
| `rare_event` | 3+ 中框 / 2+ 红牌 |

### 7.6 F. 淘汰赛专项 (Knockout) — 8 个

| 检测器 | 触发条件 |
|--------|---------|
| `halftime_adjustment` | 上下半场射门差逆转 |
| `extra_time_collapse` | 加时赛射门率降 > 50% |
| `penalty_shootout_hero` | 点球大战有人罚失 |
| `lead_protect_mode` | 控球率从 >55% 骤降至 <45% |
| `et_sub_impact` | 加时赛有换人 |
| `diff_stage_rhythm` | 不同阶段射门数差 ≥ 3 倍 |
| `period_goal_cluster` | 单时段 3+ 进球 |
| `dominant_et` | 加时赛射门 ≥ 3 倍对手 |

### 7.7 G. 趋势驱动 (Trends) — 6 个

| 检测器 | 触发条件 |
|--------|---------|
| `rhythm_swing` | 比赛节奏主导权转换 ≥ 3 次 |
| `duel_decay_alert` | 对抗成功率前后半场衰减 > 20% |
| `stamina_fade` | 压迫效率后半段衰减 > 20% |
| `tactical_shift` | 长传/短传或传中/进攻比例显著变化 |
| `turning_point_alert` | 趋势数据检测到多个转折点 |
| `momentum_surge` | 进攻速率在某时刻急剧攀升 |

### 信号筛选策略

`get_top_signals()` 先按类别各取最强信号，再从剩余中按强度补齐至 Top 6，确保报告角度多样性。

---

## 8. 自创指标速查（辅助参考）

| 指标 | 公式（核心） | 范围 | 数据源 |
|---|---|---|---|
| **CI** 控制指数 | 0.35×控球 + 0.25×传球 + 0.25×区域 + 0.15×回收 | 0-100 (两队之和=100) | Possession%, Pass%, Shots insidebox, Corners, Ball Recoveries |
| **TCR** 威胁转化率 | 100×(xG+0.3×绝佳机会)/(射门+0.3×角球) | 通常 2-35 | xG, Big Chances, Total Shots, Corners |
| **PE%** 压迫效率 | 100×(回收/(犯规+1)) / 双方之和 | 0-100 | Ball Recoveries, Fouls |
| **LDI** 运气偏离 | P(实际比分)/P(最可能比分) | 0-1+ | xG + 蒙特卡洛模拟 |

> 注：自创指标在 v2 中降级为辅助参考。报告叙事主要由信号检测器驱动，不再围绕 CI/TCR/PE 展开。

---

## 9. 降级策略

| 场景 | 策略 |
|---|---|
| `scipy` 未安装 | → 尝试 `numpy.random.poisson` |
| `numpy` 未安装 | → 纯 Python Knuth 算法，模拟次数降至 2000 |
| `matplotlib` / `mplsoccer` 未安装 | → `--no-images` 跳过图表 |
| `openai` SDK 未安装 | → LLMClient 自动降级为 `requests` HTTP POST |
| xG 无球队级 | → 从球员 xG(5304) 汇总 |
| Ball Recoveries 无球队级 | → 从球员 ball_recoveries(27271) 汇总 |
| Trends 数据为空 | → 趋势驱动 6 个检测器跳过，其余 30 个正常执行 |
| Periods 数据为空 | → 淘汰赛专项 8 个检测器降级为通用逻辑 |
| 中文方框 | → `src/visualizer/__init__.py` 已配置 SimHei / Microsoft YaHei |

---

## 10. 调试建议

### 10.1 先 dry-run（含信号检测）
```bash
python run.py --match 19683241 --dry-run
```
只拉数据 + 算指标 + 趋势分析 + 信号检测，不调 LLM。检查 `data/raw/{id}/raw_data.json` 和 `data/computed/{id}.json`。

### 10.2 查看检测到的信号
```bash
python -c "
import json; d=json.load(open('data/computed/19683241.json','r',encoding='utf-8'))
for s in d.get('signals', []):
    print(f\"{s['strength']:.2f} [{s['category']}] {s['name']}: {s['narrative_hint'][:80]}\")
"
```

### 10.3 查看趋势数据中的可用 type_id
```python
import json
raw = json.load(open("data/raw/19683241/raw_data.json", "r", encoding="utf-8"))
trends = raw.get("trends", {})
for pid, type_dict in trends.items():
    print(f"Participant {pid}: types = {list(type_dict.keys())[:20]} ...")
```

### 10.4 单模块重跑
```python
from src.collector.api_client import fetch_all
import yaml
config = yaml.safe_load(open("config.yaml"))
raw = fetch_all(19683241, config["sportmonks"])

# 趋势分析
from src.engine.trends import analyze_trends
ta = analyze_trends(raw)
print(f"Turning points: {len(ta.turning_points)}")
print(f"Duel decay home: {ta.duel_decay_home}")
print(f"Pressing fade: H={ta.pressing_fade_home:.3f} A={ta.pressing_fade_away:.3f}")

# 信号检测
from src.engine.signals import detect_all, get_top_signals
from src.engine.metrics import compute_all
computed = compute_all(raw)
all_sigs = detect_all(raw, None, ta)
for s in get_top_signals(all_sigs, 6):
    print(f"  {s.strength:.2f} [{s.category}] {s.name}")
```

### 10.5 验证 xG / Recoveries 采集
```python
import json
raw = json.load(open("data/raw/19683241/raw_data.json", "r", encoding="utf-8"))
home_xg = sum(p.get("xg", 0) or 0 for p in raw["home_players"])
away_xg = sum(p.get("xg", 0) or 0 for p in raw["away_players"])
home_rec = sum(p.get("ball_recoveries", 0) or 0 for p in raw["home_players"])
print(f"xG: H={home_xg:.4f} A={away_xg:.4f}  Recoveries: H={home_rec}")
```

### 10.6 检查 LLM 是否可用
```bash
python -c "from src.generator.llm_client import LLMClient; import yaml; c=LLMClient(yaml.safe_load(open('config.yaml'))['llm']); print(c.generate('你是翻译','将hello翻译成中文'))"
```

---

## 11. 已知问题与待办

- [x] ~~API-Football 抢断/球权回收缺失~~ → SportMonks 已解决
- [x] ~~球场Logo未显示~~ → SportMonks 提供 `image_path`
- [x] ~~图表中文方框~~ → 已配置中文字体 SimHei/YaHei
- [x] ~~换人方向搞反~~ → 已修正 (player_name=换上, related_player_name=换下)
- [x] ~~事件类型映射错误 (22/23 = VAR/OwnGoal)~~ → 实测修正为点球大战
- [x] ~~xG 不可用~~ → 球员级 5304/5305 已接入
- [x] ~~固定模板套所有比赛~~ → v2 信号驱动动态叙事
- [x] ~~9 次 LLM 调用太慢~~ → v2 单次叙事调用
- [x] ~~未利用 trends 数据~~ → 已接入逐分钟趋势 + 趋势驱动6个检测器
- [x] ~~未利用 periods 数据~~ → 已接入分时段统计 + 淘汰赛专项8个检测器
- [ ] Shot Map 坐标 — SportMonks events 不返回射门 (x,y) 坐标
- [ ] PPDA (压迫强度) — 无直接数据，但 trends 中可间接计算
- [ ] Pass Network 数据 — 当前 `home_lineup.players` 为空，传球网络图数据不足
- [ ] 15+ 个未识别球员级 type_id (111/114/115/571/584 等)

---

## 12. 多环境迁移清单

1. `git clone` 本项目
2. `pip install requests pyyaml matplotlib mplsoccer numpy scipy openai markdown jinja2 openpyxl playwright`
3. `playwright install chromium`
4. 设置环境变量 `SPORTMONKS_API_TOKEN` 和 `DEEPSEEK_API_KEY`（或直接写入 config.yaml）
5. `python -c "from src.collector.api_client import SportMonksClient; print('OK')"` → 验证导入
6. `python generate_match_report.py 19683241 --no-llm` → ★ 验证统一管线（战术V2+球员V6，不含LLM）
7. `python generate_match_report.py 19683241` → ★ 完整生成（含 LLM 叙事 + 图表）
8. `python run.py --match 19683241 --dry-run` → 验证旧版管线（采集+指标+趋势+信号）
9. `python run_player_v6.py 19683241` → 独立运行球员贡献 Excel + JSON
10. `python generate_cards_v6.py 19683241` → 生成全体球员 PNG 卡片

---

## 13. 球员贡献检测器 v6

### 13.1 概述

v6 采用**两层叙事模型**，从 66 项球员级指标出发，输出七维贡献向量 + LLM 球员分析。

**设计文档**：[`design/球员贡献检测器方案-v6.md`](design/球员贡献检测器方案-v6.md)

### 13.2 快速启动

```bash
# 完整管线（Excel + JSON）
python run_player_v6.py                         # 三场默认比赛
python run_player_v6.py 19683241                # 单场

# 生成卡片 PNG（依赖已生成的 JSON）
python generate_cards_v6.py 19683241            # 全体球员
python generate_cards_v6.py 19683241 --key-only # 仅关键球员
python generate_cards_v6.py 19683241 --player "Declan Rice"  # 指定球员
```

### 13.3 Layer 1：七维贡献模型

| 维度 | 简称 | 副标题 | 指标数 | 核心正指标 |
|------|------|--------|:---:|------|
| C1 进攻 | 进攻 | 创造机会，转化进球 | 15 | goals, xg, assists, shots_on, big_chances_created |
| C2 推进 | 推进 | 构建攻势，推进阵地 | 12 | passes_final_third, dribbles_success, crosses |
| C3 控制 | 控制 | 掌控节奏，寻找机会 | 8 | passes_total, passes_accuracy, touches |
| C4 防守 | 防守 | 抢断拦截，阻止得分 | 10 | tackles, clearances, blocked_shots, ball_recoveries |
| C5 对抗 | 对抗 | 积极拼抢，拿下球权 | 13 | duels_won, aerials_won, ball_recoveries |
| C6 关键事件 | — | — | 8 种事件 | 绝杀(+4.5), 制胜球(+4.0), 首开记录(+3.0), 点球大战进球(+1.5) |
| C7 门将 | — | — | 4-D per-90 | saves, xgot_faced, punches |

**算法**：`zscore_composite_v6()` — 每个指标组内 Z-score × 权重 → 求和 → `tanh(x/6.0)*6.0` 软封顶。

### 13.4 Layer 2：LLM 球员分析

**分析范围**：所有出场 ≥15 分钟的球员（含门将），分两类：

| 类型 | 定义 | 交给 LLM 的数据 |
|------|------|---------------|
| **关键球员** | 任一项 C1-C5 队内排名 ≤5 且 zscore > 0 | 仅优势维度指标 |
| **其他球员** | 非关键 + 门将 | 全部 C1-C5 维度指标 |

**提示词**：[`prompts/player_analysis.yaml`](prompts/player_analysis.yaml)
- 风格：张佳玮的诗意画面 + 内德的数据洞见
- 要求：引用具体指标数值、结合关键事件和比赛结果、不贬低、90-150 字
- 分批调用：每批 ≤15 球员，动态 max_tokens
- 回退：LLM 不可用时退回余弦相似度角色推断（14 种原型角色）

### 13.5 输出物

| 格式 | 路径 | 内容 |
|------|------|------|
| **Excel** | `data/computed/{id}_players_v6.xlsx` | 9 sheets: 概要 + C1-C5 明细(含队排/场排) + C6 事件 + C7 门将 + 角色叙事 |
| **JSON** | `data/computed/{id}_players_v6.json` | 结构化数据，供卡片/下游消费 |
| **PNG 卡片** | `output/{id}_.../cards/{player}.png` | 头像 + 姓名 + 事件 + LLM 评语 + 七维卡片网格 + 排名高亮 |

### 13.6 调试

```bash
# 查看 JSON 数据结构
python -c "import json; d=json.load(open('data/computed/19683241_players_v6.json','r',encoding='utf-8')); p=d[0]; print(p['name'], list(p['contributions'].keys()), p.get('llm_summary','')[:60])"

# 查看关键识别逻辑触发情况
python -c "
import json; d=json.load(open('data/computed/19683241_players_v6.json','r',encoding='utf-8'))
for p in d:
    for ck in ['C1','C2','C3','C4','C5']:
        c = p['contributions'].get(ck,{})
        if c.get('rank',99) <= 5 and c.get('zscore',0) > 0:
            print(f\"{p['name']} {ck}: rank={c['rank']} z={c['zscore']}\")
            break
"
```

### 13.7 核心文件

| 文件 | 行数 | 职责 |
|------|:---:|------|
| `src/engine/player_insights_v6.py` | ~1350 | 核心引擎：数据结构/七维计算/LLM 调用/排名 |
| `src/engine/key_events.py` | ~210 | 统一关键事件判定（首开/绝杀/制胜/点球大战） |
| `src/reporter/player_excel.py` | ~480 | Excel 9-sheet 导出 |
| `src/generator/llm_client.py` | ~95 | DeepSeek API（OpenAI SDK + HTTP 回退） |
| `run_player_v6.py` | ~140 | 入口脚本 |
| `generate_cards_v6.py` | ~460 | Playwright HTML→PNG 卡片生成 |
| `prompts/player_analysis.yaml` | ~45 | LLM 分析提示词模板 |
