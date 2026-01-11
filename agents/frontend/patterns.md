# 前端常用模式

> 推荐的实现方式和最佳实践

---

## 🧱 组件模式

### 1. 容器/展示分离

```tsx
// 容器组件：负责数据获取
function GoalListContainer() {
  const { data, isLoading } = useGoals();
  
  if (isLoading) return <GoalListSkeleton />;
  return <GoalList goals={data} />;
}

// 展示组件：负责渲染
function GoalList({ goals }: { goals: Goal[] }) {
  return (
    <ul>
      {goals.map(goal => <GoalCard key={goal.id} goal={goal} />)}
    </ul>
  );
}
```

### 2. 复合组件模式

```tsx
// 使用
<Card>
  <Card.Header>标题</Card.Header>
  <Card.Body>内容</Card.Body>
  <Card.Footer>底部</Card.Footer>
</Card>

// 实现
function Card({ children }) {
  return <div className="border rounded-lg">{children}</div>;
}
Card.Header = ({ children }) => <div className="p-4 border-b">{children}</div>;
Card.Body = ({ children }) => <div className="p-4">{children}</div>;
Card.Footer = ({ children }) => <div className="p-4 border-t">{children}</div>;
```

### 3. 自定义 Hook 封装

```tsx
// hooks/use-goals.ts
export function useGoals(filter?: string) {
  return useQuery({
    queryKey: ["goals", filter],
    queryFn: () => goalsApi.list(filter),
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

---

## 📊 状态模式

### 1. 加载状态

```tsx
// 骨架屏（推荐）
function GoalCardSkeleton() {
  return (
    <div className="animate-pulse space-y-3 p-4 border rounded-lg">
      <div className="h-4 bg-gray-200 rounded w-3/4" />
      <div className="h-4 bg-gray-200 rounded w-1/2" />
    </div>
  );
}

// 使用
if (isLoading) {
  return (
    <div className="space-y-4">
      {[1, 2, 3].map(i => <GoalCardSkeleton key={i} />)}
    </div>
  );
}
```

### 2. 空状态

```tsx
function EmptyState({ 
  title, 
  description, 
  action 
}: { 
  title: string;
  description: string;
  action?: { label: string; onClick: () => void };
}) {
  return (
    <div className="text-center py-12">
      <p className="text-gray-900 font-medium">{title}</p>
      <p className="text-gray-500 mt-1">{description}</p>
      {action && (
        <button 
          onClick={action.onClick}
          className="mt-4 text-blue-600 hover:text-blue-700 font-medium"
        >
          {action.label} →
        </button>
      )}
    </div>
  );
}
```

### 3. 错误状态

```tsx
function ErrorState({ 
  message, 
  onRetry 
}: { 
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="bg-red-50 border border-red-200 rounded-md p-4">
      <p className="text-sm text-red-800">{message}</p>
      {onRetry && (
        <button 
          onClick={onRetry}
          className="mt-2 text-sm text-red-600 hover:text-red-700 font-medium"
        >
          点击重试
        </button>
      )}
    </div>
  );
}
```

---

## 📝 表单模式

### 1. 基础表单

```tsx
const schema = z.object({
  name: z.string().min(1, "名称不能为空").max(100),
  description: z.string().optional(),
});

type FormData = z.infer<typeof schema>;

function GoalForm({ onSubmit }: { onSubmit: (data: FormData) => void }) {
  const form = useForm<FormData>({
    resolver: zodResolver(schema),
  });

  return (
    <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700">
          名称
        </label>
        <input
          {...form.register("name")}
          className="mt-1 w-full px-3 py-2 border rounded-md"
        />
        {form.formState.errors.name && (
          <p className="mt-1 text-sm text-red-600">
            {form.formState.errors.name.message}
          </p>
        )}
      </div>
      
      <button type="submit" className="px-4 py-2 bg-blue-600 text-white rounded-md">
        提交
      </button>
    </form>
  );
}
```

### 2. 乐观更新

```tsx
const mutation = useMutation({
  mutationFn: goalsApi.update,
  onMutate: async (newGoal) => {
    await queryClient.cancelQueries({ queryKey: ["goals"] });
    const previous = queryClient.getQueryData(["goals"]);
    
    queryClient.setQueryData(["goals"], (old: Goal[]) =>
      old.map(g => g.id === newGoal.id ? newGoal : g)
    );
    
    return { previous };
  },
  onError: (err, _, context) => {
    queryClient.setQueryData(["goals"], context?.previous);
  },
  onSettled: () => {
    queryClient.invalidateQueries({ queryKey: ["goals"] });
  },
});
```

---

## 🔐 认证模式

### Protected Route

```tsx
// middleware.ts 或布局组件
export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !user) {
      router.push("/login");
    }
  }, [user, isLoading, router]);

  if (isLoading) return <LoadingScreen />;
  if (!user) return null;

  return <>{children}</>;
}
```

---

## 🎨 样式模式

### 条件样式

```tsx
import { cn } from "@/lib/utils/cn";

<button
  className={cn(
    "px-4 py-2 rounded-md transition-colors",
    variant === "primary" && "bg-blue-600 text-white hover:bg-blue-700",
    variant === "secondary" && "bg-gray-100 text-gray-700 hover:bg-gray-200",
    disabled && "opacity-50 cursor-not-allowed"
  )}
>
```

### 响应式布局

```tsx
// 卡片网格
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
  {items.map(item => <Card key={item.id} item={item} />)}
</div>

// 侧边栏布局
<div className="flex">
  <aside className="hidden md:block w-64 shrink-0">
    <Sidebar />
  </aside>
  <main className="flex-1 min-w-0">
    {children}
  </main>
</div>
```

