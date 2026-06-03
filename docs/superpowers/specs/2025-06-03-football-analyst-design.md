# AI 足球分析员 — 系统设计文档

> 版本: 1.0 | 日期: 2025-06-03 | 状态: 设计阶段

---

## 1. 项目概述

### 1.1 目标

构建一个 AI 驱动的足球比赛分析报告生成系统。从 API-Football 获取比赛数据，通过自创指标体系与 LLM 解读，自动生成 3-5 分钟阅读量的图文结合比赛报告，供在微信公众号等社交媒体平台发布。

### 1.2 范围

- **首个目标赛事**：2026 世界杯（2026年6月11日开幕）
- **运行方式**：本地命令行工具，手动触发
- **输出格式**：Markdown + PNG 图表，适配公众号发布流程

### 1.3 技术栈

| 层 | 技术 |
|---|---|
| 语言 | Python 3.11+ |
| 数据源 | API-Football v3 (RapidAPI, Pro Plan) |
| LLM | DeepSeek (deepseek-chat, OpenAI 兼容协议) |
| 可视化 | matplotlib + mplsoccer |
| 数值计算 | numpy + scipy |
| 配置 | YAML |
| 报告模板 | Jinja2 |

### 1.4 依赖清单

```
requests>=2.31
pyyaml>=6.0
matplotlib>=3.8
mplsoccer>=1.3
numpy>=1.26
scipy>=1.11
markdown>=3.5
jinja2>=3.1
```

---

## 2. 项目结构

```
d:\football-data\
├── src/
│   ├── collector/
│   │   ├── __init__.py
│   │   └── api_client.py           # API-Football v3 封装
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── metrics.py              # CI / TCR / PE / LDI 指标计算
│   │   ├── ratings.py              # 三类球员评分
│   │   └── simulator.py            # 蒙特卡洛 xG 模拟
│   ├── composer/
│   │   ├── __init__.py
│   │   ├── data_builder.py         # 组装各模块的数据卡片
│   │   └── prompt_loader.py        # 加载 + 渲染 prompt 模板
│   ├── generator/
│   │   ├── __init__.py
│   │   └── llm_client.py           # LLM API 调用封装
│   ├── visualizer/
│   │   ├── __init__.py
│   │   ├── shots.py                # 射门分布图
│   │   ├── pass_network.py         # 传球网络图
│   │   ├── radar.py                # 球员雷达图
│   │   ├── momentum.py             # 动量曲线图
│   │   ├── subs.py                 # 换人对比图
│   │   └── xg_hist.py              # xG 模拟分布图
│   └── reporter/
│       ├── __init__.py
│       └── build_report.py         # 拼装最终 Markdown 报告
├── prompts/
│   ├── cover.yaml                  # 模块1: 封面卡片
│   ├── contrast.yaml               # 模块2: 反差数据面板
│   ├── momentum.yaml               # 模块3: 比赛走势
│   ├── tactics.yaml                # 模块4: 战术兑现度
│   ├── mvp.yaml                    # 模块5a: 账面MVP
│   ├── hidden_mvp.yaml             # 模块5b: 隐性MVP
│   ├── black_hole.yaml             # 模块5c: 黑洞球员
│   ├── subs.yaml                   # 模块6: 换人效果
│   └── replay.yaml                 # 模块7: 重踢100次
├── data/
│   ├── raw/                        # 原始 API JSON（按 match_id 目录）
│   └── computed/                   # 计算后数据 JSON
├── output/                         # 生成的报告
│   └── {YYYY-MM-DD}_{HOME}_vs_{AWAY}/
│       ├── images/
│       │   ├── 01_shots.png
│       │   ├── 02_momentum.png
│       │   ├── 03_pass_network.png
│       │   ├── 04a_radar_mvp.png
│       │   ├── 04b_radar_hidden.png
│       │   ├── 05_subs.png
│       │   └── 06_xg_hist.png
│       ├── report.md
│       ├── report.html
│       └── copy_paste.txt
├── config.yaml                     # 全局配置
├── run.py                          # 入口脚本
└── requirements.txt
```

---

## 3. 配置文件设计

### 3.1 config.yaml 结构

```yaml
api_football:
  base_url: "https://api-football-v1.p.rapidapi.com/v3"
  api_key: "${API_FOOTBALL_KEY}"
  api_host: "api-football-v1.p.rapidapi.com"

llm:
  provider: "deepseek"
  api_key: "${DEEPSEEK_API_KEY}"
  base_url: "https://api.deepseek.com/v1"
  model: "deepseek-chat"
  temperature: 0.7
  max_tokens: 800

competition:
  league_id: 1                      # 1=World Cup
  season: 2026

visual:
  dpi: 150
  pitch_color: "grass"
  font_family: "sans-serif"
```

