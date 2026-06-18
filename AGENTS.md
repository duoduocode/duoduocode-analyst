# AGENTS.md — AI 足球分析员 (Football Analyst)

> 本文档供 AI Agent 理解项目上下文、架构与常见问题，便于在新环境中快速上手调试。
> 最后更新: 2026-06-18

---

## 1. 项目概述

**目标**：从 **SportMonks Football API V3** 获取比赛全量数据 → 趋势分析 + **36 个信号检测器**自动识别比赛看点 → 调用 DeepSeek + 豆包 双 LLM 生成动态叙事 → mplsoccer 生成图表 → 拼装 HTML 图文报告，适配微信公众号发布。

**核心理念**：不再用固定模板套每场比赛，而是通过**信号驱动**自动发现每场比赛最值得分析的独特角度。

**技术栈**：Python 3.11+ / requests / pyyaml / matplotlib / mplsoccer / numpy / scipy / markdown / jinja2 / BeautifulSoup / Playwright

**LLM 双引擎**：
- **DeepSeek** (`deepseek-v4-pro`)：战术叙事、压迫分析、文章取名、球员特稿等深度文本生成。OpenAI 兼容协议，SDK 优先，requests 后备。
- **豆包 Doubao** (`doubao-seed-2-0-pro-260215`)：联网搜索赛前/赛况/赛后新闻摘要 + 图片源定位。使用火山引擎 Ark Responses API + `web_search` tool。

**数据来源**：SportMonks V3 — 单次 API 请求（含 `periods.statistics`, `periods.events`, `trends`, `coaches` 等全量 include）获取 ~1700 条趋势记录 + 分时段统计 + 球员/球队/事件/比分数据。

---

## 2. 快速启动

```bash
# 1. 安装依赖
pip install requests pyyaml matplotlib mplsoccer numpy scipy openai markdown jinja2 beautifulsoup4 playwright urllib3

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
```

---

## 3. 项目结构

