---
name: orchestrator-playbook
description: Playbook 项目生命周期的显式兼容入口。仅按用户要求开始、恢复、交接、接任、配置、查看或暂停。
license: MIT
compatibility: POSIX 上的 Python 3.9+；Git 可选。旧 shell 适配器另需 bash 及其文档列出的依赖。
metadata:
  version: "3.1.0-dev.1"
  repository: "https://github.com/sakyaroy-007/orchestrator-playbook"
disable-model-invocation: true
---

# Orchestrator Playbook

这是 `playbook` 路由的兼容名称。五个显式入口为 `playbook`、`playbook-start`、`playbook-resume`、`playbook-handoff`、`playbook-takeover`。每个安装入口都带所需脚本、参考和模板；根入口也可独立使用。

只在显式调用时使用。没有具体动作的调用只做导航和只读检查，不任命、不授予派发权限。执行者仍只负责分配的单卡。维护本技能仓库时按 AGENTS.md 做维护者，不能因为读到技能就在这里铺控制面。

## 执行用户所需操作

1. 读目标项目规则与[共享生命周期流程](references/lifecycle.zh.md)。把 `PLAYBOOK_SKILL_DIR` 解析为**本次加载的 SKILL.md** 所在目录，`PLAYBOOK_PROJECT` 解析为用户目标，不依赖 cwd。使用宿主已有的文件和命令能力，不要求客户端专有工具。
2. 先发现：

   ```bash
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" discover --project "$PLAYBOOK_PROJECT"
   ```

   已初始化项目再读权威状态：

   ```bash
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" status --project "$PLAYBOOK_PROJECT"
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" doctor --project "$PLAYBOOK_PROJECT"
   ```

3. 用用户语言呈现简短工作台：实际项目／路径、状态与本会话角色、阻塞、一个推荐下一步和至多三个备选。修改前核对请求路径与实际根目录。只有真实未决选择才使用宿主选择框，不支持时用编号文本。已经明确的操作直接执行，不重复确认；首次设置给具体推荐，复用已定决定。所有流程随包提供，无需调用其他入口。含糊的“继续”不能替换另一活动持有者。

| 用户请求 | 执行 |
|---|---|
| 开始或采用 | 生命周期“开始”：discover，按[配置参考](references/configuration.zh.md)至多四组问题，真正初始化，只创建缺失文件，规划首任务 |
| 恢复 | 生命周期“恢复”：用本会话保存的身份/epoch，检查变化基线和尝试，不重放 |
| 交接 | 生命周期“检查点、暂停与交接”：保护成果，准备完整检查点，返回 handoff ID 并停止受管修改 |
| 接任 | 生命周期“接任”：已准备交接加显式调用即构成任命；未准备恢复有单独前提 |
| 配置 | 读当前策略和[配置参考](references/configuration.zh.md)，写商定临时草案，再 configure |
| 状态 / 诊断 | 只读报告 status/doctor 的证据和未知项，不自动修复 |
| 暂停 | 先持久化停止新增工作，再建检查点；单列不完整恢复，保留已有员工 |
| 撤回交接 | 接任前由交出方按生命周期执行 `handoff --cancel`，旧编号失效、回到 paused |
| 取消执行 | 针对选定 attempt 请求监督进程取消，保留证据，核对实际结束确认 |
| 检查／补齐基座 | 开局助手 check／受管只创建缺失文件的 apply，按配置路径并保留原文件 |
| 运行时版本 | 只读 version 和 doctor 诊断，不覆盖不同的项目副本 |

4. configure/pause 使用本会话自己的 `PLAYBOOK_SESSION`/`PLAYBOOK_EPOCH`。局部变更时，`PLAYBOOK_CONFIG` 是仅含已批准变更的临时 JSON patch；完整替换使用互斥的 `--config`。只运行选中的命令：

   ```bash
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" configure --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --epoch "$PLAYBOOK_EPOCH" --patch "$PLAYBOOK_CONFIG"
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" pause --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --epoch "$PLAYBOOK_EPOCH"
   ```

5. 检查退出状态并解析成功 JSON 后再宣布变更。运行时 owner/epoch 优先于 TEAM.md，不复制别人 ID。新派发前核查孤儿、运行中和未知尝试。CLI 存在、建议或退出码 0，都不证明已登录、模型配置生效或验收通过。
6. 按项目策略进入生命周期工作循环，报告改了什么、实际验证、保留成果、没做什么及剩余缺口。

## 共享参考

- [生命周期](references/lifecycle.zh.md)：身份、start/resume/handoff/takeover、暂停、检查点、工作循环与限制。
- [配置](references/configuration.zh.md)：精简引导、员工继承、权限与 Git 策略。
- [开局](references/bootstrap.zh.md)与[交接文件](references/handoff-files.zh.md)：只创建缺失规划文件和持久证据。
- [任务卡](references/cards.zh.md)、[派发](references/dispatch.zh.md)、[审查](references/review.zh.md)与[结构化任务](references/work-protocol.zh.md)：有边界的工作、分阶段执行、内容绑定证据与集成。
- [与拍板人协作](references/stakeholder.zh.md)、[经验](references/lessons.zh.md)及 `templates/`：决定和可复用项目文件。

未配置的 v2 shell 工具仍可用，但不享有 v3 所有权/检查点/限额保证，采用必须显式。首版协调同一 POSIX 机器上的协作会话，不能控制任意工具或多台机器。不承诺自动安装、发布、原生对话恢复或未经验证的模型/思考映射。英文版：[SKILL.md](SKILL.md)。
