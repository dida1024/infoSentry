# Goal Matches 接口超时：问题定位与长期稳定修复方案

## 1. 背景与目标

### 1.1 线上症状

线上调用接口：

- `GET /api/v1/goals/{goal_id}/matches`

出现现象：

- 请求经常超时（客户端超时/网关 502）
- 同一个参数在不同时刻响应时间抖动非常大

### 1.2 本文目标

本文用于评审以下内容：

1. 问题是什么（现象与影响）
2. 问题怎么定位出来（排查思路与证据链）
3. 根因是什么（代码路径与复杂度）
4. 为什么临时方案不够
5. 长期稳定方案（架构、迁移、回滚、验收）

---

## 2. 现状与影响

### 2.1 影响范围

- 直接影响：`/goals/{goal_id}/matches` 列表查询
- 间接影响：前端目标详情页、人工检查匹配结果流程
- 风险：
  - 用户体验不稳定（频繁转圈/失败）
  - 网关/应用连接占用上升
  - 高并发时可能放大为局部雪崩

### 2.2 业务影响

- 查询接口不可用会干扰“匹配质量”反馈闭环
- 排查推送误报时，难以稳定拿到匹配样本

---

## 3. 问题定位过程（思路）

定位遵循从外到内、先排除再确认：

1. 先确认网络与网关可达
2. 再确认鉴权是否异常
3. 再看业务查询路径是否存在高复杂度
4. 最后判断是否是数据库层慢查询触发超时

### 3.1 第一步：排除“服务不可达”

无鉴权访问同路径可快速返回 401，说明：

- 域名解析正常
- 网关可达
- 应用进程可响应

结论：不是纯网络故障。

### 3.2 第二步：对比参数影响

同接口在不同过滤条件下，响应差异明显：

- 高过滤（例如高 `min_score`）可较快返回
- 常规查询（默认过滤）容易超时或返回 502

结论：超时与“候选数据规模/查询计划”高度相关。

### 3.3 第三步：代码路径排查

关键路径（应用层）：

- `src/modules/goals/application/services.py`
  - `list_matches(...)`
  - `_list_matches_deduped_by_topic(...)`

关键点：

- 目前实现会为了去重，循环拉取多页候选后再在 Python 侧去重
- 每次分页查询批量大小为 `MATCH_ITEMS_RECENT_PAGE_SIZE=500`

关键配置：

- `src/core/config.py`
  - `MATCH_ITEMS_RECENT_PAGE_SIZE: int = 500`

关键底层查询（仓储层）：

- `src/modules/items/infrastructure/repositories.py`
  - `list_by_goal(...)`

该查询包含：

- `count(...) over()` 窗口计数
- 按 rank 模式排序（含 join + 计算）
- `offset/limit` 分页

结论：应用层“全量候选拉取 + 去重”叠加仓储层“重查询 + offset 翻页”，导致大数据量 goal 下稳定性差。

---

## 4. 根因分析（Root Cause）

### 4.1 直接根因

`matches` 去重在应用层实现为“先尽可能取全量，再分页返回”，导致：

1. 请求第一页也可能扫描大量历史匹配
2. 查询耗时与历史数据量线性甚至超线性增长
3. 触发网关超时后返回 502/超时

### 4.2 复杂度问题

当前模式的代价可简化为：

- 多次调用 `list_by_goal(offset/limit)`
- 每页都要执行排序/窗口计数
- 总体接近“按页累计偏移扫描”

当 `goal` 历史匹配量达到万级后，查询波动显著，出现偶发成功 + 偶发超时的抖动特征。

### 4.3 为什么会“有时 0.6s、有时 25s”

典型原因是：

- 不同请求命中不同实例/不同缓存状态
- 数据库瞬时负载与并发不同
- 同 SQL 在不同统计信息下执行计划差异

这类抖动是慢查询系统在边界容量附近常见表现，不是随机网络问题。

---

## 5. 方案评估（为什么不是临时修）

### 5.1 已排除的临时方案

1. 应用层扫描上限（只扫描前 N 条）
  - 优点：改动快
  - 缺点：结果不完整，分页/total 语义不稳定

2. 关闭去重
  - 优点：性能回升
  - 缺点：重复问题回归，业务目标未满足

3. 单纯加缓存
  - 优点：热点可缓解
  - 缺点：冷查询仍慢；失效策略复杂；不能解决根因

### 5.2 长期方案原则

1. 去重下沉到 SQL（数据库擅长做分组/排序）
2. 请求复杂度与“页大小”相关，而不是“历史总量”相关
3. 读语义固定（total、分页、排序可解释）
4. 迁移可回滚、可分阶段、不中断线上

---

## 6. 长期稳定方案（推荐）

## 6.1 数据模型升级

新增字段（建议）：

1. `items.topic_key`（`char(32)`）
  - 来源：canonical URL + hash
  - 用于统一主题粒度