```
duoduocode-analyst/
├── config.yaml                          # SportMonks API + DeepSeek + 豆包 配置
├── config.example.yaml
├── generate_match_report.py             # ★★ 统一报告入口（战术 V2 + 球员 V6 + 文章取名 + 球员特稿）
├── compare_players.py                   # 球员对比图生成
├── generate_cards_v6.py                 # v6 球员贡献卡片生成（Playwright → PNG）
├── AGENTS.md                            # 本文档
├── fetch_match_context.py               # [旧] Web 战报/新闻抓取模块（Bing News → 清洗 → 保存，已不再主力使用）
├── experiment_doubao_search.py          # [实验] 豆包联网搜索验证（赛前/赛况/赛后摘要）
├── experiment_search_and_images.py      # [实验] 豆包搜索 + 图片提取一体化验证
├── experiment_image_hunt.py             # [实验] 多源图片猎手（图集搜索+Bing直搜+新闻补充）
├── experiment_image_search.py           # [实验] 豆包图片搜索能力测试
├── _debug_ark.py / _debug_ark2.py       # [一次性] Ark API 调试脚本
├── prompts/                             # Prompt 模板 (Jinja2+YAML)
│   ├── tactical.yaml                   # ★ 战术分析四层模型叙事
│   ├── pressing.yaml                   # ★ 压迫分析四段式
│   ├── article_naming.yaml             # ★ 文章取名 (含角度约束 + few-shot)
│   ├── player_feature_recommend.yaml   # ★ 球员人物特稿推荐
│   ├── player_analysis.yaml            # ★ v6 球员分析提示词
│   ├── narrative.yaml                   # 信号驱动叙事模板（旧）
│   ├── narrative_v3.yaml               # v3 六段叙事
│   ├── player_summary.yaml            # 旧版张佳玮短评模板（已停用）
│   └── momentum.yaml / tactics.yaml / mvp.yaml / ...
├── src/
│   ├── collector/
│   │   └── api_client.py               # SportMonks V3 客户端 + type_id 映射 + 全量数据解析
│   ├── engine/
│   │   ├── tactical_insights.py        # ★ 战术分析引擎（四层因果模型）
│   │   ├── player_insights_v6.py       # ★ v6 球员贡献检测引擎（五维模型 + LLM分析）
│   │   ├── player_insights.py          # 13 个球员探测器 (D1-D13)
│   │   ├── player_feature_selector.py  # ★ 球员文章价值评分 + 预筛选
│   │   ├── key_events.py               # ★ 统一关键事件判定（首开/绝杀/制胜/点球等）
│   │   ├── signals.py                  # 36 个信号检测器 + Top N 筛选
│   │   ├── trends.py                   # 趋势分析：增量计算/窗口聚合/斜率/转折点
│   │   ├── metrics.py                  # CI/TCR/PE/LDI 自创指标 + ComputedData
│   │   ├── cross_insights.py           # 交叉洞察（控球有效性等硬事实）
│   │   ├── sub_impact.py               # 换人影响分析
│   │   └── ratings.py / simulator.py   # 球员贡献分 + 蒙特卡洛模拟
│   ├── composer/
│   │   ├── prompt_loader.py            # YAML 加载 + Jinja2 渲染
│   │   ├── tactical_prompt.py          # ★ 战术叙事 Prompt 构建
│   │   ├── pressing_prompt.py          # ★ 压迫分析 Prompt 构建
│   │   ├── article_naming_prompt.py    # ★ 文章取名 Prompt 组装 + 解析
│   │   ├── player_feature_prompt.py    # ★ 球员推荐 Prompt 组装
│   │   ├── match_overview_prompt.py    # ★ match_overview 润色 Prompt
│   │   └── data_builder.py             # v3 六段叙事 Prompt 组装
│   ├── generator/
│   │   └── llm_client.py              # ★ LLMClient (DeepSeek) + DoubaoClient (豆包联网搜索)
│   ├── visualizer/
│   │   ├── __init__.py                 # 颜色常量 + matplotlib 中文字体配置
│   │   ├── tactical_charts.py          # ★ 战术图表（雷达/控球/射门/PPDA/压迫/时间轴），Playwright 渲染支持系统 Chrome
│   │   ├── lineup.py                   # ★ 阵容图（HTML + PNG），Playwright 渲染支持系统 Chrome
│   │   ├── player_comparison.py        # ★ 球员对比图（双面板 + 雷达图）
│   │   ├── player_card.py              # ★ 球员贡献卡片
│   │   ├── efficiency.py / momentum.py / pass_network.py / radar.py / subs.py / xg_hist.py
│   │   └── player_tables.py            # 球员数据表
│   ├── reporter/
│   │   ├── build_report.py            # v3 动态章节报告拼装（旧，不再主力维护）
│   │   └── player_excel.py            # ★ v6 球员贡献 Excel 9-sheet 导出
│   └── player_names.py                # 球员中英文名映射表
├── design/                             # 产品文档
│   ├── 战术分析板块设计-v2.md            # v2 战术分析板块（四层因果模型）
│   ├── 球员贡献检测器方案-v6.md          # v6 两层叙事模型设计文档
│   ├── 文章命名与球员推荐文章方案.md      # ★ 环节一+二设计文档
│   ├── 比赛报告架构v3.md / 球员贡献检测器方案-v5.md / ...
│   ├── SportMonks统计指标全集.md         # 全部可用的球队+球员+事件指标 (type_id映射)
│   └── SportMonks_Fixture_Include全集.md # SportMonks 全部 include 参数说明
├── data/
│   ├── raw/{match_id}/raw_data.json    # 解析后的结构化数据（含 trends/periods/coaches）
│   ├── computed/{match_id}.json        # 计算后指标 + 检测到的信号
│   ├── computed/{match_id}_players_v6.json   # ★ v6 球员贡献 JSON
│   └── computed/{match_id}_players_v6.xlsx   # ★ v6 球员贡献 Excel (9 sheets)
└── output/{match_id}_{HOME}_vs_{AWAY}/
    ├── tactical_report.html            # ★★ 主力产品：战术分析报告 V2 (8 大板块)
    ├── report_v3.html                  # v3 报告（旧格式，不再生成）
    ├── article_titles.json             # ★ 环节一：10 篇文章标题
    ├── player_features.md              # ★ 环节二：球员人物特稿推荐
    ├── tactical_analysis.json          # 战术原始数据
    ├── tactical_analysis.xlsx          # 战术 Excel
    ├── player_cards/                   # 球员贡献卡片 (29 张 PNG)
    ├── compare/                        # 球员对比图
    │   └── PlayerA_vs_PlayerB.png
    ├── web_context/                    # ★ 豆包联网搜索产出的新闻 + 图片 (v4 新流程)
    │   ├── pre.txt                     #   赛前新闻摘要 (含阵容/前瞻/历史交锋)
    │   ├── match.txt                   #   赛况战报 (含首发阵容 + 关键事件时间线 + 比赛摘要)
    │   ├── post.txt                    #   赛后新闻摘要 (含球员评价/纪录/出线形势)
    │   ├── images.json                 #   图片索引 (含 URL、来源文章、alt 文本)
    │   └── images/                     #   比赛相关图片 (最多30张，按匹配度排序)
    └── images/                         # 战术图表 (9 张)
        ├── tactical_radar.png          # 战术雷达图
        ├── tactical_shots.png          # 时段射门分布
        ├── tactical_ppda.png           # 压迫强度对比
        ├── tactical_ppda_timeline.png  # 压迫强度时间曲线
        ├── pressing_effectiveness.png  # 压迫效果图
        ├── pressing_efficiency.png     # 压迫效率图
        ├── tactical_possession.png     # 控球摇摆图
        ├── lineup.png                 # 阵容图
        └── timeline.png               # 事件时间轴
```

