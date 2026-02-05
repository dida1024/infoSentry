#!/bin/bash
# ============================================
# infoSentry 镜像部署脚本
# ============================================
# 功能：解压镜像包并重启应用容器
# 用法：./scripts/deploy.sh <package.tar.gz>
# 注意：不会影响 postgres 和 redis 容器
#
# 镜像架构（优化后）：
#   - infosentry-backend:latest  所有后端服务共用
#   - infosentry-web:latest      前端服务

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 检查参数
if [ -z "$1" ]; then
    log_error "用法: $0 <package.tar.gz>"
    log_error "示例: $0 infosentry-images-20260129_120000.tar.gz"
    exit 1
fi

PACKAGE_FILE="$1"

# 支持相对路径和绝对路径
if [[ ! "$PACKAGE_FILE" = /* ]]; then
    PACKAGE_FILE="$(pwd)/$PACKAGE_FILE"
fi

if [ ! -f "$PACKAGE_FILE" ]; then
    log_error "文件不存在: $PACKAGE_FILE"
    exit 1
fi

# 切换到项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# 应用服务列表（排除数据库和 redis）
APP_SERVICES=(
    "api"
    "web"
    "worker_ingest"
    "worker_embed_match"
    "worker_agent"
    "worker_email"
    "beat"
)

# 需要加载的镜像
EXPECTED_IMAGES=(
    "infosentry-backend:latest"
    "infosentry-web:latest"
)

log_info "======================================"
log_info "infoSentry 镜像部署脚本"
log_info "======================================"
log_info "镜像包: $PACKAGE_FILE"
log_info "项目目录: $PROJECT_ROOT"
log_info "目标服务: ${APP_SERVICES[*]}"
echo ""

# 创建临时目录
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

log_info "步骤 1/4: 解压镜像包..."
tar -xzvf "$PACKAGE_FILE" -C "$TEMP_DIR"

# 显示清单
if [ -f "$TEMP_DIR/manifest.txt" ]; then
    echo ""
    log_info "镜像包清单:"
    cat "$TEMP_DIR/manifest.txt"
    echo ""
fi

log_info "步骤 2/4: 加载 Docker 镜像..."
docker load -i "$TEMP_DIR/images.tar"

# 验证镜像已加载
echo ""
log_info "验证镜像..."
for image in "${EXPECTED_IMAGES[@]}"; do
    if docker image inspect "$image" &>/dev/null; then
        log_info "✓ $image 已加载"
    else
        log_warn "⚠ $image 未找到（可能是旧版镜像包）"
    fi
done
echo ""

log_info "步骤 3/4: 停止应用容器（保留数据库和 Redis）..."
echo ""

# 逐个停止应用容器
for service in "${APP_SERVICES[@]}"; do
    log_info "停止 ${service}..."
    docker compose stop "$service" 2>/dev/null || true
    docker compose rm -f "$service" 2>/dev/null || true
done

log_info "步骤 4/4: 启动应用容器..."
echo ""

# 检查 postgres 和 redis 是否运行
INFRA_RUNNING=true
if ! docker compose ps postgres 2>/dev/null | grep -q "running"; then
    log_warn "postgres 未运行，正在启动..."
    docker compose up -d postgres
    INFRA_RUNNING=false
fi

if ! docker compose ps redis 2>/dev/null | grep -q "running"; then
    log_warn "redis 未运行，正在启动..."
    docker compose up -d redis
    INFRA_RUNNING=false
fi

# 等待基础设施就绪
if [ "$INFRA_RUNNING" = false ]; then
    log_info "等待基础设施服务就绪..."
    sleep 10
fi

# 启动应用容器（api 必须先启动，因为其他后端服务依赖它的镜像构建）
log_info "启动 api..."
docker compose up -d api

# 等待 api 启动
sleep 2

# 启动其他服务
for service in "${APP_SERVICES[@]}"; do
    if [ "$service" != "api" ]; then
        log_info "启动 ${service}..."
        docker compose up -d "$service"
    fi
done

# 等待服务启动
log_info "等待服务启动..."
sleep 5

# 检查服务状态
log_info "======================================"
log_info "部署完成! 服务状态:"
log_info "======================================"
echo ""
docker compose ps

echo ""
log_info "镜像信息:"
docker images | grep -E "infosentry|REPOSITORY" | head -5

echo ""
log_info "提示:"
log_info "- 查看日志: docker compose logs -f"
log_info "- 检查健康: docker compose ps"
log_info "- 如需回滚: 使用之前的镜像包重新部署"
