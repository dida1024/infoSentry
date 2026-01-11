#!/bin/bash
# ============================================
# infoSentry 备份脚本
# ============================================
# 功能：
#   - PostgreSQL 数据库完整备份（pg_dump）
#   - Redis 数据备份（AOF/RDB 快照）
#   - 自动清理过期备份
#   - 可选上传到 S3/OSS
#
# 使用方法：
#   ./scripts/backup.sh                    # 执行完整备份
#   ./scripts/backup.sh --pg-only          # 仅备份数据库
#   ./scripts/backup.sh --redis-only       # 仅备份 Redis
#   ./scripts/backup.sh --restore pg       # 恢复数据库
#   ./scripts/backup.sh --restore redis    # 恢复 Redis
#
# 建议配置 cron 每日自动备份：
#   0 3 * * * /path/to/scripts/backup.sh >> /var/log/infosentry-backup.log 2>&1

set -euo pipefail

# ============================================
# 配置
# ============================================

# 备份目录
BACKUP_DIR="${BACKUP_DIR:-/data/backups/infosentry}"
PG_BACKUP_DIR="${BACKUP_DIR}/postgres"
REDIS_BACKUP_DIR="${BACKUP_DIR}/redis"

# 保留天数
RETENTION_DAYS="${RETENTION_DAYS:-7}"

# 数据库配置（从环境变量读取或使用默认值）
PG_HOST="${POSTGRES_SERVER:-localhost}"
PG_PORT="${POSTGRES_PORT:-5432}"
PG_USER="${POSTGRES_USER:-infosentry}"
PG_DB="${POSTGRES_DB:-infosentry}"
PGPASSWORD="${POSTGRES_PASSWORD:-}"

# Redis 配置
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"

# Docker 容器名称（如果使用 docker-compose）
PG_CONTAINER="${PG_CONTAINER:-infosentry-postgres}"
REDIS_CONTAINER="${REDIS_CONTAINER:-infosentry-redis}"

# 是否使用 Docker
USE_DOCKER="${USE_DOCKER:-true}"

# 压缩选项
COMPRESS="${COMPRESS:-true}"

# 时间戳
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DATE=$(date +%Y%m%d)

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ============================================
# 辅助函数
# ============================================

log_info() {
    echo -e "${GREEN}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $(date '+%Y-%m-%d %H:%M:%S') $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') $1"
}

ensure_dir() {
    mkdir -p "$1"
}

# ============================================
# PostgreSQL 备份
# ============================================

backup_postgres() {
    log_info "开始 PostgreSQL 备份..."
    ensure_dir "${PG_BACKUP_DIR}"

    local backup_file="${PG_BACKUP_DIR}/pg_backup_${TIMESTAMP}.sql"
    
    if [[ "${USE_DOCKER}" == "true" ]]; then
        # Docker 环境备份
        log_info "使用 Docker 容器备份: ${PG_CONTAINER}"
        docker exec -t "${PG_CONTAINER}" pg_dump -U "${PG_USER}" "${PG_DB}" > "${backup_file}"
    else
        # 直接备份
        export PGPASSWORD
        pg_dump -h "${PG_HOST}" -p "${PG_PORT}" -U "${PG_USER}" "${PG_DB}" > "${backup_file}"
    fi

    if [[ "${COMPRESS}" == "true" ]]; then
        log_info "压缩备份文件..."
        gzip "${backup_file}"
        backup_file="${backup_file}.gz"
    fi

    local file_size=$(du -h "${backup_file}" | cut -f1)
    log_info "PostgreSQL 备份完成: ${backup_file} (${file_size})"
    
    echo "${backup_file}"
}

# ============================================
# Redis 备份
# ============================================

