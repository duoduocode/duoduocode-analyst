# 信号检测器全量分析 — Paris Saint Germain vs FC Bayern München (2026-04-28)
**对阵**: Paris Saint Germain vs FC Bayern München | **比分**: 5-4 | **日期**: 2026-04-28

**检测器总数**: 52 (A-F: 38 + G-H趋势: 11 + I贡献王: 3) | **触发信号数**: 18

---

## 球员攻防贡献排行榜 (外场球员 Top 3)

> 进攻分 = (进球x25 + 助攻x15 + xGx20 + 射正x5 + 关键传球x6 + 过人x5 + 三区传球x1.5) x 分钟系数 + 事件加成(制胜球+20 / 扳平球+15 / 替补5分钟内进球+20)
> 防守分 = (成功抢断x10 + 拦截x8 + 解围x3 + 封堵x8 + 球权回收x4 + 赢得对抗x4) x 分钟系数
> 均衡分 = 2 x 进攻分 x 防守分 / (进攻分 + 防守分)
> 门将不参与排名。出场不足30分钟的球员不参与排名。

### Paris Saint Germain

**Paris Saint Germain - 进攻王 Top 3**

| 排名 | 球员 | 位置 | 评分 | 出场 | 进攻分 |
|:---:|------|:---:|:---:|:---:|:---:|
| 1 | Ousmane Dembélé | M | 8.25 | 90' | **114.7** |
| 2 | Khvicha Kvaratskhelia | M | 8.18 | 84' | **78.9** |
| 3 | Désiré Doué | M | 6.96 | 70' | **53.7** |

**Paris Saint Germain - 防守王 Top 3**

| 排名 | 球员 | 位置 | 评分 | 出场 | 防守分 |
|:---:|------|:---:|:---:|:---:|:---:|
| 1 | João Neves | D | 6.78 | 90' | **99.0** |
| 2 | Nuno Mendes | D | 6.20 | 84' | **68.1** |
| 3 | Marquinhos | D | 6.34 | 90' | **63.0** |

**Paris Saint Germain - 均衡王 Top 3**

| 排名 | 球员 | 位置 | 评分 | 出场 | 进攻分 | 防守分 | 均衡分 |
|:---:|------|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 | Khvicha Kvaratskhelia | M | 8.18 | 84' | 78.9 | 45.7 | **57.9** |
| 2 | João Neves | D | 6.78 | 90' | 36.1 | 99.0 | **52.9** |
| 3 | Vitinha | D | 7.03 | 90' | 34.5 | 57.0 | **43.0** |

### FC Bayern München

**FC Bayern München - 进攻王 Top 3**

| 排名 | 球员 | 位置 | 评分 | 出场 | 进攻分 |
|:---:|------|:---:|:---:|:---:|:---:|
| 1 | Luis Díaz | D | 8.55 | 90' | **102.8** |
| 2 | Michael Olise | D | 7.49 | 90' | **99.6** |
| 3 | Harry Kane | M | 8.64 | 90' | **98.7** |

**FC Bayern München - 防守王 Top 3**

| 排名 | 球员 | 位置 | 评分 | 出场 | 防守分 |
|:---:|------|:---:|:---:|:---:|:---:|
| 1 | Aleksandar Pavlovic | D | 7.20 | 90' | **101.2** |
| 2 | Dayot Upamecano | D | 6.91 | 90' | **97.0** |
| 3 | Josip Stanisic | D | 6.32 | 90' | **82.0** |

**FC Bayern München - 均衡王 Top 3**

| 排名 | 球员 | 位置 | 评分 | 出场 | 进攻分 | 防守分 | 均衡分 |
|:---:|------|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 | Luis Díaz | D | 8.55 | 90' | 102.8 | 80.0 | **90.0** |
| 2 | Michael Olise | D | 7.49 | 90' | 99.6 | 66.0 | **79.4** |
| 3 | Harry Kane | M | 8.64 | 90' | 98.7 | 53.0 | **69.0** |

---

## 触发信号汇总

