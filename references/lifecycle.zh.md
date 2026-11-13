# 生命周期与共享操作规则

这是五个显式入口共用的流程。初始化或修改策略前先读[配置参考](configuration.zh.md)。入口负责导航，不各自建立一套授权规则。

## 定位技能和项目

根据宿主提供的安装信息，把 `PLAYBOOK_SKILL_DIR` 解析为**本次加载的** `SKILL.md` 所在目录。把 `PLAYBOOK_PROJECT` 解析为用户指定的目标项目，不依赖当前工作目录。命令中始终给路径加引号。以下示例假定这两个变量已经设为解析后的路径；不要直接复制占位路径，也不要猜测全局安装位置。

使用宿主已有的读文件、写文件和执行命令能力，不要求某一客户端专有的工具名称。改文件前读项目规则。目标不明确时先做能做的只读检查，修改前再确定目标。不能仅因当前目录是技能仓库，就把它初始化成受控项目。

```bash
python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" discover --project "$PLAYBOOK_PROJECT"
python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" --help
```

成功命令返回 JSON。先检查退出状态并解析 JSON，再使用其中的 ID 或宣布成功。失败要给出可执行的说明，不能靠更换身份或绕过检查重试。安装版本的实际选项以 `ACTION --help` 为准。

## 授权、身份与证据

- 用户显式调用 `playbook-start`，在无人占任时就是任命**当前会话**，不用再问同一任命。它不等于一并允许派发、Git、花钱或发布。
- `playbook`、状态、诊断及读文件都不构成任命。执行者只做分配的单卡，不初始化、不派发、不改共享策略、不认领所有权。
- 新会话用 `session-id` 创建新身份，在本会话上下文保存返回的 ID 和当前 epoch。同一持续会话在压缩后可以沿用自己保存的身份。不能从 `status` 复制别人的 ID 冒充；客户端或模型同名不代表会话相同。
- 共享 Git common directory 中的运行时状态（非 Git 为 `.orchestrator/local/`）是 owner、epoch、尝试记录的权威来源；`.orchestrator/config.json` 是策略来源。TEAM.md 和看板是可读摘要，不是锁或任命书。
- 已准备的交接，加用户显式调用 takeover，就授权指定的新会话接任，不再问同一任命。未准备的替换必须有用户指示停止/替换并先核查现场；时间过去、没收到通知、锁很旧，都不是接任授权。
- 保护用户未提交、未跟踪、未合并的成果。区分亲自观察的事实、员工自报、配置建议和未知项。子进程成功仅表示 `reported`，不代表验收通过。

```bash
python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" session-id --project "$PLAYBOOK_PROJECT"
python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" status --project "$PLAYBOOK_PROJECT"
python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" doctor --project "$PLAYBOOK_PROJECT"
```

从新身份的 JSON 设置 `PLAYBOOK_SESSION`，从成功的所有权操作设置 `PLAYBOOK_EPOCH`。`status` 在 `policy` 返回完整配置，并给出 `config_path`、`project_root`；采用返回的位置，不猜测各 worktree 下的策略副本。无法确认所有权时保持只读，说明冲突。

## 开始：检查、配置、初始化、规划

