"""集成测试包。

集成测试特点：
- 需要真实的 DB/Redis（通过 Docker）
- 测试模块间交互
- 使用事务回滚保持隔离

运行方式：
    # 先启动依赖服务
    docker-compose up -d postgres redis

    # 运行集成测试
    uv run pytest tests/integration/ -v -m integration
"""
