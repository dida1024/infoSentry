#!/usr/bin/env python3
"""健康检查脚本。

用于检查系统各组件的健康状态。
可作为运维脚本或监控探针使用。

使用方式：
    # 完整健康检查
    python scripts/health_check.py

    # 只检查特定组件
    python scripts/health_check.py --component database
    python scripts/health_check.py --component redis
    python scripts/health_check.py --component queues

    # JSON 输出
    python scripts/health_check.py --json

    # 退出码检查（用于 CI/CD）
    python scripts/health_check.py --strict
"""

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


async def check_database() -> dict:
    """检查数据库连接。"""
    try:
        from src.core.domain.events import SimpleEventBus
        from src.core.infrastructure.database.session import get_async_session
        from src.modules.agent.infrastructure.mappers import BudgetDailyMapper
        from src.modules.agent.infrastructure.repositories import (
            PostgreSQLBudgetDailyRepository,
        )

        async with get_async_session() as session:
            event_bus = SimpleEventBus()
            budget_repo = PostgreSQLBudgetDailyRepository(
                session, BudgetDailyMapper(), event_bus
            )
            await budget_repo.get_or_create_today()

        return {"status": "healthy", "message": "Database connection OK"}

    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


async def check_redis() -> dict:
    """检查 Redis 连接。"""
    try:
        from src.core.infrastructure.redis.client import RedisClient

        redis_client = RedisClient()
        is_ok = await redis_client.ping()

        if is_ok:
            return {"status": "healthy", "message": "Redis connection OK"}
        else:
            return {"status": "unhealthy", "error": "Redis ping failed"}

    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


async def check_queues() -> dict:
    """检查 Celery 队列状态。"""
    try:
        from src.core.infrastructure.celery.queues import Queues
        from src.core.infrastructure.redis.client import RedisClient

        redis_client = RedisClient()

        queues = {}
        total_backlog = 0

        for queue in [Queues.INGEST, Queues.EMBED, Queues.MATCH, Queues.AGENT, Queues.EMAIL]:
            try:
                length = await redis_client.llen(queue)
                queues[queue] = {"length": length}
                total_backlog += length
            except Exception as e:
                queues[queue] = {"error": str(e)}

        status = "healthy"
        if total_backlog > 100:
            status = "warning"
        if total_backlog > 500:
            status = "unhealthy"

        return {
            "status": status,
            "total_backlog": total_backlog,
            "queues": queues,
        }

    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


async def check_budget() -> dict:
    """检查预算状态。"""
    try:
        from src.core.config import settings
        from src.core.infrastructure.redis.client import RedisClient
        from src.modules.items.application.budget_service import BudgetService

        redis_client = RedisClient()
        budget_service = BudgetService(redis_client)
        status = await budget_service.get_status()

        usage_percent = (status.usd_est / settings.DAILY_USD_BUDGET) * 100 if settings.DAILY_USD_BUDGET > 0 else 0

        health_status = "healthy"
        if usage_percent >= 80:
            health_status = "warning"
        if usage_percent >= 100:
            health_status = "critical"

        return {
            "status": health_status,
            "date": status.date,
            "usd_est": round(status.usd_est, 4),
            "daily_limit": settings.DAILY_USD_BUDGET,
            "usage_percent": round(usage_percent, 1),
            "embedding_disabled": status.embedding_disabled,
            "judge_disabled": status.judge_disabled,
        }

    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


async def check_workers() -> dict:
    """检查 Worker 心跳状态。"""
    try:
        from src.core.infrastructure.redis.client import RedisClient
        from src.modules.agent.application.monitoring_service import MonitoringService

        redis_client = RedisClient()
        monitoring = MonitoringService(redis_client)
        workers_result = await monitoring.get_worker_heartbeats()

        stale_workers = [
            name
            for name, heartbeat in workers_result.workers.items()
            if heartbeat.status in ("stale", "unknown")
        ]

        status = "healthy"
        if stale_workers:
            status = "warning" if len(stale_workers) < 3 else "unhealthy"

        return {
            "status": status,
            "workers": workers_result.to_dict(),
            "stale_workers": stale_workers,
        }

    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


