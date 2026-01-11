#!/bin/bash
# ============================================
# infoSentry 故障演练脚本
# ============================================
# 功能：
#   - 模拟各种故障场景
#   - 验证系统降级行为
#   - 检查恢复能力
#
# 使用方法：
#   ./scripts/chaos.sh openai       # 模拟 OpenAI 不可用
#   ./scripts/chaos.sh smtp         # 模拟 SMTP 故障
#   ./scripts/chaos.sh redis        # 模拟 Redis 重启
#   ./scripts/chaos.sh worker       # 模拟 Worker 故障
#   ./scripts/chaos.sh budget       # 模拟预算耗尽
#   ./scripts/chaos.sh recover      # 恢复所有模拟故障
#
# 警告：请在测试环境中运行！

set -euo pipefail

# ============================================
# 配置
# ============================================

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
API_URL="${API_URL:-http://localhost:8000}"
ADMIN_TOKEN="${ADMIN_TOKEN:-}"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

check_health() {
    log_info "检查系统健康状态..."
    
    # API 健康检查
    if curl -s "${API_URL}/health" | grep -q "ok"; then
        log_info "  API: OK"
    else
        log_error "  API: FAILED"
    fi
    
    # PostgreSQL 检查
    if docker exec infosentry-postgres pg_isready -U infosentry > /dev/null 2>&1; then
        log_info "  PostgreSQL: OK"
    else
        log_error "  PostgreSQL: FAILED"
    fi
    
    # Redis 检查
    if docker exec infosentry-redis redis-cli ping | grep -q "PONG"; then
        log_info "  Redis: OK"
    else
        log_error "  Redis: FAILED"
    fi
    
    # Worker 检查
    local workers_running=$(docker ps --filter "name=infosentry-worker" --format "{{.Names}}" | wc -l)
    log_info "  Workers 运行中: ${workers_running}"
}

wait_and_verify() {
    local wait_time="${1:-10}"
    log_info "等待 ${wait_time} 秒后验证..."
    sleep "${wait_time}"
    check_health
}

# ============================================
# 故障场景：OpenAI 不可用
# ============================================

chaos_openai() {
    log_warn "=== 故障演练：OpenAI 不可用 ==="
    log_info "场景：模拟 OpenAI API 断网"
    log_info "预期：边界判别全部降级 Batch，agent_runs.status = FALLBACK"
    echo ""
    
    log_step "1. 通过 API 关闭 LLM"
    if [[ -n "${ADMIN_TOKEN}" ]]; then
        curl -s -X POST "${API_URL}/api/v1/admin/config" \
            -H "Authorization: Bearer ${ADMIN_TOKEN}" \
            -H "Content-Type: application/json" \
            -d '{"LLM_ENABLED": false}' | jq .
    else
        log_warn "未设置 ADMIN_TOKEN，请手动设置环境变量 LLM_ENABLED=false"
    fi
    
    log_step "2. 验证系统行为"
    log_info "  - 新的边界判别应该降级到 Batch"
    log_info "  - agent_runs 应该有 FALLBACK 状态记录"
    log_info "  - Immediate 推送暂停，Batch/Digest 正常"
    
    echo ""
    log_info "验证命令："
    echo "  # 检查 agent_runs 中的 FALLBACK 记录"
    echo "  docker exec infosentry-postgres psql -U infosentry -d infosentry -c \\"
    echo "    \"SELECT id, status, error_message FROM agent_runs WHERE status = 'FALLBACK' ORDER BY created_at DESC LIMIT 5;\""
    
    echo ""
    log_step "3. 恢复方法"
    echo "  curl -X POST ${API_URL}/api/v1/admin/config \\"
    echo "    -H 'Authorization: Bearer \$TOKEN' \\"
    echo "    -d '{\"LLM_ENABLED\": true}'"
    
    wait_and_verify 5
}

# ============================================
# 故障场景：SMTP 故障
# ============================================

