# SportMonks API 统计指标全集

> 基于 SportMonks Football API V3，以 PSG vs Arsenal (fixture 19683241) 实际返回数据验证。
> 
> 标记说明：✅ 当前已采集 | ⚠️ API 返回但代码未采集 | ❌ 当前套餐不返回

---

## 一、球队级统计 (Fixture Statistics) — 44 项

### 1.1 射门 (Shooting)

| type_id | 开发者名称 | 中文名 | 状态 |
|--------:|-----------|--------|:--:|
| 42 | SHOTS_TOTAL | 总射门 | ✅ |
| 86 | SHOTS_ON_TARGET | 射正 | ✅ |
| 41 | SHOTS_OFF_TARGET | 射偏 | ✅ |
| 58 | SHOTS_BLOCKED | 被封堵射门 | ✅ |
| 49 | SHOTS_INSIDEBOX | 禁区内射门 | ✅ |
| 50 | SHOTS_OUTSIDEBOX | 禁区外射门 | ✅ |
| 64 | HIT_WOODWORK | 中框（门柱/横梁） | ✅ |
| 54 | GOAL_ATTEMPTS | 射门尝试 | ✅ |
| 580 | BIG_CHANCES_CREATED | 创造绝佳机会 | ✅ |
| 581 | BIG_CHANCES_MISSED | 错失绝佳机会 | ⚠️ |
| 47 | PENALTIES | 点球 | ✅ |
| 52 | GOALS | 进球 | ✅ |

### 1.2 传球 (Passing)

| type_id | 开发者名称 | 中文名 | 状态 |
|--------:|-----------|--------|:--:|
| 80 | PASSES | 传球总次数 | ✅ |（用于汇总）
| 81 | SUCCESSFUL_PASSES | 成功传球 | ⚠️ |
| 82 | SUCCESSFUL_PASSES_PERCENTAGE | 传球成功率 % | ✅ |
| 116 | ACCURATE_PASSES | 准确传球次数 | ⚠️ |
| 117 | KEY_PASSES | 关键传球 | ⚠️ |
| 62 | LONG_PASSES | 长传 | ✅ |
| 63 | SHORT_PASSES | 短传 | ✅ |
| 98 | TOTAL_CROSSES | 传中总次数 | ✅ |
| 99 | ACCURATE_CROSSES | 精准传中 | ⚠️ |
| 124 | THROUGH_BALLS | 直塞球 | ⚠️ |
| 125 | THROUGH_BALLS_WON | 成功直塞球 | ⚠️ |

### 1.3 防守 (Defense)

| type_id | 开发者名称 | 中文名 | 状态 |
|--------:|-----------|--------|:--:|
| 78 | TACKLES | 抢断 | ✅ |
| 100 | INTERCEPTIONS | 拦截 | ✅ |
| 66 | SUCCESSFUL_INTERCEPTIONS | 成功拦截 | ⚠️ |
| 101 | CLEARANCES | 解围 | ⚠️ |
| 57 | SAVES | 扑救 | ✅ |
| 104 | SAVES_INSIDE_BOX | 禁区内扑救 | ⚠️ |
| 97 | BLOCKED_SHOTS | 封堵射门（球员） | ⚠️ |
| 46 | BALL_SAFE | 安全回传 | ⚠️ |
| 76 | GOALKEEPER_COME_OUTS | 门将出击 | ⚠️ |
| 77 | CHALLENGES | 身体对抗 | ⚠️ |

### 1.4 对抗与头球 (Duels & Headers)

| type_id | 开发者名称 | 中文名 | 状态 |
|--------:|-----------|--------|:--:|
| 105 | TOTAL_DUELS | 总对抗次数 | ⚠️ |
| 106 | DUELS_WON | 赢得对抗 | ⚠️ |
| 65 | SUCCESSFUL_HEADERS | 成功头球 | ⚠️ |
| 70 | HEADERS | 头球总数 | ⚠️ |

### 1.5 盘带 (Dribbles)

| type_id | 开发者名称 | 中文名 | 状态 |
|--------:|-----------|--------|:--:|
| 108 | DRIBBLE_ATTEMPTS | 尝试过人 | ⚠️ |
| 109 | SUCCESSFUL_DRIBBLES | 成功过人 | ⚠️ |

### 1.6 控球与空间 (Possession & Territory)

| type_id | 开发者名称 | 中文名 | 状态 |
|--------:|-----------|--------|:--:|
| 45 | BALL_POSSESSION | 控球率 % | ✅ |
| 43 | ATTACKS | 进攻次数 | ✅ |
| 44 | DANGEROUS_ATTACKS | 危险进攻 | ✅ |
| 34 | CORNERS | 角球 | ✅ |
| 51 | OFFSIDES | 越位 | ✅ |
| 53 | GOAL_KICKS | 球门球 | ✅ |
| 55 | FREE_KICKS | 任意球 | ✅ |
| 60 | THROWINS | 界外球 | ✅ |

