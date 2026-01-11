# infoSentry 前端开发规范

版本：v0  
日期：2025-01-07  
技术栈：Next.js 15 + TypeScript + Tailwind CSS

---

## 1. 技术选型

### 1.1 核心技术栈
- **框架**: Next.js 15 (App Router)
- **语言**: TypeScript 5.x (严格模式)
- **样式**: Tailwind CSS 3.x
- **UI 组件**: shadcn/ui (基于 Radix UI)
- **状态管理**: React Query (TanStack Query) + React Context
- **表单**: React Hook Form + Zod
- **HTTP 客户端**: Axios
- **图标**: Lucide React

### 1.2 开发工具
- **包管理**: pnpm
- **代码检查**: ESLint + Prettier
- **Git Hooks**: Husky + lint-staged
- **类型检查**: TypeScript strict mode

---

## 2. 目录结构

```
infoSentry-web/
├── app/                      # Next.js App Router 页面
│   ├── (auth)/               # 认证相关页面组
│   │   ├── login/
│   │   │   └── page.tsx
│   │   └── auth/
│   │       └── callback/
│   │           └── page.tsx
│   ├── (dashboard)/          # 主应用页面组（需要登录）
│   │   ├── layout.tsx        # 带侧边栏的布局
│   │   ├── goals/
│   │   │   ├── page.tsx      # Goal 列表
│   │   │   ├── new/
│   │   │   │   └── page.tsx  # 新建 Goal
│   │   │   └── [id]/
│   │   │       ├── page.tsx  # Goal 详情
│   │   │       └── edit/
│   │   │           └── page.tsx
│   │   ├── sources/
│   │   │   └── page.tsx      # RSS 管理
│   │   └── inbox/
│   │       └── page.tsx      # 收件箱
│   ├── r/
│   │   └── [itemId]/
│   │       └── route.ts      # 重定向追踪
│   ├── layout.tsx            # 根布局
│   ├── page.tsx              # 首页（重定向到 /goals）
│   └── globals.css           # 全局样式
├── components/               # 共享组件
│   ├── ui/                   # shadcn/ui 基础组件
│   │   ├── button.tsx
│   │   ├── card.tsx
│   │   ├── dialog.tsx
│   │   └── ...
│   ├── layout/               # 布局组件
│   │   ├── header.tsx
│   │   ├── sidebar.tsx
│   │   └── footer.tsx
│   ├── goals/                # Goal 相关业务组件
│   │   ├── goal-card.tsx
│   │   ├── goal-form.tsx
│   │   └── goal-item-list.tsx
│   ├── sources/              # Source 相关组件
│   │   ├── source-card.tsx
│   │   └── source-form.tsx
│   ├── inbox/                # Inbox 相关组件
│   │   ├── notification-card.tsx
│   │   └── feedback-buttons.tsx
│   └── shared/               # 通用业务组件
│       ├── loading-spinner.tsx
│       ├── error-boundary.tsx
│       └── empty-state.tsx
├── lib/                      # 工具库
│   ├── api/                  # API 客户端
│   │   ├── client.ts         # 基础 HTTP 客户端
│   │   ├── goals.ts          # Goals API
│   │   ├── sources.ts        # Sources API
│   │   ├── auth.ts           # Auth API
│   │   └── types.ts          # API 类型定义
│   ├── hooks/                # 自定义 Hooks
│   │   ├── use-goals.ts
│   │   ├── use-sources.ts
│   │   ├── use-auth.ts
│   │   └── use-notifications.ts
│   ├── utils/                # 工具函数
│   │   ├── cn.ts             # className 合并
│   │   ├── format.ts         # 格式化函数
│   │   └── validation.ts     # 校验函数
│   └── constants.ts          # 常量定义
├── contexts/                 # React Context
│   └── auth-context.tsx
├── types/                    # TypeScript 类型
│   ├── goal.ts
│   ├── source.ts
│   ├── notification.ts
│   └── user.ts
├── public/                   # 静态资源
│   ├── favicon.ico
│   └── images/
├── .env.example              # 环境变量示例
├── .env.local                # 本地环境变量（不提交）
├── next.config.ts            # Next.js 配置
├── tailwind.config.ts        # Tailwind 配置
├── tsconfig.json             # TypeScript 配置
├── package.json
└── pnpm-lock.yaml
```

---

## 3. 命名规范

### 3.1 文件命名
- **组件文件**: `kebab-case.tsx`（如 `goal-card.tsx`）
- **工具文件**: `kebab-case.ts`（如 `format.ts`）
- **类型文件**: `kebab-case.ts`（如 `goal.ts`）
- **页面文件**: `page.tsx`（Next.js 约定）
- **布局文件**: `layout.tsx`（Next.js 约定）