> **已废弃**: `run.py`（旧版入口）、`generate_player_cards.py`、`run_player_v6.py`、`run_tactical_only.py` 不再维护，以 `generate_match_report.py` 为准。

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
| A1 | 四层因果模型计算 | `raw_data.json` | 内存中的 tactical_data dict | `src/engine/tactical_insights.py` |
| **A1.5** | **豆包联网搜索 + 图片抓取 (v4)** | 豆包 Responses API | `web_context/{pre,match,post}.txt` + 图片 + `images.json` | `generate_match_report.py` 内嵌 |
| A2 | **match_overview 生成** | 豆包赛况摘要 + DeepSeek 精细润色 | 新闻战报风格概述 (~500-600 字) | `src/composer/match_overview_prompt.py` |
| A3 | LLM 五段战术叙事 | `prompts/tactical.yaml`, A1, A2 | 叙事文本 (~4000 tokens) | `src/composer/tactical_prompt.py` |
| A4 | 战术图表 ×5 | A1 | radar/possession/shots/ppda/ppda_timeline | `src/visualizer/tactical_charts.py` |
| A5 | 压迫分析图表 ×2 | A1 + raw trends | pressing_effectiveness / pressing_efficiency | `src/visualizer/tactical_charts.py` |
| A6 | LLM 压迫叙事 | `prompts/pressing.yaml`, A1, A2 | 四段叙事 (布局/回报/代价/总结) | `src/composer/pressing_prompt.py` |
| A7 | 事件时间轴 + 阵容图 | `raw_data.json` | timeline.png / lineup.png | `src/visualizer/tactical_charts.py` / `lineup.py` |
| A8 | 保存战术数据 | A1+A3 | `tactical_analysis.json` / `.xlsx` | `generate_match_report.py` |
| A9 | LLM 文章取名 | `prompts/article_naming.yaml`, A2+A3 | 10 标题 (战术/人物/数据/自由) → `article_titles.json` | `src/composer/article_naming_prompt.py` |
| A10 | LLM 球员特稿推荐 | `prompts/player_feature_recommend.yaml`, A2+A3+探测器+关键事件 | 特稿 (看点/标题大纲) → `player_features.md` | `src/composer/player_feature_prompt.py` + `src/engine/player_feature_selector.py` |
| A11 | 组装 HTML 报告 | 以上全部产物 | `tactical_report.html` ★ (含 8 大板块) | `generate_match_report.py` `_build_tactical_html()` |

