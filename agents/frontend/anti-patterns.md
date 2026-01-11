# 前端反模式

> 禁止的做法和常见错误

---

## ❌ 类型相关

### 滥用 any

```tsx
// ❌ 禁止
const data: any = fetchData();
const handleClick = (e: any) => { };

// ✅ 正确
const data: Goal[] = fetchData();
const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => { };
```

### 忽略类型错误

```tsx
// ❌ 禁止
// @ts-ignore
// @ts-expect-error

// ✅ 正确：修复类型问题或使用类型断言（有充分理由时）
const data = response as Goal;
```

---

## ❌ 数据获取

### useEffect 中直接 fetch

```tsx
// ❌ 禁止
useEffect(() => {
  fetch('/api/goals')
    .then(res => res.json())
    .then(setGoals);
}, []);

// ✅ 正确：使用 React Query
const { data: goals } = useQuery({
  queryKey: ["goals"],
  queryFn: goalsApi.list,
});
```

### 不处理加载/错误状态

```tsx
// ❌ 禁止
function GoalList() {
  const { data } = useGoals();
  return <ul>{data.map(...)}</ul>; // data 可能是 undefined
}

// ✅ 正确
function GoalList() {
  const { data, isLoading, error } = useGoals();
  
  if (isLoading) return <Skeleton />;
  if (error) return <ErrorState message="加载失败" />;
  if (!data?.length) return <EmptyState />;
  
  return <ul>{data.map(...)}</ul>;
}
```

---

## ❌ 组件设计

### 过大的组件

```tsx
// ❌ 禁止：单个组件超过 200 行
function GiantComponent() {
  // 500 行代码...
}

// ✅ 正确：拆分为多个小组件
function GoalPage() {
  return (
    <>
      <GoalHeader />
      <GoalList />
      <GoalFooter />
    </>
  );
}
```

### Props Drilling

```tsx
// ❌ 禁止：层层传递 props
<App user={user}>
  <Layout user={user}>
    <Sidebar user={user}>
      <UserAvatar user={user} />

// ✅ 正确：使用 Context
const { user } = useAuth();
```

### 在循环中使用索引作为 key

```tsx
// ❌ 禁止（除非列表不会重排序）
{items.map((item, index) => <Item key={index} />)}

// ✅ 正确
{items.map(item => <Item key={item.id} />)}
```

---

## ❌ 样式相关

### 内联样式

```tsx
// ❌ 禁止
<div style={{ display: 'flex', padding: '16px' }}>

// ✅ 正确
<div className="flex p-4">
```

### 硬编码颜色

```tsx
// ❌ 禁止
<div className="bg-[#2563eb]">

// ✅ 正确：使用 Tailwind 预设或 CSS 变量
<div className="bg-blue-600">
<div className="bg-accent">
```

### 过度嵌套

```tsx
// ❌ 禁止
<div className="...">
  <div className="...">
    <div className="...">
      <div className="...">
        <span>内容</span>

// ✅ 正确：扁平化结构
<article className="...">
  <header className="...">...</header>
  <section className="...">...</section>
</article>
```

---

## ❌ 状态管理

### 不必要的状态

```tsx
// ❌ 禁止：可以从其他状态派生
const [items, setItems] = useState([]);
const [itemCount, setItemCount] = useState(0);

// ✅ 正确：派生值不需要状态
const [items, setItems] = useState([]);
const itemCount = items.length;
```

### 直接修改状态

```tsx
// ❌ 禁止
const handleAdd = () => {
  items.push(newItem);
  setItems(items);
};

// ✅ 正确
const handleAdd = () => {
  setItems([...items, newItem]);
};
```

---

## ❌ 副作用

### useEffect 依赖不完整

```tsx
// ❌ 禁止：缺少依赖
useEffect(() => {
  fetchData(userId);
}, []); // ESLint 会警告

// ✅ 正确
useEffect(() => {
  fetchData(userId);
}, [userId]);
```

### 忘记清理副作用

```tsx
// ❌ 禁止
useEffect(() => {
  const timer = setInterval(() => { }, 1000);
  // 没有清理！
}, []);

// ✅ 正确
useEffect(() => {
  const timer = setInterval(() => { }, 1000);
  return () => clearInterval(timer);
}, []);
```

---

## ❌ 其他

### 硬编码字符串

```tsx
// ❌ 禁止
<a href="http://localhost:8000/api">

// ✅ 正确：使用环境变量或常量
<a href={`${API_BASE_URL}/api`}>
```

### 忽略 ESLint 警告

```tsx
// ❌ 禁止：随意禁用规则
// eslint-disable-next-line

// ✅ 正确：修复问题，或在有充分理由时添加注释说明
// eslint-disable-next-line @typescript-eslint/no-explicit-any -- 第三方库类型不完整
```

### console.log 残留

```tsx
// ❌ 禁止：提交代码前清理
console.log("debug", data);

// ✅ 正确：使用开发工具或条件日志
if (process.env.NODE_ENV === 'development') {
  console.log(data);
}
```

