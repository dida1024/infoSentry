# 文档结构规范

> 项目文档的组织和管理

---

## 1. 目录结构

```
docs/
├── README.md                    # 文档索引
├── product/                     # 产品文档
│   ├── PRD_v0.md
│   ├── PRD_LIFECYCLE.md
│   ├── ROADMAP.md
│   └── ACCEPTANCE_CHECKLIST.md
├── specs/                       # 技术规格
│   ├── TECH_SPEC_v0.md
│   └── API_SPEC_v0.md
├── decisions/                   # 决策记录
│   ├── ARCHITECTURE_DECISIONS.md
│   └── DECISIONS.md
├── ops/                         # 运维文档
│   ├── DEPLOYMENT.md
│   └── RUNBOOK_VM.md
├── dev/                         # 开发规范
│   └── FRONTEND_CONVENTIONS.md
└── agents/                      # Agent 相关
    └── AGENT_RUNTIME_SPEC.md
```

---

## 2. 文档分类

### 2.1 产品文档

| 文档 | 用途 | 更新频率 |
|------|------|----------|
| PRD | 产品需求和功能边界 | 版本迭代时 |
| ROADMAP | 产品路线图 | 季度/月度 |

### 2.2 技术文档

| 文档 | 用途 | 更新频率 |
|------|------|----------|
| TECH_SPEC | 技术设计和数据模型 | 架构变更时 |
| API_SPEC | API 接口定义 | API 变更时 |
| ARCHITECTURE_DECISIONS | 架构决策记录 | 有决策时 |

### 2.3 开发文档

| 文档 | 用途 | 更新频率 |
|------|------|----------|
| FRONTEND_CONVENTIONS | 前端开发规范 | 规范变更时 |
| agents/backend/* | 后端开发规范 | 规范变更时 |

### 2.4 运维文档

| 文档 | 用途 | 更新频率 |
|------|------|----------|
| DEPLOYMENT | 部署指南 | 部署流程变更时 |
| RUNBOOK_VM | 运维操作手册 | 运维流程变更时 |

---

## 3. 版本控制

### 3.1 文档版本号

重要文档使用版本号：

```
PRD_v0.md      # v0 版本
PRD_v1.md      # v1 版本（如果需要）
```

### 3.2 版本头信息

每个版本化的文档包含：

```markdown
版本：v0.2
日期：2025-01-08
作者：xxx
```

### 3.3 更新日志

文档末尾记录变更：

```markdown
## 更新日志

| 日期 | 版本 | 变更 |
|------|------|------|
| 2025-01-08 | v0.2 | 添加 Agent 模块 |
| 2025-01-01 | v0.1 | 初始版本 |
```

---

## 4. 文档关系

```
PRD_v0.md
    ├── 引用 → TECH_SPEC_v0.md
    │           ├── 详细设计 → ARCHITECTURE_DECISIONS.md
    │           └── API 定义 → API_SPEC_v0.md
    │
    └── 规范 → FRONTEND_CONVENTIONS.md
              agents/backend/conventions.md
```

---

## 5. 命名规范

### 5.1 文件名

| 类型 | 规范 | 示例 |
|------|------|------|
| 规格文档 | `{TYPE}_v{N}.md` | `PRD_v0.md` |
| 规范文档 | `{NAME}_CONVENTIONS.md` | `FRONTEND_CONVENTIONS.md` |
| 指南文档 | `{NAME}.md` | `DEPLOYMENT.md` |
| 手册 | `RUNBOOK_{NAME}.md` | `RUNBOOK_VM.md` |

### 5.2 章节编号

使用数字编号：

```markdown
## 1. 概述
## 2. 详细设计
### 2.1 数据模型
### 2.2 API 设计
## 3. 实现计划
```

---

## 6. 搜索友好

### 6.1 关键词

在文档开头列出关键概念：

```markdown
# 技术规格

> 关键词：DDD, FastAPI, PostgreSQL, Celery, Agent
```

### 6.2 术语表

技术文档应包含术语定义：

```markdown
## 术语表

| 术语 | 定义 |
|------|------|
| Goal | 用户创建的追踪目标 |
| Item | 抓取到的信息条目 |
| Agent | 负责推送决策的 AI 系统 |
```

---

## 7. 临时文档

### 7.1 标记

临时文档在文件名或内容中标记：

```markdown
# Agent 设计问答（临时）

> ⚠️ 这是临时文档，完成后将被清理
```

### 7.2 清理

定期清理不再需要的临时文档。

---

## 8. 文档检查清单

新建文档时检查：

```
□ 文件名符合规范
□ 放在正确的目录
□ 包含版本和日期（如需要）
□ 有概述/简介
□ 结构清晰，章节编号
□ 与其他文档无冲突
□ 更新了相关文档的链接
```
