#!/bin/bash
# ============================================
# infoSentry 轻量压测脚本
# ============================================
# 功能：
#   - 监控队列积压情况
#   - 检查邮件去重有效性
#   - 验证 48h 运行稳定性
#
# 使用方法：
#   ./scripts/load_test.sh monitor      # 持续监控队列
#   ./scripts/load_test.sh dedupe       # 检查邮件去重
#   ./scripts/load_test.sh stress       # 压力测试
#   ./scripts/load_test.sh report       # 生成报告

set -euo pipefail

# ============================================
# 配置
# ============================================

API_URL="${API_URL:-http://localhost:8000}"
REDIS_CONTAINER="${REDIS_CONTAINER:-infosentry-redis}"
PG_CONTAINER="${PG_CONTAINER:-infosentry-postgres}"
LOG_FILE="${LOG_FILE:-/tmp/infosentry-loadtest.log}"
MONITOR_INTERVAL="${MONITOR_INTERVAL:-60}"  # 监控间隔（秒）
QUEUE_THRESHOLD="${QUEUE_THRESHOLD:-100}"   # 队列积压告警阈值

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ============================================
# 辅助函数
# ============================================

log_info() {
    local msg="$(date '+%Y-%m-%d %H:%M:%S') [INFO] $1"
    echo -e "${GREEN}${msg}${NC}"
    echo "$msg" >> "$LOG_FILE"
}

log_warn() {
    local msg="$(date '+%Y-%m-%d %H:%M:%S') [WARN] $1"
    echo -e "${YELLOW}${msg}${NC}"
    echo "$msg" >> "$LOG_FILE"
}

log_error() {
    local msg="$(date '+%Y-%m-%d %H:%M:%S') [ERROR] $1"
    echo -e "${RED}${msg}${NC}"
    echo "$msg" >> "$LOG_FILE"
}

# ============================================
# 队列监控
# ============================================

get_queue_length() {
    local queue="$1"
    docker exec "$REDIS_CONTAINER" redis-cli LLEN "$queue" 2>/dev/null || echo "0"
}

monitor_queues() {
    log_info "开始队列监控..."
    log_info "监控间隔: ${MONITOR_INTERVAL}s"
    log_info "告警阈值: ${QUEUE_THRESHOLD}"
    log_info ""
    
    local iteration=0
    local start_time=$(date +%s)
    
    while true; do
        iteration=$((iteration + 1))
        local now=$(date '+%Y-%m-%d %H:%M:%S')
        local runtime=$(($(date +%s) - start_time))
        local hours=$((runtime / 3600))
        local mins=$(((runtime % 3600) / 60))
        
        # 获取队列长度
        local q_ingest=$(get_queue_length "q_ingest")
        local q_embed=$(get_queue_length "q_embed")
        local q_match=$(get_queue_length "q_match")
        local q_agent=$(get_queue_length "q_agent")
        local q_email=$(get_queue_length "q_email")
        
        # 输出状态
        echo "[$now] 运行时间: ${hours}h${mins}m | 检查次数: $iteration"
        printf "  q_ingest: %-5s q_embed: %-5s q_match: %-5s q_agent: %-5s q_email: %-5s\n" \
            "$q_ingest" "$q_embed" "$q_match" "$q_agent" "$q_email"
        
        # 记录到日志
        echo "[$now] queues: ingest=$q_ingest embed=$q_embed match=$q_match agent=$q_agent email=$q_email" >> "$LOG_FILE"
        
        # 检查积压告警
        local alert=0
        if [[ "$q_embed" -gt "$QUEUE_THRESHOLD" ]]; then
            log_warn "q_embed 积压超过阈值: $q_embed > $QUEUE_THRESHOLD"
            alert=1
        fi
        if [[ "$q_agent" -gt "$QUEUE_THRESHOLD" ]]; then
            log_warn "q_agent 积压超过阈值: $q_agent > $QUEUE_THRESHOLD"
            alert=1
        fi
        if [[ "$q_email" -gt "$QUEUE_THRESHOLD" ]]; then
            log_warn "q_email 积压超过阈值: $q_email > $QUEUE_THRESHOLD"
            alert=1
        fi
        
        if [[ "$alert" -eq 0 ]]; then
            echo -e "  ${GREEN}状态: 正常${NC}"
        fi
        
        echo ""
        sleep "$MONITOR_INTERVAL"
    done
}

# ============================================
# 邮件去重检查
# ============================================

