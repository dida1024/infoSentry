"""API router configuration."""

from fastapi import APIRouter

from src.modules.agent.interfaces.router import router as agent_router
from src.modules.goals.interfaces.router import router as goals_router
from src.modules.push.interfaces.router import router as push_router
from src.modules.sources.interfaces.router import router as sources_router
from src.modules.users.interfaces.router import router as users_router

api_router = APIRouter()

# Auth and Users
api_router.include_router(users_router)

# Sources
api_router.include_router(sources_router)

# Goals
api_router.include_router(goals_router)

# Push/Notifications
api_router.include_router(push_router)

# Agent/Observability
api_router.include_router(agent_router)
