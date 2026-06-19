# Q-agent

类似 Claude Code 的桌面端 AI 工具，对接本地 LLM 大模型。

## 快速启动

```bash
pip install -e ".[dev]"
python -m q_agent version
python -m q_agent chat "echo 你好"
python -m q_agent skills
```

## 测试

```bash
pytest
ruff check . && ruff format --check .
mypy q_agent
```