**说明**：
- `${...}` 变量从环境变量读取，不在配置文件里放密钥明文
- `league_id: 1` 是 API-Football 中世界杯的 ID

---

## 4. 数据采集层 (collector/api_client.py)

### 4.1 接口定义

```python
class APIFootballClient:
    """API-Football v3 客户端 (RapidAPI)"""
    
    def __init__(self, config: dict): ...
    
    def get_fixture(self, match_id: int) -> dict:
        """GET /fixtures?id={match_id} → 比分、裁判、场馆、状态"""
    
    def get_statistics(self, fixture_id: int) -> dict:
        """GET /fixtures/statistics?fixture={fixture_id} → 球队统计数据"""
    
    def get_players(self, fixture_id: int) -> dict:
        """GET /fixtures/players?fixture={fixture_id} → 球员统计数据"""
    
    def get_events(self, fixture_id: int) -> dict:
        """GET /fixtures/events?fixture={fixture_id} → 进球、换人、红黄牌"""
    
    def get_lineups(self, fixture_id: int) -> dict:
        """GET /fixtures/lineups?fixture={fixture_id} → 首发阵容 + 阵型"""
```

### 4.2 数据获取流程

```python
def fetch_all(match_id: int) -> RawMatchData:
    """
    1. 调用 get_fixture → 获取 fixture_id, 比分, 半场比分, 状态
    2. 并行调用剩余 4 个接口（statistics, players, events, lineups）
    3. 所有原始 JSON 存到 data/raw/{match_id}/ 目录
    4. 返回 RawMatchData dataclass
    """
```

### 4.3 RawMatchData 数据结构

```python
@dataclass
class RawMatchData:
    match_id: int
    fixture_id: int
    home_team: TeamInfo
    away_team: TeamInfo
    score: ScoreInfo
    status: str                           # "FT" / "AET" / "PEN"
    
    home_stats: dict                      # statistics 中 home 部分
    away_stats: dict                      # statistics 中 away 部分
    
    home_players: list[PlayerStats]       # players 中 home 部分
    away_players: list[PlayerStats]       # players 中 away 部分
    
    events: list[MatchEvent]
    home_lineup: LineupInfo
    away_lineup: LineupInfo

@dataclass
class TeamInfo:
    id: int
    name: str
    logo_url: str

@dataclass
class ScoreInfo:
    home: int
    away: int
    halftime_home: int
    halftime_away: int

@dataclass
class PlayerStats:
    id: int
    name: str
    number: int
    position: str
    grid: str | None                     # 阵型中的网格位置
    is_substitute: bool
    minutes_played: int
    
    # statistics 子对象
    rating: float | None                 # games.rating
    goals: int
    assists: int
    shots_total: int
    shots_on: int
    passes_total: int
    passes_key: int
    passes_accuracy: int                 # 百分比如 85
    tackles_total: int
    tackles_interceptions: int
    duels_total: int
    duels_won: int
    dribbles_attempts: int
    dribbles_success: int
    fouls_committed: int
    fouls_drawn: int

@dataclass
class MatchEvent:
    time_elapsed: int
    time_extra: int | None
    team_id: int
    player_name: str
    assist_name: str | None
    event_type: str                      # "Goal" | "Card" | "subst" | "Var"
    detail: str                          # "Normal Goal" | "Yellow Card" | ...
    comments: str | None

@dataclass
class LineupInfo:
    formation: str                       # "4-3-3"
    players: list[LineupPlayer]

@dataclass
class LineupPlayer:
    id: int
    name: str
    number: int
    position: str                        # "G" "D" "M" "F"
    grid: str | None                     # "1:1" 等
```

### 4.4 关键字段映射（API-Football → 内部字段）

| API-Football 路径 | 内部字段 |
|---|---|
| `fixtures[0].teams.home.name` | `home_team.name` |
| `fixtures[0].goals.home` | `score.home` |
| `fixtures[0].score.halftime.home` | `score.halftime_home` |
| `statistics[0].statistics[]` (type=字段名, value=值) | `home_stats[字段名]` |
| `players[0].players[].statistics[0].games.rating` | `PlayerStats.rating` |
| `players[0].players[].statistics[0].goals.total` | `PlayerStats.goals` |
| `players[0].players[].statistics[0].passes.key` | `PlayerStats.passes_key` |
| `events[].time.elapsed` | `MatchEvent.time_elapsed` |
| `lineups[].formation` | `LineupInfo.formation` |

