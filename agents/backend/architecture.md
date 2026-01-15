# 后端架构指南

> 本项目采用 DDD（领域驱动设计）风格的模块化单体架构

---

## 1. 分层架构

```
┌─────────────────────────────────────────┐
│              Interfaces                  │  HTTP 路由、事件处理
├─────────────────────────────────────────┤
│              Application                 │  用例编排、事务管理
├─────────────────────────────────────────┤
│                Domain                    │  业务逻辑、实体、规则
├─────────────────────────────────────────┤
│             Infrastructure               │  技术实现（DB、Redis、外部 API）
└─────────────────────────────────────────┘
```

---

## 2. 层级职责

### 2.1 Domain 层

**职责**：纯业务逻辑，不依赖任何框架

```python
# domain/entities.py
@dataclass
class Goal:
    id: str
    name: str
    description: str
    status: GoalStatus
    
    def pause(self) -> None:
        if self.status != GoalStatus.ACTIVE:
            raise InvalidStateError("Only active goals can be paused")
        self.status = GoalStatus.PAUSED
```

**包含**：
- `entities.py` - 实体
- `value_objects.py` - 值对象
- `repository.py` - 仓储接口（抽象类）
- `services.py` - 领域服务
- `exceptions.py` - 领域异常

### 2.2 Application 层

**职责**：用例编排，协调领域对象

```python
# application/services.py
class GoalService:
    def __init__(self, goal_repo: GoalRepository):
        self.goal_repo = goal_repo
    
    async def pause_goal(self, goal_id: str, user_id: str) -> Goal:
        goal = await self.goal_repo.get_by_id(goal_id)
        if not goal:
            raise GoalNotFoundError(goal_id)
        
        goal.pause()  # 调用领域方法
        await self.goal_repo.save(goal)
        return goal
```

**包含**：
- `services.py` - 应用服务
- `commands.py` - 命令对象
- `queries.py` - 查询对象

### 2.3 Infrastructure 层

**职责**：技术实现

```python
# infrastructure/repository.py
class SQLAlchemyGoalRepository(GoalRepository):
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_by_id(self, goal_id: str) -> Goal | None:
        model = await self.session.get(GoalModel, goal_id)
        return GoalMapper.to_entity(model) if model else None
```

**包含**：
- `models.py` - SQLAlchemy 模型
- `repository.py` - 仓储实现
- `mappers.py` - 实体-模型映射

### 2.4 Interfaces 层

**职责**：对外接口

```python
# interfaces/routers.py
router = APIRouter(prefix="/goals", tags=["goals"])

@router.post("/", response_model=GoalResponse)
async def create_goal(
    request: CreateGoalRequest,
    service: GoalService = Depends(get_goal_service),
) -> GoalResponse:
    goal = await service.create_goal(...)
    return GoalResponse.model_validate(goal)
```

**包含**：
- `routers.py` - FastAPI 路由
- `schemas.py` - Pydantic 模型

---

## 3. 依赖规则

```
interfaces ──→ application ──→ domain
     │              │
     └──────→ infrastructure
                    │
                    └──→ domain (实现接口)
```

**关键规则**：
- ✅ Domain 不依赖任何其他层
- ✅ Application 只依赖 Domain
- ✅ Infrastructure 实现 Domain 定义的接口
- ✅ Interfaces 调用 Application
- ✅ Interfaces 不直接依赖 Domain 仓储/实体（通过 Application 服务或 DTO）

---

## 4. 模块边界

### 4.1 模块间通信

```python
# ✅ 通过 Application Service 调用
class PushService:
    def __init__(self, goal_service: GoalService):
        self.goal_service = goal_service
    
    async def get_goal_context(self, goal_id: str) -> GoalContext:
        goal = await self.goal_service.get_goal(goal_id)
        ...

# ❌ 跨模块直接访问 Repository
class PushService:
    def __init__(self, goal_repo: GoalRepository):  # 不推荐
        ...
```

### 4.2 事件驱动解耦

```python
# 发布事件
class GoalService:
    async def create_goal(self, ...) -> Goal:
        goal = Goal.create(...)
        await self.event_publisher.publish(GoalCreated(goal_id=goal.id))
        return goal

# 订阅事件（另一个模块）
@event_handler(GoalCreated)
async def handle_goal_created(event: GoalCreated):
    await match_service.compute_matches_for_goal(event.goal_id)
```

---

## 5. 常见问题

### Q: 什么时候需要新建模块？

当满足以下条件时考虑新建模块：
1. 有独立的领域概念
2. 有独立的数据表
3. 可以独立变更和部署（未来）

### Q: 模块间如何共享代码？

放在 `src/core/` 下：
- `core/domain/` - 领域基类
- `core/infrastructure/` - 基础设施
- `core/interfaces/` - 接口基类

### Q: 简单 CRUD 需要完整分层吗？

可以简化，但保持目录结构：
```python
# 简单模块可以合并文件
modules/simple/
├── domain.py          # 合并 entities + repository
├── infrastructure.py  # 合并 models + repository impl
└── interfaces.py      # 合并 routers + schemas
```

---

## 参考

- [Cosmic Python](https://www.cosmicpython.com/) - Python DDD 最佳实践
- [Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