### 3.2 组件命名
- **React 组件**: `PascalCase`（如 `GoalCard`）
- **导出**: 默认导出命名组件

```tsx
// ✅ 推荐
export default function GoalCard({ goal }: GoalCardProps) {
  return <div>...</div>;
}

// ❌ 避免
export default ({ goal }) => <div>...</div>;
```

### 3.3 变量与函数命名
- **变量**: `camelCase`
- **常量**: `UPPER_SNAKE_CASE`
- **函数**: `camelCase`，动词开头
- **布尔值**: `is`/`has`/`can`/`should` 前缀
- **事件处理**: `handle` 前缀（如 `handleClick`）

### 3.4 类型命名
- **接口/类型**: `PascalCase`
- **Props 类型**: `ComponentNameProps`
- **API 响应**: `ComponentNameResponse`

```tsx
interface Goal {
  id: string;
  name: string;
  description: string;
}

interface GoalCardProps {
  goal: Goal;
  onEdit?: () => void;
}
```

---

## 4. 组件规范

### 4.1 组件结构

```tsx
"use client"; // 仅客户端组件需要

import { useState, useEffect } from "react";

// 外部依赖
import { useQuery } from "@tanstack/react-query";

// 内部组件
import { Button } from "@/components/ui/button";
import { GoalCard } from "@/components/goals/goal-card";

// 工具函数
import { formatDate } from "@/lib/utils/format";

// 类型
import type { Goal } from "@/types/goal";

// Props 接口
interface GoalListProps {
  filter?: string;
  onSelect?: (goal: Goal) => void;
}

// 组件
export default function GoalList({ filter, onSelect }: GoalListProps) {
  // Hooks（按顺序：state → ref → context → query → memo → effect）
  const [selectedId, setSelectedId] = useState<string | null>(null);
  
  // 事件处理
  const handleSelect = (goal: Goal) => {
    setSelectedId(goal.id);
    onSelect?.(goal);
  };

  // 渲染
  return (
    <div className="space-y-4">
      {/* ... */}
    </div>
  );
}
```

### 4.2 客户端 vs 服务端组件

```tsx
// 服务端组件（默认）- 不需要 "use client"
// 用于：数据获取、访问后端资源、保持敏感信息在服务端

// 客户端组件 - 需要 "use client"
// 用于：交互性（onClick 等）、状态管理（useState 等）、浏览器 API
```

### 4.3 加载与错误状态

每个页面都应该处理：
- `loading.tsx`: 加载状态
- `error.tsx`: 错误状态
- `not-found.tsx`: 404 状态

---

## 5. 样式规范

### 5.1 Tailwind CSS 优先

```tsx
// ✅ 推荐
<div className="flex items-center gap-4 p-4 bg-white rounded-lg shadow">

// ❌ 避免
<div style={{ display: 'flex', alignItems: 'center' }}>
```

### 5.2 响应式设计

使用 Tailwind 断点：
- `sm`: 640px
- `md`: 768px
- `lg`: 1024px
- `xl`: 1280px

```tsx
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
```

### 5.3 暗色模式

使用 `dark:` 前缀支持暗色模式：

```tsx
<div className="bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100">
```

### 5.4 className 合并

使用 `cn` 工具函数合并类名：

```tsx
import { cn } from "@/lib/utils/cn";

<button className={cn(
  "px-4 py-2 rounded",
  variant === "primary" && "bg-blue-500 text-white",
  variant === "secondary" && "bg-gray-200 text-gray-800",
  disabled && "opacity-50 cursor-not-allowed"
)}>
```

---

## 6. 数据获取规范

### 6.1 React Query 使用

```tsx
// lib/hooks/use-goals.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { goalsApi } from "@/lib/api/goals";

export function useGoals(filter?: string) {
  return useQuery({
    queryKey: ["goals", filter],
    queryFn: () => goalsApi.list(filter),
  });
}

export function useGoal(id: string) {
  return useQuery({
    queryKey: ["goal", id],
    queryFn: () => goalsApi.get(id),
    enabled: !!id,
  });
}

export function useCreateGoal() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: goalsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["goals"] });
    },
  });
}
```

### 6.2 API 客户端 (Axios)

