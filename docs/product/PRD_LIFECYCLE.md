# 信息追踪 Agent（Goal Tracking Agent）生命周期 PRD（Master PRD）

版本：Lifecycle v1.0  
日期：2025-12-28  
交互：Web + Email（SMTP）  
核心：Goal-first、少打扰、证据链、Agent 可控（结构化/守门/可回放/可降级）

---

## 1. 执行摘要

用户的真实需求不是"刷信息流"，而是围绕一个或多个明确目标（Goal）持续追踪信息：
- **超高价值**变化要立刻知道（Immediate）
- **中高价值**在空闲窗口合并推送（Batch）
- **其余内容**以 Digest 兜底（Daily Digest）

系统通过反馈闭环持续收敛，并坚持安全红线：不自动执行高风险动作（投递/下单等）。

---

## 2. 目标用户与场景（Lifecycle）

### 2.1 用户演进
- P0：单人自用（你本人）
- P1：信息密集型个人（求职/研究/产品/投资/技术跟踪）
- P2：小团队（竞品/市场/政策/安全情报）
- P3：组织级（可选）：更强权限、审计、合规模块（若商业化）

### 2.2 长期稳定的核心场景
- 远程岗位追踪：技术栈/公司/地区/薪资等变化
- AI 模型发布：官方 release / 关键 benchmark / 研究突破
- 电车新车/品牌动态：品牌、发布会、预售、量产节点
- 竞品/政策/安全漏洞：高价值变化预警

---

## 3. 北极星指标与阶段性 OKR

### 3.1 北极星指标（长期）
**Goal-level Weekly Value Delivered（每Goal每周交付价值）**  
代理指标（v0-v1）：每周有效点击/like 数（按 goal_id）

### 3.2 分阶段 OKR（建议）

#### v0（可用）：跑通闭环（Agent 在生产链路决策）
- O：Immediate/Batch/Digest 三层推送可用、可回溯、可降级
- KR：Agent success_rate ≥ 95%；48h 稳定运行；Weekly Useful Clicks > 0

#### v1（好用）：更准更省心
- O：降低噪音，提高 Immediate 质量
- KR：Immediate CTR +30%；负反馈率 -30%；漏报主观样本下降

#### v2（可增长）：可复用与扩散
- O：支持多用户、模板化 onboarding、扩源与多渠道
- KR：新用户首日 Goal 创建率 > 60%；周留存 > 30%（视实际调整）

#### v3（平台化，可选）：生态与工作流
- O：插件化源/渠道/渲染器，形成可扩展系统
- KR：第三方源接入成本下降；团队权限/审计可用（若需要）

---

## 4. 产品原则（长期不变）

1) 少打扰：即时推送只给超高价值  
2) 证据优先：判别/总结必须可追溯到 items  
3) Agent 可控：结构化输入输出、硬规则守门、失败可降级  
4) 成本可控：LLM 分层调用、边界才用、支持预算  
5) 安全红线：不自动执行高风险动作；防 prompt injection（隔离外部内容）

---

## 5. 能力地图（Capability Map）

### 5.1 信息获取层
- Source 管理：默认源、RSS、（v2）插件源
- 抓取质量：退避/熔断、去重、解析监控
- 内容处理：摘要、embedding、（v1+）语言检测/分类/实体抽取

### 5.2 Goal 模型层
- Goal 描述与约束：must/nice/negative（v0 可空）
- 超高价值标准：priority_terms + mode（STRICT/SOFT）
- 范围：all / selected sources /（v1+）groups /（v2+）topic filters

### 5.3 匹配与排序层
- v0：可解释 match_score + reasons
- v1：基于反馈动态调权、阈值建议
- v2：个性化 rerank（按Goal/用户习惯）

### 5.4 推送与渠道层（核心）
- v0：Immediate/Batch/Digest 三层推送（Email）
- v1：更细策略（静默、频率自适应、热点合并）
- v2：多渠道（Telegram/Slack/Mobile push 可选）

### 5.5 Agent 层（贯穿演进）
- v0：Push Orchestrator Agent（推送调度+边界判别）
- v1：Goal Health Agent（Goal 太宽/太窄/噪音源建议）
- v2：Source Quality Agent（源质量评分、淘汰/新增建议）
- v3：Workflow Agent（低风险工作流输出：周报/对比/趋势）

---

## 6. 生命周期路线图（摘要）

- v0：可用（闭环跑通、Agent 决策、三层推送）
- v1：好用（准确性、收敛、模板与健康建议）
- v2：可增长（多用户、扩源、多渠道、可运营）
- v3：平台化（插件生态、团队能力、工作流）

详细见 `/docs/product/ROADMAP.md`。

---

## 7. 生命周期指标体系（全景）

- Activation：创建Goal → 首封邮件点击 → 首次 like
- Retention：周活跃 Goal、连续点击周数
- Quality：Immediate CTR、负反馈率、漏报样本
- Efficiency：LLM 调用/成本、每Goal日均邮件封数
- Growth（v2+）：注册→创建Goal→首周留存、模板使用率

---

## 8. 风险与治理（全生命周期）

- 误报/打扰：三层推送 + 守门 + 反馈收敛
- 内容安全：输入隔离、引用限制、结构化输出
- 成本：分层调用、边界才用、预算与熔断
- 扩源噪音：源质量评分、自动建议淘汰/新增（v1+）
- 多用户合规：权限/数据隔离/审计（v2+）

---

## 9. 发布与复盘机制（每个迭代必须产出）

- Release notes：变更点/风险/回滚
- 指标看板：本迭代 3 个关键指标
- 复盘：假设是否成立、下一步调参/改设计
- Decision log：关键决策更新到 `/docs/decisions/DECISIONS.md`