> **tactical_report.html 8 大板块**: 战术画像 → 战术演绎 → 战术验证 → 数据卡片 → 战术博弈 → 压迫分析 → 🖋️文章标题推荐 → 📰球员人物特稿推荐 → 事件时间轴

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

同前，略。

---

### 4.2 完整文件清单

```
外部输入（只读）
  config.yaml                           # SportMonks API + DeepSeek + 豆包 配置
  prompts/tactical.yaml                 # 战术叙事 Prompt 模板
  prompts/pressing.yaml                 # 压迫分析 Prompt 模板
  prompts/article_naming.yaml           # 文章取名 Prompt 模板
  prompts/player_feature_recommend.yaml # 球员特稿 Prompt 模板
  prompts/player_analysis.yaml          # 球员叙事 Prompt 模板

                     ┌─ 管道 A ─────────────────────────────────────
                     │
  data/raw/          │   output/{id}_{HOME}_vs_{AWAY}/
  {id}/raw_data.json─┤   ├── tactical_report.html ★ 主力产品 (8 大板块)
      (唯一数据源)    │   ├── article_titles.json (环节一: 10 标题)
                     │   ├── player_features.md  (环节二: 球员特稿)
                     │   ├── tactical_analysis.json / .xlsx
                     │   ├── web_context/         ★ 豆包联网搜索产出
                     │   │   ├── pre.txt          (赛前新闻摘要)
                     │   │   ├── match.txt        (赛况战报 + 首发)
                     │   │   ├── post.txt         (赛后新闻摘要)
                     │   │   ├── images.json      (图片索引)
                     │   │   └── images/          (比赛图片, ≤30张)
                     │   ├── images/ (9 张战术图表)
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
                           ├─ 管道 C ── output/.../player_cards/{Name}.png (29 张)
                           │            (依赖: _players_v6.json)
                           │
                           └─ 管道 D ── output/.../compare/{A}_vs_{B}.png
                                        (依赖: raw_data.json + _players_v6.json)
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

## 5. LLM 双引擎架构

### 5.1 架构概览

```
LLM 双引擎
├── DeepSeek (LLMClient)
│   用途: 战术叙事 / 压迫分析 / 文章取名 / 球员特稿 / 球员分析
│   协议: OpenAI 兼容 Chat Completions
│   端点: /v1/chat/completions
│   配置: config.yaml → llm 节点
│
└── 豆包 Doubao (DoubaoClient)
    用途: 联网搜索赛前/赛况/赛后新闻 + 图片源URL定位
    协议: 火山引擎 Ark Responses API
    端点: /api/v3/responses
    配置: config.yaml → doubao 节点
    特性: tools: [{"type": "web_search"}] 开启联网搜索
```

### 5.2 DeepSeek (LLMClient)

- **模型**: `deepseek-v4-pro` (当前主力)
- **调用方式**: OpenAI SDK 优先 → 失败回退 requests HTTP POST
- **代码位置**: `src/generator/llm_client.py` → `LLMClient` 类
- **方法**: `generate(system_prompt, user_prompt, max_tokens)` → str
- **重试**: 3次，指数退避 (1s, 2s, 4s)
- **Token 用量**: 日志输出 `LLM: tokens=N`

### 5.3 豆包 Doubao (DoubaoClient)

- **模型**: `doubao-seed-2-0-pro-260215`
- **API Key**: `ark-b3a3d353-b34b-4310-a789-8e88b3cd3269-51821`
- **端点**: `https://ark.cn-beijing.volces.com/api/v3/responses`
- **前置条件**: 需在火山引擎控制台开通"联网内容插件" → https://console.volcengine.com/common-buy/CC_content_plugin
- **方法**: `search(prompt, max_tokens, enable_web_search)` → dict {content, annotations, article_urls, input_tokens, output_tokens}
- **input 格式**: `[{"role": "user", "content": [{"type": "input_text", "text": prompt}]}]`
- **output 解析**: 遍历 `data["output"]`，提取 `output_text` + `annotations` 中的 `url_citation`
- **模型名格式**: `doubao-seed-2-0-pro-260215`（连字符格式），不是 `doubao-seed-2.0-pro`（点号格式会 404）
- **费用**: 输入 ¥0.514/1M tokens + 输出 ¥2.57/1M tokens（约 ¥0.05~0.15/场）