backup_redis() {
    log_info "开始 Redis 备份..."
    ensure_dir "${REDIS_BACKUP_DIR}"

    local backup_file="${REDIS_BACKUP_DIR}/redis_backup_${TIMESTAMP}"
    
    if [[ "${USE_DOCKER}" == "true" ]]; then
        # Docker 环境备份
        log_info "使用 Docker 容器备份: ${REDIS_CONTAINER}"
        
        # 触发 BGSAVE
        docker exec "${REDIS_CONTAINER}" redis-cli BGSAVE
        
        # 等待后台保存完成
        log_info "等待 Redis BGSAVE 完成..."
        sleep 2
        while [[ $(docker exec "${REDIS_CONTAINER}" redis-cli LASTSAVE) == $(docker exec "${REDIS_CONTAINER}" redis-cli LASTSAVE) ]]; do
            sleep 1
        done
        
        # 复制 dump.rdb
        docker cp "${REDIS_CONTAINER}:/data/dump.rdb" "${backup_file}.rdb" 2>/dev/null || true
        
        # 复制 appendonly.aof（如果存在）
        docker cp "${REDIS_CONTAINER}:/data/appendonly.aof" "${backup_file}.aof" 2>/dev/null || true
    else
        # 直接备份
        redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" BGSAVE
        sleep 2
        
        # 复制数据文件
        local redis_data_dir="/var/lib/redis"
        cp "${redis_data_dir}/dump.rdb" "${backup_file}.rdb" 2>/dev/null || true
        cp "${redis_data_dir}/appendonly.aof" "${backup_file}.aof" 2>/dev/null || true
    fi

    if [[ "${COMPRESS}" == "true" ]]; then
        log_info "压缩备份文件..."
        [[ -f "${backup_file}.rdb" ]] && gzip "${backup_file}.rdb"
        [[ -f "${backup_file}.aof" ]] && gzip "${backup_file}.aof"
    fi

    log_info "Redis 备份完成: ${REDIS_BACKUP_DIR}"
}

# ============================================
# 清理过期备份
# ============================================

cleanup_old_backups() {
    log_info "清理 ${RETENTION_DAYS} 天前的备份..."
    
    # 清理 PostgreSQL 备份
    find "${PG_BACKUP_DIR}" -name "pg_backup_*.sql*" -mtime +${RETENTION_DAYS} -delete 2>/dev/null || true
    
    # 清理 Redis 备份
    find "${REDIS_BACKUP_DIR}" -name "redis_backup_*" -mtime +${RETENTION_DAYS} -delete 2>/dev/null || true
    
    log_info "清理完成"
}

# ============================================
# 恢复功能
# ============================================

restore_postgres() {
    local backup_file="$1"
    
    if [[ -z "${backup_file}" ]]; then
        # 找到最新的备份
        backup_file=$(ls -t "${PG_BACKUP_DIR}"/pg_backup_*.sql* 2>/dev/null | head -1)
    fi
    
    if [[ -z "${backup_file}" || ! -f "${backup_file}" ]]; then
        log_error "找不到备份文件: ${backup_file}"
        exit 1
    fi
    
    log_warn "警告：即将恢复数据库，这将覆盖现有数据！"
    log_info "备份文件: ${backup_file}"
    read -p "确定要继续吗？(yes/no) " confirm
    
    if [[ "${confirm}" != "yes" ]]; then
        log_info "取消恢复"
        exit 0
    fi
    
    log_info "开始恢复 PostgreSQL..."
    
    # 解压（如果需要）
    local restore_file="${backup_file}"
    if [[ "${backup_file}" == *.gz ]]; then
        restore_file="${backup_file%.gz}"
        gunzip -k "${backup_file}"
    fi
    
    if [[ "${USE_DOCKER}" == "true" ]]; then
        cat "${restore_file}" | docker exec -i "${PG_CONTAINER}" psql -U "${PG_USER}" "${PG_DB}"
    else
        export PGPASSWORD
        psql -h "${PG_HOST}" -p "${PG_PORT}" -U "${PG_USER}" "${PG_DB}" < "${restore_file}"
    fi
    
    # 清理临时解压文件
    if [[ "${backup_file}" == *.gz ]]; then
        rm -f "${restore_file}"
    fi
    
    log_info "PostgreSQL 恢复完成"
}