1. 先运行 `discover`，只读检查项目规则、现有计划、Git/worktree 和旧 `.orchestrator` 文件。用户指定的新目录尚不存在时如实说明，只读检查已知父目录；确定用户目标/设置后，init 前创建该目标目录，不能静默替换成别的项目。发现可执行文件不等于调用模型、验证登录或验证能力。
2. 已配置项目读 `status` 和 `doctor`。不能覆盖现任：同一会话走 resume，不同会话走 takeover。未配置的旧文件只有在用户明确要求导入已有项目时才用 `--adopt`，即使采用也保留旧文件。
3. 按[配置参考](configuration.zh.md)的四组简短问题收集信息。沿用对话和项目里已确定的选择。给出精简推荐，补齐缺项，把完整的 version 1 JSON 草案写到项目外临时文件，令 `PLAYBOOK_CONFIG` 指向它。不改客户端全局设置，不写凭据。
4. 需要时获取新会话 ID。`PLAYBOOK_CLIENT` 填当前会话的客户端标识，`PLAYBOOK_GOAL` 填已定的可验收阶段目标。真正初始化：

   ```bash
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" init --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --client "$PLAYBOOK_CLIENT" --goal "$PLAYBOOK_GOAL" --config "$PLAYBOOK_CONFIG"
   ```

   只有用户要求导入已有项目时才追加 `--adopt`。同一 owner 的初始化幂等，冲突会失败。init 时目标目录必须已存在，用户要新建项目时先创建该目录；不必已有 Git，init 不执行 `git init`。已初始化的非 Git 项目转 Git 不自动迁移，布局冲突时停止并保护原 owner/状态，不能再初始化第二 owner。
5. 读 `status`，保存 owner/epoch/revision，核实落盘目标与策略。init 失败不能把草案说成已经初始化。按[开局参考](bootstrap.zh.md)使用基座助手先检查，再按配置路径只创建缺失 README／规划／运行文件。选择 minimal 或 standard，保留现有 AGENTS.md、交接、计划和代码，冲突不覆盖。apply 经 `guard --action scaffold` 校验 owner/epoch/active；显式 start 元数据不另问权限。按真实事实完成首卡与结构化 spec，再检查 readiness；生成草稿不等于可派发。旧 `init-plan.sh --dry-run` 保留给默认 Git 布局。
6. 按真实基线规划第一张小卡，写清范围、验收和缺口。有实际协作阻塞才先做地基卡；已就绪项目不强制加地基波次。已授权范围内继续推进，否则指出具体缺少的派发选择。start 不自动启动员工。

## 恢复：只恢复原 owner，不重放

读取规则、配置、交接、看板和已定决定，与 `status`、`doctor` 核对。只使用本会话此前保存的身份及最后已知 epoch：

```bash
python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" resume --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --epoch "$PLAYBOOK_EPOCH"
```

resume 可以恢复同一 owner 的暂停状态。它不夺取别人的角色，不重放派发、不重跑测试、不提交、不推送。规划新任务前检查变动基线及每个 reserved/running/unknown 任务。日志缺失不等于任务没跑过。所有权或 epoch 冲突时停止受管修改，说明 takeover 路径，不能靠改 TEAM.md 消除冲突。

## 检查点、暂停与交接

先用现有日志、分支、未提交文件和进程身份核对任务记录。避免共享写入与快照竞争；能协调时让员工先到稳定点。pause 不会杀员工。把仍在运行或未知的事项、未推提交、资源、待定决定和下一步写进配置指定的交接文档。项目相关记忆写入项目文件，不复制私人凭据或无关个人笔记。

```bash
python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" checkpoint --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --epoch "$PLAYBOOK_EPOCH"
python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" pause --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --epoch "$PLAYBOOK_EPOCH"
```

按需要选择操作，不要求依次运行。pause 先在所有权锁内持久化 `paused`，再尝试检查点。捕获失败时报告非零结果与不完整恢复点；新增受管工作仍保持暂停，已有员工和 partial 证据保留。若存储失败导致暂停本身未落盘，不能宣布已经暂停。checkpoint 保存实际 HEAD/worktree、覆盖范围内未提交和未跟踪源码的恢复副本、任务与配置，不做 commit/push/reset。Git 忽略的未跟踪文件不收进快照：需要恢复的 ignored 证据先在获准内容范围内显式归档到有记录、会被覆盖的位置，不能假定已经保存；cleanup 仍拒绝含 ignored 成果的工作树。unmerged index 和 dirty submodule 会被明确拒绝，不支持的特殊文件、超量、不可读或变化内容也可使检查点失败并留下 partial 恢复数据；保留 partial、报告缺口，不能宣布完整恢复点或已准备交接。索引有冲突时，先保存各 stage 需要保留的内容并解决冲突，再正常 handoff；不能为了通过检查抹掉 stage 内容。本地快照不进入常规发布。