### 1.7 纪律 (Discipline)

| type_id | 开发者名称 | 中文名 | 状态 |
|--------:|-----------|--------|:--:|
| 56 | FOULS | 犯规 | ✅ |
| 84 | YELLOWCARDS | 黄牌 | ✅ |
| 83 | REDCARDS | 红牌 | ✅ |
| 85 | YELLOWRED_CARDS | 两黄变红 | ✅ |

### 1.8 其他

| type_id | 开发者名称 | 中文名 | 状态 |
|--------:|-----------|--------|:--:|
| 59 | SUBSTITUTIONS | 换人次数 | ✅ |
| 79 | ASSISTS | 助攻 | ✅ |
| 87 | INJURIES | 伤病 | ✅ |
| 88 | GOALS_CONCEDED | 失球 | ⚠️ |
| 72 | FIRST_SUBSTITUTION | 第一次换人时间 | ⚠️ |
| 61 | BEATS | 被突破次数 | ⚠️ |

---

## 二、球员级统计 (Player Statistics) — 53 项

球员数据通过 `lineups.details` 获取，每次返回该球员在本场比赛中的各项统计。

### 2.1 基础

| type_id | 开发者名称 | 中文名 | 状态 | 示例值 |
|--------:|-----------|--------|:--:|--------|
| 40 | CAPTAIN | 是否队长 | ⚠️ | True/False |
| 118 | RATING | 比赛评分 | ✅ | 6.63 |
| 119 | MINUTES_PLAYED | 出场时间(分钟) | ✅ | 120 |
| 52 | GOALS | 进球 | ✅ | 1 |
| 79 | ASSISTS | 助攻 | ✅ | 1 |
| 88 | GOALS_CONCEDED | 失球 | ⚠️ | — |

### 2.2 射门

| type_id | 开发者名称 | 中文名 | 状态 |
|--------:|-----------|--------|:--:|
| 42 | SHOTS_TOTAL | 总射门 | ✅ |
| 86 | SHOTS_ON_TARGET | 射正 | ✅ |
| 41 | SHOTS_OFF_TARGET | 射偏 | ⚠️ |
| 58 | SHOTS_BLOCKED | 被封堵射门 | ⚠️ |
| 64 | HIT_WOODWORK | 中框 | ⚠️ |
| 97 | BLOCKED_SHOTS | 封堵对方射门 | ⚠️ |
| 47 | PENALTIES | 点球（主罚） | ⚠️ |

### 2.3 传球

| type_id | 开发者名称 | 中文名 | 状态 |
|--------:|-----------|--------|:--:|
| 80 | PASSES | 传球次数 | ✅ |
| 116 | ACCURATE_PASSES | 准确传球次数 | ⚠️ |
| 1584 | PASSES_ACCURACY | 传球成功率 % | ⚠️ |
| 117 | KEY_PASSES | 关键传球 | ✅ |
| 98 | TOTAL_CROSSES | 传中总次数 | ✅ |
| 99 | ACCURATE_CROSSES | 精准传中 | ⚠️ |
| 122 | LONG_BALLS | 长传 | ⚠️ |
| 123 | LONG_BALLS_WON | 成功长传 | ⚠️ |

### 2.4 防守

| type_id | 开发者名称 | 中文名 | 状态 |
|--------:|-----------|--------|:--:|
| 78 | TACKLES | 抢断 | ✅ |
| 100 | INTERCEPTIONS | 拦截 | ✅ |
| 101 | CLEARANCES | 解围 | ⚠️ |
| 27271 | BALL_RECOVERIES | **球权回收** | ⚠️ |
| 57 | SAVES | 扑救(门将) | ✅ |
| 104 | SAVES_INSIDE_BOX | 禁区内扑救 | ⚠️ |
| 103 | PUNCHES | 门将击球 | ⚠️ |

### 2.5 对抗

| type_id | 开发者名称 | 中文名 | 状态 |
|--------:|-----------|--------|:--:|
| 105 | TOTAL_DUELS | 总对抗 | ✅ |
| 106 | DUELS_WON | 赢得对抗 | ✅ |
| 107 | AERIALS_WON | 赢得空中对抗 | ⚠️ |
| 110 | DRIBBLED_PAST | 被过人 | ⚠️ |

### 2.6 盘带

| type_id | 开发者名称 | 中文名 | 状态 |
|--------:|-----------|--------|:--:|
| 108 | DRIBBLE_ATTEMPTS | 尝试过人 | ✅ |
| 109 | SUCCESSFUL_DRIBBLES | 成功过人 | ✅ |
| 94 | DISPOSSESSED | 被抢断 | ⚠️ |

