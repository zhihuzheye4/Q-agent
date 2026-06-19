"""内置 echo 技能：原样回显，用于冒烟测试。"""

from q_agent.skills.registry import skill


@skill(name="echo", desc="回显输入文本")
def echo(text: str) -> str:
    """参数 text：用户输入；返回 原文。"""
    return text
