---
name: playbook-resume
description: 显式恢复当前占任会话，检查基线变化与已有任务，不夺取其他会话的角色，不重放任务。
license: MIT
compatibility: POSIX 上的 Python 3.9+；Git 可选。
metadata:
  version: "3.1.0-dev.1"
disable-model-invocation: true
---

# 恢复本会话

1. 读项目规则与[生命周期](references/lifecycle.zh.md)，特别是身份和恢复部分。从本次加载的 SKILL.md 定位 `PLAYBOOK_SKILL_DIR`，从用户目标定位 `PLAYBOOK_PROJECT`，不依赖 cwd。使用宿主的文件/命令能力。
2. 只读检查权威状态：

   ```bash
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" status --project "$PLAYBOOK_PROJECT"
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" doctor --project "$PLAYBOOK_PROJECT"
   ```

   读当前配置、配置指定的交接/计划/员工规则、看板和已定决定。未初始化时说明生命周期里的 start 流程，不能把初始化当 resume 的附带动作。
3. 使用**本会话此前保存的** `PLAYBOOK_SESSION` 与 `PLAYBOOK_EPOCH`。客户端/模型相同不代表会话相同。不能从 status 或 TEAM.md 复制 holder 身份获得权限。新会话或现任为别人时保持只读，按用户要求执行本包生命周期参考里的 takeover 流程。
4. 只恢复匹配的 owner：

   ```bash
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" resume --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --epoch "$PLAYBOOK_EPOCH"
   ```

   解析成功 JSON。epoch 过期或所有权冲突时停止受管修改。resume 可以恢复本 owner 的暂停状态，不重放派发或测试。
5. 比较基线/worktree/dirty 文件、日志和任务记录。新启动前核查孤儿、reserved、running、unknown 尝试与待确认取消。查看 runtime API／项目副本差异和不完整检查点，不自动覆盖或升级。保留已有成果与已定选择。读[派发](references/dispatch.zh.md)、[审查](references/review.zh.md)及[结构化任务](references/work-protocol.zh.md)：复核回执适用性与 readiness，实现结束后再做重型验证；结构化任务须有适用的验收／集成证据。
6. 报告当前 owner/epoch、检查点后的变化、在途任务、未知项、哪些没有重跑及下一项获准步骤。恢复成功不表示过去的测试结论仍然适用。

英文版：[SKILL.md](SKILL.md)。
