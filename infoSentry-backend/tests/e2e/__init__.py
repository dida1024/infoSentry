"""端到端测试包。

E2E 测试特点：
- 测试完整业务流程
- 模拟真实用户操作
- 可能需要 Mock 外部 API（OpenAI/SMTP）

运行方式：
    uv run pytest tests/e2e/ -v -m e2e
"""
