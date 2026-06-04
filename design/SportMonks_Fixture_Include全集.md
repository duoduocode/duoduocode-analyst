# SportMonks `/fixtures/{id}?include=` 全集参考

> 基于 SportMonks Football API V3 官方文档整理 (2026-06-04)。
> 
> 使用方式: `GET /v3/football/fixtures/{id}?api_token=TOKEN&include=participants;events.type;lineups.details`
> 
> 多个 include 用 `;` 分隔，嵌套用 `.` 连接。当前项目已采集的标记 ✅。

---

## 总览 (31 项 include)

| 序号 | include | 含义 | 数据量级 | 当前项目 |
|:---:|---------|------|:---:|:---:|
| 1 | `sport` | 运动类型 | 1 条 | |
| 2 | `round` | 比赛轮次 | 1 条 | |
| 3 | `stage` | 赛事阶段 | 1 条 | |
| 4 | `group` | 小组 | 1 条 | |
| 5 | `aggregate` | 两回合总比分 | 1 条 | |
| 6 | `league` | 联赛信息 | 1 条 | |
| 7 | `season` | 赛季信息 | 1 条 | |
| 8 | `coaches` | 两队教练 | ~2 条 | |
| 9 | `tvStations` | 电视转播台 | N 条 | |
| 10 | `venue` | 球场/场馆 | 1 条 | |
| 11 | `state` | 比赛状态 | 1 条 | |
| 12 | `weatherReport` | 天气报告 | 1 条 | |
| 13 | `lineups` | 阵容 | ~22+ 条 | ✅ |
| 14 | `events` | 比赛事件 | ~30 条 | ✅ |
| 15 | `timeline` | 关键时刻 | ~50 条 | |
| 16 | `comments` | 文字直播 | 数十条 | |
| 17 | `trends` | 逐分钟趋势 | ~1700 条 | |
| 18 | `statistics` | 球队统计 | 40 项 | ✅ |
| 19 | `periods` | 比赛时段 | ~5 条 | |
| 20 | `participants` | 参赛球队 | 2 条 | ✅ |
| 21 | `odds` | 赔率 | 数百条 | |
| 22 | `premiumOdds` | 高级赔率 | 数百条 | |
| 23 | `inplayOdds` | 滚球赔率 | 数百条 | |
| 24 | `prematchNews` | 赛前新闻 | 数条 | |
| 25 | `postmatchNews` | 赛后新闻 | 数条 | |
| 26 | `metadata` | 元数据 | 不定 | |
| 27 | `sidelined` | 伤病/停赛 | 不定 | |
| 28 | `predictions` | AI 预测 | 数条 | |
| 29 | `referees` | 裁判信息 | ~4 条 | |
| 30 | `formations` | 阵型 | 2 条 | |
| 31 | `ballCoordinates` | 足球坐标 | ~1400 条 | |
| 32 | `scores` | 各组比分 | ~5 条 | ✅ |

---

## 一、竞赛结构 (Competition Structure)

### 1. `sport` — 运动类型

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | Sport ID |
| `name` | string | 运动名称 (Football) |
| `code` | string | 代码 (football) |

### 2. `league` — 联赛信息

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | 联赛 ID |
| `sport_id` | int | 运动类型 |
| `country_id` | int | 所属国家 |
| `name` | string | 联赛名称 (如 "UEFA Champions League") |
| `active` | bool | 是否活跃 |
| `short_code` | string | 短代码 |
| `image_path` | string | logo 图片 URL |
| `type` | string | 联赛类型 |
| `sub_type` | string | 子类型 |

**嵌套 include**: `league.country`

### 3. `season` — 赛季信息

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | 赛季 ID |
| `sport_id` | int | 运动 |
| `league_id` | int | 所属联赛 |
| `name` | string | 赛季名 (如 "2025/2026") |
| `finished` | bool | 是否已结束 |
| `pending` | bool | 是否待开始 |
| `is_current` | bool | 是否当前赛季 |
| `starting_at` | string | 开始日期 |
| `ending_at` | string | 结束日期 |