async def run_full_check() -> dict:
    """运行完整健康检查。"""
    results = {
        "timestamp": datetime.now(UTC).isoformat(),
        "overall_status": "healthy",
        "components": {},
    }

    # 并行执行所有检查
    database_result, redis_result, queues_result, budget_result, workers_result = await asyncio.gather(
        check_database(),
        check_redis(),
        check_queues(),
        check_budget(),
        check_workers(),
        return_exceptions=True,
    )

    results["components"]["database"] = database_result if not isinstance(database_result, Exception) else {"status": "error", "error": str(database_result)}
    results["components"]["redis"] = redis_result if not isinstance(redis_result, Exception) else {"status": "error", "error": str(redis_result)}
    results["components"]["queues"] = queues_result if not isinstance(queues_result, Exception) else {"status": "error", "error": str(queues_result)}
    results["components"]["budget"] = budget_result if not isinstance(budget_result, Exception) else {"status": "error", "error": str(budget_result)}
    results["components"]["workers"] = workers_result if not isinstance(workers_result, Exception) else {"status": "error", "error": str(workers_result)}

    # 确定整体状态
    statuses = [c.get("status", "unknown") for c in results["components"].values()]

    if any(s in ("unhealthy", "error") for s in statuses):
        results["overall_status"] = "unhealthy"
    elif any(s in ("warning", "critical") for s in statuses):
        results["overall_status"] = "degraded"

    return results


async def run_component_check(component: str) -> dict:
    """运行单个组件检查。"""
    checkers = {
        "database": check_database,
        "redis": check_redis,
        "queues": check_queues,
        "budget": check_budget,
        "workers": check_workers,
    }

    if component not in checkers:
        return {"error": f"Unknown component: {component}"}

    result = await checkers[component]()
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "component": component,
        "result": result,
    }


def print_result(result: dict, json_output: bool = False):
    """打印检查结果。"""
    if json_output:
        print(json.dumps(result, indent=2))
    else:
        print(f"\n{'=' * 60}")
        print(f"Health Check Report - {result.get('timestamp', 'N/A')}")
        print(f"{'=' * 60}")

        if "overall_status" in result:
            status_emoji = "✅" if result["overall_status"] == "healthy" else "⚠️" if result["overall_status"] == "degraded" else "❌"
            print(f"\nOverall Status: {status_emoji} {result['overall_status'].upper()}")

            print(f"\n{'-' * 40}")
            for component, info in result.get("components", {}).items():
                comp_status = info.get("status", "unknown")
                comp_emoji = "✅" if comp_status == "healthy" else "⚠️" if comp_status in ("warning", "degraded") else "❌"
                print(f"{comp_emoji} {component}: {comp_status}")

                # 打印额外信息
                if comp_status != "healthy":
                    for key, value in info.items():
                        if key != "status":
                            print(f"    {key}: {value}")

        elif "result" in result:
            info = result["result"]
            comp_status = info.get("status", "unknown")
            comp_emoji = "✅" if comp_status == "healthy" else "⚠️" if comp_status in ("warning", "degraded") else "❌"
            print(f"\n{result.get('component', 'Component')}: {comp_emoji} {comp_status}")

            for key, value in info.items():
                if key != "status":
                    print(f"  {key}: {value}")

        print(f"\n{'=' * 60}\n")


def main():
    """主函数。"""
    parser = argparse.ArgumentParser(description="系统健康检查脚本")
    parser.add_argument(
        "--component",
        "-c",
        type=str,
        choices=["database", "redis", "queues", "budget", "workers"],
        help="只检查特定组件",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="输出 JSON 格式",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="严格模式：任何非 healthy 状态都返回非零退出码",
    )

    args = parser.parse_args()

    if args.component:
        result = asyncio.run(run_component_check(args.component))
    else:
        result = asyncio.run(run_full_check())

    print_result(result, args.json)

    # 确定退出码
    if args.strict:
        overall = result.get("overall_status", result.get("result", {}).get("status", "unknown"))
        if overall != "healthy":
            sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()

