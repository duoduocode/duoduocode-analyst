# SportMonks API 统计指标全集

> 基于 SportMonks Football API V3，以 PSG vs Arsenal (fixture 19683241) 实际返回数据验证。
> 
> 标记说明：✅ 已采集并存入数据模型 | 🔶 PLAYER_STAT_MAP 已映射，但 PlayerStats dataclass 缺少对应字段 | ⚠️ API 返回但代码未采集 | ❌ 当前套餐不返回

---

## 一、球队级统计 (Fixture Statistics) — 44 项

### 1.1 射门 (Shooting)

| type_id | 开发者名称 | 中文名 | 状态 | 用途 |
|--------:|-----------|--------|:--:|------|
| 42 | SHOTS_TOTAL | 总射门 | ✅ | TCR 分母 |
| 86 | SHOTS_ON_TARGET | 射正 | ✅ | 动量计算 |
| 41 | SHOTS_OFF_TARGET | 射偏 | ✅ | — |
| 58 | SHOTS_BLOCKED | 被封堵射门 | ✅ | — |
| 49 | SHOTS_INSIDEBOX | 禁区内射门 | ✅ | CI 区域维度 |
| 50 | SHOTS_OUTSIDEBOX | 禁区外射门 | ✅ | — |
| 64 | HIT_WOODWORK | 中框（门柱/横梁） | ✅ | — |
| 54 | GOAL_ATTEMPTS | 射门尝试 | ✅ | — |
| 580 | BIG_CHANCES_CREATED | 创造绝佳机会 | ✅ | TCR 分子 |
| 581 | BIG_CHANCES_MISSED | 错失绝佳机会 | ✅ | — |
| 47 | PENALTIES | 点球 | ✅ | — |
| 52 | GOALS | 进球 | ✅ | 比分标签 |

### 1.2 传球 (Passing)

| type_id | 开发者名称 | 中文名 | 状态 | 用途 |
|--------:|-----------|--------|:--:|------|
| 80 | PASSES | 传球总次数 | ✅ | — |
| 81 | SUCCESSFUL_PASSES | 成功传球 | ✅ | — |
| 82 | SUCCESSFUL_PASSES_PERCENTAGE | 传球成功率 % | ✅ | CI 传球维度 |
| 116 | ACCURATE_PASSES | 准确传球次数 | ⚠️ | API 返回但代码未采集 |
| 117 | KEY_PASSES | 关键传球 | ✅ | — |
| 62 | LONG_PASSES | 长传 | ✅ | 长传比 |
| 63 | SHORT_PASSES | 短传 | ✅ | — |
| 98 | TOTAL_CROSSES | 传中总次数 | ✅ | — |
| 99 | ACCURATE_CROSSES | 精准传中 | ✅ | — |
| 124 | THROUGH_BALLS | 直塞球 | ⚠️ | API 返回但代码未采集 |
| 125 | THROUGH_BALLS_WON | 成功直塞球 | ⚠️ | API 返回但代码未采集 |

### 1.3 防守 (Defense)

| type_id | 开发者名称 | 中文名 | 状态 | 用途 |
|--------:|-----------|--------|:--:|------|
| 78 | TACKLES | 抢断 | ✅ | — |
| 100 | INTERCEPTIONS | 拦截 | ✅ | — |
| 66 | SUCCESSFUL_INTERCEPTIONS | 成功拦截 | ⚠️ | API 返回但代码未采集 |
| 101 | CLEARANCES | 解围 | ⚠️ | API 返回但代码未采集 |
| 57 | SAVES | 扑救 | ✅ | — |
| 104 | SAVES_INSIDE_BOX | 禁区内扑救 | ⚠️ | API 返回但代码未采集 |
| 97 | BLOCKED_SHOTS | 封堵射门（球员） | ⚠️ | API 返回但代码未采集 |
| 46 | BALL_SAFE | 安全回传 | ✅ | — |
| 76 | GOALKEEPER_COME_OUTS | 门将出击 | ⚠️ | API 返回但代码未采集 |
| 77 | CHALLENGES | 身体对抗 | ⚠️ | API 返回但代码未采集 |

### 1.4 对抗与头球 (Duels & Headers)

