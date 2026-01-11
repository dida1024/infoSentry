# 组件规范

> 基于 shadcn/ui 的组件使用规范

---

## 1. 按钮 (Button)

### 变体

| 变体 | 用途 | 每页数量 |
|------|------|---------|
| default (Primary) | 主操作 | 最多 1-2 个 |
| outline (Secondary) | 次要操作 | 不限 |
| destructive | 危险操作 | 谨慎使用 |
| ghost | 弱操作 | 不限 |
| link | 链接样式 | 不限 |

### 代码示例

```tsx
import { Button } from "@/components/ui/button";

// 主操作
<Button>保存目标</Button>

// 次要操作
<Button variant="outline">取消</Button>

// 危险操作（需要确认）
<Button variant="destructive">删除</Button>

// 弱操作
<Button variant="ghost">了解更多</Button>

// 带图标
<Button>
  <Plus className="h-4 w-4 mr-2" />
  新建
</Button>

// 加载状态
<Button disabled>
  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
  保存中...
</Button>
```

### 规则

- ✅ 按钮文案使用动词（"保存"、"删除"、"创建"）
- ✅ 危险操作需要二次确认
- ❌ 不要在一个区域放置过多按钮

---

## 2. 卡片 (Card)

### 结构

```tsx
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";

<Card>
  <CardHeader>
    <CardTitle>目标名称</CardTitle>
    <CardDescription>创建于 2025-01-01</CardDescription>
  </CardHeader>
  <CardContent>
    <p className="text-sm text-gray-600">目标描述内容...</p>
  </CardContent>
  <CardFooter className="flex justify-end gap-2">
    <Button variant="outline" size="sm">编辑</Button>
    <Button size="sm">查看详情</Button>
  </CardFooter>
</Card>
```

### 规则

- ✅ 保持卡片内容简洁
- ✅ 使用一致的卡片高度（或让内容决定高度）
- ❌ 不要在卡片上使用渐变背景
- ❌ 不要在每个卡片都放装饰性图标

---

## 3. 输入框 (Input)

### 基本用法

```tsx
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

<div className="space-y-1.5">
  <Label htmlFor="name">目标名称</Label>
  <Input 
    id="name" 
    placeholder="例如：AI 行业动态追踪" 
  />
  <p className="text-xs text-gray-500">简短描述这个追踪目标</p>
</div>
```

### 错误状态

```tsx
<div className="space-y-1.5">
  <Label htmlFor="name">目标名称</Label>
  <Input 
    id="name" 
    className="border-red-500 focus:ring-red-500" 
  />
  <p className="text-xs text-red-500">名称不能为空</p>
</div>
```

### 规则

- ✅ 始终使用 Label
- ✅ 提供有意义的 placeholder
- ✅ 显示验证错误信息
- ❌ 不要只用 placeholder 代替 Label

---

## 4. 文本域 (Textarea)

```tsx
import { Textarea } from "@/components/ui/textarea";

<div className="space-y-1.5">
  <Label htmlFor="description">目标描述</Label>
  <Textarea 
    id="description"
    placeholder="描述你想追踪的信息..."
    rows={4}
  />
</div>
```

---

## 5. 选择器 (Select)

```tsx
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";

<div className="space-y-1.5">
  <Label>优先模式</Label>
  <Select defaultValue="soft">
    <SelectTrigger>
      <SelectValue placeholder="选择模式" />
    </SelectTrigger>
    <SelectContent>
      <SelectItem value="strict">严格模式</SelectItem>
      <SelectItem value="soft">宽松模式</SelectItem>
    </SelectContent>
  </Select>
</div>
```

---

## 6. 对话框 (Dialog)

```tsx
import { Dialog, DialogTrigger, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";

<Dialog>
  <DialogTrigger asChild>
    <Button variant="destructive">删除</Button>
  </DialogTrigger>
  <DialogContent>
    <DialogHeader>
      <DialogTitle>确认删除</DialogTitle>
      <DialogDescription>
        删除后无法恢复，确定要删除这个目标吗？
      </DialogDescription>
    </DialogHeader>
    <DialogFooter>
      <Button variant="outline">取消</Button>
      <Button variant="destructive">删除</Button>
    </DialogFooter>
  </DialogContent>
</Dialog>
```

---

## 7. 警告 (Alert)

```tsx
import { Alert, AlertDescription } from "@/components/ui/alert";

// 信息提示
<Alert>
  <AlertDescription>这是一条提示信息</AlertDescription>
</Alert>

// 错误提示
<Alert variant="destructive">
  <AlertDescription>
    操作失败：网络连接超时
    <Button variant="link" size="sm">重试</Button>
  </AlertDescription>
</Alert>
```

---

## 8. 徽章 (Badge)

```tsx
import { Badge } from "@/components/ui/badge";

// 状态徽章
<Badge>活跃</Badge>
<Badge variant="secondary">暂停</Badge>
<Badge variant="destructive">已删除</Badge>
<Badge variant="outline">草稿</Badge>
```

---

## 9. 骨架屏 (Skeleton)

```tsx
import { Skeleton } from "@/components/ui/skeleton";

// 卡片骨架
<Card>
  <CardHeader>
    <Skeleton className="h-5 w-1/2" />
    <Skeleton className="h-4 w-1/4" />
  </CardHeader>
  <CardContent>
    <Skeleton className="h-4 w-full" />
    <Skeleton className="h-4 w-3/4 mt-2" />
  </CardContent>
</Card>
```

---

## 10. 空状态 (EmptyState)

```tsx
// 自定义组件
<div className="text-center py-12">
  <div className="text-gray-400 mb-4">
    <FolderOpen className="h-12 w-12 mx-auto" />
  </div>
  <h3 className="text-lg font-medium text-gray-900 mb-1">
    还没有目标
  </h3>
  <p className="text-gray-500 mb-4">
    创建第一个追踪目标开始使用
  </p>
  <Button>
    <Plus className="h-4 w-4 mr-2" />
    新建目标
  </Button>
</div>
```

---

## 组件使用原则

1. **一致性**：相同场景使用相同组件
2. **简洁**：不要过度嵌套组件
3. **可访问性**：确保键盘可操作，颜色对比度足够
4. **反馈**：操作后给用户明确的反馈

