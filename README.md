# infoSentry（Monorepo）

本仓库采用单仓库（monorepo）管理方式，统一维护前端、后端与基础设施配置。

## 目录结构

- `infoSentry-backend/`：后端（FastAPI + SQLModel + Alembic + Celery）
- `infosentry-web/`：前端（Next.js）
- `nginx/`：Nginx 配置
- `docker-compose.dev.yml`：开发环境编排
- `docker-compose.prod.yml`：生产环境编排
- `docs/`：产品/规格/运维/开发规范文档

## 快速开始（推荐）

使用 Docker Compose 启动开发环境：

```bash
make dev
```

服务地址：

- API: `http://localhost:8000`
- Web: `http://localhost:3000`

## 详细文档

- 文档索引：`docs/README.md`
- 后端说明：`infoSentry-backend/README.md`
- 前端说明：`infosentry-web/README.md`
