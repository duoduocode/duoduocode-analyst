# SportMonks API 统计指标全集

> 基于 SportMonks Football API V3，以 PSG vs Arsenal (fixture 19683241) 实际返回数据验证。
>
> 标记说明：✅ 已采集并存入数据模型 | ⚠️ API 返回但代码未采集 | — 球员级 API 不返回此数据

---

## 一、球队级统计 (Fixture Statistics) — 44 项

球队统计通过 `fixtures/{id}?include=statistics` 获取，使用 `FIXTURE_STAT_MAP` 映射。

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
| 116 | ACCURATE_PASSES | 准确传球次数 | ⚠️ | API 返回但代码未采集（球队级） |
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
| 88 | GOALS_CONCEDED | 球队失球(在场时) | ✅ | — |
| 72 | FIRST_SUBSTITUTION | 第一次换人时间 | ⚠️ | API 返回但代码未采集 |
| 61 | BEATS | 被突破次数 | ⚠️ | API 返回但代码未采集 |

---

## 二、球员级统计 (Player Statistics)

球员数据通过 `lineups.details` 获取。基于 fixture 19683241 实测，SportMonks API 返回 **66 项** type_id，当前 `PLAYER_STAT_MAP` 已映射 **49 项**，PlayerStats dataclass 全部覆盖。

> 标记说明：✅ 已采集 | ⚠️ API 返回但代码未映射 | — 此指标在球员级 API 不返回（仅球队级）

### 2.1 基础信息 (Basic Info)

| type_id | 开发者名称 | 中文名 | 状态 | 备注 |
|--------:|-----------|--------|:--:|------|
| 40 | CAPTAIN | 是否队长 | ✅ | 布尔值 |
| 118 | RATING | 比赛评分 | ✅ | 浮点数 |
| 119 | MINUTES_PLAYED | 出场时间(分钟) | ✅ | |
| 117172 | CUMULATIVE_MINUTES_PLAYED | 赛季累计出场时间 | ⚠️ | |
| 1490 | MAN_OF_MATCH | 全场最佳 | ✅ | 布尔值 |
| 120 | TOUCHES | 触球次数 | ✅ | |

### 2.2 射门 (Shooting)

| type_id | 开发者名称 | 中文名 | 状态 | 备注 |
|--------:|-----------|--------|:--:|------|
| 42 | SHOTS_TOTAL | 总射门 | ✅ | `shots_total` |
| 86 | SHOTS_ON_TARGET | 射正 | ✅ | `shots_on` |
| 41 | SHOTS_OFF_TARGET | 射偏 | ⚠️ | |
| 58 | SHOTS_BLOCKED | 被封堵射门 | ⚠️ | |
| 64 | HIT_WOODWORK | 中框（门柱/横梁） | ✅ | `hit_woodwork` |

### 2.3 进球与助攻 (Goals & Assists)

| type_id | 开发者名称 | 中文名 | 状态 | 备注 |
|--------:|-----------|--------|:--:|------|
| 52 | GOALS | 进球 | ✅ | `goals` |
| 79 | ASSISTS | 助攻 | ✅ | `assists` |
| 111 | PENALTIES_SCORED | 点球进球 | ✅ | `penalties_scored` |
| 580 | BIG_CHANCES_CREATED | 创造绝佳机会 | ✅ | `big_chances_created` |
| 581 | BIG_CHANCES_MISSED | 错失绝佳机会 | ⚠️ | |
| 9706 | CHANCES_CREATED | 创造机会 | ✅ | `chances_created` |

### 2.4 传球 (Passing)