check_dedupe() {
    log_info "检查邮件去重有效性..."
    
    # 查询重复推送
    local query="
    SELECT 
        dedupe_key,
        COUNT(*) as count,
        MIN(created_at) as first_at,
        MAX(created_at) as last_at
    FROM push_decisions
    WHERE status = 'SENT'
    GROUP BY dedupe_key
    HAVING COUNT(*) > 1
    ORDER BY count DESC
    LIMIT 20;
    "
    
    log_info "查询重复推送记录..."
    local result=$(docker exec "$PG_CONTAINER" psql -U infosentry -d infosentry -t -c "$query" 2>/dev/null)
    
    if [[ -z "$result" || "$result" == *"(0 rows)"* ]]; then
        echo -e "${GREEN}✓ 未发现重复推送${NC}"
    else
        log_warn "发现重复推送记录:"
        echo "$result"
    fi
    
    # 统计去重键分布
    log_info ""
    log_info "推送统计..."
    
    local stats_query="
    SELECT 
        decision,
        status,
        COUNT(*) as count
    FROM push_decisions
    WHERE created_at > NOW() - INTERVAL '24 hours'
    GROUP BY decision, status
    ORDER BY decision, status;
    "
    
    docker exec "$PG_CONTAINER" psql -U infosentry -d infosentry -c "$stats_query" 2>/dev/null
}

# ============================================
# 压力测试
# ============================================

stress_test() {
    log_info "开始压力测试..."
    log_info "注意: 这将产生大量测试数据，请在测试环境运行"
    
    read -p "确定要继续吗？(yes/no) " confirm
    if [[ "$confirm" != "yes" ]]; then
        log_info "取消压力测试"
        return
    fi
    
    # 模拟批量抓取
    log_info "模拟批量抓取任务..."
    
    local start_time=$(date +%s)
    local tasks_created=0
    
    # 注入测试任务
    for i in $(seq 1 50); do
        # 模拟抓取任务
        docker exec "$REDIS_CONTAINER" redis-cli LPUSH q_ingest \
            "{\"type\":\"test\",\"source_id\":\"test-source-$i\",\"timestamp\":$(date +%s)}" \
            > /dev/null
        tasks_created=$((tasks_created + 1))
    done
    
    log_info "已创建 $tasks_created 个测试任务"
    
    # 监控处理速度
    log_info "监控处理速度 (60s)..."
    
    local initial_length=$(get_queue_length "q_ingest")
    sleep 60
    local final_length=$(get_queue_length "q_ingest")
    
    local processed=$((initial_length - final_length + tasks_created))
    log_info "60s 内处理: $processed 个任务"
    log_info "处理速度: $(echo "scale=2; $processed / 60" | bc) 任务/秒"
}

# ============================================
# 生成报告
# ============================================

generate_report() {
    log_info "生成测试报告..."
    
    local report_file="/tmp/infosentry-report-$(date +%Y%m%d-%H%M%S).txt"
    
    {
        echo "============================================"
        echo "infoSentry 测试报告"
        echo "生成时间: $(date)"
        echo "============================================"
        echo ""
        
        echo "## 1. 系统状态"
        echo ""
        
        # API 健康检查
        echo "### API 健康检查"
        curl -s "${API_URL}/health" 2>/dev/null | head -c 200 || echo "API 无法访问"
        echo ""
        echo ""
        
        # 队列状态
        echo "### 队列状态"
        echo "q_ingest: $(get_queue_length q_ingest)"
        echo "q_embed: $(get_queue_length q_embed)"
        echo "q_match: $(get_queue_length q_match)"
        echo "q_agent: $(get_queue_length q_agent)"
        echo "q_email: $(get_queue_length q_email)"
        echo ""
        
        # 数据库统计
        echo "## 2. 数据统计"
        echo ""
        
        echo "### 过去 24 小时"
        docker exec "$PG_CONTAINER" psql -U infosentry -d infosentry -c "
        SELECT 
            'items' as table_name,
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE ingested_at > NOW() - INTERVAL '24 hours') as last_24h
        FROM items
        UNION ALL
        SELECT 
            'push_decisions' as table_name,
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '24 hours') as last_24h
        FROM push_decisions
        UNION ALL
        SELECT 
            'agent_runs' as table_name,
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '24 hours') as last_24h
        FROM agent_runs;
        " 2>/dev/null || echo "数据库查询失败"
        echo ""
        
        # Agent 运行统计
        echo "### Agent 运行状态分布"
        docker exec "$PG_CONTAINER" psql -U infosentry -d infosentry -c "
        SELECT status, COUNT(*) 
        FROM agent_runs 
        WHERE created_at > NOW() - INTERVAL '24 hours'
        GROUP BY status;
        " 2>/dev/null || echo "查询失败"
        echo ""
        
        # 推送统计
        echo "### 推送决策分布"
        docker exec "$PG_CONTAINER" psql -U infosentry -d infosentry -c "
        SELECT decision, status, COUNT(*) 
        FROM push_decisions 
        WHERE created_at > NOW() - INTERVAL '24 hours'
        GROUP BY decision, status
        ORDER BY decision, status;
        " 2>/dev/null || echo "查询失败"
        echo ""
        
        # 重复推送检查
        echo "## 3. 去重检查"
        echo ""
        echo "重复推送数量: "
        docker exec "$PG_CONTAINER" psql -U infosentry -d infosentry -t -c "
        SELECT COUNT(*) FROM (
            SELECT dedupe_key, COUNT(*) 
            FROM push_decisions 
            WHERE status = 'SENT'
            GROUP BY dedupe_key 
            HAVING COUNT(*) > 1
        ) as dups;
        " 2>/dev/null || echo "0"
        echo ""
        
        # 预算使用
        echo "## 4. 预算使用"
        echo ""
        docker exec "$PG_CONTAINER" psql -U infosentry -d infosentry -c "
        SELECT 
            date,
            embedding_tokens,
            judge_tokens,
            usd_spent,
            is_breaker_open
        FROM budget_daily
        ORDER BY date DESC
        LIMIT 7;
        " 2>/dev/null || echo "budget_daily 表不存在或为空"
        echo ""
        
        echo "============================================"
        echo "报告结束"
        echo "============================================"
        
    } > "$report_file"
    
    log_info "报告已保存到: $report_file"
    cat "$report_file"
}

