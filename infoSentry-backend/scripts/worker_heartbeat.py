#!/usr/bin/env python3
"""Worker 心跳脚本。

用于定期发送 Worker 心跳信号到 Redis。
在 Worker 启动脚本中调用，或作为独立进程运行。

使用方式：
    # 作为独立进程运行
    python scripts/worker_heartbeat.py --worker-type ingest

    # 或在 Worker 启动脚本中集成
    from scripts.worker_heartbeat import send_heartbeat
    await send_heartbeat("ingest")
"""

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


async def send_heartbeat(worker_type: str) -> bool:
    """发送单次心跳。

    Args:
        worker_type: Worker 类型（ingest/embed/match/agent/email）

    Returns:
        是否成功发送
    """
    try:
        from src.core.infrastructure.redis.client import RedisClient

        redis_client = RedisClient()
        heartbeat_key = f"worker:heartbeat:{worker_type}"

        await redis_client.set(
            heartbeat_key,
            datetime.now(UTC).isoformat(),
            ex=300,  # 5 分钟过期
        )

        return True

    except Exception as e:
        print(f"Failed to send heartbeat: {e}", file=sys.stderr)
        return False


async def run_heartbeat_loop(worker_type: str, interval: int = 60):
    """运行心跳循环。

    Args:
        worker_type: Worker 类型
        interval: 心跳间隔（秒），默认 60
    """
    print(f"Starting heartbeat loop for worker: {worker_type}")
    print(f"Interval: {interval} seconds")

    while True:
        success = await send_heartbeat(worker_type)
        if success:
            print(f"[{datetime.now(UTC).isoformat()}] Heartbeat sent: {worker_type}")
        else:
            print(f"[{datetime.now(UTC).isoformat()}] Heartbeat failed: {worker_type}")

        await asyncio.sleep(interval)


def main():
    """主函数。"""
    parser = argparse.ArgumentParser(description="Worker 心跳脚本")
    parser.add_argument(
        "--worker-type",
        "-w",
        type=str,
        required=True,
        choices=["ingest", "embed", "match", "agent", "email"],
        help="Worker 类型",
    )
    parser.add_argument(
        "--interval",
        "-i",
        type=int,
        default=60,
        help="心跳间隔（秒），默认 60",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="只发送一次心跳后退出",
    )

    args = parser.parse_args()

    if args.once:
        success = asyncio.run(send_heartbeat(args.worker_type))
        sys.exit(0 if success else 1)
    else:
        try:
            asyncio.run(run_heartbeat_loop(args.worker_type, args.interval))
        except KeyboardInterrupt:
            print("\nHeartbeat loop stopped")
            sys.exit(0)


if __name__ == "__main__":
    main()

