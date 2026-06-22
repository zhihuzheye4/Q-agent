<!--
权限：L3 完全权限
说明：由 /ui-ux-pro-max skill 产出的设计系统规范，AI 可读可改可删。
       作为 Q-agent UI 实施的视觉/交互/排版基线。
       下次设计调整时可用 --spec 此文件覆盖脚本默认参数。
       后续若要扩展（如 spacing/shadow/component specs），调 --persist --page <page> 生成补充。
-->

# Q-Agent 设计系统规范

- 生成时间：2026-06-19 20:15
- 产出方式：`/ui-ux-pro-max --design-system -f markdown` + `--domain ux` 深挖
- 适用：桌面端 AI 工具，IDE 类目（Developer Tool / IDE）

## Pattern

- **Name**：Minimal Single Column
- **Sections**：Hero headline / Short description / Benefit bullets (3 max) / CTA / Footer
- **CTA Placement**：Center, large CTA button
- **Color Strategy**：极简（Brand + white + accent），按钮对比度 7:1+

## Style

- **Name**：Dark Mode (OLED)
- **Mode Support**：仅暗色（不支持亮色）
- **Keywords**：暗色主题 / 低光 / 高对比 / 深黑 / 午夜蓝 / 护眼 / OLED / 夜间模式 / 节能
- **Best For**：编码平台 / AI 仪表盘 / 高端生产力工具 / 护眼夜间使用
- **Performance**：⚡ Excellent | **Accessibility**：✓ WCAG AAA

## Colors（10 个语义 token）

| Role | Hex | QSS 用法 |
|------|-----|---------|
| Primary | `#1E293B` | 主按钮背景 / 侧边栏选中态 / 工具栏图标 active |
| On Primary | `#FFFFFF` | 主色之上的文字 |
| Secondary | `#334155` | 次级按钮 / 悬停态 |
| Accent/CTA | `#22C55E` | 发送按钮 / 关键操作强调（绿：运行/成功） |
| Background | `#0F172A` | 窗口背景 / 主内容区背景 |
| Foreground | `#F8FAFC` | 主文字色（近白） |
| Muted | `#272F42` | 占位符 / 禁用态 / 弱化文字 |
| Border | `#475569` | 边框 / 分隔线 |
| Destructive | `#EF4444` | 删除 / 危险操作 |
| Ring | `#3B82F6` | 焦点环（亮蓝，在 Background `#0F172A` 上可见；2026-06-22 规则审查修订，原 `#1E293B` 与 Primary 同色导致不可见） |

## 扩展调色板（v0.0.4+ 新增 UI 元素用色，2026-06-22 补录）

主 10 个语义 token 之外的扩展色，用于多元素区分场景。所有扩展色在 Background `#0F172A` 上均达 WCAG AA 对比度。

### 模型名 8 色调色板（v0.0.4 起，chat_page 按模型名 hash 取色）

同一模型每次显示同色（crc32 mod 8），8 色高对比：

| 索引 | Hex | 中文色名 | 用途 |
|------|-----|---------|------|
| 0 | `#22C55E` | 绿 | 模型名标签色 1 |
| 1 | `#3B82F6` | 蓝 | 模型名标签色 2 |
| 2 | `#A855F7` | 紫 | 模型名标签色 3 |
| 3 | `#EC4899` | 粉 | 模型名标签色 4 |
| 4 | `#F97316` | 橙 | 模型名标签色 5 |
| 5 | `#14B8A6` | 青 | 模型名标签色 6 |
| 6 | `#EAB308` | 黄 | 模型名标签色 7 |
| 7 | `#6366F1` | 靛 | 模型名标签色 8 |

碰撞概率 1/8 可接受；如需扩展可升至 16 色。

### 硬件监控 6 色（v0.0.12 起，hardware_monitor 折线图）

