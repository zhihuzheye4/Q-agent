"""Q-agent UI 模块（PySide6 实现）。

职责：
    - 提供 q_agent 桌面端 UI 主窗口骨架
    - 4 个 tab（对话/技能/记忆/设置）切换
    - 输入框 + 发送按钮（前端 echo，无后端）
    - 工具栏 + 菜单栏（按钮可按，无实际行为）
    - 图标方案 D：QIcon 直接受 SVG，不写预渲染层（见 ADR-016）

模块结构：
    main_window.py    主窗口（QMainWindow）
    sidebar.py        侧边栏 4 tab 切换
    pages/            各 tab 内容页
    toolbar.py        顶部工具栏
    menu_bar.py       顶部菜单栏
    theme.py          QSS 暗色主题（从设计规范翻译）
    icons.py          图标加载（方案 D 核心）

约束：
    - UI 是"活的空壳"：界面可跳转、按钮可按，但无实际功能
    - 不接 LLM / 不调 skills / 不读写 memory（留待后续里程碑）
    - PySide6 import 延迟到 cmd_ui() 调用时，避免无 PySide6 环境崩
"""