### 4. `stage` — 赛事阶段

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | 阶段 ID |
| `sport_id` | int | 运动 |
| `league_id` | int | 所属联赛 |
| `season_id` | int | 所属赛季 |
| `type_id` | int | 阶段类型 |
| `name` | string | 阶段名 (如 "Knockout Stage") |
| `sort_order` | int | 排序 |
| `finished` / `pending` / `is_current` | bool | 状态 |
| `starting_at` / `ending_at` | string | 时间 |

### 5. `round` — 比赛轮次

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | 轮次 ID |
| `sport_id` / `league_id` / `season_id` / `stage_id` | int | 层级关系 |
| `name` | string | 轮次名 (如 "Round of 16") |
| `finished` / `pending` / `is_current` | bool | 状态 |
| `starting_at` / `ending_at` | string | 时间 |

### 6. `group` — 小组

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | 小组 ID |
| `sport_id` / `league_id` / `season_id` / `stage_id` | int | 层级关系 |
| `name` | string | 小组名 (如 "Group A") |
| `starting_at` / `ending_at` | string | 时间 |

### 7. `aggregate` — 两回合总比分

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | ID |
| `league_id` / `season_id` / `stage_id` | int | 层级 |
| `name` | string | 聚合名称 |
| `fixture_ids` | array | 所有相关 fixture ID |
| `result` | string | 最终总比分结果 |
| `detail` | string | 结果详情 |
| `winner_participant_id` | int | 胜方球队 ID |

---

## 二、人员 (Personnel)

### 8. `participants` — 参赛球队 ✅

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | 球队 ID |
| `sport_id` | int | 运动 |
| `country_id` | int | 所属国家 |
| `venue_id` | int | 主场场馆 |
| `name` | string | 球队名称 |
| `short_code` | string | 短代码 |
| `image_path` | string | **队徽 logo URL** |
| `founded` | int | 成立年份 |
| `type` | string | 类型 (domestic/international) |
| `gender` | string | 性别 |
| `meta.location` | string | **主客场标记** ("home"/"away") |

**嵌套 include**: `participants.country`, `participants.venue`

### 9. `coaches` — 两队教练

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | 教练 ID |
| `player_id` | int | (如果曾是球员) 球员 ID |
| `country_id` / `nationality_id` / `city_id` | int | 地区信息 |
| `common_name` | string | 常用名 |
| `firstname` / `lastname` | string | 名 / 姓 |
| `name` | string | 全名 |
| `display_name` | string | 显示名 |
| `image_path` | string | **头像 URL** |
| `height` / `weight` | int | 身高 / 体重 |
| `date_of_birth` | string | 出生日期 |
| `gender` | string | 性别 |

**嵌套 include**: `coaches.country`, `coaches.nationality`

### 10. `referees` — 裁判组

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | 裁判 ID |
| `country_id` / `nationality_id` / `city_id` | int | 地区 |
| `common_name` | string | 常用名 |
| `firstname` / `lastname` | string | 名 / 姓 |
| `name` / `display_name` | string | 姓名 |
| `image_path` | string | **头像 URL** |
| `height` / `weight` | int | 身高 / 体重 |
| `date_of_birth` | string | 出生日期 |

---

## 三、场地与环境 (Venue & Environment)

### 11. `venue` — 球场信息

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | 场馆 ID |
| `country_id` | int | 国家 |
| `name` | string | 球场名称 |
| `address` | string | 地址 |
| `city_name` | string | 所在城市 |
| `zipcode` | string | 邮编 |
| `latitude` / `longitude` | string | GPS 坐标 |
| `capacity` | int | 容纳人数 |
| `surface` | string | 草皮类型 |
| `image_path` | string | 场馆图片 |
| `national_team` | bool | 是否国家队主场 |

### 12. `weatherReport` — 天气报告

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | ID |
| `fixture_id` / `venue_id` | int | 关联 |
| `temperature` | object | 当日气温序列 |
| `feels_like` | object | 体感温度序列 |
| `wind` | object | 风速/风向 |
| `humidity` | string | 湿度 |
| `pressure` | int | 气压 |
| `clouds` | string | 云量 |
| `description` | string | 天气描述 (如 "Clear") |
| `icon` | string | 天气图标 |
| `type` | string | 类型 ("actual"/"forecast") |
| `metric` | string | 温度单位 |

---