| type_id | 开发者名称 | 中文名 | 状态 | 用途 |
|--------:|-----------|--------|:--:|------|
| 105 | TOTAL_DUELS | 总对抗次数 | ⚠️ | API 返回但代码未采集 |
| 106 | DUELS_WON | 赢得对抗 | ✅ | — |
| 65 | SUCCESSFUL_HEADERS | 成功头球 | ✅ | — |
| 70 | HEADERS | 头球总数 | ⚠️ | API 返回但代码未采集 |

### 1.5 盘带 (Dribbles)

| type_id | 开发者名称 | 中文名 | 状态 | 用途 |
|--------:|-----------|--------|:--:|------|
| 108 | DRIBBLE_ATTEMPTS | 尝试过人 | ✅ | — |
| 109 | SUCCESSFUL_DRIBBLES | 成功过人 | ✅ | — |

### 1.6 控球与空间 (Possession & Territory)

| type_id | 开发者名称 | 中文名 | 状态 | 用途 |
|--------:|-----------|--------|:--:|------|
| 45 | BALL_POSSESSION | 控球率 % | ✅ | CI 控球维度 |
| 43 | ATTACKS | 进攻次数 | ✅ | — |
| 44 | DANGEROUS_ATTACKS | 危险进攻 | ✅ | — |
| 34 | CORNERS | 角球 | ✅ | CI 区域维度 / TCR 分母 |
| 51 | OFFSIDES | 越位 | ✅ | — |
| 53 | GOAL_KICKS | 球门球 | ✅ | — |
| 55 | FREE_KICKS | 任意球 | ✅ | — |
| 60 | THROWINS | 界外球 | ✅ | — |

### 1.7 纪律 (Discipline)

| type_id | 开发者名称 | 中文名 | 状态 |
|--------:|-----------|--------|:--:|
| 56 | FOULS | 犯规 | ✅ |
| 84 | YELLOWCARDS | 黄牌 | ✅ |
| 83 | REDCARDS | 红牌 | ✅ |
| 85 | YELLOWRED_CARDS | 两黄变红 | ✅ |

### 1.8 其他

| type_id | 开发者名称 | 中文名 | 状态 | 用途 |
|--------:|-----------|--------|:--:|------|
| 59 | SUBSTITUTIONS | 换人次数 | ✅ | — |
| 79 | ASSISTS | 助攻 | ✅ | — |
| 87 | INJURIES | 伤病 | ✅ | — |
| 88 | GOALS_CONCEDED | 球队失球(在场时) | ✅ | 非门将专属,所有场上球员均有值=在场期间球队丢球数 |
| 72 | FIRST_SUBSTITUTION | 第一次换人时间 | ⚠️ | API 返回但代码未采集 |
| 61 | BEATS | 被突破次数 | ⚠️ | API 返回但代码未采集 |

---

## 二、球员级统计 (Player Statistics) — 66 项全部识别

球员数据通过 `lineups.details` 获取，每次返回该球员在本场比赛中的各项统计。
基于 fixture 19683241 实测 + `lineups.details.type` 嵌套获取官方名称，**66 项 type_id 全部识别，无一未知**。

> 标记说明：✅ 已采集并存入 PlayerStats | 🔶 PLAYER_STAT_MAP 已映射但 PlayerStats 无对应字段 | ⚠️ API 返回但代码未采集

### 2.1 基础信息 (Basic Info)

| type_id | 开发者名称 | 中文名 | 状态 | 备注 |
|--------:|-----------|--------|:--:|------|
| 40 | CAPTAIN | 是否队长 | ⚠️ | 布尔值 True/False |
| 118 | RATING | 比赛评分 | ✅ | 浮点数，如 6.63 |
| 119 | MINUTES_PLAYED | 出场时间(分钟) | ✅ | 如 120 |
| 117172 | CUMULATIVE_MINUTES_PLAYED | 赛季累计出场时间 | ⚠️ | 如 136 |
| 1490 | MAN_OF_MATCH | 全场最佳 | ⚠️ | 布尔值，本场 1 人 |
| 120 | TOUCHES | 触球次数 | ⚠️ | 如 51 |

### 2.2 射门 (Shooting)

| type_id | 开发者名称 | 中文名 | 状态 | 备注 |
|--------:|-----------|--------|:--:|------|
| 42 | SHOTS_TOTAL | 总射门 | ✅ | `shots_total` |
| 86 | SHOTS_ON_TARGET | 射正 | ✅ | `shots_on` |
| 41 | SHOTS_OFF_TARGET | 射偏 | ⚠️ | 代码未采集 |
| 58 | SHOTS_BLOCKED | 被封堵射门 | ⚠️ | 代码未采集 |
| 64 | HIT_WOODWORK | 中框（门柱/横梁） | ⚠️ | 代码未采集 |

