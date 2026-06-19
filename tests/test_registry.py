"""@skill 装饰器注册测试。"""

import pytest

from q_agent.skills.registry import _REGISTRY, lookup, skill


def test_skill_registered() -> None:
    """装饰后应能通过 lookup 找到，且 fn 调用正确。

    用 try/finally 清理临时注册项，避免断言失败时污染全局注册表。
    """

    @skill(name="test_temp", desc="测试")
    def fn(x: str) -> str:
        return x

    try:
        assert lookup("test_temp") is not None
        assert lookup("test_temp").fn("x") == "x"
    finally:
        _REGISTRY.pop("test_temp", None)


def test_skill_name_conflict_rejected() -> None:
    """重名注册应抛 ValueError，且不影响已有项。"""

    @skill(name="test_conflict", desc="第一次")
    def fn1(x: str) -> str:
        return x

    try:
        with pytest.raises(ValueError, match="技能名冲突"):

            @skill(name="test_conflict", desc="第二次")
            def fn2(x: str) -> str:
                return x

        # 原注册项未被覆盖
        assert lookup("test_conflict").fn("a") == "a"
    finally:
        _REGISTRY.pop("test_conflict", None)