交接时先写完离任文档，再运行：

```bash
python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" handoff --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --epoch "$PLAYBOOK_EPOCH"
```

已知具体接任**会话 ID** 时追加 `--to "$PLAYBOOK_NEXT_SESSION"`；客户端或模型名称不是目标会话。命令先做完整检查点，再进入 `prepared`。失败不能宣布交接已准备好；成功后把 handoff ID 和目标交给用户，停止受管修改/派发，包括继续修改共享文档。重复同一次 handoff 幂等。takeover 成功前，旧 owner 仍是记录中的离任 owner，不能在 TEAM.md 提前任命新 owner。提交/推送由项目策略决定，不是本地交接的前提。

准备成功后，给包含真实项目路径的可复制接手短句，简述保留成果。接任会话从 status 取得 handoff ID，不要求用户抄写运行时编号。不能把准备完成说成新持有者已经上任。

### 撤回尚未接收的交接

接任前用户改变计划，记录中的交出方 owner 可以明确撤回：

```bash
python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" handoff --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --epoch "$PLAYBOOK_EPOCH" --cancel
```

撤回使已准备编号失效，保留历史和检查点，回到 paused。按用户要求 resume 或重新准备交接。共享锁解决撤回／接任竞争；接任成功后，旧 owner 不能再撤回。不能借撤回冒充别人或丢弃快照后变化。

### 取消某次受管执行

暂停阻止新增工作，不停止已有员工。用户明确取消时，从 status 选择真实 attempt，以 active 或 paused 状态的当前 owner 记录原因并请求：

```bash
python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" cancel --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --epoch "$PLAYBOOK_EPOCH" --attempt "$PLAYBOOK_ATTEMPT" --reason "$PLAYBOOK_REASON"
```

对应监督进程看到请求后，只停止自己的进程组。记录请求不等于已经收到结束确认：核对后续结果后，才能报告进程已停或资源已释放。保留日志、文件、尝试次数，以及在取消竞争中先完成的真实结果。监督进程丢失／孤儿任务保持 unknown，须明确核对；不能猜 PID、按名称杀进程或凭时间释放预留。

## 接任：已准备交接或明确恢复

1. 读规则、配置、交接、看板和决定台账，运行只读 `status`、`doctor`，核查尝试记录、日志、分支、未提交成果。不能为了接任就自动起服务或重跑验收。
2. 使用接任会话自己的新 ID。已准备交接时，从权威状态或离任结果获取 ID，设为 `PLAYBOOK_HANDOFF`，运行：

   ```bash
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" takeover --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --client "$PLAYBOOK_CLIENT" --handoff "$PLAYBOOK_HANDOFF"
   ```

   运行时在共享锁内验证目标、机器、revision、基线和恢复内容，再增加 epoch 并更换 owner。基线变化必须显式呈现，核对后处理，不能绕过校验。同一 owner 重复成功认领幂等。
3. 没有已准备交接时，先确认用户明确要求替换，且前会话已经停止继续工作。核查孤儿和在途任务，保留已有成果，通过恢复路径建立/核对恢复检查点，再运行：

   ```bash
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" takeover --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --client "$PLAYBOOK_CLIENT" --recover --previous-stopped
   ```

   `--previous-stopped` 是这项声明的记录，不证明原始外部写入已被隔离。不能根据年龄、超时或猜测设置它。缺少必要指示或证据时保持只读，报告具体阻塞；不删锁或运行时状态。

   只有 configure 配置/状态双文件更新中断或损坏需要修复配置，且用户已经审定完整替代配置时，才使用显式恢复变体。把 `PLAYBOOK_CONFIG` 指向项目外这份审定 JSON，不手动覆盖原配置：

   ```bash
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" takeover --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --client "$PLAYBOOK_CLIENT" --recover --previous-stopped --config "$PLAYBOOK_CONFIG"
   ```

   运行时先私存原 config 和旧 state 作为证据，再修复并记录配置 revision，然后 checkpoint、接任。报告证据位置与 revision；即使已记录配置修复，检查点失败仍会阻塞接任。不带 `--config` 的恢复保持严格校验，普通已准备 takeover 不支持覆盖配置。prepared 校验失败不授权静默改策略或切换到此修复路径，明确恢复和用户审定配置的前提仍须满足。