### 5.4 config.yaml 完整配置

```yaml
sportmonks:
  base_url: "https://api.sportmonks.com/v3/football"
  api_token: "你的SportMonks Token"

llm:                          # DeepSeek
  provider: "deepseek"
  api_key: "sk-xxx"
  base_url: "https://api.deepseek.com"
  model: "deepseek-v4-pro"
  temperature: 0.7
  max_tokens: 2048

doubao:                       # 豆包联网搜索
  api_key: "ark-xxx"
  base_url: "https://ark.cn-beijing.volces.com/api/v3"
  model: "doubao-seed-2-0-pro-260215"
  temperature: 0.7
  max_tokens: 4096

competition:
  league_id: 1
  season: 2026

visual:
  dpi: 150
  pitch_color: "grass"
  font_family: "sans-serif"
```

---

## 6. Step A1.5 详细设计：豆包联网搜索 + 图片抓取 (v4)

### 6.1 流程

```
Step A1.5 (v4) ─ 替代旧版 Bing News 抓取
│
├── [1] 三轮豆包联网搜索
│     ├── pre (赛前):  阵容/伤病/前瞻/历史交锋 → pre.txt
│     ├── match (赛况): 首发/进球/关键数据/赛后评价 → match.txt (含完整时间线)
│     └── post (赛后):  球员评价/纪录/出线形势 → post.txt
│     每次搜索返回: 摘要文本 + 引用文章URL列表 (annotations)
│
├── [2] 文章URL去重 → 逐页提取图片
│     └── _extract_images_from_page(url) 内嵌函数
│         ├── 跳过: 追踪像素、Logo、图标、二维码、头像、CSS背景
│         ├── 四层匹配:
│         │   Level 1: alt/URL 含队名（如 "France", "法国"）
│         │   Level 2: alt/URL 含通用关键词（"世界杯", "goal", Top6球员名）
│         │   Level 3: 父元素文本含队名
│         │   Level 4: 无匹配但通过格式过滤 → 兜底保留
│         ├── 按匹配度排序，Level 1-3 优先
│         └── alt 黑名单: "avatar", "header", "discusser", "bg@", "logo", "favicon" 等 → 直接丢弃
│
├── [3] 图片去重 → 下载（最多30张，≥5KB）
│     └── → web_context/images/img_001~030.jpg
│
├── [4] 保存 images.json (含 URL / 来源文章 / alt / 大小)
│
└── [5] 组装 match_overview
      ├── 豆包赛况摘要作为初稿
      └── DeepSeek 精细润色 → 最终 match_overview (传给后续 LLM 叙事)
```

### 6.2 与旧版 (Bing News v3) 对比

| | v3 (Bing News) | v4 (豆包) |
|:--|:--|:--|
| 新闻来源 | Bing News 搜索 → 3篇文章URL | 豆包联网搜索 → 多源文章URL |
| 文本生成 | 抓取HTML → 清洗 → DeepSeek改写 | 豆包直接生成摘要 |
| 首发阵容 | 抓取不到 | 豆包直接输出完整首发 |
| 关键事件 | 仅 SportMonks 数据 | 豆包 + SportMonks 互补 |
| 图片 | alt 含队名 → 0~10张 | 四层匹配 → 最多30张 |
| 步骤数 | 5步 (搜索→抓取→清洗→LLM改写→图片) | 2步 (搜索→摘要+图片) |
| 费用 | DeepSeek改写 ~¥0.01 | 豆包3次搜索 ~¥0.05~0.15 |