restore_redis() {
    local backup_file="$1"
    
    log_warn "Redis 恢复需要手动操作："
    log_info "1. 停止 Redis 服务"
    log_info "2. 复制备份文件到 Redis 数据目录"
    log_info "3. 重启 Redis 服务"
    log_info ""
    log_info "Docker 环境命令："
    log_info "  docker-compose -f docker-compose.prod.yml stop redis"
    log_info "  docker cp ${backup_file} infosentry-redis:/data/"
    log_info "  docker-compose -f docker-compose.prod.yml start redis"
}

# ============================================
# 显示备份状态
# ============================================

show_status() {
    log_info "=== 备份状态 ==="
    log_info ""
    
    log_info "PostgreSQL 备份目录: ${PG_BACKUP_DIR}"
    if [[ -d "${PG_BACKUP_DIR}" ]]; then
        local pg_count=$(ls -1 "${PG_BACKUP_DIR}"/pg_backup_*.sql* 2>/dev/null | wc -l)
        local pg_latest=$(ls -t "${PG_BACKUP_DIR}"/pg_backup_*.sql* 2>/dev/null | head -1)
        local pg_size=$(du -sh "${PG_BACKUP_DIR}" 2>/dev/null | cut -f1)
        log_info "  备份数量: ${pg_count}"
        log_info "  总大小: ${pg_size}"
        [[ -n "${pg_latest}" ]] && log_info "  最新备份: ${pg_latest}"
    else
        log_warn "  目录不存在"
    fi
    
    log_info ""
    log_info "Redis 备份目录: ${REDIS_BACKUP_DIR}"
    if [[ -d "${REDIS_BACKUP_DIR}" ]]; then
        local redis_count=$(ls -1 "${REDIS_BACKUP_DIR}"/redis_backup_* 2>/dev/null | wc -l)
        local redis_size=$(du -sh "${REDIS_BACKUP_DIR}" 2>/dev/null | cut -f1)
        log_info "  备份数量: ${redis_count}"
        log_info "  总大小: ${redis_size}"
    else
        log_warn "  目录不存在"
    fi
}

# ============================================
# 主函数
# ============================================

main() {
    local action="${1:-full}"
    
    log_info "=== infoSentry 备份脚本 ==="
    log_info "时间: $(date)"
    log_info "操作: ${action}"
    log_info ""
    
    case "${action}" in
        "--pg-only")
            backup_postgres
            cleanup_old_backups
            ;;
        "--redis-only")
            backup_redis
            cleanup_old_backups
            ;;
        "--restore")
            local target="${2:-}"
            case "${target}" in
                "pg"|"postgres")
                    restore_postgres "${3:-}"
                    ;;
                "redis")
                    restore_redis "${3:-}"
                    ;;
                *)
                    log_error "请指定恢复目标: pg 或 redis"
                    exit 1
                    ;;
            esac
            ;;
        "--status")
            show_status
            ;;
        "--help"|"-h")
            echo "用法: $0 [选项]"
            echo ""
            echo "选项:"
            echo "  (无参数)      执行完整备份（PostgreSQL + Redis）"
            echo "  --pg-only     仅备份 PostgreSQL"
            echo "  --redis-only  仅备份 Redis"
            echo "  --restore pg [file]   恢复 PostgreSQL"
            echo "  --restore redis [file] 恢复 Redis"
            echo "  --status      显示备份状态"
            echo "  --help        显示帮助"
            echo ""
            echo "环境变量:"
            echo "  BACKUP_DIR      备份目录 (默认: /data/backups/infosentry)"
            echo "  RETENTION_DAYS  备份保留天数 (默认: 7)"
            echo "  USE_DOCKER      是否使用 Docker (默认: true)"
            echo "  COMPRESS        是否压缩备份 (默认: true)"
            ;;
        *)
            # 完整备份
            backup_postgres
            backup_redis
            cleanup_old_backups
            ;;
    esac
    
    log_info ""
    log_info "=== 备份脚本执行完成 ==="
}

main "$@"