**注意**：API-Football 的 statistics 响应结构是 `{"statistics": [{"type": "Ball Possession", "value": "65%"}, ...]}`，需要在解析时做 key→value 映射。

---

## 5. 数据计算引擎 (engine/)

### 5.1 控制指数 CI (metrics.py)

```python
def compute_control_index(
    home_possession: float,      # 0-100
    away_possession: float,
    home_pass_accuracy: float,   # 0-100
    away_pass_accuracy: float,
    home_shots_insidebox: int,
    away_shots_insidebox: int,
    home_corners: int,
    away_corners: int,
    home_ball_recoveries: int,
    away_ball_recoveries: int,
) -> tuple[float, float]:
    """
    返回 (CI_home, CI_away)，两者之和恒为 100
    
    公式:
      CI_home = 100 × (
          0.35 × poss_home / (poss_home + poss_away)
        + 0.25 × pass_acc_home / (pass_acc_home + pass_acc_away)
        + 0.25 × territory_home / (territory_home + territory_away)
        + 0.15 × recovery_home / (recovery_home + recovery_away)
      )
      territory = shots_insidebox + corners
      recovery = ball_recoveries
    
    分子 + 0.001 防止除以零
    """
```

### 5.2 威胁转化率 TCR (metrics.py)

```python
def compute_threat_conversion_rate(
    xg: float,
    big_chances: int,
    total_shots: int,
    corners: int,
) -> float:
    """
    返回 TCR (0-100+)
    
    公式:
      TCR = 100 × (xg + 0.3 × big_chances) / (total_shots + 0.3 × corners + 0.01)
    
    解读:
      > 25   : 极其高效
      15-25  : 进攻高效
      8-15   : 正常范围
      4-8    : 效率偏低
      < 4    : 进攻乏力
    """
```

### 5.3 压迫效率 PE (metrics.py)

```python
def compute_pressing_efficiency(
    home_rec: int, home_fouls: int,
    away_rec: int, away_fouls: int,
) -> tuple[float, float]:
    """
    返回 (PE%_home, PE%_away)，两者之和恒为 100
    
    公式:
      raw_home = home_rec / (home_fouls + 1)
      raw_away = away_rec / (away_fouls + 1)
      PE%_home = 100 × raw_home / (raw_home + raw_away)
      
    +1 防止除以零
    """
```

### 5.4 运气偏离指数 LDI (simulator.py)

```python
def compute_luck_deviation(
    home_xg: float,
    away_xg: float,
    actual_home_goals: int,
    actual_away_goals: int,
    simulations: int = 10000,
) -> dict:
    """
    蒙特卡洛模拟 × N 次，返回:
    {
        "home_win_pct": float,     # 主胜概率%
        "draw_pct": float,         # 平局概率%
        "away_win_pct": float,     # 客胜概率%
        "top3_scores": list[tuple], # 最可能比分 Top3
        "ldi": float,              # 运气偏离指数
        "interpretation": str,     # "实力碾压" | "正常范围" | "运气较大" | "极度反常"
    }
    
    算法:
    1. 以 home_xg, away_xg 为 λ 参数
    2. 投两次泊松分布 → (h_goals, a_goals)
    3. 重复 N 次，统计各比分频率
    4. LDI = P_actual_result / P_most_likely_result
    5. 使用 scipy.stats.poisson
    """
```

### 5.5 球员评分系统 (ratings.py)

```python
def compute_player_contribution(player: PlayerStats) -> float:
    """
    综合贡献分:
      goals × 30
      + assists × 20
      + shots_on × 5
      + passes_key × 8
      + tackles × 3
      + tackles_interceptions × 3
      + duel_win_rate × 10       # duels_won/duels_total (按0-1)
      - fouls_committed × 3
    """

def classify_players(
    players: list[PlayerStats],
) -> dict:
    """
    返回:
    {
        "mvp": PlayerStats,           # rating 最高者
        "hidden_mvp": PlayerStats,     # 综合贡献分最高但 rating 不在前三
        "black_hole": PlayerStats,     # 出场>60min + rating<6.5 + 同位置贡献分最低
    }
    """
```

### 5.6 动量分数 (metrics.py)

