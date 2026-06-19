"""技能层：@skill 装饰器注册体系，函数签名即协议。"""

import q_agent.skills.builtin  # 触发内置技能注册  # noqa: F401
from q_agent.skills.registry import all_skills, lookup, skill  # noqa: F401
