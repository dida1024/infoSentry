# 前端开发规范（精简版）

> 快速参考，完整规范见 `docs/dev/FRONTEND_CONVENTIONS.md`

---

## 📦 技术栈

| 类别 | 选型 |
|------|------|
| 框架 | Next.js 15 (App Router) |
| 语言 | TypeScript (strict) |
| 样式 | Tailwind CSS |
| 状态 | React Query + Context |
| 表单 | React Hook Form + Zod |
| UI | shadcn/ui |
| 图标 | Lucide React |

---

## 📝 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 文件名 | kebab-case | `goal-card.tsx` |
| 组件名 | PascalCase | `GoalCard` |
| 函数/变量 | camelCase | `handleClick` |
| 常量 | UPPER_SNAKE | `API_BASE_URL` |
| 类型/接口 | PascalCase | `GoalCardProps` |
| 布尔值 | is/has/can 前缀 | `isLoading` |

---

## 🧱 组件规范

### 客户端 vs 服务端

```tsx
// 服务端组件（默认）- 数据获取、无交互
export default async function Page() {
  const data = await fetchData();
  return <div>{data}</div>;
}

// 客户端组件 - 交互、状态、浏览器 API
"use client";
export default function Button() {
  const [count, setCount] = useState(0);
  return <button onClick={() => setCount(c => c + 1)}>{count}</button>;
}
```

### 状态处理

每个页面/组件必须处理：
- ✅ Loading 状态（骨架屏优于 Spinner）
- ✅ Error 状态（提供重试按钮）
- ✅ Empty 状态（提供行动引导）

---

## 🎨 样式规范

### Tailwind 优先

```tsx
// ✅ 推荐
<div className="flex items-center gap-4 p-4">

// ❌ 避免
<div style={{ display: 'flex' }}>
```

### 响应式断点

```tsx
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
```

| 断点 | 宽度 |
|------|------|
| sm | 640px |
| md | 768px |
| lg | 1024px |
| xl | 1280px |

### 暗色模式

```tsx
<div className="bg-white dark:bg-gray-900">
```

---

## 🔗 数据获取

### React Query（推荐）

```tsx
// 查询
const { data, isLoading, error } = useQuery({
  queryKey: ["goals", filter],
  queryFn: () => goalsApi.list(filter),
});

// 变更
const mutation = useMutation({
  mutationFn: goalsApi.create,
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ["goals"] });
  },
});
```

---

## 📋 表单

### React Hook Form + Zod

```tsx
const schema = z.object({
  name: z.string().min(1, "名称不能为空"),
  email: z.string().email("邮箱格式不正确"),
});

const form = useForm({
  resolver: zodResolver(schema),
});
```

---

## 📚 参考资源

- [Next.js Docs](https://nextjs.org/docs)
- [Tailwind CSS](https://tailwindcss.com/docs)
- [React Query](https://tanstack.com/query/latest)
- [shadcn/ui](https://ui.shadcn.com/)