```python
def compute_momentum(
    home_events: list[MatchEvent],
    away_events: list[MatchEvent],
) -> dict:
    """
    将比赛按 15 分钟分段，每段计算动量分:
      momentum = shots_on × 2 + (shots - shots_on) × 0.5 
               + corners × 1 + big_chances × 3
    
    返回:
    {
        "segments": [
            {"minute_range": "0-15",  "home": float, "away": float},
            {"minute_range": "15-30", "home": float, "away": float},
            ...
        ],
        "key_events": [...]           # 标注的关键事件
    }
    """
```

### 5.7 ComputedData 聚合结构 (类型定义)

```python
@dataclass
class ComputedData:
    """所有计算结果的聚合体，由 engine 层产出"""
    match_id: int
    
    # CI
    home_ci: float
    away_ci: float
    
    # TCR
    home_tcr: float
    away_tcr: float
    
    # PE
    home_pe: float
    away_pe: float
    
    # LDI 模拟结果
    ldi_result: dict                   # compute_luck_deviation() 的返回值
    
    # 动量
    momentum: dict                     # compute_momentum() 的返回值
    
    # 球员分类
    home_mvp: PlayerStats
    home_hidden_mvp: PlayerStats
    home_black_hole: PlayerStats | None
    away_mvp: PlayerStats
    away_hidden_mvp: PlayerStats
    away_black_hole: PlayerStats | None
    
    # 换人效果
    home_subs_effect: list[dict]
    away_subs_effect: list[dict]
    
    # 比赛标签
    tags: list[str]                    # ["一边倒", "冷门", "对攻"]
    
    # 战术特征
    home_attack_distribution: dict     # {"left": pct, "center": pct, "right": pct}
    away_attack_distribution: dict
    home_long_ball_ratio: float
    away_long_ball_ratio: float
```

---

## 6. 可视化层 (visualizer/)

### 6.1 通用约定

- 所有图表输出 PNG 格式，DPI=150
- 颜色方案：主队绿色系 `#2ecc71`/`#27ae60`，客队蓝色系 `#3498db`/`#2980b9`
- 保存路径：`output/{match_dir}/images/{filename}.png`
- 每个函数返回保存路径字符串

```python
# 颜色常量
HOME_COLOR = "#2ecc71"
HOME_COLOR_DARK = "#27ae60"
AWAY_COLOR = "#3498db"
AWAY_COLOR_DARK = "#2980b9"
NEUTRAL_COLOR = "#95a5a6"
HIGHLIGHT_COLOR = "#e74c3c"
```

### 6.2 射门分布图 (shots.py)

```python
def plot_shot_map(
    home_shots: list[dict],      # [{x, y, xg, goal, player, minute}, ...]
    away_shots: list[dict],
    home_name: str,
    away_name: str,
    output_path: str,
) -> str:
    """
    使用 mplsoccer.Pitch(pitch_type='statsbomb')
    
    实现:
    - 球场背景 + 球门
    - 主队射门: 空心圆=射失, 实心圆=进球, 大小 ∝ xG
    - 客队射门: 空心方=射失, 实心方=进球, 大小 ∝ xG
    - 标注进球球员名 + 分钟数
    - 图例: xG 比例尺 + 进球标记
    - 标题: "{主队} vs {客队} 射门分布 | xG {主xG} - {客xG}"
    
    尺寸: 12×8 inches
    """
```

### 6.3 动量曲线图 (momentum.py)

```python
def plot_momentum_curve(
    segments: list[dict],        # 6个15分钟段
    key_events: list[dict],      # [{minute, label, type}, ...]
    home_name: str,
    away_name: str,
    output_path: str,
) -> str:
    """
    使用 matplotlib (双色填充面积图)
    
    实现:
    - x轴: 时间(分钟), y轴: 动量分
    - 主队在上(绿色填充), 客队在下(蓝色填充)
    - 关键事件标注在对应时间点 (使用 ax.annotate)
    - 事件类型区分: ⚽进球 / 🔴红牌 / 🟡黄牌 / 🔄换人
    - 标题: "比赛动量走势 - {主队} vs {客队}"
    
    尺寸: 12×5 inches
    """
```

### 6.4 传球网络图 (pass_network.py)

