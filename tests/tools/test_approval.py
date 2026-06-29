"""M5 审批与权限测试：三级权限 + 缓存 + deny + 永不沙箱风险知情。"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "minimal")
pytest.importorskip("PySide6")

from q_agent.tools.approval import (
    ack_sandbox_risk,
    check_permission,
    is_cached_allow,
    is_cached_deny,
    needs_sandbox_risk_ack,
    record_approval,
    reset_session_cache,
)


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def _reset_cache() -> None:
    """每个测试前清空会话内缓存，避免相互污染。"""
    reset_session_cache()


@pytest.fixture
def settings_path(tmp_path: Path, monkeypatch) -> Path:
    """重定向 SETTINGS_FILE 到 tmp_path 避免污染用户家目录。"""
    from q_agent.tools import approval as approval_mod

    fake_settings = tmp_path / "settings.json"
    monkeypatch.setattr(approval_mod, "SETTINGS_FILE", fake_settings)
    return fake_settings


# ---- 三级权限判定 ----


def test_read_only_auto_pass() -> None:
    """read_only 级应自动通过，不弹窗。"""
    mode = check_permission("file_read", "read_only", ("/tmp/x",), {})
    assert mode == "auto"


def test_write_first_call_pending() -> None:
    """write 级首次调用应返回 pending（需弹窗）。"""
    mode = check_permission("file_write", "write", ("/tmp/x",), {"content": "hi"})
    assert mode == "pending"


def test_destructive_always_pending() -> None:
    """destructive 级每次都应返回 pending，永不缓存。"""
    args = ("/tmp/x",)
    kwargs: dict[str, object] = {}
    # 即使 record_approval("always")，destructive 也不入 allow 缓存
    record_approval("file_move", "destructive", args, kwargs, "always")
    mode = check_permission("file_move", "destructive", args, kwargs)
    assert mode == "pending"


# ---- write 级缓存 ----


def test_write_always_caches_session() -> None:
    """write 级 'always' 后，相同 args_hash 应命中 allow 缓存。"""
    args = ("/tmp/x",)
    kwargs: dict[str, object] = {"content": "hi"}
    record_approval("file_write", "write", args, kwargs, "always")
    assert is_cached_allow("file_write", args, kwargs)
    mode = check_permission("file_write", "write", args, kwargs)
    assert mode == "auto"


def test_write_once_does_not_cache() -> None:
    """write 级 'once' 后，相同 args_hash 仍应弹窗。"""
    args = ("/tmp/x",)
    kwargs: dict[str, object] = {"content": "hi"}
    record_approval("file_write", "write", args, kwargs, "once")
    assert not is_cached_allow("file_write", args, kwargs)
    mode = check_permission("file_write", "write", args, kwargs)
    assert mode == "pending"


def test_write_different_args_not_cached() -> None:
    """不同参数应分别弹窗。"""
    record_approval("file_write", "write", ("/a",), {"content": "x"}, "always")
    mode = check_permission("file_write", "write", ("/b",), {"content": "x"})
    assert mode == "pending"


def test_write_deny_caches_deny() -> None:
    """write 级 'deny' 后，相同 args_hash 应命中 deny 缓存。"""
    args = ("/tmp/x",)
    kwargs: dict[str, object] = {"content": "hi"}
    record_approval("file_write", "write", args, kwargs, "deny")
    assert is_cached_deny("file_write", args, kwargs)
    mode = check_permission("file_write", "write", args, kwargs)
    assert mode == "deny"


# ---- 缓存重置 ----


def test_reset_session_cache_clears_all() -> None:
    """reset_session_cache 应同时清空 allow + deny 缓存。"""
    record_approval("file_write", "write", ("/x",), {"content": "a"}, "always")
    record_approval("file_write", "write", ("/y",), {"content": "b"}, "deny")
    reset_session_cache()
    assert not is_cached_allow("file_write", ("/x",), {"content": "a"})
    assert not is_cached_deny("file_write", ("/y",), {"content": "b"})


# ---- 永不沙箱风险知情 ----


def test_needs_ack_when_no_settings(settings_path: Path) -> None:
    """settings.json 不存在时应需 ack。"""
    assert not settings_path.exists()
    assert needs_sandbox_risk_ack() is True


def test_needs_ack_when_not_acked(settings_path: Path) -> None:
    """settings.json 存在但 sandbox_risk_acked=False 时应需 ack。"""
    settings_path.write_text(json.dumps({"sandbox_risk_acked": False}), encoding="utf-8")
    assert needs_sandbox_risk_ack() is True


def test_no_need_ack_after_acked(settings_path: Path) -> None:
    """ack_sandbox_risk 后应不再需要 ack。"""
    ack_sandbox_risk()
    assert settings_path.exists()
    assert needs_sandbox_risk_ack() is False


def test_ack_preserves_other_settings(settings_path: Path) -> None:
    """ack_sandbox_risk 应保留既有其他字段。"""
    settings_path.write_text(
        json.dumps({"theme": "dark", "host": "localhost:11434"}),
        encoding="utf-8",
    )
    ack_sandbox_risk()
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    assert data["sandbox_risk_acked"] is True
    assert data["theme"] == "dark"
    assert data["host"] == "localhost:11434"


def test_needs_ack_handles_corrupted_settings(settings_path: Path) -> None:
    """settings.json 损坏时应返回 True（容错）。"""
    settings_path.write_text("not a json", encoding="utf-8")
    assert needs_sandbox_risk_ack() is True


# ---- UI 弹窗（ApprovalDialog）----


def test_approval_dialog_emit_once(qapp) -> None:  # noqa: ANN001
    """ApprovalDialog 点击'允许一次'应发射 'once'。"""
    from q_agent.ui.approval_dialog import ApprovalDialog

    dlg = ApprovalDialog(
        tool_name="file_write",
        permission_level="write",
        args_hash="abc123def456",
        args_preview="path=/tmp/x",
    )
    received: list[str] = []
    dlg.approved.connect(lambda m: received.append(m))

    # 不勾选 cb，点 once
    dlg.cb.setChecked(False)
    dlg._emit("once")  # type: ignore[attr-defined]
    assert received == ["once"]


def test_approval_dialog_always_without_checkbox_falls_back_to_once(qapp) -> None:  # noqa: ANN001
    """未勾选'不再追问'时，'always' 应回退为 'once'。"""
    from q_agent.ui.approval_dialog import ApprovalDialog

    dlg = ApprovalDialog(
        tool_name="file_write",
        permission_level="write",
        args_hash="abc123def456",
        args_preview="path=/tmp/x",
    )
    received: list[str] = []
    dlg.approved.connect(lambda m: received.append(m))

    dlg.cb.setChecked(False)
    dlg._emit("always")  # type: ignore[attr-defined]
    assert received == ["once"]


def test_approval_dialog_always_with_checkbox_emits_always(qapp) -> None:  # noqa: ANN001
    """勾选'不再追问'时，'always' 应正确发射。"""
    from q_agent.ui.approval_dialog import ApprovalDialog

    dlg = ApprovalDialog(
        tool_name="file_write",
        permission_level="write",
        args_hash="abc123def456",
        args_preview="path=/tmp/x",
    )
    received: list[str] = []
    dlg.approved.connect(lambda m: received.append(m))

    dlg.cb.setChecked(True)
    dlg._emit("always")  # type: ignore[attr-defined]
    assert received == ["always"]


def test_approval_dialog_destructive_disables_checkbox(qapp) -> None:  # noqa: ANN001
    """destructive 级应禁用'不再追问'勾选。"""
    from q_agent.ui.approval_dialog import ApprovalDialog

    dlg = ApprovalDialog(
        tool_name="file_move",
        permission_level="destructive",
        args_hash="abc123def456",
        args_preview="src=/a dst=/b",
    )
    assert not dlg.cb.isEnabled()


# ---- UI 弹窗（SandboxRiskDialog）----


def test_sandbox_risk_dialog_confirm_button_disabled_initially(qapp) -> None:  # noqa: ANN001
    """SandboxRiskDialog 确认按钮初始应禁用。"""
    from q_agent.ui.approval_dialog import SandboxRiskDialog

    dlg = SandboxRiskDialog()
    assert not dlg._btn.isEnabled()  # type: ignore[attr-defined]


def test_sandbox_risk_dialog_confirm_enabled_after_check(qapp) -> None:  # noqa: ANN001
    """勾选'我已了解'后确认按钮应启用。"""
    from q_agent.ui.approval_dialog import SandboxRiskDialog

    dlg = SandboxRiskDialog()
    dlg.cb.setChecked(True)
    assert dlg._btn.isEnabled()  # type: ignore[attr-defined]


def test_sandbox_risk_dialog_emits_acknowledged(qapp) -> None:  # noqa: ANN001
    """勾选后点确认应发射 acknowledged 信号。"""
    from q_agent.ui.approval_dialog import SandboxRiskDialog

    dlg = SandboxRiskDialog()
    received: list[bool] = []
    dlg.acknowledged.connect(lambda: received.append(True))

    dlg.cb.setChecked(True)
    dlg._on_ok()  # type: ignore[attr-defined]
    assert received == [True]


def test_sandbox_risk_dialog_no_ack_without_checkbox(qapp) -> None:  # noqa: ANN001
    """未勾选时点确认不应发射 acknowledged。"""
    from q_agent.ui.approval_dialog import SandboxRiskDialog

    dlg = SandboxRiskDialog()
    received: list[bool] = []
    dlg.acknowledged.connect(lambda: received.append(True))

    dlg.cb.setChecked(False)
    dlg._on_ok()  # type: ignore[attr-defined]
    assert received == []
