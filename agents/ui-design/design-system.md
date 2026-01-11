# 设计系统

> 基于 `docs/dev/FRONTEND_CONVENTIONS.md` 第 9 节提取的设计令牌

---

## 1. 颜色系统

### 1.1 中性色

| 用途 | 变量 | 值 | Tailwind |
|------|------|-----|----------|
| 主背景 | `--color-bg-primary` | #ffffff | `bg-white` |
| 次级背景 | `--color-bg-secondary` | #f9fafb | `bg-gray-50` |
| 区块背景 | `--color-bg-tertiary` | #f3f4f6 | `bg-gray-100` |
| 边框 | `--color-border` | #e5e7eb | `border-gray-200` |
| 强调边框 | `--color-border-strong` | #d1d5db | `border-gray-300` |
| 主文字 | `--color-text-primary` | #111827 | `text-gray-900` |
| 次级文字 | `--color-text-secondary` | #6b7280 | `text-gray-500` |
| 弱文字 | `--color-text-tertiary` | #9ca3af | `text-gray-400` |

### 1.2 强调色（仅 1 个主色）

| 用途 | 值 | Tailwind |
|------|-----|----------|
| 主强调色 | #2563eb | `text-blue-600` / `bg-blue-600` |
| 悬停 | #1d4ed8 | `hover:bg-blue-700` |
| 浅色背景 | #eff6ff | `bg-blue-50` |

### 1.3 功能色

| 用途 | 值 | Tailwind |
|------|-----|----------|
| 成功 | #059669 | `text-emerald-600` |
| 警告 | #d97706 | `text-amber-600` |
| 错误 | #dc2626 | `text-red-600` |

### 1.4 对比度要求（WCAG AA）

- 正文文字：≥ 4.5:1
- 大号文字/标题：≥ 3:1
- UI 控件/图形：≥ 3:1

---

## 2. 字体系统

### 2.1 字号

| 用途 | 大小 | Tailwind |
|------|------|----------|
| 辅助文字 | 14px | `text-sm` |
| 正文 | 16px | `text-base` |
| 小标题 | 18px | `text-lg` |
| 页面标题 | 20px | `text-xl` |
| 区块标题（少用） | 24px | `text-2xl` |

### 2.2 字重

| 用途 | 值 | Tailwind |
|------|-----|----------|
| 正文 | 400 | `font-normal` |
| 强调/按钮 | 500 | `font-medium` |
| 标题 | 600 | `font-semibold` |

### 2.3 行高

| 用途 | 值 | Tailwind |
|------|-----|----------|
| 标题 | 1.25 | `leading-tight` |
| 正文 | 1.5 | `leading-normal` |
| 长文本 | 1.75 | `leading-relaxed` |

---

## 3. 间距系统

基于 4px 基准：

| 用途 | 大小 | Tailwind |
|------|------|----------|
| 紧凑内间距 | 4px | `p-1` / `gap-1` |
| 小间距 | 8px | `p-2` / `gap-2` |
| 表单元素间距 | 12px | `p-3` / `gap-3` |
| 标准间距 | 16px | `p-4` / `gap-4` |
| 区块内间距 | 24px | `p-6` / `gap-6` |
| 区块间距 | 32px | `p-8` / `gap-8` |
| 大区块间距 | 48px | `p-12` / `gap-12` |

---

## 4. 圆角

| 用途 | 大小 | Tailwind |
|------|------|----------|
| 小元素/标签 | 4px | `rounded-sm` |
| 按钮/输入框 | 6px | `rounded-md` |
| 卡片/模态框 | 8px | `rounded-lg` |

**规则**：避免超过 8px 的大圆角

---

## 5. 阴影

| 用途 | 值 | Tailwind |
|------|-----|----------|
| 微弱 | `0 1px 2px 0 rgb(0 0 0 / 0.05)` | `shadow-sm` |
| 标准 | `0 4px 6px -1px rgb(0 0 0 / 0.1)` | `shadow-md` |
| 强调（模态框/下拉） | `0 10px 15px -3px rgb(0 0 0 / 0.1)` | `shadow-lg` |

**规则**：仅用于层级区分，不做装饰

---

## 6. 断点（响应式）

| 断点 | 宽度 | 用途 |
|------|------|------|
| sm | 640px | 手机横屏 |
| md | 768px | 平板 |
| lg | 1024px | 小桌面 |
| xl | 1280px | 大桌面 |

---

## 7. 动效

### 7.1 过渡时间

| 用途 | 时间 | Tailwind |
|------|------|----------|
| 悬停效果 | 150ms | `transition-colors` |
| 展开/折叠 | 200ms | `transition-all duration-200` |
| 模态框 | 300ms | `transition-all duration-300` |

### 7.2 缓动函数

默认使用 `ease-in-out`

---

## 8. 图标

### 8.1 尺寸

| 用途 | 大小 | Tailwind |
|------|------|----------|
| 行内 | 16px | `h-4 w-4` |
| 按钮 | 20px | `h-5 w-5` |
| 导航 | 24px | `h-6 w-6` |

### 8.2 颜色

- 使用 `currentColor`，随文字颜色变化
- 避免彩色图标
