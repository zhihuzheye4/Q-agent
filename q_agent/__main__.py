"""支持 python -m q_agent 调用。"""

import sys

from q_agent.cli import main

if __name__ == "__main__":
    sys.exit(main())
