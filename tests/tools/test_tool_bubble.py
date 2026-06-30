"""M6 UI 反馈测试：ToolBubble widget 4 状态 + 折叠展开。"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "minimal")
pytest.importorskip("PySide6")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


def test_tool_bubble_constructs(qapp) -> None:  # noqa: ANN001
    """ToolBubble 应能正常构造，默认折叠态 28px。"""
    from q_agent.ui.tool_bubble import ToolBubble

    bubble = ToolBubble()
    assert bubble.objectName() == "ToolBubble"
    assert bubble._collapsed is True  # type: ignore[attr-defined]
    assert bubble.height() == 28


def test_tool_bubble_default_state_pending(qapp) -> None:  # noqa: ANN001
    """构造后状态应为 pending。"""
    from q_agent.ui.tool_bubble import ToolBubble

    bubble = ToolBubble()
    assert bubble._state == "pending"  # type: ignore[attr-defined]


def test_tool_bubble_on_started_sets_title_and_state(qapp) -> None:  # noqa: ANN001
    """on_started 应设置标题 + 状态为 pending。"""
    from q_agent.ui.tool_bubble import ToolBubble

    bubble = ToolBubble()
    bubble.on_started("file_read")
    assert "file_read" in bubble.title_lbl.text()
    assert bubble._state == "pending"  # type: ignore[attr-defined]


def test_tool_bubble_on_finished_success(qapp) -> None:  # noqa: ANN001
    """on_finished(success) 应更新标题 + 状态。"""
    from q_agent.ui.tool_bubble import ToolBubble

    bubble = ToolBubble()
    bubble.on_finished("file_read", "success", "/tmp/out.txt")
    assert "file_read" in bubble.title_lbl.text()
    assert "success" in bubble.title_lbl.text()
    assert bubble._state == "success"  # type: ignore[attr-defined]
    assert "/tmp/out.txt" in bubble.output_lbl.text()


def test_tool_bubble_on_finished_failed(qapp) -> None:  # noqa: ANN001
    """on_finished(failed) 应设状态 failed。"""
    from q_agent.ui.tool_bubble import ToolBubble

    bubble = ToolBubble()
    bubble.on_finished("file_write", "failed", "")
    assert bubble._state == "failed"  # type: ignore[attr-defined]


def test_tool_bubble_on_finished_cancelled(qapp) -> None:  # noqa: ANN001
    """on_finished(cancelled) 应设状态 cancelled。"""
    from q_agent.ui.tool_bubble import ToolBubble

    bubble = ToolBubble()
    bubble.on_finished("exec_shell", "cancelled", "")
    assert bubble._state == "cancelled"  # type: ignore[attr-defined]


def test_tool_bubble_on_finished_empty_path(qapp) -> None:  # noqa: ANN001
    """output_path 为空时应显示内联提示。"""
    from q_agent.ui.tool_bubble import ToolBubble

    bubble = ToolBubble()
    bubble.on_finished("file_read", "success", "")
    assert "内联" in bubble.output_lbl.text()


def test_tool_bubble_toggle_changes_collapse_state(qapp) -> None:  # noqa: ANN001
    """点击展开按钮应翻转折叠状态 + 按钮文本。"""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from q_agent.ui.tool_bubble import ToolBubble

    bubble = ToolBubble()
    assert bubble._collapsed is True  # type: ignore[attr-defined]
    assert bubble.expand_btn.text() == "展开"

    QTest.mouseClick(bubble.expand_btn, Qt.MouseButton.LeftButton)
    assert bubble._collapsed is False  # type: ignore[attr-defined]
    assert bubble.expand_btn.text() == "折叠"

    QTest.mouseClick(bubble.expand_btn, Qt.MouseButton.LeftButton)
    assert bubble._collapsed is True  # type: ignore[attr-defined]
    assert bubble.expand_btn.text() == "展开"
