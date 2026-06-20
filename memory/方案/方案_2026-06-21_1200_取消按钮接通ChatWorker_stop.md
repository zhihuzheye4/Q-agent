# 方案：v0.0.17 候选 1 — 取消按钮接通 ChatWorker.stop()

**日期**：2026-06-21
**分支**：feat/cancel-button
**状态**：已执行（含 3 项修订），待用户验证 v0.0.17-test.exe

## 背景

v0.0.16 完成后用户选择执行候选 1（取消按钮接 ChatWorker.stop()）。
- v0.0.8 已留接口：ChatWorker.stop() 方法 + chat_aborted 信号占位；toolbar"取消"按钮 triggered 连 status_callback 占位文案。
- 接口预留型待办第二例（首例 v0.0.8 status_callback → v0.0.16 接通）。

## 贴纸式合规审查（ADR-027 四点检查）

| 检查点 | 候选 1 表现 | 结论 |
|--------|------------|------|
| 改既有模块类继承？ | 否，Toolbar 仍 QToolBar，ChatWorker 仍 QThread，ChatPage 仍 QWidget | 合规 |
| 改既有模块 objectName？ | 否 | 合规 |
| 改既有模块既有信号签名？ | 否，仅新增 cancel_requested/chat_aborted 两个信号 | 合规 |
| 塞新功能进既有模块内部？ | 否，cancel-action 是 Toolbar 的 addAction 调用（与 refresh_btn 同模式） | 合规 |

## 首版实施（commit d1c3611）

1. **toolbar.py 扩展公开接口（纯增量）**：
   - 新增 `cancel_requested = Signal()` 信号
   - `_build_actions` 加 cancel-action（stop 图标，"取消当前 AI 回复生成"tooltip），triggered 连 `cancel_requested.emit`
   - 不改类继承/objectName/既有信号

2. **chat_worker.py 扩展公开接口（纯增量）**：
   - 新增 `chat_aborted = Signal()` 信号
   - `run()` 在 chat_stream 循环每次迭代检查 `_stop`，命中时 flush 残余 buffer + emit chat_aborted + return
   - `stop()` 方法 v0.0.8 已留，v0.0.17 接通

3. **chat_page.py 加 _cancel_chat + _on_chat_aborted 方法**：
   - `_cancel_chat`：调 `worker.stop()`（首版仅此，等后台信号）
   - `_on_chat_aborted`：保留部分回复加 [已取消] 后缀入历史 + 恢复输入状态

4. **main_window.py 加 1 行 connect**：
   - `self.toolbar.cancel_requested.connect(self.chat_page._cancel_chat)`

5. **stop-active.svg 图标**：实心方块（fill=currentColor）

## 用户验证反馈 3 个问题

1. **唤醒/思考阶段点取消无反应需第二次点击**
   - 根因：ChatWorker.run() 在 chat_stream 阻塞等首个 chunk 时无法检查 _stop 标志
   - 修复：_cancel_chat 从"仅 worker.stop() 等信号"改为"worker.stop() + 同步立即调 _on_chat_aborted() 清理 UI"
   - _on_chat_aborted 加幂等保护（pending_bubble 已 None 时 no-op），chat_aborted 信号到达时再次调用 no-op

2. **取消按钮样式 + 位置**
   - 样式：外圈圆形轮廓 + 内部红色方块
   - 位置：模型下拉列表右侧
   - 修复：scripts/generate_icons.py 改 icon_stop_active = 外圈 circle(12,12,10) + 内部 rect(8.5,8.5,7,7, fill=#EF4444, stroke=none)；toolbar.py 把 cancel-action 从 _build_actions 移到 _build_model_group 里 model_combo 之后

3. **流式中点停止气泡无 [已取消] 后缀**
   - 根因：原版本只 _messages.append 加后缀，气泡 text 没更新（数据/视图分离坑）
   - 修复：_on_chat_aborted 加 `self._pending_bubble.setText(self._pending_text + " [已取消]")` 同步刷新气泡显示后再 _messages.append

## 测试

- ruff check + format + mypy strict 全绿（43 源文件）
- pytest：156 通过（+4 新增），84.55% 覆盖率

## 打包

- v0.0.17-test .exe 重新打包覆盖（严格从 安装包/README.md 模板复制：--onefile --windowed --add-data "q_agent/assets;q_agent/assets" --hidden-import pynvml --collect-all pynvml --collect-all psutil）
- 安装包当前状态：v0.0.16 + v0.0.17-test 并存

## 验证通过后下一步

1. `git checkout main && git merge --ff-only feat/cancel-button`
2. `q_agent/__init__.py` 升版本 0.0.16 → 0.0.17
3. 重新打包到 `安装包/v0.0.17/`
4. 删除 `安装包/v0.0.16/` + `安装包/v0.0.17-test/`
5. 启动验证 `Q-agent 0.0.17`
6. git commit + push

## 验证失败时回滚

```bash
git checkout main
git branch -D feat/cancel-button
rm -rf 安装包/v0.0.17-test
```

## ADR

- ADR-031 追加：取消按钮接通 ChatWorker.stop()（接口预留型待办第二例）