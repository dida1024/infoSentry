# 前端代码审查清单

> 提交代码前的自查清单

---

## ✅ 类型安全

```
□ 所有变量和函数都有明确的类型
□ 没有使用 any 类型
□ Props 接口定义完整
□ API 响应类型正确
□ 事件处理函数类型正确
```

---

## ✅ 组件质量

```
□ 组件职责单一（<200 行）
□ 处理了 loading 状态
□ 处理了 error 状态
□ 处理了 empty 状态
□ 没有 Props drilling（>2 层用 Context）
□ 使用了语义化的 HTML 标签
```

---

## ✅ 数据获取

```
□ 使用 React Query 而非 useEffect + fetch
□ 设置了合适的 queryKey
□ 考虑了缓存策略
□ 变更操作使用 useMutation
□ 成功后正确 invalidate 缓存
```

---

## ✅ 样式

```
□ 使用 Tailwind 而非内联样式
□ 响应式设计（mobile/tablet/desktop）
□ 使用 cn() 合并条件类名
□ 遵循设计系统（颜色、间距、圆角）
□ 没有硬编码的颜色值
```

---

## ✅ 表单

```
□ 使用 React Hook Form
□ 使用 Zod 做校验
□ 显示校验错误信息
□ 提交按钮有 loading 状态
□ 处理提交成功/失败
```

---

## ✅ 可访问性

```
□ 图片有 alt 属性
□ 表单元素有 label
□ 按钮有明确的文字或 aria-label
□ 可以用键盘导航
□ 颜色对比度足够
```

---

## ✅ 性能

```
□ 避免不必要的重渲染
□ 大列表使用虚拟化
□ 图片优化（Next.js Image）
□ 按需导入组件
□ 没有内存泄漏（清理副作用）
```

---

## ✅ 代码质量

```
□ 没有 console.log 残留
□ 没有被注释掉的代码
□ 没有 TODO 遗留（或已记录）
□ ESLint 无警告
□ 命名清晰一致
```

---

## ✅ 测试（如适用）

```
□ 关键交互有测试覆盖
□ 边界情况有测试
□ 测试通过
```

---

## 快速自查命令

```bash
# 类型检查
pnpm type-check

# ESLint 检查
pnpm lint

# 格式化
pnpm format
```

