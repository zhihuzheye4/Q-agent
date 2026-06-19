"""CLI 入口：argparse 子命令分发，零第三方依赖。"""

import argparse

import q_agent.skills  # noqa: F401  副作用导入：触发内置技能注册
from q_agent.memory.runtime import RuntimeMemory
from q_agent.orchestrator.core import Orchestrator


def build_parser() -> argparse.ArgumentParser:
    """构造 CLI 解析器。"""
    parser = argparse.ArgumentParser(prog="q-agent", description="Q-agent 桌面 AI 工具")
    sub = parser.add_subparsers(dest="cmd", required=True)
    chat = sub.add_parser("chat", help="发送一条消息")
    chat.add_argument("text", help="用户输入文本")
    sub.add_parser("skills", help="列出已注册技能")
    sub.add_parser("version", help="显示版本")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI 主入口。"""
    args = build_parser().parse_args(argv)
    if args.cmd == "version":
        from q_agent import __version__

        print(f"Q-agent {__version__}")
        return 0
    orch = Orchestrator(memory=RuntimeMemory())
    if args.cmd == "chat":
        print(orch.handle(args.text))
    elif args.cmd == "skills":
        for s in orch.list_skills():
            print(f"{s.name:<15} {s.desc}")
    return 0