| 指标 | Hex | 中文色名 | 备注 |
|------|-----|---------|------|
| CPU 占用率 | `#3B82F6` | 蓝 | 折线 1 |
| GPU 利用率 | `#22C55E` | 绿 | 折线 2 |
| 显存占用率 | `#A855F7` | 紫 | 折线 3 |
| 内存占用率 | `#F97316` | 橙 | 折线 4 |
| CPU 温度 | `#94A3B8` | 灰蓝 | Windows 永远 N/A，灰色占位横线 |
| GPU 温度 | `#EF4444` | 红 | 折线 6 |
| 图例/y 轴文本 | `#94A3B8` | 灰蓝 | 与 CPU 温度同色，弱化非数据元素 |

### 中性灰阶（v0.0.4 起，toolbar 分组头/占位项）

| 用途 | Hex | 出现位置 |
|------|-----|---------|
| 分组头 disabled 灰 | `#94A3B8` | toolbar 下拉框"本地模型 / Ollama Cloud / 云端预置"分组头 |
| 占位项灰 | `#64748B` | toolbar 下拉框"未发现本地 LLM"占位项 |

## Typography

- **Heading**：Inter（300/400/500/600/700）
- **Body**：Inter（同上）
- **Mood**：dark, cinematic, technical, precision, clean, premium, developer, professional
- **Best For**：Developer tools / fintech / AI dashboards / streaming / high-end productivity
- **Google Fonts**：`https://fonts.google.com/share?selection.family=Inter:wght@300;400;500;600;700`
- **CSS Import**：
  ```css
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
  ```

**QSS 翻译**：Windows 系统 Inter 不一定预装，PyInstaller 打包需把字体文件加进 `--add-data`；本次为活 UI 空壳，先用 Qt 默认字体（Segoe UI），等用户提"字体优化"需求再升级。

## Key Effects

- 最小化光晕（text-shadow: 0 0 10px）
- 暗到亮过渡
- 低白光发射
- 高可读性
- 可见焦点

**QSS 翻译**：
- 光晕用 `QGraphicsDropShadowEffect`（Qt 程序化设置，QSS 不支持 box-shadow）
- 过渡用 `QPropertyAnimation`（QSS 不支持 transition）
- 焦点可见：`outline: 2px solid #3B82F6`（QSS 支持 outline；亮蓝在暗背景上可见）

## Anti-patterns（避免）

- 亮色模式作为默认（暗色优先）
- 性能慢（避免实时重渲染图标——方案 D QIcon 内部缓存天然满足）

## Pre-Delivery Checklist

- [x] 无 emoji 图标，全用 SVG（Lucide 风格，已实现）
- [ ] 所有可点击元素 cursor-pointer（QSS `cursor: pointing`）
- [ ] 悬停态平滑过渡 150-300ms（Qt 用 QPropertyAnimation）
- [x] 暗色文字对比度 4.5:1+（Foreground #F8FAFC on Background #0F172A ≈ 16:1）
- [ ] 焦点态可见（keyboard nav 友好）
- [ ] prefers-reduced-motion 尊重（Qt 不直接支持，需手动检测系统设置）

## UX 补充（--domain ux 深挖）

### Accessibility - Keyboard Navigation (High)
- 所有功能可键盘访问
- Tab 顺序匹配视觉顺序
- 禁止键盘陷阱 / 不合逻辑顺序

### Accessibility - Skip Links (Medium)
- 允许键盘用户跳过导航到主内容

### Interaction - Focus States (High)
- 键盘用户需要可见焦点指示
- 用可见焦点环（focus ring）
- 禁止 `outline-none` 无替代方案

**Q-agent 实施建议**：
- 侧边栏 4 tab 支持键盘 Tab 切换 + Enter 选中
- 工具栏按钮支持键盘 Tab + Enter
- 输入框支持 Tab 进入 + Enter 发送
- 所有 QAbstractButton 子类默认有焦点环

## Spacing（推测基线，待 skill --persist 补全）

基线 8px 网格：
- xs: 4px（紧凑元素内边距）
- sm: 8px（默认内边距）
- md: 16px（卡片/区块间距）
- lg: 24px（区域间距）
- xl: 32px
- 2xl: 48px
- 3xl: 64px

## Shadow Depths（推测基线，QSS 用 QGraphicsDropShadowEffect 替代）

