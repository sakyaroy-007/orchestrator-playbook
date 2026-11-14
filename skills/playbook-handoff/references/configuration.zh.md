# 项目配置

路径定位、身份和所有权见[生命周期参考](lifecycle.zh.md)。`.orchestrator/config.json` 是可移植策略，不放凭据或私人宿主配置。运行时状态、机器/会话身份、epoch、配置 revision、进程记录和本地恢复副本放在共享 Git common directory；非 Git 放 `.orchestrator/local/`，并设本地忽略规则。关联 worktree 共用一套运行时。TEAM.md 用来解释策略，不能覆盖它。

## 先发现、澄清目标，再补齐设置

推荐员工或询问设置前，先运行只读 `discover`，阅读现有规则、配置、计划和对话决定。单独调用 `playbook-start` 不要求用户准备项目说明。目标缺失或模糊时，先澄清，再给完整开局推荐：

- 空项目先了解给谁用、解决什么问题或希望得到什么结果。每轮问一至三个影响决定的关键问题；必要时给具体例子或推荐选项，帮助用户选择，不能为填满摘要而编造目标。
- 只沿着会改变首个里程碑的缺项追问：必须完成的行为、约束、不做事项、怎样判断成功。技术选择由 agent 根据证据推荐，不要求用户先设计架构或提供测试命令。
- 目标明确时只补真实缺口。旧项目先读已有计划与进度，再解决冲突、过时决定和下一阶段目标，不重新做一轮完整产品访谈。
- 商定有用结果、明确范围、不做事项和可观察的验收方式后停止深入，把摘要写入配置指定的计划和首卡；不阻塞当前工作的选择保留为后续问题。可行性未知时，商定有边界的探索任务及预期证据，不强求完整规格。

随后给出具体推荐，包含实际目标目录、目标、复用文件、minimal／standard 基座规模、员工设置、限额和操作权限，区分已确定值与建议值。用户接受摘要中的明确选择后直接落实，已经接受的事项不再确认。以下四组是缺失设置的分类，不是必走的四轮问卷，也不能为满足次数限制而编造答案；start 已经完成的任命不再问。

1. **结果与边界。** 确认可验收的阶段目标、范围、不做事项和验收方式。根据项目现状推荐最小有用里程碑。已有项目确认复用哪份计划/路径、用户是否要求采用旧状态；保留现有文件。
2. **允许员工与本地工作。** 推荐只用明确选定且可用的客户端或人工执行。在同一组“本地开发/测试/派工”选择中确认 dispatch、本地验证（`permissions.verify`）、创建 worktree（`permissions.worktree-create`），分别落盘一次，不等到每条命令再问；未授权时都缺省 `ask`。起步建议至多两个 agent 任务、一个重型验证任务，按实际资源与审查能力调整；非 Git 串行。确认超时/重试限制及费用边界。这里控制任务/尝试数量，不是硬金额预算。花名册不证明获准或已登录。
3. **模型、思考与 profile。** 推荐逐员工 `inherit`，继承**员工自己的**模型和思考，不跟随总指挥；客户端存在默认 profile 时保留它。DSH 必须显式填写 profile：收集已有非交互 profile 名称，或明确推荐 `headless` 供用户选择，不能悄悄选定。模型/思考可继承该选定 profile。可选 `recommend` 在派发前解决建议，或 `fixed` 选受支持的值。沿用已定设置，说明不支持的映射，不能因客户端同名就复制其他员工 profile。
4. **Git 与保留。** 分别确认 commit、merge、push、cleanup 权限，集成分支、合并方式、推送节奏和保留策略。推荐获准的日常本地提交/合并、手动推送，验证和证据检查通过前保留 worktree；没有授权的动作保留 `ask`（或已有 `deny`）。存在 Git 仓库不构成全权授权。非 Git 推荐串行本地快照，不做 Git 操作。

用户明确接受具体推荐，就解决该选择，记一次后继续。已有授权在其范围内跨卡、跨会话持续有效。未定项保持 `ask`，禁止项保持 `deny`；沉默不是 `allow`。显式生命周期调用所需的流程元数据不重复问权限。允许 push 不等于允许发布或部署。

## Version 1 配置

把商定的完整对象写进临时草案文件，令 `PLAYBOOK_CONFIG` 指向它，再交给 `init` 或 `configure`。以下是有效的保守基线，**不表示用户已经批准这些选择**。目标/分支/路径应替换成实际商定值；运行时可以补齐缺省项。

