# infoSentry Web

infoSentry 的前端应用，基于 Next.js 15 构建。

## 技术栈

- **框架**: Next.js 15 (App Router)
- **语言**: TypeScript
- **样式**: Tailwind CSS
- **状态管理**: React Query (TanStack Query)
- **表单**: React Hook Form + Zod
- **图标**: Lucide React

## 开始使用

### 1. 安装依赖

```bash
npm install
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env.local`：

```bash
cp .env.example .env.local
```

编辑 `.env.local`，配置 API 地址：

```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

### 3. 启动开发服务器

```bash
npm run dev
```

访问 [http://localhost:3000](http://localhost:3000)

## 项目结构

```
src/
├── app/                    # Next.js App Router 页面
│   ├── (dashboard)/        # 需要登录的页面
│   │   ├── goals/          # 目标管理
│   │   ├── sources/        # 信息源管理
│   │   ├── inbox/          # 收件箱
│   │   └── settings/       # 设置
│   ├── auth/               # 认证回调
│   └── login/              # 登录页面
├── components/             # 组件
│   ├── layout/             # 布局组件
│   └── ui/                 # 基础 UI 组件
├── contexts/               # React Context
├── hooks/                  # 自定义 Hooks
├── lib/                    # 工具库
│   ├── api/                # API 客户端
│   ├── constants.ts        # 常量
│   └── utils/              # 工具函数
└── types/                  # TypeScript 类型定义
```

## 设计原则

本项目遵循克制、专业、内容优先的设计原则：

- **无花哨效果**: 不使用渐变、玻璃拟态、过强阴影
- **功能性优先**: 每个元素都有明确用途
- **一致的视觉语言**: 统一的间距、颜色、圆角规范
- **高对比度**: 确保可访问性（WCAG AA）

详细设计规范见 `/docs/dev/FRONTEND_CONVENTIONS.md`

## 可用脚本

```bash
npm run dev      # 启动开发服务器
npm run build    # 构建生产版本
npm run start    # 启动生产服务器
npm run lint     # 运行 ESLint
```

## 功能清单

- [x] Magic Link 登录
- [x] Goal 列表 + 状态过滤
- [x] Goal 创建/编辑
- [x] Goal 详情：高分 Items、反馈按钮
- [x] RSS 信息源管理（增删启停）
- [x] Inbox 收件箱：展示推送 + 反馈操作