```python
def plot_pass_network(
    players: list[LineupPlayer],
    player_stats: list[PlayerStats],
    formation: str,
    team_name: str,
    output_path: str,
) -> str:
    """
    使用 mplsoccer.Pitch(pitch_type='statsbomb')
    
    实现:
    - 球场单侧半场背景
    - 按阵型放置球员节点（根据 grid 或 position 推算坐标）
    - 节点大小 ∝ 传球次数
    - 连线粗细 ∝ 传球量（同区域节点之间）
    - 关键传球次数标注在节点旁
    - 标题: "{球队} 传球网络 | 阵型 {formation}"
    
    注意: API-Football 不提供传球起点/终点坐标，
    采用"位置近似法"——同一区域(防线/中场/锋线)的球员之间连线，
    粗细按 passes_total 加权。
    
    尺寸: 10×7 inches
    """
```

### 6.5 球员雷达图 (radar.py)

```python
def plot_player_radar(
    player: PlayerStats,
    player_label: str,
    comparison_label: str,           # "全队平均" 或 "同位置平均"
    comparison_values: dict,
    output_path: str,
    is_hidden_mvp: bool = False,
) -> str:
    """
    使用 mplsoccer.Radar
    
    维度:
    - 射门威胁 (shots_on / total_shots + xG)
    - 传球创造力 (key_passes)
    - 抢断贡献 (tackles)
    - 拦截 (+ interceptions)
    - 对抗胜率 (duels_won / duels_total)
    - 传球稳定性 (passes_accuracy)
    - 控球贡献 (dribbles_success)
    
    两组线: 球员本人 vs 参照组
    尺寸: 7×7 inches
    """
```

### 6.6 换人对比图 (subs.py)

```python
def plot_subs_comparison(
    subs_data: list[dict],         # {time, player_in, player_out, pre_xg_diff, post_xg_diff, rating}
    team_name: str,
    output_path: str,
) -> str:
    """
    使用 matplotlib 水平分组柱状图
    
    实现:
    - x轴: 换人时间轴
    - y轴: xG差(换人前/后)
    - 用颜色区分 改善(绿)/恶化(红)/不变(灰)
    - 标注替补球员名 + 换人评级(A+/A/B/D)
    
    尺寸: 10×4 inches
    """
```

### 6.7 xG 分布直方图 (xg_hist.py)

```python
def plot_xg_histogram(
    simulation_results: dict,       # 来自 simulator.compute_luck_deviation()
    actual_home: int,
    actual_away: int,
    home_name: str,
    away_name: str,
    output_path: str,
) -> str:
    """
    使用 matplotlib 双色直方图
    
    实现:
    - x轴: 模拟比分(整理后), y轴: 频率
    - 主胜/平局/客胜用三种颜色区分
    - 红色竖线标注实际比分位置
    - 文字标注模拟结果: "主胜 {pct}% / 平 {pct}% / 客胜 {pct}%"
    - 标注 LDI 值
    
    尺寸: 10×5 inches
    """
```

---

## 7. 提示词模板层 ( prompts/ )

### 7.1 模板格式

每个 YAML 文件包含 `system` + `user` 两个字段，`user` 中使用 Jinja2 语法嵌入变量：

```yaml
# prompts/cover.yaml
system: |
  你是一位资深足球比赛分析师。你的风格是：专业但不枯燥，有洞察力但不哗众取宠。
  你相信数据能还原比赛真相，也尊重足球的不可预测性。

user: |
  请根据以下比赛数据，生成一句准确且有记忆点的开场结论（不超过40字）。
  不要太标题党，但要让读者感到"这句话说出了我隐约感觉到但说不清楚的东西"。

  比赛信息：
  - 对阵：{{ home_team }} vs {{ away_team }}
  - 比分：{{ home_goals }}-{{ away_goals }}（半场 {{ halftime_home }}-{{ halftime_away }}）
  - 数据对比：
    控球率：{{ home_team }} {{ home_possession }}% vs {{ away_team }} {{ away_possession }}%
    射门/射正：{{ home_team }} {{ home_shots }}/{{ home_shots_on }} vs {{ away_team }} {{ away_shots }}/{{ away_shots_on }}
    xG（预期进球）：{{ home_team }} {{ home_xg }} vs {{ away_team }} {{ away_xg }}
    绝佳机会：{{ home_team }} {{ home_big_chances }} vs {{ away_team }} {{ away_big_chances }}

  比赛特征标签：{{ tags }}

  请直接输出一句开头结论，不要加任何前缀。
```

### 7.2 其余 Prompts 模板

其余 8 个模板文件按照「平衡风格版」提示词填入（完整内容见对话历史），分别对应：