- sm: 0 1px 2px rgba(0,0,0,0.05) — 微弱浮起
- md: 0 4px 6px rgba(0,0,0,0.1) — 卡片浮起
- lg: 0 10px 15px rgba(0,0,0,0.1) — 弹窗浮起
- xl: 0 20px 25px rgba(0,0,0,0.15) — 模态浮起

## Component Specs（Q-agent UI 实施翻译）

### Buttons
- 主按钮：background Primary `#1E293B`，text On-Primary `#FFFFFF`，padding 8/16px，radius 6px
- CTA 按钮：background Accent `#22C55E`，text On-Primary（白），其他同主按钮
  - hover：`#16A34A`（Accent 深一档）
  - pressed：`#15803D`（Accent 再深一档）
  - disabled：background Muted `#272F42` + color Border `#475569`
  - 实际代码 padding 10/20px / radius 8px（v0.0.4 起微调，比规范略大更柔和，可视觉等价接受）
- 次按钮：background transparent，border Border `#475569`，text Foreground `#F8FAFC`

### Inputs
- 背景 Muted `#272F42`
- 边框 Border `#475569`
- 焦点边框 Ring `#3B82F6`（2px outline，亮蓝在暗背景上可见）
- 文字 Foreground `#F8FAFC`
- 占位符 Muted `#272F42`（弱化）

### Cards / Sidebar
- 背景 Secondary `#334155`
- 边框 Border `#475569`
- 圆角 8px
- 阴影 md

### Modals
- 背景 Secondary `#334155`
- 阴影 xl
- 居中显示

## Component Specs 补录（v0.0.2~v0.0.17 新增 UI 元素，2026-06-22 补录）

### 模型下拉框 QComboBox（v0.0.4）
- 背景 Muted `#272F42`，边框 Border `#475569`
- 分组头（QStandardItemModel disabled 项）：color `#94A3B8`（中性灰），bold，不可选中
- 占位项（"未发现本地 LLM"）：color `#64748B`（占位灰），italic
- 三组结构：本地模型 / Ollama Cloud / 云端预置
- 检测失败时仅显示占位项，不加云端组

### AI 气泡模型名小标签 QLabel#ModelLabel（v0.0.4）
- 字号 11px，color 取自"模型名 8 色调色板"（按模型名 crc32 hash）
- 位于 AI 气泡上方，与气泡左对齐
- 同一模型每次显示同色

### 多行输入框 QTextEdit#ChatInput（v0.0.6）
- 背景 Muted `#272F42`，边框 Border `#475569`
- 圆角 8px，padding 10/14px
- 动态高度：documentSizeChanged 信号驱动，[44, 200] px 钳制 setFixedHeight
- 文字 Foreground `#F8FAFC`，占位符 Muted
- selection-background-color Accent `#22C55E`

### 错误气泡 QLabel#MessageError（v0.0.8）
- **当前代码用亮色 `#FEE2E2` 背景 + `#DC2626` 文字，与 OLED 暗色基调冲突**（待优化项）
- 建议改为暗色版本：background `#7F1D1D`（Destructive 深一档）+ color `#FECACA`（浅红文字）
- 圆角 10px，padding 10/14px（与用户/AI 气泡一致）

### 切换模型系统提示气泡 QLabel#MessageSystem（v0.0.9）
- 居中显示，italic
- color Muted `#272F42`（弱化，非主消息流一部分）
- 无气泡背景，仅文字
- 首次自动选择时抑制（保留初始问候）

### 加载指示器 LoadingDots（v0.0.10）
- 三点跳动，QTimer 80ms tick，1.6s 一周期
- 每点偏移 60 度形成流动彩虹（HSV 色相随时间流动）
- alpha=180（约 70% 透明度），与背景融合不刺眼
- dot_size=8px（固定，不随 DPI 缩放——待优化项）
- 流动彩虹色相独立于"模型名 hash 色"色彩系统（设计取舍，非冲突）
- 嵌入 pending AI 气泡内部，首个 chunk 到达时移除

