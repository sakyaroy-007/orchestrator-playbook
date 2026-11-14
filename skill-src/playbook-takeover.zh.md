---
name: playbook-takeover
description: 显式以新会话认领已准备的交接，或核查用户指示的未准备恢复，保留已有任务与成果。
license: MIT
compatibility: POSIX 上的 Python 3.9+；Git 可选。
metadata:
  version: "3.1.0-dev.1"
disable-model-invocation: true
---

# 接任项目

已准备交接，加用户显式调用 takeover，就是对指定接任会话的任命，不重复问同一任命。本入口不能从不活跃或旧锁推断替换授权。

1. 读项目规则、[生命周期](references/lifecycle.zh.md)、[配置参考](references/configuration.zh.md)及配置指定的交接/计划/员工文件。从本次加载的 SKILL.md 定位 `PLAYBOOK_SKILL_DIR`，从目标定位 `PLAYBOOK_PROJECT`，不依赖 cwd。使用宿主的文件/命令能力。
2. 先检查，不改所有权：

   ```bash
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" status --project "$PLAYBOOK_PROJECT"
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" doctor --project "$PLAYBOOK_PROJECT"
   ```

   检查请求路径与实际根目录、基线、dirty 成果、配置 revision、runtime API／项目副本诊断、目标、任务记录、日志和已知进程。新派发前核查孤儿、在途成果与取消确认；按[结构化任务](references/work-protocol.zh.md)复核内容绑定验收与集成的适用性。不自动升级副本、重启服务或重跑测试。保留已有文件和已定决定。
3. 为这个新会话生成新 ID（只有本会话已经生成过时才沿用）：

   ```bash
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" session-id --project "$PLAYBOOK_PROJECT"
   ```

   解析为 `PLAYBOOK_SESSION`，`PLAYBOOK_CLIENT` 填当前客户端。不复制现任身份。已准备交接时从权威状态/离任输出设置 `PLAYBOOK_HANDOFF`，运行：

   ```bash
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" takeover --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --client "$PLAYBOOK_CLIENT" --handoff "$PLAYBOOK_HANDOFF"
   ```

4. **未准备的中断**改按生命周期恢复规则：必须有用户指示停止/替换，确认前会话已停，认领前保护/核对任务与恢复内容。满足后才运行：

   ```bash
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" takeover --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --client "$PLAYBOOK_CLIENT" --recover --previous-stopped
   ```

   该参数是声明，不能隔离任意 shell/编辑器写入。前提缺失时保持只读，报告具体阻塞；不删锁或状态。已准备交接校验失败，不意味着可以静默改走恢复。

   仅在修复 configure 双文件更新中断/损坏，且用户审定完整替代配置后，令 `PLAYBOOK_CONFIG` 指向项目外该 JSON 草案，使用显式恢复变体：

   ```bash
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" takeover --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --client "$PLAYBOOK_CLIENT" --recover --previous-stopped --config "$PLAYBOOK_CONFIG"
   ```

   它先私存原 config/旧 state，再修复并记录配置 revision，然后 checkpoint、接任。保留并报告证据，检查点失败仍阻塞接任。不带 `--config` 保持严格校验；普通已准备 takeover 不能覆盖配置，prepared 校验失败也不授权静默改策略。完整恢复前提见生命周期。
5. 检查成功 JSON，保存新 epoch。运行时在共享 OS 锁内校验；机器、目标、revision、基线或恢复内容冲突必须保留可见。成功后按现场更新可读摘要，保留迟到结果和未决尝试，先审后按已存策略派发。同一会话重复成功接任幂等。
6. 报告实际 owner/epoch、基线差异、保留成果、运行中/未知任务、已验证能力差异和下一步。不宣称客户端原生对话恢复、跨机仲裁或未测模型/思考配置。

英文版：[SKILL.md](SKILL.md)。
