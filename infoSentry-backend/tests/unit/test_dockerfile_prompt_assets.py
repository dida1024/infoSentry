"""Dockerfile 资产打包约束测试。

确保 prompts 目录被复制进运行镜像，避免生产缺失提示词文件。
"""

from pathlib import Path


def test_dockerfile_copies_prompt_and_resource_dirs() -> None:
    dockerfile = Path(__file__).resolve().parents[2] / "Dockerfile"
    content = dockerfile.read_text(encoding="utf-8")
    assert "COPY prompts/ ./prompts/" in content
    assert "COPY resources/ ./resources/" in content