```tsx
// lib/api/client.ts
import axios, { AxiosError, AxiosInstance, AxiosRequestConfig } from "axios";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

// 创建 Axios 实例
const axiosInstance: AxiosInstance = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
  headers: {
    "Content-Type": "application/json",
  },
});

// 请求拦截器 - 添加 Token
axiosInstance.interceptors.request.use(
  (config) => {
    if (typeof window !== "undefined") {
      const token = localStorage.getItem("token");
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// 响应拦截器 - 统一错误处理
axiosInstance.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      // Token 过期，清除并跳转登录
      if (typeof window !== "undefined") {
        localStorage.removeItem("token");
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

// 封装 API 方法
export const api = {
  get: <T>(url: string, config?: AxiosRequestConfig) =>
    axiosInstance.get<T>(url, config).then((res) => res.data),
    
  post: <T>(url: string, data?: unknown, config?: AxiosRequestConfig) =>
    axiosInstance.post<T>(url, data, config).then((res) => res.data),
    
  put: <T>(url: string, data?: unknown, config?: AxiosRequestConfig) =>
    axiosInstance.put<T>(url, data, config).then((res) => res.data),
    
  patch: <T>(url: string, data?: unknown, config?: AxiosRequestConfig) =>
    axiosInstance.patch<T>(url, data, config).then((res) => res.data),
    
  delete: <T>(url: string, config?: AxiosRequestConfig) =>
    axiosInstance.delete<T>(url, config).then((res) => res.data),
};

export default axiosInstance;
```

---

## 7. 表单规范

### 7.1 React Hook Form + Zod

```tsx
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

const goalSchema = z.object({
  name: z.string().min(1, "名称不能为空").max(100),
  description: z.string().min(1, "描述不能为空"),
  priority_mode: z.enum(["STRICT", "SOFT"]),
  priority_terms: z.string().optional(),
});

type GoalFormData = z.infer<typeof goalSchema>;

export default function GoalForm() {
  const form = useForm<GoalFormData>({
    resolver: zodResolver(goalSchema),
    defaultValues: {
      priority_mode: "SOFT",
    },
  });

  const onSubmit = (data: GoalFormData) => {
    // 提交逻辑
  };

  return (
    <form onSubmit={form.handleSubmit(onSubmit)}>
      {/* 表单字段 */}
    </form>
  );
}
```

---

## 8. 认证规范

### 8.1 Magic Link 认证流程

1. 用户输入邮箱 → 调用 `POST /api/auth/request_link`
2. 后端发送 Magic Link 邮件
3. 用户点击链接 → 跳转到 `/auth/callback?token=xxx`
4. 前端调用 `GET /api/auth/consume?token=xxx`
5. 后端返回 JWT → 存储到 localStorage
6. 重定向到 Dashboard

### 8.2 认证 Context

```tsx
// contexts/auth-context.tsx
"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  login: (token: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    // 检查本地存储的 token
    const token = localStorage.getItem("token");
    if (token) {
      // 验证 token 并获取用户信息
    }
    setIsLoading(false);
  }, []);

  const login = async (token: string) => {
    localStorage.setItem("token", token);
    // 获取用户信息
    router.push("/goals");
  };

  const logout = () => {
    localStorage.removeItem("token");
    setUser(null);
    router.push("/login");
  };

  return (
    <AuthContext.Provider value={{ user, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
```

---

## 9. UI/UX 设计规范

> **设计目标**: 做出"像真实公司设计团队做出来的系统"——克制、可用、内容优先。
> 避免一眼像 AI 生成的通用审美与模板化组件堆叠。

### 9.1 设计原则

**核心原则**:
- **信息架构优先**: 先结构后装饰，以任务流为中心
- **克制与专业**: 减少装饰性元素，突出内容本身
- **平台一致性**: 遵循 Web 平台惯例，组件/间距/命名/交互反馈保持统一
- **可用性优先**: 识别而非记忆、状态可见、可撤销/可返回

**明确禁止的 "AI 常用视觉套路"**:
- ❌ 大面积梦幻渐变背景、霓虹光晕
- ❌ 过强投影、玻璃拟态（磨砂透明卡片）
- ❌ 拟物 3D 胶状按钮
- ❌ 超级圆角卡片瀑布
- ❌ 无意义的装饰性几何漂浮物
- ❌ 千篇一律的"卡片 + 图标 + 大标题"落地页布局
- ❌ 每个卡片都配一个彩色渐变图标
- ❌ 为了"酷炫"牺牲可读性/可用性

### 9.2 设计 Tokens

#### 颜色系统