### 2.3 进球与助攻 (Goals & Assists)

| type_id | 开发者名称 | 中文名 | 状态 | 备注 |
|--------:|-----------|--------|:--:|------|
| 52 | GOALS | 进球 | ✅ | `goals` |
| 79 | ASSISTS | 助攻 | ✅ | `assists` |
| 111 | PENALTIES_SCORED | 点球进球 | ⚠️ | 代码未采集 |
| 580 | BIG_CHANCES_CREATED | 创造绝佳机会 | ⚠️ | 代码未采集 |
| 581 | BIG_CHANCES_MISSED | 错失绝佳机会 | ⚠️ | 代码未采集 |
| 9706 | CHANCES_CREATED | 创造机会 | ⚠️ | 代码未采集 |

### 2.4 传球 (Passing)

| type_id | 开发者名称 | 中文名 | 状态 | 备注 |
|--------:|-----------|--------|:--:|------|
| 80 | PASSES | 传球总次数 | ✅ | `passes_total` |
| 116 | ACCURATE_PASSES | 准确传球次数 | ⚠️ | 代码未采集 |
| 1584 | ACCURATE_PASSES_PERCENTAGE | 传球成功率 % | ✅ | `passes_accuracy` |
| 117 | KEY_PASSES | 关键传球 | ✅ | `passes_key` |
| 98 | TOTAL_CROSSES | 传中总次数 | ✅ | `crosses` |
| 99 | ACCURATE_CROSSES | 精准传中 | ⚠️ | 代码未采集 |
| 1533 | SUCCESSFUL_CROSSES_PERCENTAGE | 传中成功率 % | ⚠️ | 代码未采集 |
| 122 | LONG_BALLS | 长传次数 | ⚠️ | 代码未采集 |
| 123 | LONG_BALLS_WON | 成功长传 | ⚠️ | 代码未采集 |
| 27270 | LONG_BALLS_WON_PERCENTAGE | 长传成功率 % | ⚠️ | 代码未采集 |
| 27269 | PASSES_IN_FINAL_THIRD | **进攻三区传球** | ⚠️ | 代码未采集 |
| 27272 | BACKWARD_PASSES | 回传次数 | ⚠️ | 代码未采集 |

### 2.5 防守 (Defense)

| type_id | 开发者名称 | 中文名 | 状态 | 备注 |
|--------:|-----------|--------|:--:|------|
| 78 | TACKLES | 抢断 | ✅ | `tackles_total` |
| 27267 | TACKLES_WON | 成功抢断 | ⚠️ | 代码未采集 |
| 27268 | TACKLES_WON_PERCENTAGE | 抢断成功率 % | ⚠️ | 代码未采集 |
| 100 | INTERCEPTIONS | 拦截 | ✅ | `tackles_interceptions` |
| 101 | CLEARANCES | 解围 | ⚠️ | 代码未采集 |
| 27271 | BALL_RECOVERY | **球权回收** | ✅ | `ball_recoveries`，PE 核心 |
| 97 | BLOCKED_SHOTS | 封堵射门 | ⚠️ | 代码未采集 |
| 110 | DRIBBLED_PAST | 被过人 | ⚠️ | 代码未采集 |
| 94 | DISPOSSESSED | 被抢断 | ⚠️ | 代码未采集 |
| 27273 | POSSESSION_LOST | 丢失球权 | ⚠️ | 代码未采集 |

### 2.6 对抗 (Duels)

| type_id | 开发者名称 | 中文名 | 状态 | 备注 |
|--------:|-----------|--------|:--:|------|
| 105 | TOTAL_DUELS | 总对抗 | ✅ | `duels_total` |
| 106 | DUELS_WON | 赢得对抗 | ✅ | `duels_won` |
| 1491 | DUELS_LOST | 输掉对抗 | ⚠️ | 代码未采集 |
| 27276 | DUELS_WON_PERCENTAGE | 对抗成功率 % | ⚠️ | 代码未采集 |
| 107 | AERIALS_WON | 赢得空中对抗 | ⚠️ | 代码未采集 |
| 27274 | AERIALS | 空中对抗总次数 | ⚠️ | 代码未采集 |
| 27266 | AERIALS_LOST | 输掉空中对抗 | ⚠️ | 代码未采集 |
| 27275 | AERIALS_WON_PERCENTAGE | 空中对抗成功率 % | ⚠️ | 代码未采集 |