| 文件 | 用途 | 需要渲染的 Jinja2 变量 |
|---|---|---|
| `cover.yaml` | 封面暴击结论 (≤40字) | home_team, away_team, home_goals, away_goals, halftime_home, halftime_away, home_possession, away_possession, home_shots, away_shots, home_shots_on, away_shots_on, home_xg, away_xg, home_big_chances, away_big_chances, tags |
| `contrast.yaml` | 反差数据面板，选3项写解读 (各20-30字) | home_possession, away_possession, home_xg, away_xg, home_shots, away_shots, home_shots_on, away_shots_on, home_big_chances, away_big_chances, home_pass_acc, away_pass_acc, home_tackles, away_tackles |
| `momentum.yaml` | 比赛走势分析 (150-200字) | home_team, away_team, segments (6段动量分), events_list |
| `tactics.yaml` | 战术兑现度 (180-250字) | home_team, away_team, home_formation, away_formation, home_attack_distribution, away_attack_distribution, home_long_ball_pct, away_long_ball_pct, home_crosses, away_crosses, home_offsides, away_offsides, home_pass_acc, away_pass_acc, home_final_third_passes, away_final_third_passes, home_tackles, away_tackles, home_ci, away_ci, home_pe, away_pe |
| `mvp.yaml` | 账面MVP (60-80字) | player_name, team, minutes, rating, goals, assists, shots, shots_on, key_passes, dribbles_success, pass_accuracy |
| `hidden_mvp.yaml` | 隐性MVP (60-80字) | player_name, team, minutes, rating, rating_rank, tackles, interceptions, duel_win_pct, key_passes, pass_accuracy, distance_covered, hidden_contribution, contribution_rank |
| `black_hole.yaml` | 黑洞球员 (50-70字) | player_name, team, minutes, rating, shots, shots_on, duel_win_pct, duel_won, duel_total, fouls, possession_lost, pass_accuracy, contribution, contribution_rank_by_position |
| `subs.yaml` | 换人效果 (120-150字) | home_team, away_team, home_subs (list), away_subs (list) — 每条含 time, player_in, player_out, pre_xg_diff, post_xg_diff, sub_rating, minutes_played, key_contribution |
| `replay.yaml` | 重踢100次总结 (60-80字) | home_team, away_team, home_goals, away_goals, home_xg, away_xg, home_win_pct, draw_pct, away_win_pct, top3_scores, ldi, ldi_interpretation |

**注意**：实际 system prompt 和 user prompt 的具体措辞需按照对话历史中「平衡风格版」填入。上表仅说明各模板需要的变量，方便 `data_builder.py` 传参。

### 7.3 prompt_loader.py

```python
class PromptLoader:
    def __init__(self, prompts_dir: str): ...
    
    def load(self, name: str) -> dict:
        """加载 prompts/{name}.yaml → {system, user}"""
    
    def render(self, name: str, **kwargs) -> tuple[str, str]:
        """加载 + Jinja2 渲染 system 和 user"""
    
    def list(self) -> list[str]:
        """列出所有可用 prompt 名称"""
```

---

## 8. LLM 调用层 (generator/llm_client.py)

```python
class LLMClient:
    def __init__(self, config: dict): ...
    
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """
        调用 LLM API，返回生成的文本。
        支持 openai / azure / custom endpoint。
        - 重试机制: 最多3次
        - 超时: 30秒
        - 日志记录每次调用的 token 用量
        """
```

---

## 9. 报告拼装层 (reporter/build_report.py)

```python
def build_report(
    raw: RawMatchData,
    computed: ComputedData,        # 所有计算结果的汇总
    ai_texts: dict,                # {module_key: generated_text}
    image_paths: dict,             # {module_key: path}
    output_dir: str,
) -> str:
    """
    组装最终 Markdown 报告，返回 report.md 路径。
    
    报告模板结构:
    1. 封面卡片 (标题 + 结论)
    2. 核心数据面板 (表格 + 图表)
    3. 比赛走势解读 (动量图 + 文字)
    4. 战术兑现度分析 (传球网络图 + 文字)
    5. 三类球员点评 (射门图/雷达图 + 文字)
    6. 换人效果 (对比图 + 文字)
    7. 如果重踢100次 (xG分布图 + 文字)
    """
```

### 9.1 报告 Markdown 模板结构

