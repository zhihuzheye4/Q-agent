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
| Ring | `#1E293B` | 焦点环 |

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
- 焦点可见：`outline: 2px solid #1E293B`（QSS 支持 outline）

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
- 次按钮：background transparent，border Border `#475569`，text Foreground `#F8FAFC`

### Inputs
- 背景 Muted `#272F42`
- 边框 Border `#475569`
- 焦点边框 Ring `#1E293B`（2px outline）
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
| 焦点环 | 所有可聚焦控件 | outline Ring `#1E293B` 2px |

## 升级路径

- 调 `--persist --page chat/settings/skills/memory` 生成各页 override
- 调 `--domain icons "dark stroke minimal"` 取图标规范
- 装 Inter 字体到 `q_agent/assets/fonts/` 并加 `--add-data` 进 .exe