| type_id | 开发者名称 | 中文名 | 状态 | 备注 |
|--------:|-----------|--------|:--:|------|
| 80 | PASSES | 传球总次数 | ✅ | `passes_total` |
| 116 | ACCURATE_PASSES | 准确传球次数 | ✅ | `passes_accurate` |
| 1584 | ACCURATE_PASSES_PERCENTAGE | 传球成功率 % | ✅ | `passes_accuracy` |
| 117 | KEY_PASSES | 关键传球 | ✅ | `passes_key` |
| 98 | TOTAL_CROSSES | 传中总次数 | ✅ | `crosses` |
| 99 | ACCURATE_CROSSES | 精准传中 | ✅ | `crosses_accurate` |
| 1533 | SUCCESSFUL_CROSSES_PERCENTAGE | 传中成功率 % | ⚠️ | |
| 122 | LONG_BALLS | 长传次数 | ⚠️ | |
| 123 | LONG_BALLS_WON | 成功长传 | ⚠️ | |
| 27270 | LONG_BALLS_WON_PERCENTAGE | 长传成功率 % | ⚠️ | |
| 27269 | PASSES_IN_FINAL_THIRD | 进攻三区传球 | ✅ | `passes_final_third` |
| 27272 | BACKWARD_PASSES | 回传次数 | ✅ | `back_passes` |

### 2.5 防守 (Defense)

| type_id | 开发者名称 | 中文名 | 状态 | 备注 |
|--------:|-----------|--------|:--:|------|
| 78 | TACKLES | 抢断 | ✅ | `tackles_total` |
| 27267 | TACKLES_WON | 成功抢断 | ⚠️ | |
| 27268 | TACKLES_WON_PERCENTAGE | 抢断成功率 % | ✅ | `tackles_won_pct` |
| 100 | INTERCEPTIONS | 拦截 | ✅ | `tackles_interceptions` |
| 101 | CLEARANCES | 解围 | ✅ | `clearances` |
| 27271 | BALL_RECOVERY | 球权回收 | ✅ | `ball_recoveries` |
| 97 | BLOCKED_SHOTS | 封堵射门 | ✅ | `blocked_shots` |
| 110 | DRIBBLED_PAST | 被过人 | ✅ | `dribbled_past` |
| 94 | DISPOSSESSED | 被抢断 | ⚠️ | |
| 27273 | POSSESSION_LOST | 丢失球权 | ✅ | `possession_lost` |

### 2.6 对抗 (Duels)

| type_id | 开发者名称 | 中文名 | 状态 | 备注 |
|--------:|-----------|--------|:--:|------|
| 105 | TOTAL_DUELS | 总对抗 | ✅ | `duels_total` |
| 106 | DUELS_WON | 赢得对抗 | ✅ | `duels_won` |
| 1491 | DUELS_LOST | 输掉对抗 | ⚠️ | |
| 27276 | DUELS_WON_PERCENTAGE | 对抗成功率 % | ✅ | `duels_won_pct` |
| 107 | AERIALS_WON | 赢得空中对抗 | ✅ | `aerials_won` |
| 27274 | AERIALS | 空中对抗总次数 | ✅ | `aerials` |
| 27266 | AERIALS_LOST | 输掉空中对抗 | ⚠️ | |
| 27275 | AERIALS_WON_PERCENTAGE | 空中对抗成功率 % | ✅ | `aerials_won_pct` |

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
| 114 | PENALTIES_COMMITTED | 送点 | ⚠️ | |
| 115 | PENALTIES_WON | 赢得点球 | ✅ | `penalties_won` |
| 84 | YELLOWCARDS | 黄牌 | ✅ | `yellowcards` |
| 83 | REDCARDS | 红牌 | ✅ | `redcards` |

### 2.9 越位 (Offside)

| type_id | 开发者名称 | 中文名 | 状态 |
|--------:|-----------|--------|:--:|
| 51 | OFFSIDES | 越位次数 | ⚠️ |

### 2.10 门将 (Goalkeeper)

