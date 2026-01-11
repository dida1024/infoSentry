# 后端开发规范

> 基于 [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html) + 项目特定约束

---

## 1. 代码风格

### 1.1 格式化

- **工具**：使用 `ruff` 进行格式化和 lint
- **行宽**：88 字符（Black 默认）
- **缩进**：4 空格

### 1.2 导入顺序

```python
# 1. 标准库
from datetime import datetime
from typing import Optional

# 2. 第三方库
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

# 3. 本项目 core
from src.core.domain.repository import Repository
from src.core.infrastructure.database import get_session

# 4. 本模块
from .entities import Goal
from .repository import GoalRepository
```

---

## 2. 类型注解

### 2.1 必须使用类型注解

```python
# ✅ 
async def get_goal(self, goal_id: str) -> Goal | None:
    ...

# ❌ 
async def get_goal(self, goal_id):
    ...
```

### 2.2 使用现代语法

```python
# ✅ Python 3.10+
def process(items: list[str]) -> dict[str, int]:
    ...

# ❌ 旧语法
from typing import List, Dict
def process(items: List[str]) -> Dict[str, int]:
    ...
```

---

## 3. 错误处理

### 3.1 业务异常

```python
# 定义在 domain/exceptions.py
class GoalNotFoundError(DomainException):
    def __init__(self, goal_id: str):
        super().__init__(f"Goal not found: {goal_id}")
        self.goal_id = goal_id
```

### 3.2 异常传播

```
domain 抛出 → application 处理/转换 → interfaces 返回 HTTP 错误
```

### 3.3 禁止静默捕获

```python
# ❌ 禁止
try:
    ...
except Exception:
    pass

# ✅ 至少记录日志
try:
    ...
except SomeException as e:
    logger.exception("Failed to process: %s", e)
    raise
```

---

## 4. 日志规范

### 4.1 使用 structlog

```python
import structlog

logger = structlog.get_logger(__name__)

# 结构化日志
logger.info("goal_created", goal_id=goal.id, user_id=user_id)
```

### 4.2 日志级别

| 级别 | 用途 |
|------|------|
| DEBUG | 调试信息（生产关闭） |
| INFO | 业务事件（创建、更新、删除） |
| WARNING | 可恢复的异常情况 |
| ERROR | 需要关注的错误 |

---

## 5. 数据库操作

### 5.1 使用 Repository 模式

```python
# ✅ 通过 Repository
goal = await goal_repository.get_by_id(goal_id)

# ❌ 直接 session 操作（除非在 Repository 内部）
goal = await session.get(GoalModel, goal_id)
```

### 5.2 事务边界

```python
# 事务在 Application Service 层管理
async def create_goal(self, ...) -> Goal:
    async with self.uow:  # Unit of Work
        goal = Goal.create(...)
        await self.goal_repo.save(goal)
        await self.uow.commit()
    return goal
```

---

## 6. Pydantic 模型

### 6.1 请求/响应 Schema

```python
from pydantic import BaseModel, Field

class CreateGoalRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1)

class GoalResponse(BaseModel):
    id: str
    name: str
    description: str
    created_at: datetime
    
    model_config = {"from_attributes": True}
```

### 6.2 领域实体 vs Schema

- **领域实体**：业务逻辑，定义在 `domain/entities.py`
- **Pydantic Schema**：接口层序列化，定义在 `interfaces/schemas.py`

---

## 7. 测试规范

### 7.1 测试文件命名

```
tests/
├── unit/
│   └── test_goal_service.py
├── integration/
│   └── test_goal_api.py
└── conftest.py
```

### 7.2 测试函数命名

```python
# 格式：test_<被测方法>_<场景>_<期望结果>
def test_create_goal_with_valid_data_returns_goal():
    ...

def test_create_goal_without_name_raises_validation_error():
    ...
```

---

## 8. API 设计

### 8.1 RESTful 规范

| 操作 | 方法 | 路径 | 示例 |
|------|------|------|------|
| 列表 | GET | /resources | GET /goals |
| 详情 | GET | /resources/{id} | GET /goals/123 |
| 创建 | POST | /resources | POST /goals |
| 更新 | PUT/PATCH | /resources/{id} | PUT /goals/123 |
| 删除 | DELETE | /resources/{id} | DELETE /goals/123 |

### 8.2 响应格式

```python
# 成功响应
{
    "success": true,
    "data": { ... },
    "message": null
}

# 错误响应
{
    "success": false,
    "data": null,
    "message": "Goal not found"
}
```

---

## 参考资料

- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- [FastAPI Best Practices](https://github.com/zhanymkanov/fastapi-best-practices)
- [Cosmic Python (DDD with Python)](https://www.cosmicpython.com/)