### 释放模型确认对话框 QMessageBox（v0.0.11）
- 标准 QMessageBox.question 复用
- 标题"释放模型"，正文"确认释放 XXX 出 Ollama 内存？"
- 按钮组合：Yes/No（Yes 触发 release_model）
- release_model 后状态栏文案："API 验证通过，VRAM 已归还，任务管理器进程级 GPU 内存可能延迟显示"

### 硬件监控 MonitorCell（v0.0.12/v0.0.15）
- 单指标 cell 自绘：折线图 + 图例 + 当前数值 + 单位
- cell 整体背景 `#0F172A`（Background）
- plot 坐标系背景 `#1E293B`（Primary，与 cell 背景区分）
- 网格线 `#334155`（Secondary，5 条 0/25/50/75/100）
- y 轴：左侧 28px 刻度标签 0/25/50/75/100 + 单位 ° 或 % + 竖线
- 折线颜色取自"硬件监控 6 色"
- None 段断开不连线（如 CPU 温度 Windows 永远 N/A → 灰色占位横线）
- 数值显示格式：百分比 `f"{x:.0f}%"`，温度 `f"{x:.0f}°C"`
- 标签中文：CPU 占用率 / GPU 利用率 / 显存占用率 / 内存占用率 / CPU 温度 / GPU 温度

### 工具栏图标按钮 QToolButton（v0.0.16/v0.0.17）
- 默认态：transparent 背景 + Foreground 文字/图标
- 悬停态：Secondary `#334155` 背景
- 按下态：Primary `#1E293B` 背景
- 禁用态：Muted `#272F42` 背景 + Border `#475569` 文字
- 图标 16x16 SVG（Lucide 风格，单色描边继承 currentColor）
- 已实现按钮：new-chat / clear / about / refresh / release / cancel
- 取消按钮（v0.0.17）位置：模型下拉框右侧（不在 _build_actions 末尾）

### 硬件监控独立窗口 HardwareMonitorWindow（v0.0.15）
- 独立顶级窗口（Qt.WindowType.Window flag，不依附主窗口）
- Windows 任务栏独立条目 + 自带标题栏 X 关闭按钮
- 固定尺寸 620×520（未来可加可拖拽 resize）
- 标题"硬件监控"
- 2×3 网格 6 个 MonitorCell
- 由 menu_bar"监控"菜单 triggered 弹出（Ctrl+M 打开，Ctrl+W 关闭）
- closeEvent emit closed 信号让 MainWindow 清空 _hw_window 引用

## Q-agent UI 实施映射

| UI 元素 | Qt 控件 | 配色 |
|---------|---------|------|
| 窗口背景 | QMainWindow | Background `#0F172A` |
| 侧边栏 | QListWidget | Primary `#1E293B` |
| 侧边栏选中 | QListWidget item | Primary + 边框 Accent `#22C55E` 2px 左侧 |
| 主内容区 | QStackedWidget | Background |
| 对话消息流 | QScrollArea + QLabel | Background |
| 用户消息气泡 | QLabel | Secondary + 圆角 8px |
| AI 消息气泡 | QLabel | Muted + 圆角 8px |
| 输入框 | QLineEdit | Muted 背景 + Border 边框 |
| 发送按钮 | QPushButton | Accent `#22C55E` + On-Primary 白字 |
| 工具栏 | QToolBar | Primary 背景 |
| 工具栏按钮 | QToolButton | transparent + 悬停 Secondary |
| 菜单栏 | QMenuBar | Primary 背景 + Foreground 文字 |
| 设置复选框 | QCheckBox | Foreground 文字 + Accent 勾选 |
| 设置下拉 | QComboBox | Muted 背景 + Border 边框 |
| 焦点环 | 所有可聚焦控件 | outline Ring `#3B82F6` 2px |

## 升级路径

- 调 `--persist --page chat/settings/skills/memory` 生成各页 override
- 调 `--domain icons "dark stroke minimal"` 取图标规范
- 装 Inter 字体到 `q_agent/assets/fonts/` 并加 `--add-data` 进 .exe