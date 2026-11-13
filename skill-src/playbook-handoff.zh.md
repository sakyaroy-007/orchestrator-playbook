---
name: playbook-handoff
description: 显式由当前 owner 准备本地交接，先用完整检查点保护 dirty 与在途成果，再停止受管修改。
license: MIT
compatibility: POSIX 上的 Python 3.9+；Git 可选。
metadata:
  version: "3.0.0"
disable-model-invocation: true
---

# 准备交接

1. 读项目规则、[生命周期](references/lifecycle.zh.md)和[交接文件](references/handoff-files.zh.md)。从本次加载的 SKILL.md 定位 `PLAYBOOK_SKILL_DIR`，从目标定位 `PLAYBOOK_PROJECT`，不依赖 cwd。使用宿主的文件/命令能力。
2. 检查状态和诊断：

   ```bash
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" status --project "$PLAYBOOK_PROJECT"
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" doctor --project "$PLAYBOOK_PROJECT"
   ```

   只使用本会话保存的 `PLAYBOOK_SESSION`/`PLAYBOOK_EPOCH`。现任为别人是冲突，不允许代其交接。
3. 用日志、分支、dirty/未跟踪成果和已知进程核对尝试记录。保留孤儿和未知结果，缺少通知不证明已完成。协调稳定快照，不杀无关进程。把运行中的员工、共享资源、未推提交、基线、配置 revision、未定决定、证据缺口和下一步写入配置指定的交接文档，只复制相关项目记忆。
4. **准备检查点之前**完成上述文档编辑。Git 忽略的未跟踪文件不收进快照，需要的 ignored 证据先在获准范围内显式归档到会被覆盖的位置，cleanup 仍拒绝 ignored 成果。unmerged index 或 dirty submodule 会被拒绝，特殊文件或超量/读取失败也可能留下 partial，保留它并报告失败，不能称为完整。先保存冲突各 stage 的所需内容并解决冲突，再正常 handoff，不能为通过检查抹掉 stage 内容。不把接任会话提前标成 owner。运行：

   ```bash
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" handoff --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --epoch "$PLAYBOOK_EPOCH"
   ```

   已知具体接任会话 ID 时追加 `--to "$PLAYBOOK_NEXT_SESSION"`，不使用模型/客户端名称替代。命令先创建完整检查点，再进入 `prepared`。过大、不可读或正在变化的恢复内容是阻塞，不是交接成功。检查点失败按生命周期处理，不能为凑完整而丢掉文件。
5. 成功后解析并返回 handoff ID、目标和检查点事实，停止受管修改与派发，包括继续改共享文档。重复同一次 handoff 幂等。提交/推送和 worktree 保留遵循项目策略，本地交接不要求推远端。
6. 告诉用户保存了什么、什么仍在运行／未知。给包含真实项目路径的可复制短句：“用 playbook 接手这个项目的已准备交接，沿用当前设置，检查下一张就绪卡。”接任会话从权威 status 读取编号，显式 takeover 不重复确认同一任命。报告未做步骤，不能宣称已经接任。用户在接任前改变计划时，由交出方 owner 按生命周期执行 `handoff --cancel`，保留证据、使旧编号失效、回到 paused，再按要求恢复或重新准备。

英文版：[SKILL.md](SKILL.md)。
