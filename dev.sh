#!/bin/bash

# ============================================
# infoSentry 开发环境快速启动脚本
# ============================================

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 配置文件
COMPOSE_FILE="docker-compose.dev.yml"
ENV_FILE=".env.dev"

# 打印带颜色的消息
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查 .env.dev 文件
check_env_file() {
    if [ ! -f "$ENV_FILE" ]; then
        print_warn ".env.dev 文件不存在，是否从示例创建? (y/n)"
        read -r response
        if [[ "$response" =~ ^[Yy]$ ]]; then
            cp .env.dev.example "$ENV_FILE"
            print_info "已创建 $ENV_FILE，请根据需要修改配置"
        else
            print_warn "将使用默认配置启动"
            ENV_FILE=""
        fi
    fi
}

# 启动基础服务（仅数据库）
start_base() {
    print_info "启动基础服务 (PostgreSQL + Redis)..."
    if [ -n "$ENV_FILE" ]; then
        docker-compose -f $COMPOSE_FILE --env-file $ENV_FILE up -d postgres redis
    else
        docker-compose -f $COMPOSE_FILE up -d postgres redis
    fi
    print_info "基础服务已启动"
    print_info "PostgreSQL: localhost:5432 (用户: postgres, 密码: postgres)"
    print_info "Redis: localhost:6379"
}

# 启动核心服务（数据库 + API + Web）
start_core() {
    print_info "启动核心服务 (PostgreSQL + Redis + API + Web)..."
    if [ -n "$ENV_FILE" ]; then
        docker-compose -f $COMPOSE_FILE --env-file $ENV_FILE up -d postgres redis api web
    else
        docker-compose -f $COMPOSE_FILE up -d postgres redis api web
    fi
    print_info "核心服务已启动"
    print_info "API: http://localhost:8000"
    print_info "Web: http://localhost:3000"
    print_info "PostgreSQL: localhost:5432"
    print_info "Redis: localhost:6379"
}

# 启动所有服务（包括 Workers）
start_all() {
    print_info "启动所有服务 (包括所有 Workers)..."
    if [ -n "$ENV_FILE" ]; then
        docker-compose -f $COMPOSE_FILE --env-file $ENV_FILE --profile workers up -d
    else
        docker-compose -f $COMPOSE_FILE --profile workers up -d
    fi
    print_info "所有服务已启动"
    show_services
}

# 启动开发工具
start_tools() {
    print_info "启动开发工具 (Redis UI + PgAdmin + Flower)..."
    if [ -n "$ENV_FILE" ]; then
        docker-compose -f $COMPOSE_FILE --env-file $ENV_FILE --profile tools up -d
    else
        docker-compose -f $COMPOSE_FILE --profile tools up -d
    fi
    print_info "开发工具已启动"
    print_info "Redis UI: http://localhost:8081"
    print_info "PgAdmin: http://localhost:5050 (用户: admin@infosentry.local, 密码: admin)"
    print_info "Flower: http://localhost:5555"
}

# 停止所有服务
stop_all() {
    print_info "停止所有服务..."
    docker-compose -f $COMPOSE_FILE --profile workers --profile tools down
    print_info "所有服务已停止"
}

# 重启服务
restart() {
    print_info "重启服务..."
    stop_all
    case "$1" in
        base)
            start_base
            ;;
        core)
            start_core
            ;;
        all)
            start_all
            ;;
        *)
            start_core
            ;;
    esac
}

# 查看日志
show_logs() {
    if [ -z "$1" ]; then
        docker-compose -f $COMPOSE_FILE logs -f
    else
        docker-compose -f $COMPOSE_FILE logs -f "$1"
    fi
}

# 显示服务状态
show_status() {
    print_info "服务状态:"
    docker-compose -f $COMPOSE_FILE ps
}

# 显示所有服务地址
show_services() {
    print_info "服务地址:"
    echo "  API:          http://localhost:8000"
    echo "  API Docs:     http://localhost:8000/docs"
    echo "  Web:          http://localhost:3000"
    echo "  PostgreSQL:   localhost:5432"
    echo "  Redis:        localhost:6379"
    echo ""
    print_info "开发工具 (需要 --profile tools):"
    echo "  Redis UI:     http://localhost:8081"
    echo "  PgAdmin:      http://localhost:5050"
    echo "  Flower:       http://localhost:5555"
}

# 执行数据库迁移
run_migration() {
    print_info "执行数据库迁移..."
    docker-compose -f $COMPOSE_FILE exec api uv run alembic upgrade head
    print_info "数据库迁移完成"
}

# 进入容器 shell
enter_shell() {
    if [ -z "$1" ]; then
        print_error "请指定服务名称，例如: ./dev.sh shell api"
        exit 1
    fi
    docker-compose -f $COMPOSE_FILE exec "$1" /bin/sh
}

# 清理数据
clean_data() {
    print_warn "警告：这将删除所有开发环境数据！"
    print_warn "是否继续? (y/n)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        print_info "停止服务并清理数据..."
        docker-compose -f $COMPOSE_FILE --profile workers --profile tools down -v
        print_info "数据已清理"
    else
        print_info "取消操作"
    fi
}

# 显示帮助信息
show_help() {
    cat << EOF
infoSentry 开发环境管理脚本

用法: ./dev.sh <command> [options]

命令:
  base              启动基础服务 (PostgreSQL + Redis)
  core              启动核心服务 (基础 + API + Web) [默认]
  all               启动所有服务 (核心 + Workers)
  tools             启动开发工具 (Redis UI + PgAdmin + Flower)

  stop              停止所有服务
  restart [mode]    重启服务 (mode: base|core|all)

  logs [service]    查看日志 (不指定 service 则查看所有)
  status            查看服务状态
  services          显示所有服务地址

  migrate           执行数据库迁移
  shell <service>   进入容器 shell
  clean             停止服务并清理所有数据

  help              显示此帮助信息

示例:
  ./dev.sh core              # 启动核心服务
  ./dev.sh all               # 启动所有服务
  ./dev.sh tools             # 启动开发工具
  ./dev.sh logs api          # 查看 API 日志
  ./dev.sh shell api         # 进入 API 容器
  ./dev.sh migrate           # 执行数据库迁移

快速开始:
  1. ./dev.sh core           # 启动核心服务
  2. ./dev.sh migrate        # 执行数据库迁移
  3. ./dev.sh services       # 查看服务地址

EOF
}

# 主程序
main() {
    # 检查是否在项目根目录
    if [ ! -f "$COMPOSE_FILE" ]; then
        print_error "请在项目根目录运行此脚本"
        exit 1
    fi

    # 检查环境变量文件
    check_env_file

    # 解析命令
    case "${1:-core}" in
        base)
            start_base
            ;;
        core)
            start_core
            ;;
        all)
            start_all
            ;;
        tools)
            start_tools
            ;;
        stop)
            stop_all
            ;;
        restart)
            restart "${2:-core}"
            ;;
        logs)
            show_logs "$2"
            ;;
        status)
            show_status
            ;;
        services)
            show_services
            ;;
        migrate)
            run_migration
            ;;
        shell)
            enter_shell "$2"
            ;;
        clean)
            clean_data
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            print_error "未知命令: $1"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
