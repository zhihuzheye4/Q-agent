"""公共 fixture：临时 cwd，保护项目根目录。"""

from pathlib import Path

import pytest


@pytest.fixture
def tmp_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """切到临时目录，防止测试误伤项目根。"""
    monkeypatch.chdir(tmp_path)
    return tmp_path
