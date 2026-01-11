# 关键决策记录（Decision Log）

目的：把所有会影响实现/体验/成本的关键决策写下来，避免口头约定丢失，便于回溯与复盘。

---

## 2025-12-28：v0 关键决策（已确认）

### 产品定位
- Email-first：主要消费在邮件；Web 端负责配置/查看/反馈
- 单人自用为主，但设计上保留未来扩展（非强制）

### v0 范围
- Query 不进 v0
- 不做简历文件上传解析（只做多行 terms）
- 不做全文抓取存储（只存元数据+摘要+embedding）
- 不做 source groups、block keyword（后续版本）

### 默认源与抓取频率
- 默认源：30–40 条
- 默认源抓取：30min
- RSS 抓取：15min

### 邮件通道
- SMTP（Gmail）
- SMTP 相关配置由用户自行处理，系统实现 EmailProvider 抽象

### 时间与调度（中国时间）
- Digest：每日 09:00（Asia/Shanghai）
- Batch 窗口：默认 12:30、18:30；每Goal最多 3 个窗口（可配置）
- 不做夜间静默（v0）

### 推送策略（反对硬 cap）
- 不接受"每日最多 N 封 Trigger"这种硬 cap（会压掉真正高价值信息）
- 替代方案：三层推送 + 合并/单封长度上限
  - Immediate：5分钟合并，最多3条/封
  - Batch：每窗口每Goal最多8条/封
  - Digest：每日 top10/Goal 兜底

### 超高价值定义来源（用户补充信息优先）
- 每个 Goal 除描述外允许用户补充多行 terms
- 若用户填了补充信息：作为超高价值的优先匹配标准（priority_terms）
- 若用户没填：使用 description 作为超高价值依据（通过语义匹配与源信任、边界LLM判别）

### priority_mode
- STRICT：不命中 priority_terms 不得 Immediate
- SOFT：priority_terms 加分偏好，不强制

### Agent 定位与触发方式（v0）
- Agent 责任范围：推送调度 + 边界判别（不负责抓取）
- Immediate：事件触发（MatchComputed），由 Agent 最终判别
- Batch/Digest：窗口触发（BatchWindowTick / DigestTick）

### LLM 采用方式（边界判别，不做重型 Agent）
- v0 采用"规则 + LLM边界分类器"
- 仅对边界区间调用 LLM（示例：0.88–0.93）
- LLM 输出必须 JSON（label + reason），失败降级为保守结果（BATCH/IGNORE）
- 规则守门永远优先执行（block_source/negative 禁止 Immediate）

---

## 参数默认值（v0 建议，可调）

| 参数 | 默认值 | 说明 |
|------|--------|------|
| 候选线 | match_score >= 0.75 | 低于此分数不进入推送决策 |
| 规则直通 Immediate | match_score >= 0.93 | 且通过守门规则 |
| 边界区间 | 0.88–0.93 | 调用 LLM 判别 |
| Digest min | 0.60 | 防噪音，可调 |
| Immediate 合并窗口 | 5 分钟 | 最多 3 条/封 |
| Batch 单封上限 | 8 条 | 每窗口每Goal |
| Digest 单Goal上限 | 10 条 | 每日 |

---

## 待未来版本复议的决策点

### v1 待定
- [ ] 是否引入夜间静默
- [ ] 是否支持 block keyword
- [ ] 是否引入 source groups
- [ ] Goal Health 建议的交互方式

### v2 待定
- [ ] 是否引入多渠道推送（Telegram/Slack）
- [ ] 是否引入多用户与配额
- [ ] 是否引入简历上传解析（取决于产品方向）
- [ ] Source Plugin 接口设计

### v3 待定
- [ ] 插件 marketplace 架构
- [ ] 团队权限模型
- [ ] Workflow 输出范围与安全边界

---

## 决策更新日志

| 日期 | 决策 | 变更说明 | 决策人 |
|------|------|----------|--------|
| 2025-12-28 | v0 初始决策 | 首次记录 | - |

---

## 如何使用本文档

1. **新增决策**：在对应版本区块下添加，包含背景、选项、最终决定、理由
2. **变更决策**：不删除原决策，在下方追加"[变更]"记录
3. **每次迭代复盘**：检查是否有需要更新的决策点
4. **查阅历史**：通过 git blame 查看每条决策的添加时间

