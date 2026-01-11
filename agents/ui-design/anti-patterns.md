# UI 设计反模式

> 本项目中禁止使用的设计做法

---

## 1. 视觉反模式

### ❌ 大面积渐变背景

```tsx
// ❌ 禁止
<div className="bg-gradient-to-r from-purple-400 via-pink-500 to-red-500">

// ✅ 使用纯色
<div className="bg-white">
<div className="bg-gray-50">
```

### ❌ 霓虹光晕效果

```tsx
// ❌ 禁止
<div className="shadow-[0_0_15px_rgba(168,85,247,0.4)]">

// ✅ 使用标准阴影
<div className="shadow-md">
```

### ❌ 玻璃拟态（磨砂透明）

```tsx
// ❌ 禁止
<div className="bg-white/30 backdrop-blur-md">

// ✅ 使用实色
<div className="bg-white">
```

### ❌ 过强阴影

```tsx
// ❌ 禁止
<div className="shadow-2xl">
<div className="shadow-[0_25px_50px_rgba(0,0,0,0.25)]">

// ✅ 使用轻微阴影
<div className="shadow-sm">
<div className="shadow-md">  // 最多到这个级别
```

### ❌ 超级圆角

```tsx
// ❌ 禁止
<div className="rounded-3xl">  // 24px
<div className="rounded-full"> // 除非是头像/图标

// ✅ 使用克制的圆角
<div className="rounded-md">   // 6px
<div className="rounded-lg">   // 8px - 最大值
```

### ❌ 每个卡片都配彩色图标

```tsx
// ❌ 禁止
<Card>
  <div className="bg-gradient-to-r from-blue-500 to-purple-500 p-3 rounded-xl">
    <Target className="h-8 w-8 text-white" />
  </div>
  <CardTitle>目标追踪</CardTitle>
</Card>

// ✅ 简洁卡片
<Card>
  <CardTitle>目标追踪</CardTitle>
  <CardDescription>追踪你感兴趣的信息</CardDescription>
</Card>
```

### ❌ 无意义的装饰元素

```tsx
// ❌ 禁止 - 漂浮的几何图形
<div className="absolute top-0 right-0 opacity-20">
  <div className="w-40 h-40 bg-purple-500 rounded-full blur-3xl" />
</div>

// ✅ 保持简洁，用留白代替装饰
```

---

## 2. 布局反模式

### ❌ 过度居中

```tsx
// ❌ 禁止 - 所有内容都居中
<div className="flex flex-col items-center text-center">
  <h1>标题</h1>
  <p>一段很长的描述文字...</p>
  <form>...</form>
</div>

// ✅ 左对齐更易读
<div>
  <h1>标题</h1>
  <p>一段很长的描述文字...</p>
  <form>...</form>
</div>
```

### ❌ 卡片瀑布堆叠

```tsx
// ❌ 禁止 - 所有页面都是卡片网格
<div className="grid grid-cols-4 gap-4">
  <Card>...</Card>
  <Card>...</Card>
  <Card>...</Card>
  {/* 20+ 个相同的卡片 */}
</div>

// ✅ 根据内容选择合适的布局
// 列表适合用表格，详情适合用单列
```

### ❌ 过度使用 Hero Section

```tsx
// ❌ 禁止 - 每个页面都有大 Hero
<div className="h-96 bg-gradient-to-r ... flex items-center justify-center">
  <h1 className="text-5xl">欢迎使用</h1>
</div>

// ✅ 企业应用不需要 Hero，直接展示内容
<div className="p-6">
  <h1 className="text-xl font-semibold">目标列表</h1>
  {/* 直接是内容 */}
</div>
```

---

## 3. 文案反模式

### ❌ 空洞口号

```tsx
// ❌ 禁止
<h1>赋能未来，智启新程</h1>
<p>打造极致用户体验，引领行业变革</p>

// ✅ 使用具体描述
<h1>目标追踪</h1>
<p>追踪你感兴趣的行业动态和关键信息</p>
```

### ❌ 模糊的按钮文案

```tsx
// ❌ 禁止
<Button>提交</Button>
<Button>确定</Button>
<Button>是</Button>

// ✅ 具体说明操作
<Button>保存目标</Button>
<Button>发送验证邮件</Button>
<Button>确认删除</Button>
```

### ❌ 无意义的错误提示

```tsx
// ❌ 禁止
<Alert>出错了</Alert>
<Alert>操作失败</Alert>

// ✅ 说明原因和解决方案
<Alert>
  无法连接到服务器，请检查网络连接后重试
  <Button variant="link">重试</Button>
</Alert>
```

---

## 4. 交互反模式

### ❌ 隐藏重要操作

```tsx
// ❌ 禁止 - 需要悬停才能看到操作
<Card onMouseEnter={() => setShowActions(true)}>
  {showActions && <Button>编辑</Button>}
</Card>

// ✅ 操作始终可见
<Card>
  <CardFooter>
    <Button variant="ghost" size="sm">编辑</Button>
  </CardFooter>
</Card>
```

### ❌ 无确认的危险操作

```tsx
// ❌ 禁止 - 点击直接删除
<Button onClick={() => deleteGoal(id)}>删除</Button>

// ✅ 需要确认
<AlertDialog>
  <AlertDialogTrigger asChild>
    <Button variant="destructive">删除</Button>
  </AlertDialogTrigger>
  <AlertDialogContent>
    <AlertDialogTitle>确认删除？</AlertDialogTitle>
    <AlertDialogDescription>
      此操作无法撤销
    </AlertDialogDescription>
    <AlertDialogAction onClick={() => deleteGoal(id)}>
      删除
    </AlertDialogAction>
  </AlertDialogContent>
</AlertDialog>
```

### ❌ 无反馈的操作

```tsx
// ❌ 禁止 - 点击后无任何反馈
<Button onClick={handleSave}>保存</Button>

// ✅ 提供加载状态和完成反馈
<Button onClick={handleSave} disabled={isLoading}>
  {isLoading ? (
    <>
      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
      保存中...
    </>
  ) : "保存"}
</Button>
// 完成后显示 toast 或更新 UI
```

---

## 5. 状态处理反模式

### ❌ 只用 Spinner

```tsx
// ❌ 禁止 - 整页 Spinner
<div className="flex items-center justify-center h-full">
  <Spinner />
</div>

// ✅ 使用骨架屏，保持布局稳定
<div className="space-y-4">
  <Skeleton className="h-8 w-1/3" />
  <Skeleton className="h-32 w-full" />
  <Skeleton className="h-32 w-full" />
</div>
```

### ❌ 空白的空状态

```tsx
// ❌ 禁止 - 什么都不显示
{goals.length === 0 && null}

// ✅ 提供行动引导
{goals.length === 0 && (
  <EmptyState
    title="还没有目标"
    description="创建第一个追踪目标开始使用"
    action={<Button>新建目标</Button>}
  />
)}
```

---

## 记住

> "好的设计是无形的。用户应该注意到内容，而不是设计本身。"