chaos_smtp() {
    log_warn "=== 故障演练：SMTP 故障 ==="
    log_info "场景：模拟 SMTP 密码错误或服务不可用"
    log_info "预期：站内通知正常，邮件发送失败并重试"
    echo ""
    
    log_step "1. 通过 API 关闭邮件"
    if [[ -n "${ADMIN_TOKEN}" ]]; then
        curl -s -X POST "${API_URL}/api/v1/admin/config" \
            -H "Authorization: Bearer ${ADMIN_TOKEN}" \
            -H "Content-Type: application/json" \
            -d '{"EMAIL_ENABLED": false}' | jq .
    else
        log_warn "未设置 ADMIN_TOKEN，请手动设置环境变量 EMAIL_ENABLED=false"
    fi
    
    log_step "2. 验证系统行为"
    log_info "  - push_decisions 仍然正常创建"
    log_info "  - email 发送被跳过"
    log_info "  - 站内通知可以正常查看"
    
    echo ""
    log_info "验证命令："
    echo "  # 检查通知 API"
    echo "  curl -s ${API_URL}/api/v1/notifications -H 'Authorization: Bearer \$TOKEN' | jq '.data[:3]'"
    
    log_step "3. 恢复方法"
    echo "  curl -X POST ${API_URL}/api/v1/admin/config \\"
    echo "    -H 'Authorization: Bearer \$TOKEN' \\"
    echo "    -d '{\"EMAIL_ENABLED\": true}'"
    
    wait_and_verify 5
}

# ============================================
# 故障场景：Redis 重启
# ============================================

chaos_redis() {
    log_warn "=== 故障演练：Redis 重启 ==="
    log_info "场景：Redis 服务临时不可用后恢复"
    log_info "预期：Worker 能恢复消费，无任务永久丢失"
    echo ""
    
    log_step "1. 重启 Redis 容器"
    read -p "确定要重启 Redis？(yes/no) " confirm
    if [[ "${confirm}" != "yes" ]]; then
        log_info "取消操作"
        return
    fi
    
    docker restart infosentry-redis
    
    log_step "2. 等待 Redis 恢复"
    sleep 5
    
    log_step "3. 验证系统行为"
    log_info "  - Redis 应该恢复 PONG 响应"
    log_info "  - Worker 应该重新连接"
    log_info "  - 队列任务继续处理"
    
    echo ""
    log_info "验证命令："
    echo "  # 检查 Redis 连接"
    echo "  docker exec infosentry-redis redis-cli ping"
    echo ""
    echo "  # 检查队列长度"
    echo "  docker exec infosentry-redis redis-cli LLEN celery"
    
    wait_and_verify 10
}

# ============================================
# 故障场景：Worker 故障
# ============================================

chaos_worker() {
    log_warn "=== 故障演练：Worker 故障 ==="
    log_info "场景：Agent Worker 意外停止"
    log_info "预期：任务堆积但不丢失，恢复后继续处理"
    echo ""
    
    log_step "1. 停止 Agent Worker"
    read -p "确定要停止 Agent Worker？(yes/no) " confirm
    if [[ "${confirm}" != "yes" ]]; then
        log_info "取消操作"
        return
    fi
    
    docker stop infosentry-worker-agent
    
    log_step "2. 验证任务堆积"
    sleep 5
    log_info "检查 q_agent 队列长度..."
    docker exec infosentry-redis redis-cli LLEN q_agent
    
    log_step "3. 恢复 Worker"
    docker start infosentry-worker-agent
    
    log_step "4. 验证任务继续处理"
    log_info "等待任务处理..."
    sleep 10
    docker exec infosentry-redis redis-cli LLEN q_agent
    
    wait_and_verify 5
}

# ============================================
# 故障场景：预算耗尽
# ============================================

