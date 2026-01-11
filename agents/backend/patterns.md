# 后端常用模式

> 本项目推荐使用的设计模式和最佳实践

---

## 1. Repository 模式

### 用途

封装数据访问逻辑，领域层不关心存储细节

### 实现

```python
# domain/repository.py (接口)
from abc import ABC, abstractmethod

class GoalRepository(ABC):
    @abstractmethod
    async def get_by_id(self, goal_id: str) -> Goal | None:
        ...
    
    @abstractmethod
    async def save(self, goal: Goal) -> None:
        ...
    
    @abstractmethod
    async def list_by_user(self, user_id: str) -> list[Goal]:
        ...

# infrastructure/repository.py (实现)
class SQLAlchemyGoalRepository(GoalRepository):
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_by_id(self, goal_id: str) -> Goal | None:
        model = await self.session.get(GoalModel, goal_id)
        return GoalMapper.to_entity(model) if model else None
```

---

## 2. Mapper 模式

### 用途

在领域实体和数据库模型之间转换

### 实现

```python
# infrastructure/mappers.py
class GoalMapper:
    @staticmethod
    def to_entity(model: GoalModel) -> Goal:
        return Goal(
            id=model.id,
            name=model.name,
            description=model.description,
            status=GoalStatus(model.status),
            created_at=model.created_at,
        )
    
    @staticmethod
    def to_model(entity: Goal) -> GoalModel:
        return GoalModel(
            id=entity.id,
            name=entity.name,
            description=entity.description,
            status=entity.status.value,
            created_at=entity.created_at,
        )
```

---

## 3. Service 模式

### 用途

封装业务用例，协调领域对象

### 实现

```python
# application/services.py
class GoalService:
    def __init__(
        self,
        goal_repo: GoalRepository,
        event_publisher: EventPublisher,
    ):
        self.goal_repo = goal_repo
        self.event_publisher = event_publisher
    
    async def create_goal(
        self,
        name: str,
        description: str,
        user_id: str,
    ) -> Goal:
        goal = Goal.create(
            id=generate_id(),
            name=name,
            description=description,
            user_id=user_id,
        )
        
        await self.goal_repo.save(goal)
        await self.event_publisher.publish(GoalCreated(goal_id=goal.id))
        
        return goal
```

---

## 4. 依赖注入

### 用途

解耦组件，便于测试

### 实现

```python
# FastAPI Depends
def get_goal_service(
    session: AsyncSession = Depends(get_session),
) -> GoalService:
    repo = SQLAlchemyGoalRepository(session)
    publisher = RedisEventPublisher()
    return GoalService(goal_repo=repo, event_publisher=publisher)

# 路由使用
@router.get("/{goal_id}")
async def get_goal(
    goal_id: str,
    service: GoalService = Depends(get_goal_service),
):
    return await service.get_goal(goal_id)
```

---

## 5. 工厂模式

### 用途

创建复杂对象，隐藏创建细节

### 实现

```python
# infrastructure/fetchers/factory.py
class FetcherFactory:
    @staticmethod
    def create(source: Source) -> BaseFetcher:
        match source.type:
            case SourceType.RSS:
                return RSSFetcher(source.config)
            case SourceType.NEWSNOW:
                return NewsNowFetcher(source.config)
            case SourceType.SITE:
                return SiteFetcher(source.config)
            case _:
                raise ValueError(f"Unknown source type: {source.type}")
```

---

## 6. 策略模式

### 用途

定义一族算法，使它们可以互换

### 实现

```python
# 抽象策略
class BaseFetcher(ABC):
    @abstractmethod
    async def fetch(self) -> list[RawItem]:
        ...

# 具体策略
class RSSFetcher(BaseFetcher):
    async def fetch(self) -> list[RawItem]:
        # RSS 解析逻辑
        ...

class NewsNowFetcher(BaseFetcher):
    async def fetch(self) -> list[RawItem]:
        # NewsNow 解析逻辑
        ...
```

---

## 7. 重试模式

### 用途

处理临时性故障

### 实现

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
async def call_external_api(url: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()
```

---

## 8. 熔断模式

### 用途

防止级联故障，快速失败

### 实现

```python
# 简单的预算熔断
class BudgetService:
    async def check_embedding_allowed(self) -> bool:
        status = await self.get_budget_status()
        if status.embedding_disabled:
            return False
        if status.usd_est >= self.daily_budget:
            await self.disable_embedding()
            return False
        return True
```

---

## 9. 事件溯源模式（简化版）

### 用途

记录所有状态变更，支持回放

### 实现

```python
# Agent 运行记录
class AgentRun:
    run_id: str
    input_snapshot: dict
    tool_calls: list[ToolCall]
    actions: list[Action]
    
    def replay(self) -> list[Action]:
        """根据输入快照重放，对比结果"""
        ...
```

---

## 参考

- [Python Design Patterns](https://refactoring.guru/design-patterns/python)
- [Enterprise Integration Patterns](https://www.enterpriseintegrationpatterns.com/)

