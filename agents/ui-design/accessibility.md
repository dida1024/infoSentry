# 可访问性指南

> 确保 UI 对所有用户可用

---

## 1. 基本要求

### 1.1 WCAG 2.1 AA 标准

本项目遵循 WCAG 2.1 AA 标准：

- **可感知**：信息和界面组件可被用户感知
- **可操作**：界面组件可操作
- **可理解**：信息和操作可理解
- **健壮**：内容可被各种用户代理解释

---

## 2. 颜色与对比度

### 2.1 对比度要求

| 元素 | 最小对比度 |
|------|-----------|
| 正文文字 | 4.5:1 |
| 大号文字（18px+） | 3:1 |
| UI 组件边框 | 3:1 |
| 图标 | 3:1 |

### 2.2 检查工具

- Chrome DevTools: Inspect → Accessibility
- [WebAIM Contrast Checker](https://webaim.org/resources/contrastchecker/)

### 2.3 不要仅靠颜色传达信息

```tsx
// ❌ 仅用颜色区分
<span className="text-red-500">错误</span>
<span className="text-green-500">成功</span>

// ✅ 颜色 + 图标/文字
<span className="text-red-500">
  <XCircle className="inline h-4 w-4 mr-1" />
  错误
</span>
```

---

## 3. 键盘导航

### 3.1 焦点可见

```tsx
// ✅ 确保焦点样式可见
<Button className="focus:ring-2 focus:ring-blue-500 focus:ring-offset-2">
  点击我
</Button>

// ❌ 不要移除焦点样式
<Button className="focus:outline-none">  {/* 危险！ */}
```

### 3.2 Tab 顺序

- 按逻辑顺序排列可聚焦元素
- 避免使用 `tabindex > 0`

### 3.3 键盘快捷键

| 按键 | 操作 |
|------|------|
| Tab | 移动到下一个可聚焦元素 |
| Shift + Tab | 移动到上一个可聚焦元素 |
| Enter | 激活按钮/链接 |
| Space | 激活按钮/复选框 |
| Escape | 关闭模态框/下拉菜单 |
| Arrow Keys | 在菜单/列表中导航 |

---

## 4. 表单可访问性

### 4.1 Label 关联

```tsx
// ✅ 使用 htmlFor 关联
<Label htmlFor="email">邮箱</Label>
<Input id="email" type="email" />

// 或使用嵌套
<Label>
  邮箱
  <Input type="email" />
</Label>
```

### 4.2 错误提示

```tsx
<div>
  <Label htmlFor="email">邮箱</Label>
  <Input 
    id="email" 
    aria-invalid="true"
    aria-describedby="email-error"
  />
  <p id="email-error" className="text-red-500 text-sm">
    请输入有效的邮箱地址
  </p>
</div>
```

### 4.3 必填字段

```tsx
<Label htmlFor="name">
  名称 <span className="text-red-500">*</span>
</Label>
<Input id="name" required aria-required="true" />
```

---

## 5. 图片与图标

### 5.1 图片 Alt 文本

```tsx
// 有意义的图片
<img src="/chart.png" alt="2024年用户增长趋势图" />

// 装饰性图片
<img src="/decoration.svg" alt="" aria-hidden="true" />
```

### 5.2 图标

```tsx
// 纯装饰图标
<Search className="h-4 w-4" aria-hidden="true" />

// 有功能的图标按钮
<button aria-label="搜索">
  <Search className="h-4 w-4" />
</button>

// 图标 + 文字（图标隐藏）
<Button>
  <Plus className="h-4 w-4 mr-2" aria-hidden="true" />
  新建
</Button>
```

---

## 6. 动态内容

### 6.1 加载状态

```tsx
<div aria-busy="true" aria-live="polite">
  <Skeleton className="h-4 w-full" />
  <span className="sr-only">加载中...</span>
</div>
```

### 6.2 实时更新

```tsx
// 通知区域
<div role="status" aria-live="polite">
  {message && <p>{message}</p>}
</div>

// 错误提示
<div role="alert">
  操作失败，请重试
</div>
```

---

## 7. 模态框与对话框

```tsx
<Dialog>
  <DialogContent>
    {/* 焦点会自动锁定在模态框内 */}
    <DialogHeader>
      <DialogTitle>确认删除</DialogTitle>
      <DialogDescription>
        此操作无法撤销
      </DialogDescription>
    </DialogHeader>
    {/* ... */}
  </DialogContent>
</Dialog>
```

**规则**：
- ✅ 打开时焦点移入模态框
- ✅ 关闭时焦点返回触发元素
- ✅ Escape 键关闭
- ✅ 点击背景关闭（可选）

---

## 8. 辅助类

Tailwind 提供的辅助类：

```tsx
// 仅屏幕阅读器可见
<span className="sr-only">这段文字只有屏幕阅读器能读到</span>

// 非屏幕阅读器可见
<span className="not-sr-only">正常显示的文字</span>
```

---

## 9. 检查清单

开发完成后检查：

```
□ 所有交互元素可通过键盘操作
□ 焦点样式清晰可见
□ 颜色对比度满足要求
□ 表单字段都有关联的 Label
□ 图片都有适当的 alt 文本
□ 错误提示清晰且可访问
□ 模态框焦点管理正确
```

---

## 参考资源

- [WCAG 2.1 Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)
- [MDN Accessibility](https://developer.mozilla.org/en-US/docs/Web/Accessibility)
- [Radix UI Accessibility](https://www.radix-ui.com/docs/primitives/overview/accessibility)

