# 信息追踪 Agent（Goal Tracking Agent）PRD v0（MVP 交付版）

版本：v0  
日期：2025-12-28  
目标：两周上线可运行、可回溯、可迭代的 Agent 项目  
交互：Web + Email（SMTP）

---

## 1. v0 目标与边界

### 1.1 v0 目标
- 跑通端到端闭环：抓取 → 入库 → 匹配 → Agent 决策 → 推送 → 点击统计 → 反馈收敛
- 三层推送：Immediate（事件触发）/ Batch（窗口触发）/ Digest（每日 09:00 CST）
- Push Orchestrator Agent 在生产链路做最终判别（并可回放、可降级）

### 1.2 明确不做（v0）
- Query（Goal-scoped）
- block keyword、source groups
- 全文抓取与存储
- 简历文件上传解析（只做"多行 terms"补充）
- 多用户协作/权限体系
- 自动执行高风险动作

---

## 2. 核心概念与默认配置

### 2.1 Source
- 默认源：30–40 条（配置化）
- 抓取频率：默认源 30min；RSS 15min

### 2.2 Goal（v0 最小模型）
- name（必填）
- description（必填；可只填它）
- priority_terms（可选）：多行文本，每行一个 term（技能/品牌/公司等）
- priority_mode：STRICT / SOFT
  - STRICT：不命中 priority_terms 禁止 Immediate
  - SOFT：priority_terms 作为偏好/加分，不强制
- batch_windows：最多 3 个（默认 12:30、18:30，中国时间）
- digest_send_time：09:00（中国时间，v0 全局）

### 2.3 推送三桶
- IMMEDIATE：事件触发，超高价值（可合并）
- BATCH：窗口合并推送（每窗口每Goal一封）
- DIGEST：每日汇总兜底

### 2.4 合并与长度控制（代替"硬 cap"）
- Immediate：5分钟合并，单封最多 3 条
- Batch：单封每Goal最多 8 条
- Digest：每Goal默认 top 10

---

## 3. 端到端流程（v0）

### 3.1 Ingest（抓取→入库）
1) ingest_job 拉取 sources（默认源 / RSS）
2) 解析 items（title/url/published_at/snippet/source）
3) URL 去重入库
4) 生成 embedding（批处理）
5) 产出 ItemIngested 事件（或进入队列）

### 3.2 Match（匹配→候选）
1) match_job 消费新 items
2) 对每个 active goal 计算 match_score + match_reasons（基础版）
3) 写入 goal_item_matches
4) 触发 MatchComputed(goal_id,item_id,score,features)

### 3.3 Immediate（事件触发 + Agent 最终判别）
1) immediate_agent_job 处理 MatchComputed
2) 规则守门（block_source/negative 禁止 Immediate；STRICT需命中 priority_terms）
3) 规则分桶（>=0.93 → Immediate；>=0.75 → Batch；否则 Ignore）
4) 边界区间（0.88–0.93）调用 LLM 判别 IMMEDIATE/BATCH（JSON）
5) 写 push_decisions；若 Immediate 则进入 coalesce_buffer 并在 5min 内合并发送

### 3.4 Batch（窗口触发）
1) 每Goal按 batch_windows 触发 batch_agent_run
2) 从 batch_queue 拉取候选（未发送、未 block、在时间窗）
3) 排序（score+recency+term hits）
4) 选 top <= 8 合并成 1 封邮件发送
5) 标记 push_decisions 为 SENT_BATCH

### 3.5 Digest（每日 09:00 CST）
1) digest_scheduler 09:00 触发
2) 汇总未被 immediate/batch 消费、且 score≥digest_min（默认 0.60）
3) 每Goal top 10，合并成 Digest 发出
4) 标记 SENT_DIGEST

### 3.6 点击与反馈
- redirect：/r/{item_id}?goal_id=xx 记录 click_events 后 302
- feedback：like/dislike、block_source 立即影响后续过滤与排序（至少影响 push 决策输入）

---