## 四、比赛状态 (Match State)

### 13. `state` — 比赛状态

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | 状态 ID |
| `state` | string | 状态码 (NS/LIVE/HT/FT/AET/PEN...) |
| `name` | string | 完整名称 |
| `short_name` | string | 简称 |
| `developer_name` | string | 开发者名 |

### 14. `periods` — 比赛时段

记录每个半场/加时/点球的起止时间。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | 时段 ID |
| `fixture_id` | int | 比赛 ID |
| `type_id` | int | 时段类型 |
| `started` | int | **开始时间** (UNIX 时间戳) |
| `ended` | int | 结束时间 (UNIX 时间戳) |
| `counts_from` | int | 计时起算分钟 |
| `ticking` | bool | 是否正在进行 |
| `sort_order` | int | 排序 (1=上半场, 2=下半场...) |
| `description` | string | 描述 (如 "1st Half") |
| `time_added` | int | 补时分钟 |
| `period_length` | int | 规定时长 (45/15/...) |
| `minutes` | int | 当前分钟 (进行中时) |
| `seconds` | int | 当前秒数 |
| `has_timer` | bool | 是否有精细计时 |

**嵌套 include**: `periods.events`, `periods.timeline`, `periods.statistics`

### 15. `scores` — 比分 ✅

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | ID |
| `fixture_id` | int | 比赛 ID |
| `type_id` | int | 比分类型 |
| `participant_id` | int | 球队 ID |
| `score` | object | `{ goals: N, participant: "home"/"away" }` |
| `description` | string | 比分层级 (CURRENT / HT / FT / ET / PEN) |

**嵌套 include**: `scores.type`, `scores.participant`

---

## 五、阵容与球员统计 (Lineup & Player Stats)

### 16. `lineups` — 阵容 ✅

每个球员一条记录，包含首发/替补标记。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | lineup ID |
| `fixture_id` | int | 比赛 |
| `player_id` | int | 球员 ID |
| `team_id` | int | 球队 |
| `position_id` | int | 位置 ID |
| `detailed_position_id` | int | 详细位置 |
| `formation_field` | string | 阵型位置坐标 (如 "1:1") |
| `formation_position` | int | 阵型中数值位置 |
| `type_id` | int | **11=首发, 12=替补** |
| `jersey_number` | int | 球衣号码 |
| `player_name` | string | 球员名 |

**核心嵌套**:

| 嵌套路径 | 获取内容 | 当前项目 |
|---------|---------|:---:|
| `lineups.details` | **球员比赛统计数据** (含进球、传球、xG 等) | ✅ |
| `lineups.type` | 阵容类型元信息 | |
| `lineups.player` | 球员完整档案 (全名、头像、身高、出生日期) | |
| `lineups.player.country` | 球员国籍详情 (国旗图、ISO 代码) | |
| `lineups.player.nationality` | 球员民族信息 | |
| `lineups.position` | 位置元信息 | |
| `lineups.detailedPosition` | 详细位置元信息 | |

#### `lineups.details` — 球员统计 (LineupDetail)

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | ID |
| `lineup_id` | int | 关联 lineup |
| `player_id` / `team_id` | int | 球员 / 球队 |
| `type_id` | int | 统计类型 ID |
| `data` | object | `{ value: N }` 统计值 |

详见 [SportMonks统计指标全集.md](./SportMonks统计指标全集.md) 中的球员级统计映射表。

### 16b. `formations` — 阵型

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | ID |
| `fixture_id` | int | 比赛 |
| `participant_id` | int | 球队 |
| `formation` | string | 阵型 (如 "4-3-3") |
| `location` | string | home / away |

---

## 六、比赛事件 (Events & Commentary)

### 17. `events` — 比赛事件 ✅

记录进球、换人、红黄牌、点球等比赛事件。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | 事件 ID |
| `fixture_id` | int | 比赛 |
| `period_id` | int | 时段 |
| `participant_id` | int | 球队 |
| `type_id` | int | **事件类型** (见下表) |
| `player_id` | int | 球员 ID |
| `related_player_id` | int | 关联球员 (助攻者/换下球员) |
| `player_name` | string | 球员名 |
| `related_player_name` | string | 关联球员名 |
| `result` | string | 比分变化 (如 "1-0") |
| `info` | string | 事件描述 (如 "Left foot shot") |
| `addition` | string | 附加信息 (如 "1st Goal") |
| `minute` | int | 发生分钟 |
| `extra_minute` | int | 补时分钟 |
| `injured` | bool | (换人) 是否因伤 |
| `rescinded` | bool | (红黄牌) 是否被撤销 |
| `sort_order` | int | 排序 |

