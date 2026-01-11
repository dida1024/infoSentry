# 文档风格指南

> 确保文档风格统一

---

## 1. 语言风格

### 1.1 语气

- 使用专业但友好的语气
- 避免过于正式或过于随意
- 直接说明，不绕弯子

```markdown
# ❌ 过于正式
请务必确保您已经完成了所有必要的配置步骤

# ❌ 过于随意
搞定配置就能跑起来了～

# ✅ 适中
完成配置后即可启动服务
```

### 1.2 人称

- 指导性文档使用"你"
- 解释性文档可用"我们"或无人称

```markdown
# ✅ 指导性
你需要先安装依赖，然后运行迁移脚本

# ✅ 解释性
系统采用 DDD 架构，将业务逻辑与基础设施分离
```

### 1.3 时态

- 描述系统行为用现在时
- 描述历史决策可用过去时

```markdown
# ✅ 现在时
Agent 接收匹配结果，进行分桶决策

# ✅ 过去时（ADR 中）
我们选择了 pgvector，因为它与现有 PostgreSQL 集成更好
```

---

## 2. 术语规范

### 2.1 项目专有名词

统一使用以下写法：

| 正确 | 错误 |
|------|------|
| infoSentry | InfoSentry, Infosentry |
| Goal | goal（作为概念时大写） |
| Source | source（作为概念时大写） |
| Agent | agent（作为概念时大写） |
| Immediate/Batch/Digest | immediate/batch/digest（推送类型） |

### 2.2 技术术语

| 正确 | 错误 |
|------|------|
| PostgreSQL | Postgres, postgres |
| Redis | redis |
| FastAPI | Fastapi, fastAPI |
| Celery | celery |
| pgvector | PGVector, pg_vector |

### 2.3 缩写

首次出现时给出全称：

```markdown
使用 DDD（Domain-Driven Design，领域驱动设计）架构...
```

---

## 3. 格式规范

### 3.1 标点符号

- 中文使用中文标点：，。！？：；
- 英文/代码使用英文标点
- 列表项结尾不加标点

```markdown
# ✅
- 第一项
- 第二项

# ❌
- 第一项。
- 第二项；
```

### 3.2 空格

中英文之间加空格：

```markdown
# ✅
使用 FastAPI 构建 API

# ❌
使用FastAPI构建API
```

### 3.3 数字

- 数字与单位之间加空格
- 版本号不加空格

```markdown
# ✅
文件大小：10 MB
版本：v0.1.0

# ❌
文件大小：10MB
版本：v 0.1.0
```

---

## 4. 代码格式

### 4.1 行内代码

用于变量名、函数名、文件名等：

```markdown
调用 `create_goal()` 函数创建目标
配置文件位于 `src/core/config.py`
```

### 4.2 代码块

- 始终指定语言
- 注释文件路径

```markdown
```python
# src/modules/goals/domain/entities.py
class Goal:
    pass
```
```

### 4.3 命令行

使用 `bash` 或 `shell`：

```markdown
```bash
# 安装依赖
uv sync

# 运行迁移
uv run alembic upgrade head
```
```

---

## 5. 链接规范

### 5.1 内部链接

使用相对路径：

```markdown
详见 [技术规格](./TECH_SPEC_v0.md)
```

### 5.2 外部链接

使用完整 URL，并说明链接内容：

```markdown
参考 [FastAPI 官方文档](https://fastapi.tiangolo.com/)
```

### 5.3 锚点链接

链接到文档内的章节：

```markdown
见 [配置说明](#3-配置)
```

---

## 6. 图表规范

### 6.1 ASCII 图

简单流程图使用 ASCII：

```markdown
```
[Input] → [Process] → [Output]
```
```

### 6.2 Mermaid

复杂图使用 Mermaid（如果支持）：

```markdown
```mermaid
graph LR
    A[Start] --> B[Process]
    B --> C[End]
```
```

---

## 7. 文件命名

| 类型 | 命名规范 | 示例 |
|------|----------|------|
| 规格文档 | UPPER_SNAKE_CASE | `TECH_SPEC_v0.md` |
| 指南文档 | UPPER_SNAKE_CASE | `DEPLOYMENT.md` |
| Agent 文档 | kebab-case | `anti-patterns.md` |
| 模板 | kebab-case | `prd-template.md` |

---

## 8. 检查清单

提交文档前检查：

```
□ 标题层级正确（只有一个 H1）
□ 术语拼写统一
□ 中英文之间有空格
□ 代码块有语言标注
□ 链接有效
□ 无拼写错误
```