```css
/* 中性色（主背景与文字） */
--color-bg-primary: #ffffff;        /* 主背景 */
--color-bg-secondary: #f9fafb;      /* 次级背景 (gray-50) */
--color-bg-tertiary: #f3f4f6;       /* 区块背景 (gray-100) */
--color-border: #e5e7eb;            /* 边框 (gray-200) */
--color-border-strong: #d1d5db;     /* 强调边框 (gray-300) */

--color-text-primary: #111827;      /* 主文字 (gray-900) */
--color-text-secondary: #6b7280;    /* 次级文字 (gray-500) */
--color-text-tertiary: #9ca3af;     /* 弱文字 (gray-400) */

/* 强调色（仅 1 个主色） */
--color-accent: #2563eb;            /* 主强调色 (blue-600) */
--color-accent-hover: #1d4ed8;      /* 悬停 (blue-700) */
--color-accent-light: #eff6ff;      /* 浅色背景 (blue-50) */

/* 功能色（状态反馈） */
--color-success: #059669;           /* 成功 (emerald-600) */
--color-warning: #d97706;           /* 警告 (amber-600) */
--color-error: #dc2626;             /* 错误 (red-600) */
```

**对比度要求** (WCAG AA):
- 正文文字: ≥ 4.5:1
- 大号文字/标题: ≥ 3:1
- UI 控件/图形: ≥ 3:1

#### 字体系统

```css
/* 字号阶梯（仅 3 级主用） */
--font-size-sm: 0.875rem;    /* 14px - 辅助文字、标签 */
--font-size-base: 1rem;      /* 16px - 正文 */
--font-size-lg: 1.125rem;    /* 18px - 小标题 */
--font-size-xl: 1.25rem;     /* 20px - 页面标题 */
--font-size-2xl: 1.5rem;     /* 24px - 区块标题（少用） */

/* 字重 */
--font-weight-normal: 400;   /* 正文 */
--font-weight-medium: 500;   /* 强调、按钮 */
--font-weight-semibold: 600; /* 标题 */

/* 行高 */
--line-height-tight: 1.25;   /* 标题 */
--line-height-normal: 1.5;   /* 正文 */
--line-height-relaxed: 1.75; /* 长文本 */
```

#### 间距系统

```css
/* 4px 基准的间距阶梯 */
--spacing-1: 0.25rem;   /* 4px  - 紧凑内间距 */
--spacing-2: 0.5rem;    /* 8px  - 小间距 */
--spacing-3: 0.75rem;   /* 12px - 表单元素间距 */
--spacing-4: 1rem;      /* 16px - 标准间距 */
--spacing-6: 1.5rem;    /* 24px - 区块内间距 */
--spacing-8: 2rem;      /* 32px - 区块间距 */
--spacing-12: 3rem;     /* 48px - 大区块间距 */
```

#### 圆角（克制使用）

```css
--radius-sm: 0.25rem;   /* 4px  - 小元素、标签 */
--radius-md: 0.375rem;  /* 6px  - 按钮、输入框 */
--radius-lg: 0.5rem;    /* 8px  - 卡片、模态框 */
/* 避免超过 8px 的大圆角 */
```

#### 阴影（轻微、功能性）

```css
/* 仅用于层级区分，不做装饰 */
--shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
--shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1);
--shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1);  /* 仅模态框/下拉 */
```

### 9.3 组件规范

#### 按钮

```tsx
// Primary - 主操作（每页面最多 1-2 个）
<button className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 transition-colors">
  保存目标
</button>

// Secondary - 次要操作
<button className="px-4 py-2 bg-white text-gray-700 text-sm font-medium rounded-md border border-gray-300 hover:bg-gray-50 transition-colors">
  取消
</button>

// Danger - 危险操作
<button className="px-4 py-2 bg-red-600 text-white text-sm font-medium rounded-md hover:bg-red-700 transition-colors">
  删除
</button>

// Ghost - 弱操作
<button className="px-4 py-2 text-gray-600 text-sm font-medium rounded-md hover:bg-gray-100 transition-colors">
  了解更多
</button>
```

#### 输入框

```tsx
<div className="space-y-1.5">
  <label className="block text-sm font-medium text-gray-700">
    目标名称
  </label>
  <input
    type="text"
    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
    placeholder="例如：AI 行业动态追踪"
  />
  <p className="text-xs text-gray-500">简短描述这个追踪目标</p>
</div>
```

#### 卡片

```tsx
// 简洁卡片 - 无过度装饰
<div className="bg-white border border-gray-200 rounded-lg p-4">
  <h3 className="text-base font-semibold text-gray-900">目标名称</h3>
  <p className="mt-1 text-sm text-gray-600">目标描述内容...</p>
</div>

// 避免: 过强阴影、渐变背景、装饰性图标
```

#### 表格（企业级密度）