chaos_budget() {
    log_warn "=== 故障演练：预算耗尽 ==="
    log_info "场景：模拟每日预算用尽"
    log_info "预期：触发熔断，系统记录 FALLBACK 并继续运行"
    echo ""
    
    log_step "1. 手动触发预算熔断"
    log_info "请在数据库中执行以下 SQL:"
    echo ""
    echo "  UPDATE budget_daily SET"
    echo "    embedding_tokens = 999999,"
    echo "    judge_tokens = 999999,"
    echo "    usd_spent = 10.0,"
    echo "    is_breaker_open = true"
    echo "  WHERE date = CURRENT_DATE;"
    echo ""
    
    log_step "2. 验证系统行为"
    log_info "  - 新的 embedding 请求应该被跳过"
    log_info "  - 新的 LLM 判别应该降级 Batch"
    log_info "  - 监控告警应该触发"
    
    log_step "3. 恢复方法"
    echo "  UPDATE budget_daily SET is_breaker_open = false WHERE date = CURRENT_DATE;"
    echo ""
    echo "  # 或者等待第二天自动重置"
}

# ============================================
# 恢复所有配置
# ============================================

chaos_recover() {
    log_info "=== 恢复所有配置 ==="
    
    if [[ -n "${ADMIN_TOKEN}" ]]; then
        log_step "恢复 Feature Flags"
        curl -s -X POST "${API_URL}/api/v1/admin/config" \
            -H "Authorization: Bearer ${ADMIN_TOKEN}" \
            -H "Content-Type: application/json" \
            -d '{
                "LLM_ENABLED": true,
                "EMBEDDING_ENABLED": true,
                "IMMEDIATE_ENABLED": true,
                "EMAIL_ENABLED": true
            }' | jq .
    fi
    
    log_step "确保所有容器运行"
    docker-compose -f "${COMPOSE_FILE}" up -d
    
    wait_and_verify 10
    
    log_info "恢复完成"
}

# ============================================
# 完整演练
# ============================================

chaos_full() {
    log_warn "=== 完整故障演练 ==="
    log_warn "这将依次执行所有故障场景，仅在测试环境使用！"
    echo ""
    
    read -p "确定要执行完整演练？(yes/no) " confirm
    if [[ "${confirm}" != "yes" ]]; then
        log_info "取消操作"
        return
    fi
    
    log_info "开始演练..."
    
    # 1. OpenAI 故障
    chaos_openai
    sleep 30
    
    # 2. 恢复
    chaos_recover
    sleep 10
    
    # 3. SMTP 故障
    chaos_smtp
    sleep 30
    
    # 4. 恢复
    chaos_recover
    sleep 10
    
    # 5. Redis 重启
    chaos_redis
    sleep 30
    
    log_info "=== 演练完成 ==="
    check_health
}

# ============================================
# 显示帮助
# ============================================

show_help() {
    echo "infoSentry 故障演练脚本"
    echo ""
    echo "用法: $0 <场景>"
    echo ""
    echo "场景:"
    echo "  openai      模拟 OpenAI 不可用（LLM 降级）"
    echo "  smtp        模拟 SMTP 故障（邮件降级）"
    echo "  redis       模拟 Redis 重启"
    echo "  worker      模拟 Worker 故障"
    echo "  budget      模拟预算耗尽"
    echo "  recover     恢复所有配置"
    echo "  full        执行完整演练（依次执行所有场景）"
    echo "  status      检查系统状态"
    echo ""
    echo "环境变量:"
    echo "  COMPOSE_FILE   docker-compose 文件路径"
    echo "  API_URL        API 地址 (默认: http://localhost:8000)"
    echo "  ADMIN_TOKEN    管理员 JWT Token（用于 API 调用）"
}

# ============================================
# 主函数
# ============================================

main() {
    local scenario="${1:-help}"
    
    echo ""
    log_info "=== infoSentry 故障演练 ==="
    log_info "时间: $(date)"
    echo ""
    
    case "${scenario}" in
        "openai")
            chaos_openai
            ;;
        "smtp")
            chaos_smtp
            ;;
        "redis")
            chaos_redis
            ;;
        "worker")
            chaos_worker
            ;;
        "budget")
            chaos_budget
            ;;
        "recover")
            chaos_recover
            ;;
        "full")
            chaos_full
            ;;
        "status")
            check_health
            ;;
        *)
            show_help
            ;;
    esac
}

main "$@"

