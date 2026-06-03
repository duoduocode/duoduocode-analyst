# SportMonks 套餐升级前后对比

> 时间：2026-06-04 | 对比对象：升级前 vs 升级后，均以 fixture 接口 + `statistics;lineups.details;participants;scores` includes 采集

---

## 一、球队级统计对比

| type_id | 指标名称 | 升级前 | 升级后 | PSG值 | Arsenal值 |
|--------:|---------|:---:|:---:|------:|------:|
| 34 | 角球 (Corner Kicks) | ✅ | ✅ | 11 | 3 |
| 41 | 射偏 (Shots off Goal) | ✅ | ✅ | 17 | 6 |
| 42 | 总射门 (Total Shots) | ✅ | ✅ | 21 | 7 |
| 43 | 进攻 (Attacks) | ✅ | ✅ | 159 | 98 |
| 44 | 危险进攻 (Dangerous Attacks) | ✅ | ✅ | 101 | 36 |
| 45 | 控球率 % (Ball Possession) | ✅ | ✅ | 75 | 25 |
| 46 | 安全回传 (Ball Safe) | — | 🆕 | 98 | 89 |
| 47 | 点球 (Penalties) | ✅ | ✅ | 1 | 0 |
| 49 | 禁区内射门 (Shots Inside Box) | ✅ | ✅ | 12 | 5 |
| 50 | 禁区外射门 (Shots Outside Box) | ✅ | ✅ | 9 | 2 |
| 51 | 越位 (Offsides) | ✅ | ✅ | 0 | 3 |
| 52 | 进球 (Goals) | — | 🆕 | 1 | 1 |
| 53 | 球门球 (Goal Kicks) | ✅ | ✅ | 4 | 14 |
| 54 | 射门尝试 (Goal Attempts) | — | 🆕 | 15 | 2 |
| 55 | 任意球 (Free Kicks) | ✅ | ✅ | 19 | 11 |
| 56 | 犯规 (Fouls) | ✅ | ✅ | 11 | 17 |
| 57 | 扑救 (Goalkeeper Saves) | ✅ | ✅ | 0 | 3 |
| 58 | 被封堵射门 (Blocked Shots) | ✅ | ✅ | 5 | 5 |
| 59 | 换人次数 (Substitutions) | — | 🆕 | 5 | 6 |
| 60 | 界外球 (Throw-ins) | ✅ | ✅ | 21 | 24 |
| 62 | 长传 (Long Balls) | ✅ | ✅ | 47 | 64 |
| 64 | 中框 (Hit Woodwork) | ✅ | ✅ | 1 | 0 |
| 65 | 成功头球 (Successful Headers) | — | 🆕 | 21 | 15 |
| 78 | 抢断 (Tackles) | ✅ | ✅ | 11 | 18 |
| 79 | 助攻 (Assists) | — | 🆕 | 0 | 1 |
| 80 | 传球总次数 (Total Passes) | ✅ | ✅ | 889 | 285 |
| 81 | 成功传球 (Successful Passes) | — | 🆕 | 809 | 196 |
| 82 | 传球成功率 % (Passes %) | ✅ | ✅ | 91 | 69 |
| 84 | 黄牌 (Yellow Cards) | ✅ | ✅ | 2 | 4 |
| 86 | 射正 (Shots on Goal) | ✅ | ✅ | 4 | 1 |
| 87 | 伤病 (Injuries) | — | 🆕 | 1 | 1 |
| 98 | 传中总次数 (Crosses) | ✅ | ✅ | 34 | 14 |
| 99 | 精准传中 (Accurate Crosses) | — | 🆕 | 5 | 2 |
| 100 | 拦截 (Interceptions) | ✅ | ✅ | 8 | 7 |
| 106 | 赢得对抗 (Duels Won) | — | 🆕 | 57 | 48 |
| 108 | 尝试过人 (Dribble Attempts) | — | 🆕 | 19 | 9 |
| 109 | 成功过人 (Successful Dribbles) | — | 🆕 | 9 | 4 |
| 117 | 关键传球 (Key Passes) | — | 🆕 | 15 | 7 |
| 580 | 创造绝佳机会 (Big Chances Created) | ✅ | ✅ | 3 | 1 |
| 581 | 错失绝佳机会 (Big Chances Missed) | — | 🆕 | 2 | 0 |