---

## 7. Playwright 渲染配置

战术时间轴 (timeline.png)、阵容图 (lineup.png)、球员卡片 依赖 Playwright 渲染 HTML → PNG。

### 7.1 系统 Chrome 优先策略

由于网络限制无法通过 `playwright install chromium` 下载 bundled Chromium，代码已改为**优先使用系统已安装的 Chrome**：

- `src/visualizer/lineup.py` → `save_lineup_png()`
- `src/visualizer/tactical_charts.py` → `save_timeline_png()`

会自动检测以下路径：
- `C:/Program Files/Google/Chrome/Application/chrome.exe`
- `C:/Program Files (x86)/Google/Chrome/Application/chrome.exe`

### 7.2 故障排查

| 错误 | 原因 | 解决 |
|------|------|------|
| `Executable doesn't exist at ...chrome-headless-shell.exe` | Playwright Chromium 未安装 | 安装系统 Chrome 即可，代码会自动使用 |
| `BrowserType.launch: ...` | 无可用浏览器 | 确保系统安装了 Google Chrome |

---

## 8. 实验脚本

以下脚本用于验证特定功能，不参与正式报告生成管线：

| 脚本 | 功能 | 用法 |
|------|------|------|
| `experiment_doubao_search.py` | 验证豆包联网搜索赛前/赛况/赛后 | `python experiment_doubao_search.py` |
| `experiment_search_and_images.py` | 豆包搜索 + 图片提取一体化 | `python experiment_search_and_images.py 法国 塞内加尔` |
| `experiment_image_hunt.py` | 三策略图片猎手（图集搜索+Bing+新闻） | `python experiment_image_hunt.py 法国 塞内加尔` |
| `experiment_image_search.py` | 豆包图片搜索能力测试 | `python experiment_image_search.py` |

实验产出位于 `output/doubao_experiment/` 目录。

---

## 9. 图片过滤策略

`generate_match_report.py` 内嵌的 `_extract_images_from_page()` 使用多层过滤：

### 9.1 黑名单过滤

**URL/alt 黑名单** (直接丢弃)：
- `beacon`, `tracking`, `pixel`, `doubleclick`, `analytics` (追踪像素)
- `logo`, `icon`, `avatar`, `qr`, `ewm`, `share` (图标/头像)
- `arrow`, `btn`, `close`, `weixin`, `wechat`, `code` (UI元素)
- `homepage`, `default`, `fileftp`, `login`, `placeholder`, `blank` (占位)
- `/user/`, `discusser`, `bg@`, `top-video`, `inside-top` (头像/背景)
- `style/`, `static.`, `favicon`, `emoticon` (样式/表情)

### 9.2 四级匹配排序

| Level | 条件 | 优先级 |
|-------|------|--------|
| 1 | alt 或 URL 含球队中/英文名 | 最高 |
| 2 | alt 或 URL 含通用足球关键词 + Top6球员名 | 高 |
| 3 | 父元素文本含队名 | 中 |
| 4 | 无匹配但通过格式/尺寸过滤 | 低（兜底） |

最终按 level 排序，Level 1-3 优先下载。最多下载 30 张，最小 5KB。

### 9.3 队名中文映射

内嵌 `_NAME_MAP_DB` 字典支持中英文队名匹配：
```
netherlands→荷兰, japan→日本, england→英格兰, france→法国,
germany→德国, spain→西班牙, italy→意大利, portugal→葡萄牙,
argentina→阿根廷, brazil→巴西, sweden→瑞典, tunisia→突尼斯,
korea→韩国, south korea→韩国
```

---

## 10. 常见问题与故障排查

### 10.1 豆包 API

| 错误 | 原因 | 解决 |
|------|------|------|
| `InvalidEndpointOrModel.NotFound` (404) | 模型名格式错误 | 使用连字符格式 `doubao-seed-2-0-pro-260215`，不用点号格式 |
| `ToolNotOpen` | 联网搜索插件未开通 | 到火山引擎控制台开通联网内容插件 |
| 返回内容为空 | search 返回 annotations 但无 output_text | 检查 prompt 是否要求了文本输出 |