| type_id | 开发者名称 | 中文名 | 状态 | 备注 |
|--------:|-----------|--------|:--:|------|
| 57 | SAVES | 扑救 | ✅ | `saves` |
| 104 | SAVES_INSIDE_BOX | 禁区内扑救 | ⚠️ | |
| 103 | PUNCHES | 门将击球 | ⚠️ | |
| 88 | GOALS_CONCEDED | 球队失球(在场时) | ⚠️ | |
| 1535 | GOALKEEPER_GOALS_CONCEDED | 门将失球 | ⚠️ | |
| 584 | GOOD_HIGH_CLAIM | 成功摘高球 | ⚠️ | |

### 2.11 失误 (Errors)

| type_id | 开发者名称 | 中文名 | 状态 | 备注 |
|--------:|-----------|--------|:--:|------|
| 571 | ERROR_LEAD_TO_GOAL | 导致丢球的失误 | ✅ | `error_lead_to_goal` |
| 48997 | ERROR_LEAD_TO_SHOT | 导致射门的失误 | ⚠️ | |

### 2.12 高阶 xG 数据 (Expected Goals)

| type_id | 开发者名称 | 中文名 | 说明 | 状态 | 备注 |
|--------:|-----------|--------|------|:--:|------|
| 5304 | EXPECTED_GOALS | 期望进球 (xG) | 每脚射门 xG 之和 | ✅ | `xg`，TCR/LDI 核心输入 |
| 5305 | EXPECTED_GOALS_ON_TARGET | 射正期望进球 (xGOT) | 射正后的期望进球 | ✅ | `xgot` |
| 9685 | SHOOTING_PERFORMANCE | 射门表现 (SP) | 实际进球 − xG | ✅ | `shooting_performance` |

---

> **汇总**：API 返回 66 项球员级 type_id，`PLAYER_STAT_MAP` 已映射 **49 项**（覆盖 74%）。剩余 **17 项** 未映射。

---

## 三、未映射球员指标清单（17 项）

以下 type_id 目前 API 返回但 PLAYER_STAT_MAP 未包含：

| type_id | 开发者名称 | 中文名 | 分类 |
|--------:|-----------|--------|------|
| 41 | SHOTS_OFF_TARGET | 射偏 | 射门 |
| 58 | SHOTS_BLOCKED | 被封堵射门 | 射门 |
| 51 | OFFSIDES | 越位次数 | 越位 |
| 581 | BIG_CHANCES_MISSED | 错失绝佳机会 | 进球 |
| 122 | LONG_BALLS | 长传次数 | 传球 |
| 123 | LONG_BALLS_WON | 成功长传 | 传球 |
| 1533 | SUCCESSFUL_CROSSES_PERCENTAGE | 传中成功率 % | 传球 |
| 27270 | LONG_BALLS_WON_PERCENTAGE | 长传成功率 % | 传球 |
| 27267 | TACKLES_WON | 成功抢断 | 防守 |
| 94 | DISPOSSESSED | 被抢断 | 防守 |
| 1491 | DUELS_LOST | 输掉对抗 | 对抗 |
| 27266 | AERIALS_LOST | 输掉空中对抗 | 对抗 |
| 114 | PENALTIES_COMMITTED | 送点 | 纪律 |
| 104 | SAVES_INSIDE_BOX | 禁区内扑救 | 门将 |
| 103 | PUNCHES | 门将击球 | 门将 |
| 88 | GOALS_CONCEDED | 球队失球(在场时) | 门将 |
| 1535 | GOALKEEPER_GOALS_CONCEDED | 门将失球 | 门将 |
| 584 | GOOD_HIGH_CLAIM | 成功摘高球 | 门将 |
| 48997 | ERROR_LEAD_TO_SHOT | 导致射门的失误 | 失误 |
| 117172 | CUMULATIVE_MINUTES_PLAYED | 赛季累计出场时间 | 基础 |

---

## 四、球队级 stats 中可用但球员级不可用的指标

以下指标在球队统计中返回，但球员级 `lineups.details` 中不包含：