**事件 type_id 全集 (11种)**:

| type_id | name | code | 说明 |
|:---:|------|------|------|
| 10 | VAR | var | VAR 视频助理裁判介入 |
| 14 | Goal | goal | **运动战进球** |
| 15 | Own Goal | owngoal | **乌龙球** |
| 16 | Penalty | penalty | **点球进球** |
| 17 | Missed Penalty | missed_penalty | **点球罚失** |
| 18 | Substitution | substitution | **换人** |
| 19 | Yellowcard | yellowcard | **黄牌** |
| 20 | Redcard | redcard | **直红** |
| 21 | Yellow/Red Card | yellowredcard | **两黄变红** |
| 22 | Penalty Shootout Miss | pen_shootout_miss | 点球大战罚失/被扑 |
| 23 | Penalty Shootout Goal | pen_shootout_goal | 点球大战进球 |

**核心嵌套**:

| 嵌套路径 | 获取内容 |
|---------|---------|
| `events.type` | 事件类型元信息 (name, code, developer_name) |
| `events.player` | 球员完整档案 (头像、姓名、身高体重、出生日期) |
| `events.player.country` | 球员国籍详情 (国旗、ISO 代码、经纬度) |
| `events.player.nationality` | 球员民族 |
| `events.relatedPlayer` | 关联球员 (助攻者等) 完整档案 |
| `events.subType` | 事件子类型 |
| `events.participant` | 事件所属球队信息 |
| `events.period` | 事件所属时段 |

### 18. `timeline` — 关键时刻

与 `events` 共享 Event 实体模型，但 type_id 体系不同，记录**非进球类的比赛关键时刻**。

| type_id | 名称 | 说明 |
|:---:|------|------|
| 569 | Shot on Target | 射正 |
| 570 | Shot off Target | 射偏 |
| 126 | Corner | 角球 |
| 1514 | Offside | 越位 |
| 48995 | Hit Woodwork | 中框 (门柱/横梁) |

### 19. `comments` — 文字直播

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | ID |
| `fixture_id` | int | 比赛 |
| `comment` | string | **直播文字** |
| `minute` | int | 分钟 |
| `extra_minute` | int | 补时 |
| `is_goal` | bool | 是否进球 |
| `is_important` | bool | 是否重要事件 |
| `order` | int | 排序 |

---

## 七、统计与趋势 (Statistics & Trends)

### 20. `statistics` — 球队统计 ✅

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | ID |
| `fixture_id` | int | 比赛 |
| `participant_id` | int | 球队 |
| `type_id` | int | 统计类型 ID |
| `data` | object | `{ value: N }` 统计值 |
| `location` | string | home / away |

**共有 40 项球队级统计指标**，详见 [SportMonks统计指标全集.md](./SportMonks统计指标全集.md)。

### 21. `trends` — 逐分钟累积趋势

记录各项统计指标**逐分钟的累积值变化**，可精准还原比赛节奏。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | ID |
| `fixture_id` | int | 比赛 |
| `participant_id` | int | 球队 |
| `type_id` | int | 统计类型 ID |
| `period_id` | int | 时段 |
| `value` | int | **该分钟的累积值** |
| `minute` | int | 比赛分钟数 |

典型指标: Total Passes(80), Attacks(43), Duels Won(106), Ball Possession(45), Crosses(98) 等，大多数球队统计都有对应的趋势数据。一场比赛约 1500-1700 条记录。

---

## 八、赔率与预测 (Odds & Predictions)

