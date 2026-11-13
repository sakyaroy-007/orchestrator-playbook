---
name: playbook
description: 显式项目工作台与生命周期入口。显示状态和下一步；按要求开始、继续、交接、接任、配置、诊断、暂停、取消执行或补齐项目基座。
license: MIT
compatibility: POSIX 上的 Python 3.9+；Git 可选。旧 shell 适配器另需 bash 及其文档列出的依赖。
metadata:
  version: "3.0.0"
disable-model-invocation: true
---

# Playbook

只在用户显式调用时使用。没有具体动作的调用只做只读导航，不任命 holder、不创建项目文件、不派员工。已分配任务的执行者继续自己的单卡，不认领总指挥。

1. 读项目规则与[生命周期](references/lifecycle.zh.md)。从本次加载的 SKILL.md 定位 `PLAYBOOK_SKILL_DIR`，从用户实际目标定位 `PLAYBOOK_PROJECT`。沿用已经确定的项目，不能把用户主目录或技能仓库当作默认目标。目标不存在或有歧义时，先只读检查已知位置，只收集缺少的选择。
2. 先发现，已初始化时再查状态和诊断：

   ```bash
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" discover --project "$PLAYBOOK_PROJECT"
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" status --project "$PLAYBOOK_PROJECT"
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" doctor --project "$PLAYBOOK_PROJECT"
   ```

   对比用户请求路径与实际项目根。用户想建独立子项目却解析到上层仓库等意图冲突，必须在修改前解决；已知仓库内的常规子目录操作无需重复确认。版本或项目副本不一致时报告差异，不自动替换文件。
3. 用用户语言固定呈现简短工作台：**项目及路径、当前状态与本会话角色、阻塞事项、一个推荐操作、至多三个相关备选操作**。确有未决选择时，宿主支持选择框就使用，否则给编号文本；不能承诺所有客户端都有可点击菜单。用户已经明确选择的操作直接执行，不再问一遍。

   | 实际状态 | 推荐下一步 |
   |---|---|
   | 尚未配置 | 给具体推荐，提供开始／接入入口 |
   | active，当前会话持有 | 继续下一张就绪卡，或查看其阻塞原因 |
   | paused，当前会话持有 | 按要求恢复；恢复点不完整时明确提示 |
   | prepared，当前会话为交出方 | 等待接手；计划改变时提供明确撤回 |
   | prepared，当前会话为接收方 | 提供接任；明确接任请求即构成任命 |
   | 其他会话 active，尚无准备交接 | 只读查看，或由旧会话准备交接 |
   | 有未知尝试／版本或证据冲突 | 先诊断并核对具体阻塞 |

   含糊的“继续”不授权替换另一活动持有者。运行时编号由流程管理；已准备的 handoff ID 从权威状态读取，不要求用户手工搬运。
4. 将请求路由到随包流程：

   | 请求 | 流程 |
   |---|---|
   | 开始／接入 | [生命周期](references/lifecycle.zh.md)与[配置](references/configuration.zh.md)；初始化、补齐基座、完成首张有边界的卡 |
   | 本会话继续 | 用本会话保存的身份和 epoch 恢复，不自动重放 |
   | 准备／撤回交接 | 生命周期交接／撤回；保护成果，使已撤回编号失效 |
   | 接手 | 已准备交接，或得到明确授权的中断恢复 |
   | 修改指定设置 | 配置 patch，保留其他值和授权 |
   | 查看／诊断／运行时版本 | 只读 status、doctor 或 version，不自动修复 |
   | 暂停新增工作 | 先持久化暂停，再建检查点；单独报告不完整恢复点 |
   | 取消某次执行 | 按 attempt ID 请求取消，与暂停区分 |
   | 检查／补齐协作文件 | [开局](references/bootstrap.zh.md)的基座 check／只创建缺失文件的 apply |

5. 修改只能使用当前会话已确立的身份与现行 epoch。读取对应流程和实际命令帮助，核对成功 JSON 与退出码，保留冲突。不能复制其他 owner 的身份、修改 TEAM.md 认领，或使用旧助手逃避新版协议要求。新工作前读[任务卡](references/cards.zh.md)、[派发](references/dispatch.zh.md)和[审查](references/review.zh.md)。实现派发结束后再排程重型验证，不在同一活动任务中嵌套执行。
6. 汇报实际修改、保留文件／成果、验证、未决事项和下一项获准步骤。区分已安装、已初始化、已建基座、可派发、已报告、已验收和已集成。交接准备成功后给一条可复制的接手短句，包含真实路径：“用 playbook 接手位于〈项目路径〉的已准备交接，沿用已有设置，检查下一张就绪卡。”prepared 后不再修改共享文件。

全部流程与资源随本入口打包；其他技能入口是快捷方式，不是依赖。英文版：[SKILL.md](SKILL.md)。