### 2.7 盘带 (Dribbling)

| type_id | 开发者名称 | 中文名 | 状态 | 备注 |
|--------:|-----------|--------|:--:|------|
| 108 | DRIBBLE_ATTEMPTS | 尝试过人 | ✅ | `dribbles_attempts` |
| 109 | SUCCESSFUL_DRIBBLES | 成功过人 | ✅ | `dribbles_success` |

### 2.8 犯规与纪律 (Fouls & Discipline)

| type_id | 开发者名称 | 中文名 | 状态 | 备注 |
|--------:|-----------|--------|:--:|------|
| 56 | FOULS | 犯规 | ✅ | `fouls_committed` |
| 96 | FOULS_DRAWN | 被犯规 | ✅ | `fouls_drawn` |
| 114 | PENALTIES_COMMITTED | 送点 | ⚠️ | 代码未采集 |
| 115 | PENALTIES_WON | 赢得点球 | ⚠️ | 代码未采集 |
| 84 | YELLOWCARDS | 黄牌 | 🔶 | 映射存在但 PlayerStats 无字段 |
| 83 | REDCARDS | 红牌 | 🔶 | 映射存在但 PlayerStats 无字段（本场未出现） |

### 2.9 越位 (Offside)

| type_id | 开发者名称 | 中文名 | 状态 |
|--------:|-----------|--------|:--:|
| 51 | OFFSIDES | 越位次数 | ⚠️ |

### 2.10 门将 (Goalkeeper)

| type_id | 开发者名称 | 中文名 | 状态 | 备注 |
|--------:|-----------|--------|:--:|------|
| 57 | SAVES | 扑救 | ✅ | `saves` |
| 104 | SAVES_INSIDE_BOX | 禁区内扑救 | ⚠️ | 代码未采集 |
| 103 | PUNCHES | 门将击球 | ⚠️ | 代码未采集 |
| 88 | GOALS_CONCEDED | 球队失球(在场时) | ⚠️ | 代码未采集 |
| 1535 | GOALKEEPER_GOALS_CONCEDED | 门将失球 | ⚠️ | 代码未采集 |
| 584 | GOOD_HIGH_CLAIM | 成功摘高球 | ⚠️ | 代码未采集 |

### 2.11 失误 (Errors)

| type_id | 开发者名称 | 中文名 | 状态 | 备注 |
|--------:|-----------|--------|:--:|------|
| 571 | ERROR_LEAD_TO_GOAL | 导致丢球的失误 | ⚠️ | 代码未采集 |
| 48997 | ERROR_LEAD_TO_SHOT | 导致射门的失误 | ⚠️ | 代码未采集 |

### 2.12 高阶 xG 数据 (Expected Goals)

| type_id | 开发者名称 | 中文名 | 说明 | 状态 | 备注 |
|--------:|-----------|--------|------|:--:|------|
| 5304 | EXPECTED_GOALS | 期望进球 (xG) | 每脚射门 xG 之和 | ✅ | `xg`，TCR/LDI 核心输入 |
| 5305 | EXPECTED_GOALS_ON_TARGET | 射正期望进球 (xGOT) | 射正后的期望进球 | ✅ | `xgot` |
| 9685 | SHOOTING_PERFORMANCE | **射门表现 (SP)** | 实际进球 − xG，正值=超预期 | ⚠️ | 代码未采集 |

---

> **汇总**: PLAYER_STAT_MAP 当前映射了 25 项，实际 API 返回 66 项。尚有 **41 项** 球员指标已返回但代码未采集。新增指标重点包括：触球、长传/长传成功率、空中对抗成败、三区传球、丢失球权、失误统计等。

---

## 三、比赛事件 (Match Events)

SportMonks 事件使用 `type_id` (整数) 标识，基于 fixture 19683241 (PSG vs Arsenal，含加时+点球大战) 实测验证。

