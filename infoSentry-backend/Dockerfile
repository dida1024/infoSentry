# ============================================
# infoSentry Backend - Multi-stage Dockerfile
# ============================================
# 优化目标：镜像从 ~900MB 降至 ~300-400MB

# ===== Stage 1: Builder =====
# 负责安装依赖，包含构建工具
FROM python:3.12-slim AS builder

WORKDIR /app

# 安装构建依赖（仅构建阶段需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# 复制依赖文件
COPY pyproject.toml uv.lock ./

# 安装依赖到 .venv（--no-dev 排除开发依赖）
RUN uv sync --frozen --no-dev

# ===== Stage 2: Runtime =====
# 最小化运行镜像
FROM python:3.12-slim AS runtime

WORKDIR /app

# 只安装运行时需要的库
# - libpq5: PostgreSQL 客户端库（psycopg 运行时需要）
# - curl: healthcheck 需要
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 从 builder 复制虚拟环境（包含所有 Python 依赖）
COPY --from=builder /app/.venv /app/.venv

# 复制应用代码（src、prompts, resources 和入口文件）
COPY src/ ./src/
COPY resources/ ./resources/
COPY prompts/ ./prompts/
COPY main.py ./

# 设置环境变量
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"
ENV PYTHONUNBUFFERED=1

# 创建非 root 用户
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# 暴露端口
EXPOSE 8000

# 默认启动命令（可被 docker-compose command 覆盖）
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