```markdown
# {{ emoji_home }} {{ home_team }} {{ home_goals }}-{{ away_goals }} {{ away_team }} {{ emoji_away }}

> *{{ cover_conclusion }}*

---

## 📊 核心数据面板

|  | {{ home_team }} | {{ away_team }} |
|---|---|---|
| 控球率 | {{ home_poss }}% | {{ away_poss }}% |
| 预期进球 (xG) | {{ home_xg }} | {{ away_xg }} |
| 射门 (射正) | {{ home_shots }}({{ home_so }}) | {{ away_shots }}({{ away_so }}) |
| 绝佳机会 | {{ home_bc }} | {{ away_bc }} |

| 自创指标 | {{ home_team }} | {{ away_team }} | 解读 |
|---|---|---|---|
| 控制指数 CI | {{ home_ci }} | {{ away_ci }} | {{ ci_note }} |
| 威胁转化率 TCR | {{ home_tcr }} | {{ away_tcr }} | {{ tcr_note }} |
| 压迫效率 PE% | {{ home_pe }} | {{ away_pe }} | {{ pe_note }} |

> {{ contrast_insights }}

---

## ⚡ 比赛走势

{{ momentum_text }}

![动量曲线](images/02_momentum.png)

---

## ⚔️ 战术兑现度

{{ tactics_text }}

![传球网络 - {{ home_team }}](images/03a_pass_home.png)
![传球网络 - {{ away_team }}](images/03b_pass_away.png)

---

## 👤 球员点评

### 🏆 账面 MVP：{{ mvp_name }}

{{ mvp_text }}

![射门分布](images/01_shots.png)

### 🔍 隐性 MVP：{{ hidden_name }}

{{ hidden_text }}

![隐性MVP雷达](images/04b_radar_hidden.png)

### ⚠️ 黑洞球员：{{ black_name }}

{{ black_text }}

---

## 🔄 换人效果

{{ subs_text }}

![换人对比](images/05_subs.png)

---

## 🎲 如果重踢 100 次

{{ replay_text }}

![xG模拟](images/06_xg_hist.png)

---

*报告由 AI 足球分析员自动生成 | 数据来源：API-Football*
```

---

## 10. 入口脚本 (run.py)

```python
#!/usr/bin/env python3
"""
AI 足球分析员 - 比赛报告生成工具

用法:
    python run.py --match 1234567              # 指定比赛ID
    python run.py --match 1234567 --dry-run     # 仅采集数据，不调LLM
    python run.py --league 1 --date 2026-06-12  # 生成当天所有比赛报告
"""

import argparse
import sys
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="AI 足球比赛分析报告生成")
    parser.add_argument("--match", type=int, help="比赛 ID (fixture id)")
    parser.add_argument("--league", type=int, help="联赛 ID (默认: 1=世界杯)")
    parser.add_argument("--date", type=str, help="日期 YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true", help="仅采集数据")
    parser.add_argument("--no-images", action="store_true", help="跳过图表生成")
    args = parser.parse_args()
    
    # 1. 加载配置
    config = load_config("config.yaml")
    
    # 2. 如果指定 --league + --date，先查询该日所有比赛
    if args.league and args.date:
        client = APIFootballClient(config["api_football"])
        fixtures = client.get_fixtures_by_date(args.league, args.date)
        match_ids = [f["fixture"]["id"] for f in fixtures]
    elif args.match:
        match_ids = [args.match]
    else:
        parser.error("请指定 --match 或 (--league + --date)")
    
    # 3. 逐个比赛处理
    for match_id in match_ids:
        print(f"\n{'='*60}")
        print(f"处理比赛 #{match_id}...")
        
        # 3a. 数据采集
        raw = fetch_all(match_id, config["api_football"])
        
        # 3b. 指标计算
        computed = compute_all(raw)
        
        if args.dry_run:
            print(f"Dry-run 完成，数据已保存至 data/raw/{match_id}/")
            continue
        
        # 3c. 组装 Prompt + 调用 LLM
        ai_texts = generate_all_texts(raw, computed, config["llm"])
        
        # 3d. 生成图表 (可选)
        if not args.no_images:
            images = generate_all_visuals(raw, computed, config["visual"])
        else:
            images = {}
        
        # 3e. 拼装报告
        report_dir = build_report(raw, computed, ai_texts, images)
        print(f"报告已生成: {report_dir}/report.md")
    
    print(f"\n完成！共处理 {len(match_ids)} 场比赛。")

if __name__ == "__main__":
    main()
```

---

## 11. 完整数据流水线示意