4. 成功后保存新 epoch，按现场核对文档并记录已核实的能力差异。先收货再派新卡。前 epoch 迟到的结果仍是证据，不丢弃，也不自动验收。报告所有权、基线变化、任务未知项与下一项获准操作。

## 工作循环与策略执行

先审返回成果，再派新任务。选择依赖满足、文件范围明确、基线已知、验收针对外部行为的单卡；见[任务卡](cards.zh.md)、[派发](dispatch.zh.md)和[审查](review.zh.md)。总指挥可以实施合适的卡；按影响和项目策略选择独立审查。审查员工也占 agent 槽位。非 Git 项目串行并使用本地恢复快照，不因此获得 Git 操作。

用 `task` 记录核实后的事实，不能为了继续派发把旧任务抹掉：

```bash
python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" task --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --epoch "$PLAYBOOK_EPOCH" --id "$PLAYBOOK_TASK" --state blocked --note "$PLAYBOOK_NOTE"
```

状态包括 `reserved`、`running`、`reported`、`verified`、`integrated`、`blocked`、`unknown`。保留尝试、worktree、命令、日志和证据。runtime API 2 先登记 spec、检查 readiness、完成实现，再排程重型验证，取得适用证据后才标 verified。独立审查遵从项目／任务要求。integrated 走 begin／关联组合验证／finish，不能靠备注代替；精确命令见[结构化任务](work-protocol.zh.md)。旧 note-only 记录保持可区分。审查／整合方式、并发、重试、提交、合并、推送节奏和清理依配置。

短共享修改走 `guard`，长员工/审查/测试任务走 `run`，两者都验证 owner 和 epoch。可执行示例见[派发参考](dispatch.zh.md)。受权限策略控制且为 deny 或 ask 的操作不能执行；真实用户选择通过 configure 落盘，已授权日常操作不重复问。`scaffold` 对生命周期元数据校验 owner/epoch/active 状态，不另要权限，但不授权 Git 操作、实现或 setup hook。v3 的 `wt.sh new` 只在 guard 内创建，并把可执行 setup hook 报为待执行；guard 返回后按获准准备流程运行，hook 自身调用受管 `run` 时不再嵌套 `run`，否则走受管验证，核实准备完成再派正文。`PLAYBOOK_GUARDED=1` 只在受管子进程中设置，供协作适配器防递归；不能手动设它绕过检查。

首版只协调同一 POSIX 机器上的协作会话。OS 锁覆盖受管操作，不能约束任意编辑器/原始 shell 写入。不提供分布式仲裁、自动迁移、自动发布、客户端原生对话恢复或硬金额预算保证。模型/profile/思考设置没有已验证适配与证据时，不能称为已应用。

## 汇报与收工

报告改了什么、精确命令和真实结果、保留成果、跳过/阻塞步骤及缺口。记录基线、dirty、范围和证据位置，让后续会话能核查。在仍是 owner 时更新看板与交接，按需 checkpoint 或 pause。保留 worktree、未推提交可以是正常策略结果。清理必须保护 dirty、未合并、运行中、未知和承载证据的成果。

未配置的 v2 shell 操作仍可用，但不享有 v3 所有权、检查点和受管限额保证。只有显式采用后才能宣称 v3 保护，不静默迁移旧项目。
