# infoSentry AI Agents 开发辅助系统

> 一套 AI Agent 协作系统，用于辅助 infoSentry 项目的开发、设计与文档维护。

---

## 🎯 系统概述

本系统包含 5 个专业 Agent，由 **Lead Agent** 统一调度：

| Agent | 目录 | 职责 |
|-------|------|------|
| **Lead** | `lead/` | 项目管理、需求评估、任务分派、验收交付 |
| **Frontend** | `frontend/` | 前端开发（Next.js + TypeScript + Tailwind） |
| **Backend** | `backend/` | 后端开发（FastAPI + DDD + Celery） |
| **UI Design** | `ui-design/` | UI/UX 设计（设计系统、组件规范） |
| **Docs** | `docs/` | 文档维护（PRD、Tech Spec、ADR） |

---

## 🚀 使用方式

### 1. 与 Lead Agent 交流（推荐入口）

将 `agents/lead/agent.md` 作为 Cursor Rules 使用，Lead Agent 会：
- 评估你的需求是否合理
- 必要时否决不合理的提议并说明原因
- 调用其他专业 Agent 完成具体工作
- 验收并交付成果

### 2. 直接与专业 Agent 交流

如果你明确知道需要哪个 Agent，可以直接使用对应的 `agent.md`：
- `agents/frontend/agent.md` - 前端开发任务
- `agents/backend/agent.md` - 后端开发任务
- `agents/ui-design/agent.md` - UI 设计任务
- `agents/docs/agent.md` - 文档编写任务

---

## 📁 目录结构

```
agents/
├── README.md                           # 本文件
│
├── lead/                               # 主 Agent
│   ├── agent.md                        # 角色定义
│   ├── project-context.md              # 项目上下文
│   ├── decision-framework.md           # 决策框架
│   ├── acceptance-checklist.md         # 验收清单
│   └── workflow.md                     # 工作流程
│
├── frontend/                           # 前端 Agent
│   ├── agent.md                        # 角色定义
│   ├── conventions.md                  # 开发规范
│   ├── patterns.md                     # 常用模式
│   ├── anti-patterns.md                # 反模式
│   ├── checklist.md                    # 审查清单
│   └── examples/                       # 示例代码
│
├── backend/                            # 后端 Agent
│   ├── agent.md                        # 角色定义
│   ├── conventions.md                  # 开发规范
│   ├── architecture.md                 # 架构指南
│   ├── patterns.md                     # 常用模式
│   ├── anti-patterns.md                # 反模式
│   ├── checklist.md                    # 审查清单
│   └── examples/                       # 示例代码
│
├── ui-design/                          # UI 设计 Agent
│   ├── agent.md                        # 角色定义
│   ├── design-system.md                # 设计系统
│   ├── components.md                   # 组件规范
│   ├── accessibility.md                # 可访问性
│   ├── anti-patterns.md                # 反模式
│   └── references/                     # 参考设计
│
└── docs/                               # 文档 Agent
    ├── agent.md                        # 角色定义
    ├── style-guide.md                  # 风格指南
    ├── structure.md                    # 结构规范
    └── templates/                      # 文档模板
```

---

## 🔗 相关文档

项目核心文档位于 `docs/` 目录：
- `docs/product/PRD_v0.md` - 产品需求文档
- `docs/specs/TECH_SPEC_v0.md` - 技术规格
- `docs/decisions/ARCHITECTURE_DECISIONS.md` - 架构决策记录
- `docs/dev/FRONTEND_CONVENTIONS.md` - 前端开发规范（详细版）

---

## 📝 更新日志

| 日期 | 内容 |
|------|------|
| 2026-01-08 | 初始版本，创建 Agent 系统结构 |
