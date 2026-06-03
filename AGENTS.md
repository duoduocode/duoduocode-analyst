# AGENTS.md — AI 足球分析员 (Football Analyst)

> 本文档供 AI Agent 理解项目上下文、架构与常见问题，便于在新环境中快速上手调试。

---

## 1. 项目概述

**目标**：从 API-Football (api-sports.io 直连) 获取比赛数据 → 计算自创指标 → 调用 DeepSeek LLM 生成分析文字 → mplsoccer 生成图表 → 拼装 Markdown 图文比赛报告，适配微信公众号发布。

**技术栈**：Python 3.11+ / requests / pyyaml / matplotlib / mplsoccer / numpy / scipy / markdown / jinja2

**LLM**：DeepSeek (`deepseek-chat`)，OpenAI 兼容协议，支持两种调用方式：
- 优先尝试 `openai` SDK (Python 包)
- 后备：纯 `requests` HTTP POST 到 `/chat/completions`

---

## 2. 快速启动

```bash
# 1. 安装依赖
pip install requests pyyaml matplotlib mplsoccer numpy scipy openai markdown jinja2

# 2. 配置 API Key（两种方式）
#    方式A: 写到 config.yaml（已配置则跳过）
#    方式B: 环境变量
set API_FOOTBALL_KEY=你的key
set DEEPSEEK_API_KEY=你的key

# 3. 生成报告
python run.py --match 1544371                    # 单场完整报告
python run.py --match 1544371 --dry-run           # 仅采集+计算，不调 LLM
python run.py --match 1544371 --no-images         # 跳过图表（matplotlib 不可用时）
python run.py --league 1 --date 2026-06-12        # 批量生成某日全部比赛
```

---

## 3. 项目结构

```
d:\football-data\
├── config.yaml                          # API Key + LLM 配置
├── requirements.txt
├── run.py                               # 入口脚本
├── prompts/                             # 9 个 Jinja2+YAML Prompt 模板
│   ├── cover.yaml / contrast.yaml / momentum.yaml / tactics.yaml
│   ├── mvp.yaml / hidden_mvp.yaml / black_hole.yaml
│   └── subs.yaml / replay.yaml
├── src/
│   ├── collector/
│   │   └── api_client.py               # API-Football v3 封装
│   ├── engine/
│   │   ├── metrics.py                  # CI/TCR/PE + ComputedData + compute_all
│   │   ├── ratings.py                  # 球员贡献分 + 三类分类 + 雷达数据
│   │   └── simulator.py                # 蒙特卡洛 xG 模拟 + LDI（纯Py+scipy+numpy三级后备）
│   ├── composer/
│   │   ├── prompt_loader.py            # YAML 加载 + Jinja2 渲染
│   │   └── data_builder.py             # 9 个模块的数据→Prompt 组装
│   ├── generator/
│   │   └── llm_client.py              # DeepSeek（openai SDK 优先，requests 后备）
│   ├── visualizer/
│   │   ├── __init__.py                 # 颜色常量
│   │   ├── shots.py                    # mplsoccer 射门分布图
│   │   ├── momentum.py                 # 动量曲线 + 事件标注
│   │   ├── pass_network.py             # mplsoccer 传球网络图
│   │   ├── radar.py                    # 球员雷达图 (7维度)
│   │   ├── subs.py                     # 换人对比柱状图
│   │   └── xg_hist.py                  # xG 模拟分布图
│   └── reporter/
│       └── build_report.py            # Markdown + HTML 报告拼装
├── data/
│   ├── raw/{match_id}/raw_data.json    # 原始 API JSON
│   └── computed/{match_id}.json       # 计算后指标
├── output/{match_id}_{HOME}_vs_{AWAY}/
│   ├── images/*.png                   # 图表（需 matplotlib/mplsoccer）
│   ├── report.md                      # 完整图文报告
│   └── report.html                    # HTML 版本
└── docs/superpowers/specs/
    └── 2025-06-03-football-analyst-design.md   # 完整设计文档
```

---

## 4. 核心架构与数据流

```
run.py
  ├─ 1. load_config() → 读取 config.yaml，替换 ${ENV_VAR} 占位符
  ├─ 2. fetch_all(match_id) → API-Football × 5 端点 (ThreadPoolExecutor 并行)
  │      ├─ /fixtures?id=X         → 比分/裁判/状态
  │      ├─ /fixtures/statistics   → 球队统计（字段映射见 §5）
  │      ├─ /fixtures/players      → 球员统计
  │      ├─ /fixtures/events       → 进球/换人/红黄牌
  │      └─ /fixtures/lineups      → 首发阵型
  ├─ 3. compute_all() → 计算 CI/TCR/PE/LDI/动量/球员分类/标签
  ├─ 4. generate_all_texts() → 9 次 LLM 调用
  ├─ 5. generate_all_visuals() → 7 张 mplsoccer 图表 (可选)
  └─ 6. build_report() → Markdown + HTML 输出
```

---

## 5. 关键适配：API-Sports 直连字段映射

⚠️ **API-Sports 直连 (`v3.football.api-sports.io`) 与 RapidAPI 的字段名有时不同。**

### 5.1 statistics 端点字段名

`src/engine/metrics.py` 中的 `_stat()` 函数支持多别名回退：

```python
def _stat(stats: dict, *keys, default=0):
    for k in keys:
        v = stats.get(k)
        if v is not None:
            return v
    return default
```