| # | 信号名 | 类别 | 强度 | 简述 |
|---|--------|------|:----:|------|
| 1 | `conversion_anomaly` | 比分背离 | 1.00 | Paris Saint Germain射门转化率42%——极高转化率，每脚射门都极具威胁 |
| 2 | `high_scoring` | 叙事钩子 | 1.00 | 全场9个进球——进球大战，双方防线大开大合 |
| 3 | `halftime_adjustment` | 淘汰赛专项 | 1.00 | Paris Saint Germain上半场占优但下半场被压制——对手半场调整效果显著 |
| 4 | `period_goal_cluster` | 淘汰赛专项 | 1.00 | 第6932085时段集中出现了5个进球——这是比赛的疯狂时段 |
| 5 | `offensive_king` | 球员贡献王 | 1.00 | 进攻贡献王 —— Paris Saint Germain: Ousmane Dembélé(115分)；FC Bayern München: Luis Díaz |
| 6 | `defensive_king` | 球员贡献王 | 1.00 | 防守贡献王 —— Paris Saint Germain: João Neves(99分)；FC Bayern München: Aleksandar Pavl |
| 7 | `turning_point_alert` | 趋势驱动 | 1.00 | 趋势数据捕捉到多个比赛转折点: 第4-14分钟区间传球节奏主队明显占优; 第13-23分钟区间传球节奏主队明显占优; 第24-34分钟区间传球节奏主队明显占优 |
| 8 | `sub_impact_on_trend` | 事件x趋势 | 1.00 | FC Bayern München第90分钟换上Aleksandar Pavlovic后，提升明显——进攻+120%; 控球+100% |
| 9 | `event_coincident_inflection` | 事件x趋势 | 1.00 | 第14分钟传球节奏出现转折点（置信度100%），与第17分钟的进球直接相关——这不是巧合 |
| 10 | `balanced_king` | 球员贡献王 | 0.90 | 攻防均衡王 —— Paris Saint Germain: Khvicha Kvaratskhelia、FC Bayern München: Luis Díaz |
| 11 | `gk_disaster` | 个人英雄/罪人 | 0.80 | Matvey Safonov本场表现灾难——失球4个，扑救成功率仅33% |
| 12 | `comeback` | 叙事钩子 | 0.70 | Paris Saint Germain在落后情况下完成逆转——展现了强大的心理素质和战术调整能力 |
| 13 | `counter_attack_efficiency` | 效率撕裂 | 0.67 | Paris Saint Germain控球率仅43%，但每次射门xG高达0.169——经典的高效反击战术 |
| 14 | `penalty_decided` | 比分背离 | 0.67 | 比赛由2个点球决定——点球是改变比分平衡的关键因素 |
| 15 | `momentum_surge` | 趋势驱动 | 0.52 | 第46分钟前后Paris Saint Germain突然发力——进攻节奏急剧攀升，进入暴走模式 |
| 16 | `goal_momentum_shift` | 事件x趋势 | 0.32 | Harry Kane第17分钟进球后，Paris Saint Germain明显接管了比赛节奏——攻防势头彻底转移 |
| 17 | `sub_timing_impact` | 结构问题 | 0.30 | 第90分钟的换人带有拖延时间或最后一搏的色彩 |
| 18 | `xg_upset` | 比分背离 | 0.19 | Paris Saint Germain以5球取胜，但xG(2.02)远低于FC Bayern München的xG(2.41)——这是一场典型的效率制胜/运气球 |

---

## 全部检测器明细