```json
{
  "schema_version": 1,
  "goal": "交付商定且可验收的首个里程碑",
  "workers": [],
  "limits": {"agents": 2, "heavy_jobs": 1, "timeout_seconds": 7200, "max_attempts": 2},
  "permissions": {"dispatch": "ask", "verify": "ask", "worktree-create": "ask", "commit": "ask", "merge": "ask", "push": "ask", "cleanup": "ask"},
  "git": {"integration_branch": "main", "merge_method": "merge", "push_cadence": "manual", "cleanup_mode": "retain"},
  "review": {"level": "adaptive"},
  "paths": {"plan": "docs/plan/README.md", "worker": "docs/plan/WORKER.md", "cards": "docs/plan/tasks", "handoff": "HANDOFF.md"}
}
```

配置路径用项目相对路径。支持的枚举和边界遵从安装版本运行时的校验；被拒绝的设置没有生效。不能悄悄删掉用户要求来消除校验失败。只调整一项时保留原有其他策略和自定义路径。

可选策略标识 `runtime_api: 2` 启用扩展协作协议。新初始化记录它；已有项目通过当前 owner 的明确配置更新启用，例如 patch `{"runtime_api": 2}`。读取旧策略不会凭空插入字段或改变已保存摘要。启用后，完整替换／恢复也不能静默移除该要求。旧运行时拒绝这个未知字段，暴露不兼容，而不是忽略新约束继续执行。schema 版本与 runtime API 是不同概念。先查看 `version`／`doctor`，保留不同的项目副本；启用协议不等于自动升级脚本。

可选审查布尔项 `allow_manual` 与 `independent` 未提供时均视为 false。`allow_manual:true` 允许明确标为人工的验收材料，不把备注等同于成功测试。`independent:true` 要求协作声明中的审查者区别于已记录的实现参与者；任务可加强独立审查，不能削弱项目策略。这些声明不构成密码学身份认证。旧策略缺少可选字段时保留原摘要。回执与集成适用性见[结构化任务与验收](work-protocol.zh.md)。

员工记录有唯一 `id`，`client` 取 `claude`、`codex`、`dsh`、`hermes`、`manual`，model/effort 对象例如 `{"mode":"inherit"}`。`fixed` 或 `recommend` 另带已选/建议的 `value`。可选 `profile` 和单次 `args`（字符串数组）必须使用已安装适配器验证过的选项。适配器实际消费 args/profile/model/effort；未知映射阻塞启动，不能丢弃。同一客户端可以有多个不同身份的记录，不放凭据、认证导出或私人机器设置。

```json
{
  "id": "implementation",
  "client": "codex",
  "model": {"mode": "inherit"},
  "effort": {"mode": "inherit"},
  "args": []
}
```

| 模式 | 含义 | 启动前 |
|---|---|---|
| `inherit` | 保留该员工自己的默认配置 | 不复制总指挥模型，不编造覆盖值 |
| `recommend` | 模型/思考值的建议 | 在已有用户授权内解决建议；此时尚未应用 |
| `fixed` | 明确支持的单次调用值 | 核实适配器映射，不支持的值阻塞启动 |

模型和思考模式彼此独立。`profile` 为字符串：有自身默认值的客户端可以不填，但受管 DSH 必须填写，因为其启动器没有默认 profile。DSH 缺 profile 会在任何模型调用前阻塞启动。模型/思考/profile 使用专用字段，不用冲突的 `args` 覆盖。示例员工记录不代表获准启动。不能凭空认定各供应商思考档位等价，不能把建议自动翻译成参数，也不能改全局文件凑出可启动状态。

当前校验派发器把固定模型交给现有 `-m` 适配。在检查已安装客户端 help 后，支持 Claude `--effort`、Codex `--config model_reasoning_effort=...`、DSH 单次 `agent-default-model.reasoningEffort` patch。Hermes 使用专用 gateway 桥接器：固定模型／思考映射到 session 的 model／reasoning，可选 profile 选择 attach 目标，提交前核对会话设置。其员工记录必须明确提供 `hermes.approval` 策略，`args` 为空，审批和取消边界见 [Hermes](hermes.zh.md)。显式 profile 支持 Codex、DSH 和 Hermes，拒绝 Claude profile 覆盖。这些只是参数映射，不证明已登录、模型可用或实际推理行为。不支持的选项和未解决的 `recommend` 阻塞启动。DSH profile 必须明确选择，继承只保留选定 profile 的模型/思考，不自动选择旧版 `headless`。