# ============================================
# 48 小时稳定性测试
# ============================================

stability_test() {
    log_info "开始 48 小时稳定性测试..."
    log_info "日志文件: $LOG_FILE"
    
    local start_time=$(date +%s)
    local target_duration=$((48 * 3600))  # 48 小时
    local check_interval=300  # 每 5 分钟检查一次
    
    # 记录初始状态
    {
        echo "=== 稳定性测试开始 ==="
        echo "开始时间: $(date)"
        echo "目标时长: 48 小时"
        echo ""
    } >> "$LOG_FILE"
    
    while true; do
        local elapsed=$(($(date +%s) - start_time))
        local remaining=$((target_duration - elapsed))
        
        if [[ "$remaining" -le 0 ]]; then
            log_info "48 小时测试完成！"
            break
        fi
        
        local hours=$((elapsed / 3600))
        local mins=$(((elapsed % 3600) / 60))
        
        # 获取队列状态
        local q_embed=$(get_queue_length "q_embed")
        local q_agent=$(get_queue_length "q_agent")
        local q_email=$(get_queue_length "q_email")
        
        # 检查 API
        local api_status="DOWN"
        if curl -s "${API_URL}/health" | grep -q "ok"; then
            api_status="OK"
        fi
        
        # 记录状态
        local status_line="[$(date '+%H:%M:%S')] ${hours}h${mins}m | API:${api_status} | embed:${q_embed} agent:${q_agent} email:${q_email}"
        echo "$status_line"
        echo "$status_line" >> "$LOG_FILE"
        
        # 检查告警条件
        if [[ "$q_embed" -gt "$QUEUE_THRESHOLD" ]] || \
           [[ "$q_agent" -gt "$QUEUE_THRESHOLD" ]] || \
           [[ "$q_email" -gt "$QUEUE_THRESHOLD" ]]; then
            log_warn "队列积压超过阈值！"
        fi
        
        if [[ "$api_status" != "OK" ]]; then
            log_error "API 健康检查失败！"
        fi
        
        sleep "$check_interval"
    done
    
    # 生成最终报告
    generate_report
}

# ============================================
# 帮助信息
# ============================================

show_help() {
    echo "infoSentry 轻量压测脚本"
    echo ""
    echo "用法: $0 <命令>"
    echo ""
    echo "命令:"
    echo "  monitor     持续监控队列状态"
    echo "  dedupe      检查邮件去重有效性"
    echo "  stress      执行压力测试（会产生测试数据）"
    echo "  report      生成测试报告"
    echo "  stability   48 小时稳定性测试"
    echo ""
    echo "环境变量:"
    echo "  API_URL           API 地址 (默认: http://localhost:8000)"
    echo "  REDIS_CONTAINER   Redis 容器名 (默认: infosentry-redis)"
    echo "  PG_CONTAINER      PostgreSQL 容器名 (默认: infosentry-postgres)"
    echo "  MONITOR_INTERVAL  监控间隔秒数 (默认: 60)"
    echo "  QUEUE_THRESHOLD   队列积压告警阈值 (默认: 100)"
    echo "  LOG_FILE          日志文件路径"
}

# ============================================
# 主函数
# ============================================

main() {
    local command="${1:-help}"
    
    case "$command" in
        "monitor")
            monitor_queues
            ;;
        "dedupe")
            check_dedupe
            ;;
        "stress")
            stress_test
            ;;
        "report")
            generate_report
            ;;
        "stability")
            stability_test
            ;;
        *)
            show_help
            ;;
    esac
}

main "$@"