## 4. Push Orchestrator Agent（v0 设计）

### 4.1 Agent 职责边界（v0）
- 负责：推送调度与边界判别（Immediate事件 + Batch窗口）
- 不负责：抓取、入库、DB写入（除写决策记录）；不直接生成HTML邮件（用模板系统）

### 4.2 Agent 可控性要求
- 输入输出强制 JSON Schema 校验
- 记录 agent_runs（可回放）
- 失败/超时可降级（默认保守：BATCH/IGNORE）

### 4.3 LLM 边界判别接口（v0）
仅对边界样本调用，输出必须：
- label: IMMEDIATE | BATCH
- reason: <=120字，必须引用结构化证据（命中哪些 term/来源/发布时间等）

---

## 5. 数据模型（v0 最小集）

### 5.1 表清单
- users, login_tokens, sessions
- sources（default/rss）
- items（title,url,snippet,summary,source_id,published_at,embedding）
- goals（name,description,status,time_window_days）
- goal_push_configs（priority_mode,batch_windows,digest_send_time）
- goal_priority_terms（goal_id, term, term_type=must|negative）
- goal_item_matches（goal_id,item_id,match_score,match_reasons_json,computed_at）
- push_decisions（goal_id,item_id,decision,status,reason_json,decided_at,sent_at,channel）
- agent_runs（run_id,goal_id,run_type,inputs_json,outputs_json,status,latency_ms,llm_used,fallback）
- blocked_sources, item_feedback, click_events
- ingest_logs（可选但建议）

---

## 6. Web 信息架构（v0）

### 6.1 页面
1) 登录页（Magic Link）
2) Goal 列表页
3) Goal 编辑页（v0 核心）
   - name/description
   - priority_terms（多行）
   - priority_mode（STRICT/SOFT）
   - batch_windows（最多3）
4) Goal 详情页
   - 高分 items 列表（score desc + time desc）
   - reasons 展示
   - like/dislike/block source
5) RSS 管理页（增/启停/删）

---

## 7. 邮件设计（v0）

### 7.1 Immediate
- Subject: [Goal:{name}] 高优先级更新（{n}条）
- Body: 每条 title + 1句摘要 + reason + redirect link
- 合并：5min 内最多 3 条

### 7.2 Batch
- Subject: [Goal:{name}] 窗口更新（{HH:MM}）
- Body: top<=8 条，按相关度排序，每条附 reason
- 频率：按每Goal窗口发送

### 7.3 Digest
- Subject: 信息追踪 Digest（YYYY-MM-DD）
- Body: 按Goal分段 top10

---

## 8. 埋点与日志（v0）

事件（带 goal_id）：
- goal_created/updated/paused/resumed/archived
- item_ingested_success/fail（source_id）
- item_matched（goal_id,item_id,score）
- agent_run_started/success/fail（run_type）
- push_sent_immediate/batch/digest（goal_id,count）
- item_clicked（goal_id,channel）
- feedback_like/dislike/block_source（goal_id）
- llm_call（purpose=urgency_judge, tokens_est）

---

## 9. 验收标准（DoD）

必须满足：
- Goal 只填 description 也可跑通
- ingest → match → immediate agent decision → 邮件发送 OK
- Immediate 合并、幂等去重、不会重复轰炸
- Batch：每Goal窗口可配置（<=3），窗口发送一封合并
- Digest：每日 09:00 CST 按时发送
- block_source 立即生效（后续不再推）
- agent_runs 可回放；LLM 挂了系统可降级继续运行

---

## 10. 上线清单（Runbook v0 简版）

- 时区：所有调度使用 Asia/Shanghai（中国时间）；DB 存 UTC
- 环境变量：DB/Redis/SMTP/LLM keys
- 迁移：db migrate 一键
- 监控：抓取失败、队列积压、发信失败、LLM调用量
- 回滚：
  - 关闭 immediate_agent_job（仅 Batch/Digest）
  - 或关闭 push（仅入库+Web查看）