| type_id | 事件名 | event_type | detail | 备注 |
|--------:|--------|:---:|--------|------|
| 10 | 点球判罚 (Penalty Awarded) | Info | penalty_awarded | |
| 14 | 运动战进球 (Goal) | Goal | goal | `related_player_name` = 助攻者 |
| 15 | 射门尝试 (Shot Attempt) | Shot | shot_attempt | 非进球射门 |
| 16 | 点球进球 (Penalty Goal) | Goal | goal_penalty | |
| 17 | 点球罚失 (Missed Penalty) | Goal | missed_penalty | |
| 18 | 换人 (Substitution) | subst | substitution | `player_name`=换上, `related_player_name`=换下 |
| 19 | 黄牌 (Yellow Card) | Card | yellowcard | |
| 20 | 两黄变红 (2nd Yellow → Red) | Card | yellowredcard | |
| 21 | 直红 (Straight Red Card) | Card | redcard | |
| 22 | 点球大战罚失/被扑 | Goal | pen_shootout_miss | |
| 23 | 点球大战进球 | Goal | pen_shootout_goal | |
| 55 | VAR 介入 | VAR | var | |

---

## 四、比赛基本信息 (Match Info)

### 4.1 球队信息 (TeamInfo)

数据来源 `participants[]` 字段。

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `id` | int | SportMonks 球队 ID | 831 (PSG) |
| `name` | str | 球队名称 | "Paris Saint Germain" |
| `logo_url` | str | 队徽 URL | `image_path` 字段，如 `https://cdn.sportmonks.com/...` |
| `meta.location` | str | 主客场标识 | "home" / "away" |

### 4.2 比分信息 (ScoreInfo)

数据来源 `scores[]` 字段。SportMonks 为每个比赛阶段分别返回比分记录：

| description | 含义 | 对应 ScoreInfo 字段 |
|-------------|------|---------------------|
| `CURRENT` | 全场最终比分 | `home` / `away` |
| `HT` / `HALFTIME` | 半场比分 | `halftime_home` / `halftime_away` |
| `FT` | 常规时间比分 | `fulltime_home` / `fulltime_away` |
| `ET` | 加时赛比分 | `extratime_home` / `extratime_away` |
| `PEN` | 点球大战比分 | `penalty_home` / `penalty_away` |

### 4.3 比赛状态 (Status)

`state_id` 映射关系：

| state_id | 状态码 | 含义 |
|---------:|:------:|------|
| 1 | NS | 未开始 (Not Started) |
| 2 | LIVE | 进行中 |
| 3 | HT | 半场 (Halftime) |
| 4 | BT | 半场休息 (Break Time) |
| 5 | FT | 全场结束 (Full Time) |
| 6 | AET | 加时结束 (After Extra Time) |
| 7 | PEN | 点球大战 (Penalties) |
| 8 | PST | 推迟 (Postponed) |
| 9 | SUSP | 中断 (Suspended) |
| 10 | INT | 取消 (Interrupted) |

### 4.4 阵型信息 (LineupInfo)

数据来源 `lineups[]` 字段。

| 字段 | 类型 | 说明 |
|------|------|------|
| `formation` | str | 阵型，如 "4-3-3"、"4-4-2" |
| `players` | list[LineupPlayer] | 当前为空占位（传球网络图待完善） |

`lineups.details[]` 中 `type_id` 区分：
- `11` = 首发球员 (start)
- `12` = 替补球员 (substitute)

球员位置 `position_id` 映射：

| position_id | 位置 | 缩写 |
|------------:|------|:--:|
| 24 | Goalkeeper | G |
| 25 | Defender (full-back) | D |
| 26 | Defender (centre-back) | D |
| 27 | Midfielder | M |
| 28 | Attacker (winger) | F |
| 29 | Attacker (striker) | F |
| 30 | Defender | D |
| 31 | Midfielder | M |
| 32 | Attacker | F |

---

## 五、PlayerStats 数据模型缺口

PLAYER_STAT_MAP 中已映射但 PlayerStats dataclass **缺少对应字段**的指标（🔶标记项），`_parse_player_detail_stats()` 已从 API 解析出值，但 `_parse_player_from_lineup()` 未传入 dataclass：

| type_id | 指标名 | 缺少的字段 |
|--------:|--------|-----------|
| 98 | crosses | `crosses` |
| 57 | saves | `saves` |
| 47 | penalties | `penalties` |
| 84 | yellowcards | `yellowcards` |
| 83 | redcards | `redcards` |

> 若需这些数据，在 `PlayerStats` dataclass 中增加对应字段，并在 `_parse_player_from_lineup()` 中传入即可。

---

## 六、采集策略说明

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

## 七、与 API-Football 对比

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