### 10.2 图片下载

| 症状 | 原因 | 解决 |
|------|------|------|
| web_context/images 图片太少 | 队名匹配过严 | 当前已有 Level 1-4 分级过滤 + 兜底 |
| 图片与比赛无关 | 兜底太宽，收了头像/背景图 | alt 黑名单已过滤 avatar/header/bg@ 等 |
| 某篇文章 0 张图片 | 文章是纯文本 | 正常；或页面用了 JS 懒加载，需检查 `data-lazy-src` 等属性 |

### 10.3 Playwright

| 错误 | 解决 |
|------|------|
| Chromium 未安装 | 代码已改为使用系统 Chrome，无需单独安装 |
| 如果系统也没有 Chrome | 安装 Google Chrome 或通过 `playwright install chromium`（可能需要代理） |

### 10.4 DeepSeek

| 症状 | 原因 | 解决 |
|------|------|------|
| `_generate_http` 缺失 | DoubaoClient class 插入位置错误打断了 LLMClient 方法 | 确保 DoubaoClient 是独立 class，在 LLMClient 之后定义 |
| LLM 返回空 | prompt 太长或网络超时 | 已设 max_tokens=2048，自动重试 3 次 |

---

## 11. 关键代码位置速查

| 你想... | 去这里 |
|---------|--------|
| 修改豆包搜索 Prompt | `generate_match_report.py` → `prompts` 字典 (第 ~129 行) |
| 修改图片过滤规则 | `generate_match_report.py` → `_extract_images_from_page()` 内嵌函数 (第 ~172 行) |
| 修改图片下载数量 | `generate_match_report.py` → `if len(downloaded) >= 30:` (第 ~284 行) |
| 修改 DeepSeek LLM 配置 | `config.yaml` → `llm` 节点 |
| 修改豆包 API 配置 | `config.yaml` → `doubao` 节点 |
| 新增球队中文名 | `generate_match_report.py` → `_NAME_MAP_DB` 字典 |
| 修改球员卡片样式 | `generate_cards_v6.py` |
| 修改战术图表样式 | `src/visualizer/tactical_charts.py` |
| 修改阵容图样式 | `src/visualizer/lineup.py` |
| 修改球员对比图样式 | `src/visualizer/player_comparison.py` |
| 运行图片猎手实验 | `python experiment_image_hunt.py <队名1> <队名2>` |

---

## 12. 近期方案更新 (2026-06-18)

### 12.1 球员对比图 — 图表区改为 2×2 网格

**变更前**：3 行逐行对比（热图/传球/带球），A/B 左右并排，每行高 2.10"，图表区高度随图片数量线性增长。

**变更后**：每球员一个独立 2×2 紧凑网格，双方网格左右并排。

```
┌──────────────┐    ┌──────────────┐
│ 热图  │ 传球 │    │ 热图  │ 传球 │
├───────┼──────┤    ├───────┼──────┤
│ 带球  │ 射门★│    │ 带球  │ 射门★│
└──────────────┘    └──────────────┘
    Player A            Player B
```

**改动文件**：

| 文件 | 改动 |
|------|------|
| `src/visualizer/player_comparison.py` | 删除 `_draw_charts_row()` + `_draw_chart_card()` → 新增 `_draw_charts_2x2()`；`build_player_comparison_data()` 新增 `shot_chart_b64` 参数及返回；`chart_types` 新增 `("shot_chart_b64", "射门")`；`charts_h` 计算改为固定网格高度；新增 `from io import BytesIO` |
| `compare_players.py` | 加载 `shot_chart.png` + 传递 `shot_chart_b64` 参数给 `build_player_comparison_data()` |

**关键参数**（`_draw_charts_2x2`）：