### 2.7 犯规与纪律

| type_id | 开发者名称 | 中文名 | 状态 |
|--------:|-----------|--------|:--:|
| 56 | FOULS | 犯规 | ✅ |
| 96 | FOULS_DRAWN | 赢得犯规 | ✅ |
| 84 | YELLOWCARDS | 黄牌 | ✅ |
| 83 | REDCARDS | 红牌 | ⚠️ |

### 2.8 越位

| type_id | 开发者名称 | 中文名 | 状态 |
|--------:|-----------|--------|:--:|
| 51 | OFFSIDES | 越位 | ⚠️ |
| 91 | LAST_OFFSIDE | 最后一次越位时间 | ⚠️ |
| 92 | FIRST_OFFSIDE | 首次越位时间 | ⚠️ |
| 95 | OFFSIDES_PROVOKED | 制造对方越位 | ⚠️ |

### 2.9 高阶 xG 数据

| type_id | 开发者名称 | 中文名 | 说明 | 状态 |
|--------:|-----------|--------|------|:--:|
| 5304 | XG | 期望进球 | 每脚射门进球概率之和 | ⚠️ |
| 5305 | XGOT | 射正期望进球 | 射正情况下的期望进球 | ⚠️ |
| 9685 | XG_OVER_UNDER | 射门超/低预期 | 实际进球 - xG | ⚠️ |

### 2.10 其他进阶指标（实测返回但未完全识别）

| type_id | 可能的含义 |
|--------:|-----------|
| 114 | — |
| 115 | — |
| 571 | — |
| 584 | — |
| 1490 | — |
| 1491 | — |
| 1533 | — |
| 1535 | — |
| 9706 | — |
| 27266–27276 | 进阶细分防守/传球指标（如三区传接） |
| 48997 | — |
| 117172 | — |

---

## 三、事件类型 (Match Events)

SportMonks 事件使用 `type_id` (整数) 标识。

| type_id | 事件名 | 编码后的 event_type | detail |
|--------:|--------|:---:|--------|
| 10 | 点球判罚 (Penalty Awarded) | Info | penalty_awarded |
| 14 | 进球 (Goal - Open Play) | Goal | goal |
| 15 | 射门尝试 (Shot Attempt) | Shot | shot_attempt |
| 16 | 点球进球 (Penalty Goal) | Goal | goal_penalty |
| 17 | 点球罚失 (Missed Penalty) | missed_penalty | missed_penalty |
| 18 | 换人 (Substitution) | subst | substitution |
| 19 | 黄牌 (Yellow Card) | Card | yellowcard |
| 20 | 两黄变红 (2nd Yellow → Red) | Card | yellowredcard |
| 21 | 直红 (Red Card) | Card | redcard |
| 22 | VAR 介入 | VAR | var |
| 23 | 乌龙球 (Own Goal) | Goal | owngoal |
| 24 | 点球大战进球 | Goal | pen_shootout_goal |
| 25 | 点球大战罚失 | Goal | pen_shootout_miss |
| 55 | VAR (备选) | VAR | var |

---

## 四、采集策略说明

### 当前采集流程
```
单次 API 请求: GET /fixtures/{id}?include=statistics;lineups.details;events;participants;scores
                  │
                  ├─ statistics[]  →  type_id 转换 → home_stats / away_stats (dict)
                  ├─ lineups[]     →  details[] 解析 → home_players / away_players (PlayerStats)
                  ├─ events[]      →  type_id 转换 → events (MatchEvent)
                  ├─ participants[]→  TeamInfo (id, name, logo_url)
                  └─ scores[]      →  ScoreInfo
```

### 从球员汇总球队统计
部分指标（xG、Ball Recoveries 等）只在球员级别返回，可通过汇总获得球队值：

```python
# 示例：从球员汇总球队 xG
home_xg = sum(p.xg or 0 for p in raw.home_players)
away_xg = sum(p.xg or 0 for p in raw.away_players)
```

---

## 五、与 API-Football 对比

| 维度 | API-Football | SportMonks |
|------|:---:|:---:|
| 请求次数 | 5 次并行 | **1 次** |
| 球队统计项 | ~20 | 44 |
| 球员统计项 | ~15 | 53+ |
| xG (球队) | 部分有 | 球员级有 |
| 球权回收 | ❌ | ✅(球员级) |
| 绝佳机会 | ❌ | ✅ |
| 中框/长传/传中 | ❌ | ✅ |
| 球员头像 | player.photo | image_path |
| 队徽 | team.logo | participant.image_path |

---

*生成时间: 2026-06-04 | 数据来源: SportMonks V3 API + 官方文档*