### 22. `odds` — 赛前赔率

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | ID |
| `fixture_id` | int | 比赛 |
| `market_id` | int | 盘口类型 |
| `bookmaker_id` | int | 博彩公司 |
| `label` / `name` | string | 标签 / 名称 |
| `value` | string | **赔率值** |
| `market_description` | string | 盘口描述 |
| `probability` | string | 隐含概率 |
| `dp3` / `fractional` / `american` | string | 三种赔率格式 |
| `winning` | bool | 是否胜出 |
| `stopped` | bool | 是否停盘 |
| `total` / `handicap` | string | 大小球/让球 |
| `participants` | string | 参与方 |

**嵌套 include**: `odds.market`, `odds.bookmaker`, `odds.fixture`

### 23. `premiumOdds` — 高级赔率

与 `odds` 字段结构相同，增加:
- `latest_bookmaker_update` — 博彩公司最后更新时间

### 24. `inplayOdds` — 滚球赔率

| 字段 | 说明 |
|------|------|
| `id` | ID |
| `external_id` | 外部系统 ID |
| `fixture_id` | 比赛 |
| `market_id` / `bookmaker_id` | 盘口/博彩公司 |
| `suspended` | bool — 是否暂停 |
| `stopped` | bool — 是否停止 |

其余与 `odds` 基本相同。

### 25. `predictions` — AI 预测

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | ID |
| `fixture_id` | int | 比赛 |
| `type_id` | int | 预测类型 |
| `predictions` | object | **预测值对象** |

---

## 九、新闻与媒体 (News & Media)

### 26. `prematchNews` — 赛前新闻

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | ID |
| `fixture_id` / `league_id` | int | 关联 |
| `title` | string | 新闻标题 |
| `type` | string | 类型 |

**嵌套 include**: `prematchNews.lines` → `{ text, type }` 解析文章正文

### 27. `postmatchNews` — 赛后新闻

字段结构同 `prematchNews`。

### 28. `tvStations` — 电视转播

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | ID |
| `name` | string | 电视频道名 |
| `url` | string | 频道网址 |
| `image_path` | string | 频道 logo |

---

## 十、其他

### 29. `metadata` — 元数据

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | ID |
| `metadatable_type` | string | 关联实体类型 |
| `metadatable_id` | int | 关联实体 ID |
| `type_id` | int | 元数据类型 |
| `value` | mixed | 元数据值 |
| `value_type` | string | 值类型 |

### 30. `sidelined` — 伤病/停赛

记录本场比赛两队球员的伤病和停赛情况。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | ID |
| `fixture_id` | int | 比赛 |
| `player_id` | int | 球员 |
| `type_id` | int | 类型 (伤病/停赛) |
| `category` | string | 分类 |
| `team_id` | int | 球队 |
| `season_id` | int | 赛季 |
| `start_date` | string | 开始日期 |
| `end_date` | string | 预计复出日期 |
| `games_missed` | int | 已缺席场次 |
| `completed` | bool | 是否已结束 |

**嵌套 include**: `sidelined.player`, `sidelined.player.country`, `sidelined.type`, `sidelined.sideline`

### 31. `ballCoordinates` — 足球坐标

记录比赛过程中足球的实时位置坐标 (通常每隔几秒采样一次)。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | ID |
| `fixture_id` | int | 比赛 |
| `period_id` | int | 时段 |
| `timer` | string | **时间戳** (如 "23:15") |
| `x` | float | **X 坐标** (0~1, 纵向, 0=主队底线) |
| `y` | float | **Y 坐标** (0~1, 横向, 0=左边线) |

一场比赛约 1300-1400 条坐标记录。

---

## 十一、当前项目采集配置

[api_client.py 第 246 行](../src/collector/api_client.py#L246):

```python
includes = "statistics;lineups.details;events;participants;scores"
```

可选扩展建议:

| 优先级 | 建议添加的 include | 收益 |
|:---:|---------|------|
| 高 | `trends` | 替代动量均分估算，精准还原比赛节奏 |
| 高 | `events.player.country` | 进球/红黄牌事件显示球员头像和国籍国旗 |
| 中 | `ballCoordinates` | 足球位置热力图，分析进攻方向 |
| 中 | `formations` | 阵型展示 |
| 低 | `coaches;referees` | 教练/裁判信息 |
| 低 | `comments` | 文字直播内容 |

---

*数据来源: SportMonks V3 API 官方文档 (docs.sportmonks.com) + fixture 19683241 实测验证*