当前已知字段映射：

| 代码期望名 | API 实际返回名 | 备注 |
|---|---|---|
| `Expected Goals` | `expected_goals` | ⚠️ API-Sports 用蛇形 |
| `Ball Possession` | `Ball Possession` | 两者一致 |
| `Total Shots` | `Total Shots` | 两者一致 |
| `Shots on Goal` | `Shots on Goal` | 两者一致 |
| `Corner Kicks` | `Corner Kicks` | 两者一致 |
| `Passes %` | `Passes %` | 两者一致 |
| `Big Chances Created` | 不返回 | Pro Plan 可能也不含 |
| `Ball Recoveries` | 不返回 | Pro Plan 可能也不含 |
| `Crosses` / `Offsides` / `Tackles` / `Fouls` | 同名字段 | OK |

### 5.2 球员 passes.accuracy

⚠️ API-Sports 返回的 `passes.accuracy` 是**准确传球次数**（count），不是百分比。代码在 `api_client.py` 中已转换为百分比：

```python
passes_total_val = _safe_int(passes.get("total"))
passes_accurate_count = _safe_int(passes.get("accuracy"))
passes_accuracy_pct = round(passes_accurate_count / max(passes_total_val, 1) * 100, 1)
```

### 5.3 认证方式

```python
if "api-sports.io" in self.api_host:
    self.headers = {"x-apisports-key": self.api_key}
else:
    self.headers = {"X-RapidAPI-Key": ..., "X-RapidAPI-Host": ...}
```

---

## 6. 自创指标速查

| 指标 | 公式（核心） | 范围 | 数据源 |
|---|---|---|---|
| **CI** 控制指数 | 0.35×控球 + 0.25×传球 + 0.25×区域 + 0.15×回收 | 0-100 (两队之和=100) | Possession%, Pass%, Shots insidebox, Corners, Ball Recoveries |
| **TCR** 威胁转化率 | 100×(xG+0.3×绝佳机会)/(射门+0.3×角球) | 通常 2-35 | xG, Big Chances, Total Shots, Corners |
| **PE%** 压迫效率 | 100×(回收/(犯规+1)) / 双方之和 | 0-100 | Ball Recoveries, Fouls |
| **LDI** 运气偏离 | P(实际比分)/P(最可能比分) | 0-1+ | xG + 蒙特卡洛模拟 |

指标解读区间见 `src/engine/metrics.py` 中的 `interpret_tcr()` 和 `simulator.py` 中的 LDI interpretation。

---

## 7. 降级策略

| 场景 | 策略 |
|---|---|
| `scipy` 未安装 | → 尝试 `numpy.random.poisson` |
| `numpy` 未安装 | → 纯 Python Knuth 算法，模拟次数降至 2000 |
| `matplotlib` / `mplsoccer` 未安装 | → `--no-images` 跳过图表 |
| `openai` SDK 未安装 | → LLMClient 自动降级为 `requests` HTTP POST |
| `Big Chances Created` 不返回 | → 默认 0，TCR 分母仍正常 |
| `Ball Recoveries` 不返回 | → 默认 0，PE 回归 50/50 中性值 |

---

## 8. 调试建议

### 8.1 先 dry-run
```bash
python run.py --match 1544371 --dry-run
```
只拉数据 + 算指标，不调 LLM。检查 `data/raw/{id}/raw_data.json` 确认字段是否正确。

### 8.2 查看原始 API 返回的字段
```bash
python -c "import json; d=json.load(open('data/raw/1544371/raw_data.json','utf-8')); print(list(d['home_stats'].keys()))"
```

### 8.3 检查 LLM 是否可用
```bash
python -c "from src.generator.llm_client import LLMClient; import yaml; c=LLMClient(yaml.safe_load(open('config.yaml'))['llm']); print(c.generate('你是翻译','将hello翻译成中文'))"
```

### 8.4 单模块重跑
如果某个模块失败，可以在 Python 交互环境中单独测试：
```python
from src.collector.api_client import fetch_all
raw = fetch_all(1544371, config["api_football"])

from src.engine.metrics import compute_all
computed = compute_all(raw)

from src.composer.data_builder import DataBuilder
from src.composer.prompt_loader import PromptLoader
pl = PromptLoader("prompts")
builder = DataBuilder(pl)
sys_p, user_p = builder.build_cover(raw, computed)
```

---

## 9. 已知问题与待办

- [ ] `Big Chances Created` 和 `Ball Recoveries` 在 API-Sports 直连中不返回（Pro Plan 确认）
- [ ] `Tackles` 统计数据返回 0，可能字段名不同
- [ ] 射门坐标 (x,y) 需要确认 Pro Plan `fixtures/players` 端点是否返回
- [ ] mplsoccer 图表在无图形环境的服务器上需要设置 `matplotlib.use("Agg")`（已设置）
- [ ] Windows 环境下 `matplotlib` 中文字体需要单独配置

---

## 10. 多环境迁移清单

在新电脑上部署时，按顺序检查：

1. `git clone` 本项目
2. `pip install -r requirements.txt`
3. 将 `config.yaml` 中的 API Key 填入（或用环境变量）
4. `python -c "from src.collector.api_client import APIFootballClient; print('OK')"` → 验证导入
5. `python run.py --match 1544371 --dry-run` → 验证数据管线
6. `python run.py --match 1544371` → 完整生成
