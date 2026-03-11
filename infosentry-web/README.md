# infoSentry Web

`infosentry-web/` 是 infoSentry 的前端应用，负责用户登录、Goals 配置、Sources 管理、Inbox 查看、开发者设置与日常反馈操作。

技术栈：

- Next.js 15 App Router
- TypeScript
- Tailwind CSS
- TanStack Query
- React Hook Form + Zod

## 前端负责什么

前端的职责不是展示营销页，而是提供一套克制、可靠、以任务完成为导向的操作界面，让用户能完成这些关键动作：

- 登录并管理账户
- 创建、编辑、查看 Goals
- 管理 Sources 与订阅状态
- 查看 Inbox / Notifications
- 提交 like / dislike / block source 反馈
- 管理 API Keys 与开发者接入

## 快速开始

1. 安装依赖：

```bash
npm install
```

2. 配置环境变量：

```bash
cp .env.example .env.local
```

示例：

```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

3. 启动开发服务器：

```bash
npm run dev
```

默认访问地址：

- App: `http://localhost:3000`

如果你从仓库根目录联动开发，优先使用：

```bash
make dev
```

## 页面结构

```text
src/
├── app/
│   ├── (dashboard)/        # 登录后主界面
│   │   ├── goals/          # Goal 列表、创建、编辑、详情
│   │   ├── sources/        # 信息源管理
│   │   ├── inbox/          # 通知与反馈
│   │   └── settings/       # 用户设置、开发者能力
│   ├── auth/               # 认证回调
│   └── login/              # 登录页
├── components/
│   ├── layout/             # 布局组件
│   └── ui/                 # 基础 UI 组件
├── contexts/               # Auth / Query / Theme
├── hooks/                  # 页面级数据获取与交互封装
├── lib/
│   ├── api/                # API 客户端
│   └── utils/              # 工具函数
└── types/                  # 类型定义
```

## UI 原则

这个前端遵循仓库既定的产品风格：

- 内容优先，不做装饰性页面
- 清晰、克制、稳定，避免视觉噪音
- 优先保证表单、列表、状态切换、反馈链路可用
- 设计与实现遵循 [`../docs/dev/FRONTEND_CONVENTIONS.md`](/Users/ray/Documents/code/infoSentry/docs/dev/FRONTEND_CONVENTIONS.md)

## 开发命令

```bash
npm run dev
npm run build
npm run start
npm run lint
```

仓库要求的前端交付检查：

```bash
npm run lint
npm run build
```

## 当前覆盖的主要功能

- Magic Link 登录
- Goal 列表、创建、编辑、详情
- Goal 邮件发送入口
- Sources 列表与新增
- Inbox / Notifications 展示与反馈
- Settings / Developers / API Keys

## 相关文档

- 仓库入口：[`../README.md`](/Users/ray/Documents/code/infoSentry/README.md)
- 后端说明：[`../infoSentry-backend/README.md`](/Users/ray/Documents/code/infoSentry/infoSentry-backend/README.md)
- 前端规范：[`../docs/dev/FRONTEND_CONVENTIONS.md`](/Users/ray/Documents/code/infoSentry/docs/dev/FRONTEND_CONVENTIONS.md)
