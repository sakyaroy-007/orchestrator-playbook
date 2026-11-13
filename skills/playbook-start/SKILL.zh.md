---
name: playbook-start
description: 显式开始或采用项目，先只读发现，再收集精简策略、初始化当前会话并规划首任务，不覆盖已有文件。
license: MIT
compatibility: POSIX 上的 Python 3.9+；Git 可选。
metadata:
  version: "3.0.0"
disable-model-invocation: true
---

<!-- Generated from skill-src/playbook-start.zh.md by scripts/build-skills.py; edit the source, then rebuild. -->

# 开始项目

用户显式调用 start，在无人占任时就是任命当前具体会话，不再重复问任命。保留已有 holder 和文件；start 不自动授权派发、提交、推送或发布。

1. 读项目规则、[生命周期](references/lifecycle.zh.md)和[配置参考](references/configuration.zh.md)。从本次加载的 SKILL.md 定位 `PLAYBOOK_SKILL_DIR`，从目标项目定位 `PLAYBOOK_PROJECT`，不依赖 cwd。使用宿主的文件/命令能力。
2. 先运行只读发现：

   ```bash
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" discover --project "$PLAYBOOK_PROJECT"
   ```

   检查现有计划、代码、dirty 成果和旧文件。已配置项目读 `status`、`doctor`；同一会话按生命周期 resume，不同会话按 takeover，不能覆盖现任。CLI 存在不证明已登录或能力可用。
3. 单独调用入口即可，不要求预先写好目标。目标缺失或模糊时，先按配置参考的目标澄清流程，每轮问一至三个影响首阶段的关键问题，复用已有答案，再提出里程碑；旧项目从已有计划和进度出发。商定首阶段的结果、范围与验收后，给出具体开局摘要：请求／实际项目路径、阶段目标、沿用文件、员工与设置、限额、操作授权、基座规模（默认 minimal）。只在至多四组中补缺项：目标/边界、员工/本地工作/限额、模型/思考/profile、Git/保留策略；这是问题分类，不是必走的四轮问卷。用户接受具体推荐即解决对应选择。继承员工自己受支持的默认值。DSH 没有默认 profile，须取得已有非交互 profile 或明确推荐 `headless`，模型/思考再继承选定 profile。沿用已定事项，未验证的建议/映射不算已应用。
4. 把商定的 version 1 JSON 写到项目外临时草案，设置 `PLAYBOOK_CONFIG`、`PLAYBOOK_GOAL` 和当前 `PLAYBOOK_CLIENT`，再生成本会话 ID：

   ```bash
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" session-id --project "$PLAYBOOK_PROJECT"
   ```

   解析返回 ID 为 `PLAYBOOK_SESSION`，不使用其他 owner 的身份。真正初始化：

   ```bash
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" init --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --client "$PLAYBOOK_CLIENT" --goal "$PLAYBOOK_GOAL" --config "$PLAYBOOK_CONFIG"
   ```

   执行这条 init 前目标目录必须存在；发现指定的新目标不存在时，在确定目标/设置后先创建它。init 不执行 `git init`。只有用户要求导入已有项目时才追加 `--adopt`。非 Git 转 Git 不自动迁移，保护原运行时，不能创建第二 owner。失败是阻塞，不是 reset 或覆盖状态的许可。
5. 读 `status`，保留 owner/epoch/revision，再按[开局参考](references/bootstrap.zh.md)运行 `playbook-foundation.py check`，核对新建／保留／冲突清单，以商定规模在 scaffold guard 下 `apply`。Git 和非 Git 都按配置路径建基座，缺少根 README 时创建真实项目说明，保留全部已有文件。运行依赖缺失或旧副本不同要记录，不自动替换。把首卡的真实要求、内容范围、依赖、独占资源和分阶段检查填写完整，登记结构化 spec 并检查 readiness 后再派发。生成草稿、未知测试命令均不等于已经就绪。v3 worktree setup hook 会报待执行，guard 返回后按获准流程准备，避免嵌套受管 run，核实准备完成再通过[派发参考](references/dispatch.zh.md)派发首张有边界的卡。
6. 报告初始化后的项目/会话、实际保存的策略、首任务、保留文件、已做验证和未决缺口。区分已初始化、已规划、已启动。完整 start 流程和工作循环在生命周期参考中，不依赖其他入口。

英文版：[SKILL.md](SKILL.md)。
