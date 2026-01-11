# infoSentry 项目上下文

> Lead Agent 的项目知识库，提供项目概述和技术栈信息。
> 详细信息请检索 `docs/` 目录下的文档。

---

## 📌 项目概述

**infoSentry** 是一个信息追踪系统（Goal Tracking Agent），帮助用户追踪感兴趣的信息源，并智能推送相关内容。

### 核心流程

```
信息源抓取 → 去重入库 → 向量化 → 目标匹配 → Agent 决策 → 推送通知
```

### 三层推送机制

| 推送类型 | 触发方式 | 说明 |
|---------|---------|------|
| **Immediate** | 事件触发 | 超高价值内容，5分钟合并窗口 |
| **Batch** | 窗口触发 | 每个窗口合并推送（最多3个窗口/天） |
| **Digest** | 每日 09:00 | 每日汇总兜底 |

---

## 🛠️ 技术栈

### 后端 (`infoSentry-backend/`)

| 层级 | 技术 |
|------|------|
| Web 框架 | FastAPI |
| 任务队列 | Celery + Redis |
| 数据库 | PostgreSQL + pgvector |
| ORM | SQLAlchemy 2.0 (async) |
| 迁移 | Alembic |
| AI | OpenAI API (embedding + LLM) |
| 邮件 | SMTP |

**架构风格**：DDD（领域驱动设计）模块化单体

```
src/
├── core/           # 核心基础设施
│   ├── domain/     # 领域基类
│   ├── infrastructure/  # 基础设施（DB、Redis、Celery）
│   └── interfaces/      # HTTP 接口基类
└── modules/        # 业务模块
    ├── users/      # 用户认证
    ├── sources/    # 信息源管理
    ├── items/      # 内容条目
    ├── goals/      # 追踪目标
    ├── agent/      # Agent Runtime
    └── push/       # 推送决策
```

### 前端 (`infosentry-web/`)

| 技术 | 版本/说明 |
|------|----------|
| 框架 | Next.js 15 (App Router) |
| 语言 | TypeScript (strict) |
| 样式 | Tailwind CSS |
| 状态 | React Query + Context |
| 表单 | React Hook Form + Zod |
| UI 组件 | shadcn/ui |

---

## 📂 关键文档索引

| 文档 | 路径 | 内容 |
|------|------|------|
| 产品需求 | `docs/product/PRD_v0.md` | 功能范围、推送规则、验收标准 |
| 技术规格 | `docs/specs/TECH_SPEC_v0.md` | 架构、数据模型、API 设计 |
| 架构决策 | `docs/decisions/ARCHITECTURE_DECISIONS.md` | ADR 记录 |
| 前端规范 | `docs/dev/FRONTEND_CONVENTIONS.md` | 前端开发规范（详细） |
| Agent 运行时 | `docs/agents/AGENT_RUNTIME_SPEC.md` | Push Agent 设计 |

---

## 🏗️ 模块边界

### 已完成模块（v0）

- ✅ 用户认证（Magic Link）
- ✅ 信息源管理（NewsNow / RSS / SITE）
- ✅ 内容抓取与去重
- ✅ 向量化与匹配
- ✅ Agent 决策（Immediate / Batch / Digest）
- ✅ 邮件推送
- ✅ 反馈系统（like / dislike / block）

### v0 明确不做

- ❌ 全文抓取与存储
- ❌ 多用户协作/权限体系
- ❌ 自动执行高风险动作
- ❌ Query（Goal-scoped 搜索）

---

## ⚠️ 重要约束

1. **预算控制**：LLM 月成本 ≤ $10
2. **单机部署**：2c4g VM，不做微服务
3. **时区**：调度使用 Asia/Shanghai，DB 存 UTC
4. **降级策略**：LLM 失败时保守降级到 Batch

---

## 🔗 快速链接

- 后端入口：`infoSentry-backend/main.py`
- 前端入口：`infosentry-web/src/app/`
- 数据库模型：`src/modules/*/infrastructure/models.py`
- Celery 任务：`src/modules/*/tasks.py`