2. `goal_item_matches.topic_key`（`char(32)`）
  - 冗余存储，避免读时 join `items`

3. `goal_item_matches.item_time`（`timestamptz`）
  - 值：`coalesce(items.published_at, items.ingested_at)`
  - 用于 `recent/hybrid` 排序，不再依赖 join

可选增强（建议）：

- `topic_key_version`（`smallint`，默认 1）
  - 为未来 canonical 规则升级留演进空间

## 6.2 写路径改造

1. Ingest 写 `items.topic_key`
2. Match upsert 时写 `goal_item_matches.topic_key/item_time`
3. 保持 DDD 方向：
  - `application` 负责业务编排与字段计算
  - `infrastructure` 负责持久化

## 6.3 读路径重写（核心）

新增仓储方法：

- `list_by_goal_deduped(...)`

SQL 思路：

1. 先按过滤条件拿候选（goal_id/min_score/since）
2. 根据 `rank_mode` 计算排序键
3. 用窗口函数去重：

```sql
row_number() over (
  partition by topic_key
  order by <rank_key> desc, match_score desc, computed_at desc
) as rn
```

4. 只取 `rn = 1` 后再 `limit/offset`
5. `total` 用同过滤条件下去重后的 count

这样请求第一页时不再需要应用层扫描全量历史。

## 6.4 索引设计

建议新增索引（按查询模式）：

1. `goal_item_matches(goal_id, topic_key, match_score desc, computed_at desc)`
2. `goal_item_matches(goal_id, item_time desc, match_score desc)`
3. `goal_item_matches(goal_id, computed_at desc)`
4. 可选 partial index：`where is_deleted = false`

目标：

- 降低排序与去重代价
- 让分页稳定命中索引路径

---

## 7. 迁移与上线方案

### 7.1 分阶段迁移（零停机）

Phase A：Schema 扩展（向前兼容）

1. Alembic 增列：`items.topic_key`、`goal_item_matches.topic_key/item_time`
2. 先允许 nullable
3. 建索引（大表建议并发创建）

Phase B：双写上线

1. 新写入路径开始填充上述字段
2. 老数据保持空值，不影响线上读

Phase C：历史回填

1. 批处理回填 `items.topic_key`
2. 批处理回填 `goal_item_matches.topic_key/item_time`
3. 分批按主键区间执行，避免长事务

Phase D：读路径切换

1. 将 `matches` 切到 SQL 去重查询
2. 验证稳定后保留旧路径一段时间用于回滚

Phase E：约束收敛

1. 回填完成后加 `NOT NULL`
2. 移除旧应用层全量去重逻辑

### 7.2 回滚策略

任一阶段可回退：

1. 读路径回滚到旧仓储查询
2. 新增列保留（不影响旧代码）
3. 双写可关闭，不影响主流程

---

## 8. 验收标准（SLO + 正确性）

### 8.1 性能

在目标数据规模（至少万级 match / goal）下：

1. `/matches` P95 < 500ms
2. `/matches` P99 < 1.5s
3. 超时率 < 0.1%

### 8.2 正确性

1. 去重后每个 `topic_key` 最多 1 条
2. `total` 为去重后的总数
3. `rank_mode` 语义不变（hybrid/match_score/recent）
4. 与现有鉴权和分页协议兼容

### 8.3 稳定性

1. 连续 7 天无该接口超时告警
2. 无 502 峰值异常

---

## 9. 可观测性与排障增强

上线时同步加监控：

1. API 指标：QPS、P50/P95/P99、4xx/5xx、timeout rate
2. SQL 指标：执行耗时、扫描行数、临时排序/磁盘排序比率
3. 业务指标：
  - 原始候选数
  - 去重后候选数
  - 去重率

日志建议：

- 为 `matches` 增加结构化日志字段：
  - `goal_id`
  - `rank_mode`
  - `raw_candidates`
  - `deduped_candidates`
  - `db_query_ms`

---

## 10. 实施拆分建议（便于评审与发布）

建议拆 3 个 PR：

1. PR-1：Schema + 双写
  - 新列、新索引、写路径填充
  - 不改读路径

2. PR-2：回填任务 + 监控埋点
  - 批处理脚本与运行手册

3. PR-3：读路径切换到 SQL 去重
  - 删除应用层全量去重逻辑
  - 增加性能回归测试

---

## 11. 结论

本次超时的根因不是网络，而是去重实现位置不当：

- 把“主题去重 + 分页”放在应用层全量扫描，导致大数据量下不可预测超时。

长期稳定解法是：

- 持久化 `topic_key`，
- 把去重与分页下沉到 SQL，
- 通过分阶段迁移实现无停机切换。

该方案能同时满足：

1. 性能稳定（请求复杂度与页大小相关）
2. 语义稳定（total/排序/分页可解释）
3. 维护稳定（有回滚、有监控、有演进空间）
