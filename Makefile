.PHONY: format format-check lint test dev-infra dev dev-stop

format:
	cd infoSentry-backend && uv run ruff format .

format-check:
	cd infoSentry-backend && uv run ruff format --check .
	cd infoSentry-backend && uv run ruff check .
	cd infosentry-web && npm run lint

lint:
	cd infoSentry-backend && uv run ruff check .
	cd infoSentry-backend && uv run mypy .
	cd infosentry-web && npm run lint

test:
	cd infoSentry-backend && uv run pytest

# ============================================
# 开发环境启动
# ============================================

dev-infra:  ## 启动 backend/PostgreSQL + Redis (docker)
	docker-compose -f infoSentry-backend/docker-compose.yml up -d postgres redis
# 	数据库迁移脚本
	cd infoSentry-backend && uv run alembic upgrade head

dev:  ## 一键启动所有应用服务 (需先运行 dev-infra)
	cd infoSentry-backend && uv run honcho start -f ../Procfile.dev

dev-stop:  ## 停止所有 docker 服务
	docker-compose -f infoSentry-backend/docker-compose.yml down

