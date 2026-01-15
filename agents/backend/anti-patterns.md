# 后端反模式

> 禁止在本项目中使用的做法

---

## 1. 架构反模式

### ❌ Domain 层依赖 Infrastructure

```python
# ❌ 错误：Domain 导入 SQLAlchemy
from sqlalchemy import Column, String
from src.core.infrastructure.database import Base

class Goal(Base):  # Domain 实体不应该继承 ORM 模型
    __tablename__ = "goals"
    id = Column(String, primary_key=True)
```

```python
# ✅ 正确：Domain 是纯 Python
@dataclass
class Goal:
    id: str
    name: str
    description: str
```

---

### ❌ 在路由层写业务逻辑

```python
# ❌ 错误：路由里写业务逻辑
@router.post("/goals")
async def create_goal(request: CreateGoalRequest, session: AsyncSession = Depends()):
    goal = GoalModel(
        id=str(uuid4()),
        name=request.name,
        # 业务验证逻辑...
        # 事件发布逻辑...
    )
    session.add(goal)
    await session.commit()
```

```python
# ✅ 正确：路由只做转发
@router.post("/goals")
async def create_goal(
    request: CreateGoalRequest,
    service: GoalService = Depends(get_goal_service),
):
    goal = await service.create_goal(
        name=request.name,
        description=request.description,
    )
    return GoalResponse.model_validate(goal)
```

---

### ❌ Interfaces 直接依赖 Domain 仓储/实体

```python
# ❌ 错误：接口层直接注入 Domain Repository
from src.modules.goals.domain.repository import GoalRepository

@router.get("/goals/{goal_id}")
async def get_goal(goal_id: str, repo: GoalRepository = Depends(...)):
    goal = await repo.get_by_id(goal_id)
    ...
```

```python
# ✅ 正确：接口层调用 Application Service
from src.modules.goals.application.services import GoalQueryService

@router.get("/goals/{goal_id}")
async def get_goal(goal_id: str, service: GoalQueryService = Depends(...)):
    return await service.get_goal_detail(goal_id)
```

---

### ❌ 跨模块直接访问数据库

```python
# ❌ 错误：Push 模块直接查 Goals 表
class PushService:
    async def send_push(self, goal_id: str):
        goal = await self.session.get(GoalModel, goal_id)  # 跨模块访问
```

```python
# ✅ 正确：通过 Application Service 调用
class PushService:
    def __init__(self, goal_service: GoalService):
        self.goal_service = goal_service
    
    async def send_push(self, goal_id: str):
        goal = await self.goal_service.get_goal(goal_id)
```

---

## 2. 代码反模式

### ❌ 使用 `# type: ignore` 逃避类型检查

```python
# ❌ 错误
result = some_function()  # type: ignore
```

```python
# ✅ 正确：修复类型问题或使用 cast
from typing import cast
result = cast(ExpectedType, some_function())
```

---

### ❌ 捕获 Exception 而不处理

```python
# ❌ 错误：静默吞掉异常
try:
    await do_something()
except Exception:
    pass
```

```python
# ✅ 正确：至少记录日志
try:
    await do_something()
except SpecificError as e:
    logger.warning("Operation failed: %s", e)
    # 决定是否重新抛出
```

```python
# ❌ 错误：接口层吞掉异常并返回通用错误但不记录日志
try:
    ...
except Exception:
    return ApiResponse.error(message="Failed", code=500)
```

```python
# ✅ 正确：记录异常并返回错误响应
try:
    ...
except Exception as e:
    logger.exception("Failed to handle request")
    return ApiResponse.error(message="Failed", code=500)
```

---

### ❌ 硬编码配置值

```python
# ❌ 错误
REDIS_URL = "redis://localhost:6379/0"
API_KEY = "sk-xxxxx"
```

```python
# ✅ 正确：使用配置
from src.core.config import settings

redis_url = settings.REDIS_URL
api_key = settings.OPENAI_API_KEY
```

```python
# ❌ 错误：分页/游标默认值硬编码在服务或路由中
def _decode_cursor(cursor: str | None) -> tuple[int, int]:
    return 1, 20
```

```python
# ✅ 正确：默认值从配置读取
def _decode_cursor(cursor: str | None) -> tuple[int, int]:
    return settings.DEFAULT_PAGE, settings.DEFAULT_PAGE_SIZE
```

---

### ❌ 同步阻塞调用

```python
# ❌ 错误：在 async 函数中使用同步 I/O
async def fetch_data():
    import requests
    response = requests.get(url)  # 阻塞整个事件循环
```

```python
# ✅ 正确：使用 async 库
async def fetch_data():
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
```

---

## 3. 数据库反模式

### ❌ N+1 查询

```python
# ❌ 错误：循环中查询
goals = await goal_repo.list_all()
for goal in goals:
    items = await item_repo.list_by_goal(goal.id)  # N 次查询
```

```python
# ✅ 正确：批量查询或 JOIN
goal_ids = [g.id for g in goals]
items_map = await item_repo.list_by_goals(goal_ids)  # 1 次查询
```

---

### ❌ 在代码中拼接 SQL

```python
# ❌ 错误：SQL 注入风险
query = f"SELECT * FROM goals WHERE id = '{goal_id}'"
```

```python
# ✅ 正确：使用参数化查询
stmt = select(GoalModel).where(GoalModel.id == goal_id)
```

---

### ❌ 不使用事务

```python
# ❌ 错误：多个操作不在事务中
await repo.save(goal)
await repo.save(config)  # 如果失败，goal 已保存，数据不一致
```

```python
# ✅ 正确：使用事务
async with session.begin():
    await repo.save(goal)
    await repo.save(config)
```

---

## 4. API 反模式

### ❌ 返回内部错误信息

```python
# ❌ 错误：暴露内部细节
raise HTTPException(
    status_code=500,
    detail=f"Database error: {str(e)}"  # 暴露数据库信息
)
```

```python
# ✅ 正确：返回通用错误
logger.exception("Database error")
raise HTTPException(
    status_code=500,
    detail="Internal server error"
)
```

---

### ❌ 不一致的响应格式

```python
# ❌ 错误：有时返回 data，有时直接返回对象
@router.get("/goals")
async def list_goals():
    return goals  # 直接返回列表

@router.get("/goals/{id}")
async def get_goal():
    return {"data": goal}  # 包在 data 里
```

```python
# ✅ 正确：统一格式
@router.get("/goals", response_model=ApiResponse[list[GoalResponse]])
@router.get("/goals/{id}", response_model=ApiResponse[GoalResponse])
```

---

## 5. 测试反模式

### ❌ 测试依赖外部服务

```python
# ❌ 错误：单元测试调用真实 API
async def test_embedding():
    result = await openai_client.embeddings.create(...)  # 调用真实 API
```

```python
# ✅ 正确：Mock 外部依赖
async def test_embedding(mock_openai):
    mock_openai.return_value = [0.1, 0.2, ...]
    result = await embedding_service.generate(...)
```

---

### ❌ 测试之间有依赖

```python
# ❌ 错误：test_2 依赖 test_1 的副作用
def test_1_create_goal():
    create_goal(...)

def test_2_update_goal():
    update_goal(goal_id)  # 假设 test_1 已创建
```

```python
# ✅ 正确：每个测试独立
def test_update_goal():
    goal = create_goal(...)  # 测试内部创建
    update_goal(goal.id)
```

---

## 记住

> "如果你不确定某个做法是否正确，问自己：这段代码一年后还容易理解和修改吗？"