**球队级汇总：27 项 → 40 项（净增 13 项）**

---

## 二、球员级统计对比

### 原有字段（升级前后均有）

| type_id | 字段名 | 说明 |
|--------:|--------|------|
| 118 | rating | 比赛评分 |
| 119 | minutes_played | 出场时间 |
| 52 | goals | 进球 |
| 79 | assists | 助攻 |
| 42 | shots_total | 总射门 |
| 86 | shots_on | 射正 |
| 80 | passes_total | 传球次数 |
| 117 | passes_key | 关键传球 |
| 1584 | passes_accuracy | 传球成功率% |
| 78 | tackles_total | 抢断 |
| 100 | tackles_interceptions | 拦截 |
| 105 | duels_total | 总对抗 |
| 106 | duels_won | 赢得对抗 |
| 108 | dribbles_attempts | 尝试过人 |
| 109 | dribbles_success | 成功过人 |
| 56 | fouls_committed | 犯规 |
| 96 | fouls_drawn | 赢得犯规 |
| 83 | redcards | 红牌 |
| 84 | yellowcards | 黄牌 |
| 98 | crosses | 传中 |
| 57 | saves | 扑救 |
| 47 | penalties | 点球 |

### 新增字段（套餐升级后）

| type_id | 字段名 | 说明 | PSG 汇总 | Arsenal 汇总 |
|--------:|--------|------|------:|------:|
| **5304** | **xg** | **期望进球 (Expected Goals)** | **2.1677** | **0.4265** |
| **5305** | **xgot** | **射正期望进球 (xG on Target)** | **1.8849** | **0.5758** |
| **27271** | **ball_recoveries** | **球权回收 (Ball Recoveries)** | **56** | **47** |

**球员级汇总：22 项 → 25 项（净增 3 项高阶指标）**

---

## 三、统计总览

| 维度 | 升级前 | 升级后 | 增量 |
|------|:---:|:---:|:---:|
| 球队级统计 | 27 项 | **40 项** | +13 |
| 球员级统计 | 22 项 | **25 项** | +3 (含 xG) |
| 合计 | 49 项 | **65 项** | **+16** |

---

## 四、关键能力变化

| 能力 | 升级前 | 升级后 |
|------|:---:|:---:|
| 传球分析 (总次数+成功率+精准) | 基础 | ✅ 完整 |
| 传中分析 (总次数+精准率) | 基础 | ✅ 完整 |
| 对抗分析 (赢得对抗) | ❌ | ✅ |
| 盘带分析 (尝试+成功) | ❌ | ✅ |
| 头球分析 (成功头球) | ❌ | ✅ |
| 关键传球 | ❌ | ✅ |
| 绝佳机会 (创造+错失) | 部分 | ✅ 完整 |
| 换人/伤病统计 | ❌ | ✅ |
| 安全回传 (防守控球) | ❌ | ✅ |
| **xG 期望进球** | ❌ | ✅ (球员级) |
| **xGOT 射正期望进球** | ❌ | ✅ (球员级) |
| **Ball Recoveries 球权回收** | ❌ | ✅ (球员级) |

---

## 五、仍需改进

| 问题 | 说明 |
|------|------|
| xG 无球队级 | xG(5304) 仅返回球员级，需在代码中汇总到球队 |
| 球权回收无球队级 | 同上，需从球员汇总 |
| type_id 1605/27264/27265 未知 | 球队级有 3 个未识别指标，含义待确认 |
| 球员级 15+ 个未知 type_id | 编号 111/114/115/571/584 等未在文档中定位 |
| Shot Map 无坐标 | SportMonks events 不返回射门坐标 (x,y) |

---

*基于 fixture 19683241 (PSG vs Arsenal) 实测数据生成*