| 参数 | 值 | 说明 |
|------|-----|------|
| `grid_cell_w` | `(info_panel_w - 0.24) / 2` | 每格宽 |
| `grid_cell_h` | 1.30 | 每格高（图片+标签） |
| `grid_gap` | 0.08 | 格间距 |
| `img_h` | `grid_cell_h - 0.28` | 图片区高度 |

**缺失处理**：图表缺失时显示浅色圆角空框 + 居中浅灰色斜体「无数据」。

### 12.2 球员汇总卡片 — 基本信息双列指标

**变更**：`_draw_player_info_card()` 从单列 3 项（进球/助攻/关键事件）改为双列 7 项：

| 左列 | 右列 |
|------|------|
| 进球 | 关键事件 |
| 助攻 | 传球 |
| 射门 | 传球成功率 |
| xG | |

数据源：`goals`/`assists`/`key_events` 来自 player dict 顶层，`shots`/`xG` 从 `dim_tables["进攻"]` 提取，`passes`/`pass_pct` 从 `dim_tables["控制"]` 提取。

`card_h`：1.85 → 2.30（容纳双列指标）。

### 12.3 雷达图网格颜色与线宽增强

| 参数 | 变更前 | 变更后 |
|------|--------|--------|
| `GRID_COLOR` | `#2a2a4a`（与背景色相近） | `#4a5a7a` |
| 网格线宽 | 0.5 | 0.7 |
| 网格 alpha | 0.5 | 0.7 |
| 轴线线宽 | 0.5 | 0.7 |
| 轴线 alpha | 0.4 | 0.6 |

### 12.4 分区标签文案统一

所有图表区分区标签统一为「球员活动对比」：
- `— 比赛视觉分析 —` → `— 球员活动对比 —`
- `— Player Map 对比 —` → `— 球员活动对比 —`
- 注释中的 `Player Map 标签` → `球员活动对比 标签`

### 12.5 球员点评文字优化

`_draw_llm_narrative()` 布局重构：

| 参数 | 变更前 | 变更后 | 说明 |
|------|--------|--------|------|
| 标题字号 | 9.5 | **10.5** | 更大更醒目 |
| 正文字号 | 8.5 → 9.0 → | **10.0** | 经两次迭代最终确定 |
| 正文行距 | 0.22 | **0.18** | 更紧凑 |
| 正文对齐 | ha="left"（左对齐） | **ha="center"（居中）** | |
| 正文字重 | 普通 | **fontweight="bold"（加粗）** | |
| 标题-正文间距 | 无精确控制 | **title_y - 0.14** | 明确预留 0.14 间距，避免标题正文重叠 |
| 底部留白 | 无 | **y_bot + 0.10** | 明确底部留白 |
| 换行宽度 | width=18（左对齐时） | **width=14**（居中适应面板宽度） | |

### 12.6 全卡字体统一放大

全部字体在原有基准上增大 1-2pt：

| 区域 | 元素 | 字体大小 |
|------|------|----------|
| 球员基本信息 | 姓名#号码 | 10 → **11** |
| | 出场时间 | 8.5 → **9.5** |
| | 跑动/推进 | 8 → **9** |
| | 双列指标标签+值 | 8.5 → **9.5** |
| 雷达图 | 维度标签 | 9 → **10.5** |
| | 图例球员名 | 7 → **8** |
| 图表区 | 分栏标题 "球员活动对比" | 8.5 → **10** |
| | 球员名+图表标签 | 7.5 → **9** |
| | 占位符 "暂无数据/加载失败" | 7 → **8** |
| 维度表格(detail) | 表头 | 6.5 → **7.5** |
| | 行数据 | 7 → **8** |

### 12.7 赛后融合报道生成

```bash
python generate_fusion_report.py 19609149
```

将战术分析段落 + 压迫分析段落 + 关键事件 + 新闻摘要融合为一篇战术+叙事综合比赛报道（HTML + Markdown），产出到 `output/{id}/fusion_report.html`。包含三个 LLM 调用步骤：战术叙事 → 压迫叙事 → 融合组装。
