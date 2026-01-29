#!/bin/bash
# ============================================
# infoSentry 镜像打包脚本
# ============================================
# 功能：编译应用容器镜像并打包成压缩包
# 用法：./scripts/pack.sh [--no-build] [output_name]
#   --no-build  跳过构建，直接打包已有镜像
# 输出：infosentry-images-{timestamp}.tar.gz

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 解析参数
SKIP_BUILD=false
OUTPUT_NAME=""
for arg in "$@"; do
    case "$arg" in
        --no-build) SKIP_BUILD=true ;;
        *) OUTPUT_NAME="$arg" ;;
    esac
done

# 切换到项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# 输出文件名
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_NAME="${OUTPUT_NAME:-infosentry-images-${TIMESTAMP}}"
OUTPUT_DIR="$PROJECT_ROOT/dist"
OUTPUT_FILE="$OUTPUT_DIR/${OUTPUT_NAME}.tar.gz"

# 需要构建的服务（排除 postgres 和 redis）
APP_SERVICES=(
    "api"
    "web"
    "worker_ingest"
    "worker_embed_match"
    "worker_agent"
    "worker_email"
    "beat"
)

# 镜像名称前缀
IMAGE_PREFIX="infosentry"

log_info "======================================"
log_info "infoSentry 镜像打包脚本"
log_info "======================================"
log_info "项目目录: $PROJECT_ROOT"
log_info "输出文件: $OUTPUT_FILE"
log_info "目标服务: ${APP_SERVICES[*]}"
echo ""

# 创建输出目录
mkdir -p "$OUTPUT_DIR"

# 临时目录存放镜像文件
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

# 步骤 1: 构建（可跳过）
if [ "$SKIP_BUILD" = true ]; then
    log_info "步骤 1/3: 跳过构建（--no-build）"
else
    log_info "步骤 1/3: 构建 Docker 镜像..."
    echo ""

    # 构建所有服务镜像
    for service in "${APP_SERVICES[@]}"; do
        log_info "构建 ${service}..."
        docker compose build "$service" --no-cache
    done

    log_info "所有镜像构建完成"
fi
echo ""

log_info "步骤 2/3: 导出镜像..."
echo ""

# 获取 docker compose 项目名（默认为目录名小写）
COMPOSE_PROJECT=$(docker compose config --format json 2>/dev/null | python3 -c "import sys,json;print(json.load(sys.stdin)['name'])" 2>/dev/null || echo "$IMAGE_PREFIX")
log_info "Compose 项目名: $COMPOSE_PROJECT"

# 收集镜像名称
IMAGES=()
for service in "${APP_SERVICES[@]}"; do
    image_name="${COMPOSE_PROJECT}-${service}"
    IMAGES+=("$image_name")
    log_info "记录镜像: $image_name"
done

# 保存所有镜像到单个 tar 文件
log_info "导出镜像到 tar 文件..."
docker save "${IMAGES[@]}" -o "$TEMP_DIR/images.tar"

# 复制 docker-compose.yml
cp "$PROJECT_ROOT/docker-compose.yml" "$TEMP_DIR/"

# 复制 .env.example（如果存在）
if [ -f "$PROJECT_ROOT/.env.example" ]; then
    cp "$PROJECT_ROOT/.env.example" "$TEMP_DIR/"
fi

# 生成镜像清单
cat > "$TEMP_DIR/manifest.txt" << EOF
# infoSentry 镜像包清单
# 打包时间: $(date '+%Y-%m-%d %H:%M:%S')
# 打包平台: $(uname -s) $(uname -m)

镜像列表:
$(printf '%s\n' "${IMAGES[@]}")

文件清单:
- images.tar        Docker 镜像文件
- docker-compose.yml  编排配置
- manifest.txt      本清单文件
EOF

log_info "步骤 3/3: 创建压缩包..."
echo ""

# 创建压缩包
cd "$TEMP_DIR"
tar -czvf "$OUTPUT_FILE" ./*

# 显示结果
FILE_SIZE=$(du -h "$OUTPUT_FILE" | cut -f1)
log_info "======================================"
log_info "打包完成!"
log_info "======================================"
log_info "输出文件: $OUTPUT_FILE"
log_info "文件大小: $FILE_SIZE"
echo ""
log_info "部署说明:"
log_info "1. 将 $OUTPUT_FILE 传输到目标服务器"
log_info "2. 运行: ./scripts/deploy.sh ${OUTPUT_NAME}.tar.gz"