| # | 信号名 | 类别 | 公式 | 依赖指标 | 强度 | 触发? |
|---|--------|------|------|----------|:----:|:---:|
| 1 | `xg_upset` | 比分背离 | |xG差|>0.3且xG劣势方赢球 | xG, Score | 0.19 | YES |
| 2 | `conversion_anomaly` | 比分背离 | 转化率>35%或<5% | Goals, Shots | 1.00 | YES |
| 3 | `penalty_decided` | 比分背离 | 点球进球>=|分差|>0 | Events, Score | 0.67 | YES |
| 4 | `red_card_turning` | 比分背离 | 红牌后对方连入2+球 | Events, Score | 0.00 | — |
| 5 | `own_goal_impact` | 比分背离 | 乌龙球直接改变结果 | Events, Score | 0.00 | — |
| 6 | `late_winner` | 比分背离 | 75后翻盘逆转(最终胜负) | Events, Score | 0.00 | — |
| 7 | `possession_waste` | 效率撕裂 | 控球>55%且xG<0.8 | Poss%, xG | 0.00 | — |
| 8 | `counter_attack_efficiency` | 效率撕裂 | 控球<45%且xG/shot>2x | Poss%, xG, Shots | 0.67 | YES |
| 9 | `pass_efficiency_gap` | 效率撕裂 | 关键传球率差>3% | KP, Passes | 0.00 | — |
| 10 | `shot_quality_gap` | 效率撕裂 | xG/shot差>=2倍 | xG, Shots | 0.00 | — |
| 11 | `corner_efficiency` | 效率撕裂 | 角球进球>=2 | Corners, Events | 0.00 | — |
| 12 | `big_chance_conversion` | 效率撕裂 | 绝佳机会错失>60% | Big Chances, Goals | 0.00 | — |
| 13 | `one_man_team` | 个人英雄/罪人 | 单人进球>=75% | Goals(player) | 0.00 | — |
| 14 | `gk_hero` | 个人英雄/罪人 | 扑救>=5且xGOT>2 | Saves, xGOT(opp) | 0.00 | — |
| 15 | `gk_disaster` | 个人英雄/罪人 | 丢球>=3且扑救率<50% | Saves, GA | 0.80 | YES |
| 16 | `super_sub` | 个人英雄/罪人 | 替补G+A>=3分 | Events(subst), Goals | 0.00 | — |
| 17 | `fatal_error` | 个人英雄/罪人 | 致命失误>0 | ErrToGoal | 0.00 | — |
| 18 | `rating_paradox` | 个人英雄/罪人 | 评分>7.5基础数据差 | Rating, Stats | 0.00 | — |
| 19 | `wing_domination` | 结构问题 | 传中差>=2.5倍 | Crosses | 0.00 | — |
| 20 | `attack_channel_bias` | 结构问题 | 单路进攻>50% | Channels | 0.00 | — |
| 21 | `aerial_domination` | 结构问题 | 头球差>=2倍 | Aerials | 0.00 | — |
| 22 | `tactical_fouls` | 结构问题 | 犯规>=5黄牌<=2 | Fouls, Yellows | 0.00 | — |
| 23 | `sub_timing_impact` | 结构问题 | 换人<30或>=85 | Events(subst) | 0.30 | YES |
| 24 | `formation_mismatch` | 结构问题 | 禁区外射>1.5x内 | Shots in/out | 0.00 | — |
| 25 | `mirror_match` | 叙事钩子 | 5+指标差<25% | Multi stats | 0.00 | — |
| 26 | `high_scoring` | 叙事钩子 | 总进球>=5 | Score | 1.00 | YES |
| 27 | `clean_sheet` | 叙事钩子 | 一方零封 | Score | 0.00 | — |
| 28 | `comeback` | 叙事钩子 | 落后最终逆转取胜 | Score, Events | 0.70 | YES |
| 29 | `draw_drama` | 叙事钩子 | 平局但xG差>0.5 | Score, xG | 0.00 | — |
| 30 | `rare_event` | 叙事钩子 | 3+门框/2+红牌 | Woodwork, Red | 0.00 | — |
| 31 | `halftime_adjustment` | 淘汰赛专项 | 半场射门控球逆转 | Period stats | 1.00 | YES |
| 32 | `extra_time_collapse` | 淘汰赛专项 | 加时射门率降>50% | Events, Shots | 0.00 | — |
| 33 | `penalty_shootout_hero` | 淘汰赛专项 | 点球大战有罚失 | Events(shootout) | 0.00 | — |
| 34 | `lead_protect_mode` | 淘汰赛专项 | 控球55%->45% | Poss(trends) | 0.00 | — |
| 35 | `et_sub_impact` | 淘汰赛专项 | 加时赛有换人 | Events(subst) | 0.00 | — |
| 36 | `diff_stage_rhythm` | 淘汰赛专项 | 阶段射门差>=3倍 | Events, Periods | 0.00 | — |
| 37 | `period_goal_cluster` | 淘汰赛专项 | 单15min3+进球 | Events, Periods | 1.00 | YES |
| 38 | `dominant_et` | 淘汰赛专项 | 加时射门>=3倍对手 | Shots, Events | 0.00 | — |
| 39 | `offensive_king` | 球员贡献王 | 7攻+事件加成(外场) | G.A.xG.SoT.KP.Drb.P3rd | 1.00 | YES |
| 40 | `defensive_king` | 球员贡献王 | 6防加权(外场) | TkW.Int.Clr.Blk.Rec.DuW | 1.00 | YES |
| 41 | `balanced_king` | 球员贡献王 | 调和平均(攻x防) | 攻分,防分 | 0.90 | YES |
| 42 | `rhythm_swing` | 趋势驱动 | 节奏转换>=3次 | Trends | 0.00 | — |
| 43 | `duel_decay_alert` | 趋势驱动 | 对抗衰减>20% | Trends(duels) | 0.00 | — |
| 44 | `stamina_fade` | 趋势驱动 | 压迫衰减>20% | Trends(press) | 0.00 | — |
| 45 | `tactical_shift` | 趋势驱动 | 传球风格显著变化 | Trends | 0.00 | — |
| 46 | `turning_point_alert` | 趋势驱动 | 转折点>=3 | Trends | 1.00 | YES |
| 47 | `momentum_surge` | 趋势驱动 | 进攻速率急升 | Trends | 0.52 | YES |
| 48 | `sub_impact_on_trend` | 事件x趋势 | 换人前后趋势变化 | Events+Trends | 1.00 | YES |
| 49 | `red_card_collapse` | 事件x趋势 | 红牌后趋势断崖 | Events+Trends | 0.00 | — |
| 50 | `goal_momentum_shift` | 事件x趋势 | 进球后动量逆转 | Events+Trends | 0.32 | YES |
| 51 | `var_disruption` | 事件x趋势 | VAR后趋势停顿 | Events+Trends | 0.00 | — |
| 52 | `event_coincident_inflection` | 事件x趋势 | 事件与转折点<3min | Events+Trends | 1.00 | YES |

---
*生成时间: 2026-06-04 | 数据: SportMonks V3 | fixture_id: 19683240*