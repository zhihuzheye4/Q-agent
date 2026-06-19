"""冒烟测试：CLI + echo 往返。"""

import subprocess
import sys

from q_agent.memory.runtime import RuntimeMemory
from q_agent.orchestrator.core import Orchestrator


def test_echo_roundtrip() -> None:
    """orchestrator 直调 echo 应返回原文。"""
    orch = Orchestrator(memory=RuntimeMemory())
    assert orch.handle("echo 你好").endswith("你好")


def test_cli_chat() -> None:
    """CLI chat 子命令应输出 echo 结果。"""
    result = subprocess.run(
        [sys.executable, "-m", "q_agent", "chat", "echo 你好"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "你好" in result.stdout


def test_cli_version() -> None:
    """CLI version 子命令应输出版本。"""
    result = subprocess.run(
        [sys.executable, "-m", "q_agent", "version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Q-agent" in result.stdout


def test_cli_skills() -> None:
    """CLI skills 子命令应列出 echo。"""
    result = subprocess.run(
        [sys.executable, "-m", "q_agent", "skills"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "echo" in result.stdout