Git 支持的值：合并方式 `merge|squash|rebase|ff-only`，节奏 `manual|after-merge|stage|never`，清理 `retain|after-merge|manual`。当前受管 push 路径拒绝 `manual` 和 `never`；推送前通过 configure 设置获准的 `stage` 或 `after-merge` 节奏。即使 cleanup 为 allow，`retain` 仍阻止清理。

## CLI 发现、实际能力与登录分开记录

- **发现**只列项目/Git 事实和已知可执行文件，不调用 LLM，不读取秘密、不安装软件、不测登录、不改全局配置。
- **能力证据**来自已安装客户端的文档/help 和验证过的适配器。记录版本、查看过的选项和支持的映射。help 可读不证明真实请求一定成功。
- **登录/就绪**需要适合该客户端的获准检查，或获准运行的实际证据。未知就写未知；不能为把发现结果写成完整而读取密钥值或发起付费任务。
- **实际执行**记录真实命令、员工 ID、cwd、可见的模型/思考、日志和退出状态。客户端不报告某项时，有效值写未核实。PATH 上有可执行文件或 TEAM.md 写了推荐，都不是实际运行证据。

## 应用并核实

初始化按[生命周期参考](lifecycle.zh.md)的 start 流程。用户要求“只改这一项，其他照旧”时，把商定变更写入项目外临时 JSON patch，例如 `{"limits":{"agents":3}}`，以当前 owner 运行：

```bash
python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" configure --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --epoch "$PLAYBOOK_EPOCH" --patch "$PLAYBOOK_CONFIG"
python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" status --project "$PLAYBOOK_PROJECT"
```

patch 在锁内合并到当前权威策略；未提供字段保持，数组只有明确提供时整体替换。非法字段和值会拒绝更新。根据返回的变化字段和 revision 汇报，而不只展示提议。确实要完整替换策略时使用与 patch 互斥的 `--config FILE`；省略的普通字段仍按原接口补默认值。不能把局部对象交给完整替换来完成“其他照旧”。

运行时校验策略后分别原子替换文件，保留所有权/任务并记录配置 revision。config 和运行时 state 是两个文件，中断可能留下不一致，不能把两者称为一个原子事务。根据成功输出报告落盘 revision 和生效选择，另列待定建议和不支持项。写了草案不代表配置已应用，新会话不能把 configure 当 takeover，不能用未协调编辑使已准备的交接失效。

configure 双文件更新中断或损坏时，按[生命周期](lifecycle.zh.md)的显式恢复流程处理。用户指示停止/替换且审定完整配置后，新会话才可使用 `takeover --recover --previous-stopped --config FILE`。运行时先私存原 config 和旧 state 作为证据，再记录修复配置 revision，然后 checkpoint、接任。保留证据，检查点失败就报告接任阻塞，即使配置修复已记录。不带 `--config` 仍严格校验，普通已准备 takeover 不允许覆盖配置；prepared 校验失败不是静默修复策略的许可。

## 权限与成果保护

- `allow` 在商定范围和当前策略内允许操作，`ask` 表示尚有真实未定选择，`deny` 禁止操作。已获准的日常动作不反复问，也不能换原始 shell 绕过禁止项。
- `guard` 在共享 OS 锁内完成短操作的 owner/策略检查和修改。其中 `scaffold` 校验生命周期元数据的 owner/epoch/active 状态；显式 start 元数据不另要权限，也不新增 config 权限字段。已配置 `init-plan.sh` 写入走它，`--dry-run` 仍只读。`run` 在启动前预留唯一尝试和资源槽位，见[派发参考](dispatch.zh.md)。它们保护单机协作操作，不能控制任意工具或伪造环境变量。
- 员工/审查任务受 `limits.agents` 限制，验证任务受 `limits.heavy_jobs` 限制。中断留下的 reserved/unknown 仍然可见，核查后才能发起新尝试。遵守超时与 `max_attempts`；次数按任务和 action 分别计算，使 dispatch 与后续 verify 保持各自尝试预算，不能换任务 ID 绕过限额。
- 权限为 `allow` 时，合并方式、推送节奏和清理保留仍有效。清理还要证明已整合，并核查 dirty、未跟踪、ignored、运行中、未知和承载证据的成果。旧 force 参数不能绕过 v3；工具无法证明 squash 已整合时保留分支供核对。
- 非 Git 项目用串行操作和本地快照，不附带创建分支、提交或远端。
- 不含自动安装客户端、配置宿主、升级、发布或部署。用户要求但不支持的设置阻塞启动，不能静默忽略。
