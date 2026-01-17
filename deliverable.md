# Deliverable: Backend Standards Remediation (Pass 2)

## Key Changes
- Replaced interface-layer domain enum dependencies with API-layer enums in schemas (goals, sources, agent, push).
- Mapped interface enums to application/domain via value conversion in routers.
- Moved remaining hardcoded task/tool constants to settings and wired usages.
- Added missing async return type annotations in sources/agent tasks.

## Files Touched
- `infoSentry-backend/src/modules/goals/interfaces/schemas.py`
- `infoSentry-backend/src/modules/goals/interfaces/router.py`
- `infoSentry-backend/src/modules/sources/interfaces/schemas.py`
- `infoSentry-backend/src/modules/sources/interfaces/router.py`
- `infoSentry-backend/src/modules/sources/application/services.py`
- `infoSentry-backend/src/modules/agent/interfaces/schemas.py`
- `infoSentry-backend/src/modules/push/interfaces/schemas.py`
- `infoSentry-backend/src/modules/push/interfaces/router.py`
- `infoSentry-backend/src/core/config.py`
- `infoSentry-backend/src/modules/items/tasks.py`
- `infoSentry-backend/src/modules/items/application/match_service.py`
- `infoSentry-backend/src/modules/agent/application/tools.py`
- `infoSentry-backend/src/modules/agent/tasks.py`
- `infoSentry-backend/src/modules/push/tasks.py`
- `infoSentry-backend/src/modules/sources/tasks.py`