```tsx
<table className="min-w-full divide-y divide-gray-200">
  <thead className="bg-gray-50">
    <tr>
      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
        标题
      </th>
      {/* 提供排序/筛选能力 */}
    </tr>
  </thead>
  <tbody className="bg-white divide-y divide-gray-200">
    <tr className="hover:bg-gray-50">
      <td className="px-4 py-3 text-sm text-gray-900">
        数据内容
      </td>
    </tr>
  </tbody>
</table>
```

### 9.4 状态处理

每个页面/组件必须处理以下状态:

```tsx
// 1. 加载状态 - 骨架屏优于 Spinner
<div className="animate-pulse space-y-3">
  <div className="h-4 bg-gray-200 rounded w-3/4"></div>
  <div className="h-4 bg-gray-200 rounded w-1/2"></div>
</div>

// 2. 空状态 - 提供行动引导
<div className="text-center py-12">
  <p className="text-gray-500 mb-4">还没有创建任何目标</p>
  <button className="text-blue-600 hover:text-blue-700 font-medium">
    创建第一个目标 →
  </button>
</div>

// 3. 错误状态 - 提供可执行的恢复路径
<div className="bg-red-50 border border-red-200 rounded-md p-4">
  <p className="text-sm text-red-800">
    加载失败：网络连接超时
  </p>
  <button className="mt-2 text-sm text-red-600 hover:text-red-700 font-medium">
    点击重试
  </button>
</div>

// 4. 成功反馈 - 简洁明确
<div className="bg-green-50 border border-green-200 rounded-md p-4">
  <p className="text-sm text-green-800">目标已保存</p>
</div>
```

### 9.5 图标使用原则

- **少而准**: 能不用就不用，只在确实需要时使用
- **单色**: 使用 `currentColor`，随文字颜色变化
- **统一尺寸**: 16px（行内）、20px（按钮）、24px（导航）
- **避免**: 每个卡片都配一个彩色渐变图标

```tsx
import { Plus, Search, Settings } from "lucide-react";

// 正确：简洁、功能性
<button className="inline-flex items-center gap-2 text-sm">
  <Plus className="h-4 w-4" />
  新建
</button>

// 避免：装饰性、彩色图标
```

### 9.6 真实感细节

**文案规范**:
- 使用真实业务语言，避免空洞口号
- 表单标签用具体名称（"目标名称" 而非 "标题"）
- 错误提示给可执行的恢复路径

```tsx
// ✅ 好的错误提示
"无法连接到服务器，请检查网络连接后重试"

// ❌ 差的错误提示
"出错了"
```

**表单/表格**:
- 按企业系统习惯做密度与对齐
- 提供排序/筛选/批量操作/导出等真实能力

### 9.7 设计自检清单

每次设计/开发完成后，检查以下问题:

1. **是否有大面积渐变或装饰性元素？** → 如有，删除或替换为纯色
2. **圆角是否超过 8px？阴影是否过强？** → 调整为更克制的值
3. **每个区块是否都有装饰性图标？** → 评估必要性，能省则省
4. **文案是否使用真实业务语言？** → 避免"Lorem ipsum"和空洞口号
5. **错误/空状态是否提供了行动引导？** → 必须有可执行的下一步

---

## 10. 环境配置

### 10.1 环境变量

```bash
# .env.example
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

### 10.2 Next.js 配置

```ts
// next.config.ts
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // 严格模式
  reactStrictMode: true,
  
  // 图片域名白名单
  images: {
    remotePatterns: [
      { hostname: "localhost" },
    ],
  },
};

export default nextConfig;
```

---

## 11. 开发流程

### 11.1 启动开发

```bash
cd infoSentry-web
pnpm install
pnpm dev
```

### 11.2 代码检查

```bash
pnpm lint          # ESLint 检查
pnpm type-check    # TypeScript 类型检查
pnpm format        # Prettier 格式化
```

### 11.3 构建

```bash
pnpm build         # 生产构建
pnpm start         # 启动生产服务
```

---

## 12. 完成标准

### 12.1 功能清单
- [ ] 魔法链接登录（请求/消费 token）
- [ ] Goal 列表 + 状态过滤
- [ ] Goal 编辑（name/description/priority_terms/mode/batch_windows）
- [ ] Goal 详情：高分 items、原因、反馈按钮
- [ ] RSS 管理页面（增删启停）
- [ ] Inbox 列表：展示 push_decisions + actions（like/dislike/block/open）

### 12.2 验收标准
- Chrome 最新版完整覆盖
- Goal 只填 description 也可进入推送闭环
- 反馈动作无刷新更新
- 响应式设计（移动端可用）
- 加载/错误状态处理完善

