# Contributing

本仓库为单仓库（monorepo）。请避免在子目录单独初始化 Git；所有改动通过根目录统一提交与审阅。

## 分支与提交

- 主分支：`main`（保持可部署/可运行）
- 功能分支建议：
  - `feat(api)-...` / `fix(api)-...`：后端相关
  - `feat(web)-...` / `fix(web)-...`：前端相关
  - `chore(infra)-...`：Compose/Nginx/脚本
  - `docs-...`：文档
- 提交信息建议使用 Conventional Commits：
  - `feat(api): ...` `fix(web): ...` `chore(infra): ...` `docs: ...`

## 本地开发

从根目录启动（推荐）：

```bash
./dev.sh core
./dev.sh migrate
```

## 代码格式检查（推荐）

在仓库根目录：

```bash
make format-check
```

## 后端（`infoSentry-backend/`）

```bash
cd infoSentry-backend
uv run ruff check .
uv run mypy .
uv run pytest
```

## 前端（`infosentry-web/`）

```bash
cd infosentry-web
npm run lint
npm run build
```

## 配置与密钥

- 不要提交 `.env` / `.env.*` 等包含密钥的文件
- 请提交示例文件：`.env.example` / `.env.*.example` / `env.example`