```
run.py 入口
    │
    ▼
┌─────────────────────────────────────────────┐
│ 1. config.yaml 加载                         │
│    + 环境变量替换 ${...}                     │
└──────────────┬──────────────────────────────┘
               ▼
┌─────────────────────────────────────────────┐
│ 2. 数据采集 (collector)                     │
│    API-Football × 5 端点                     │
│    → RawMatchData                           │
│    → 原始 JSON 存 data/raw/{id}/            │
└──────────────┬──────────────────────────────┘
               ▼
┌─────────────────────────────────────────────┐
│ 3. 数据计算 (engine)                        │
│    ├── metrics.compute_control_index()       │
│    ├── metrics.compute_threat_conversion()   │
│    ├── metrics.compute_pressing_efficiency() │
│    ├── metrics.compute_momentum()            │
│    ├── simulator.compute_luck_deviation()    │
│    └── ratings.classify_players()           │
│    → ComputedData                           │
│    → 计算结果存 data/computed/{id}.json     │
└──────────────┬──────────────────────────────┘
               ▼
┌─────────────────────────────────────────────┐
│ 4. 数据→Prompt 组装 (composer)             │
│    为每个模块拼装 Jinja2 变量，渲染 prompt    │
│    → 9 组 (system, user) prompt 文本        │
└──────────────┬──────────────────────────────┘
               ▼
┌─────────────────────────────────────────────┐
│ 5. AI 文本生成 (generator)                  │
│    LLM API × 9 次调用 (可并行)               │
│    → dict[module_name, generated_text]      │
└──────────────┬──────────────────────────────┘
               ▼
┌─────────────────────────────────────────────┐
│ 6. 图表生成 (visualizer)                    │
│    mplsoccer + matplotlib × 7 张图           │
│    → output/{dir}/images/*.png              │
└──────────────┬──────────────────────────────┘
               ▼
┌─────────────────────────────────────────────┐
│ 7. 报告拼装 (reporter)                      │
│    Jinja2 模板 + Markdown                   │
│    → output/{dir}/report.md                 │
│    → output/{dir}/report.html (可选)        │
│    → output/{dir}/copy_paste.txt (可选)     │
└─────────────────────────────────────────────┘
```

---

## 12. 实施的建议顺序

| 阶段 | 内容 | 产出物 |
|---|---|---|
| **Phase 1** | 项目骨架 + API 客户端 | `src/collector/`, `config.yaml`, 能成功调 API 获取数据 |
| **Phase 2** | 数据引擎 | `src/engine/`, 能打印出 CI/TCR/PE/LDI 等指标 |
| **Phase 3** | Prompt 模板 + LLM 调用 | `prompts/*.yaml`, `src/composer/`, `src/generator/`, 能生成文字 |
| **Phase 4** | mplsoccer 可视化 | `src/visualizer/`, 能生成所有 PNG 图表 |
| **Phase 5** | 报告拼装 | `src/reporter/`, `run.py`, 端到端跑通 |
| **Phase 6** | 打磨 + 真实比赛测试 | 用已完成的世界杯比赛数据校准 |

---

## 13. 关键风险与对策

| 风险 | 应对 |
|---|---|
| API-Football 的射门坐标(x,y)不可用 | 射门图降级为射门位置「区域示意」（禁区内/外区分） |
| API-Football 不提供传球网络数据 | 使用"位置近似法"，基于阵型推算传球网络 |
| LLM 生成质量不稳定 | Prompt 模板独立管理，提供参数可快速调试 |
| 世界杯赛程紧凑，API 限流 | 对 API 响应做本地缓存，单场数据只拉一次 |
| mplsoccer 与 matplotlib 版本兼容 | 锁定依赖版本号 |

---

## 14. 附录：自创指标速查卡

| 指标 | 公式（核心） | 范围 | 数据源 |
|---|---|---|---|
| **CI** 控制指数 | 0.35×控球 + 0.25×传球 + 0.25×区域 + 0.15×回收 | 0-100 (两队之和=100) | Possession%, Pass%, Shots insidebox, Corners, Ball Recoveries |
| **TCR** 威胁转化率 | 100×(xG+0.3×绝佳机会)/(射门+0.3×角球) | 通常 2-35 | Expected Goals, Big Chances, Total Shots, Corners |
| **PE%** 压迫效率 | 100×(回收/(犯规+1)) / 双方之和 | 0-100 | Ball Recoveries, Fouls Committed |
| **LDI** 运气偏离 | P(实际比分)/P(最可能比分) | 0-1+ | xG + 蒙特卡洛模拟 |