| type_id | 开发者名称 | 中文名 |
|--------:|-----------|--------|
| 62 | LONG_PASSES | 长传 |
| 81 | SUCCESSFUL_PASSES | 成功传球 |
| 82 | SUCCESSFUL_PASSES_PERCENTAGE | 传球成功率 % |
| 49 | SHOTS_INSIDEBOX | 禁区内射门 |
| 50 | SHOTS_OUTSIDEBOX | 禁区外射门 |

---

## 五、比赛事件 (Match Events)

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

## 六、比赛基本信息 (Match Info)

### 6.1 球队信息 (TeamInfo)

数据来源 `participants[]` 字段。

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `id` | int | SportMonks 球队 ID | 831 (PSG) |
| `name` | str | 球队名称 | "Paris Saint Germain" |
| `logo_url` | str | 队徽 URL | `image_path` 字段 |
| `meta.location` | str | 主客场标识 | "home" / "away" |

### 6.2 比分信息 (ScoreInfo)

| description | 含义 | 对应字段 |
|-------------|------|----------|
| `CURRENT` | 全场最终比分 | `home` / `away` |
| `HT` / `HALFTIME` | 半场比分 | `halftime_home` / `halftime_away` |
| `FT` | 常规时间比分 | `fulltime_home` / `fulltime_away` |
| `ET` | 加时赛比分 | `extratime_home` / `extratime_away` |
| `PEN` | 点球大战比分 | `penalty_home` / `penalty_away` |

### 6.3 比赛状态 (Status)

| state_id | 状态码 | 含义 |
|---------:|:------:|------|
| 1 | NS | 未开始 |
| 2 | LIVE | 进行中 |
| 3 | HT | 半场 |
| 4 | BT | 半场休息 |
| 5 | FT | 全场结束 |
| 6 | AET | 加时结束 |
| 7 | PEN | 点球大战 |
| 8 | PST | 推迟 |
| 9 | SUSP | 中断 |
| 10 | INT | 取消 |

### 6.4 阵型信息 (LineupInfo)

`lineups[].details[].type_id` 区分：
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

## 七、采集策略说明

```
单次 API 请求: GET /fixtures/{id}?include=statistics;periods.statistics;periods.events;
                trends;timeline;lineups.details;events;participants;scores;
                coaches;referees;formations;stage;venue
                  │
                  ├─ statistics[]  →  FIXTURE_STAT_MAP 转换 → home_stats / away_stats (dict)
                  ├─ lineups[]     →  details[] 解析 → home_players / away_players (PlayerStats)
                  ├─ events[]      →  type_id 转换 → events (MatchEvent)
                  ├─ participants[]→  TeamInfo (id, name, logo_url)
                  ├─ scores[]      →  ScoreInfo
                  ├─ trends[]      → 趋势数据 (_parse_trends)
                  ├─ periods[]     →  分时段统计 (PeriodData)
                  ├─ coaches[]     →  CoachInfo
                  ├─ formations[]  →  阵型
                  ├─ stage[]       →  比赛阶段信息
                  └─ venue[]       →  球场信息
```

### 从球员汇总球队统计
部分指标（xG、Ball Recoveries 等）只在球员级别返回：

```python
home_xg = sum(p.xg or 0 for p in raw.home_players)
home_recoveries = sum(p.ball_recoveries or 0 for p in raw.home_players)
```

---

## 八、与 API-Football 对比

| 维度 | API-Football | SportMonks |
|------|:---:|:---:|
| 请求次数 | 5 次并行 | **1 次** |
| 球队统计项 | ~20 | 44 |
| 球员统计项(已采集) | ~15 | **49** |
| 球员统计项(API 返回) | — | 66 |
| xG (球员级) | 部分有 | ✅ |
| 球权回收 | ❌ | ✅ |
| 绝佳机会 | ❌ | ✅ |
| 中框/长传/传中 | ❌ | ✅ |
| 球员头像 | player.photo | image_path |
| 队徽 | team.logo | participant.image_path |

---

*更新时间: 2026-06-07 | 数据来源: SportMonks V3 API + 官方文档 + fixture 19683241 实测*
