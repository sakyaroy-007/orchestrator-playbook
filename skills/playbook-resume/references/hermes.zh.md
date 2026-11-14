# Hermes 适配

Hermes 无须安装五个总指挥入口，就能作为员工交付任务；原生命令插件是另一项集成。本适配依据 Hermes 0.23.1（`3b421578588243f920886e6fe79a6faa87ea026e`）的公开 gateway 协议实现，真实模型执行和前端插件加载须另行验证。

## 受管员工配置

通过正常项目配置流程选择员工，例如：

```json
{
  "id": "hermes-worker",
  "client": "hermes",
  "model": {"mode": "inherit"},
  "effort": {"mode": "inherit"},
  "hermes": {"approval": "inherit"},
  "args": []
}
```

可选 `profile` 通过 `hermes --profile NAME gateway attach --json` 选择已有 profile；省略时由 Hermes 解析自身当前／默认 profile。桥接器不修改 profile 配置、不安装依赖、不启动或重启 gateway，也不传 `--start`、`--recover`、`-z`、`yolo` 或 `unattended`。所选 profile 必须已有就绪的 gateway。Hermes 原生启动器可能执行自身引导维护，因此不能把 attach 描述为绝无副作用的发现探针。

`model.mode:fixed` 映射为 `session.create.model`，`effort.mode:fixed` 映射为原生 `reasoning` 值。桥接器检查实际 owner 声明的能力和创建参数，要求客户端与 owner 代码 SHA 一致，并在提交任务前核对 session 的 profile、工作目录和所选参数回显。回显只能证明配置选择，不证明供应商可用或模型实际思考行为。不支持的值会失败，不编造跨供应商档位换算。`recommend` 必须先落实。受管 Hermes 的 `args` 必须为空，不能通过 CLI 透传悄悄改变此协议。

旧员工记录仍可读取，摘要不因读取改变。派工前必须明确选择 `hermes.approval`，不会把旧 `-z` 的选择直接解释为新通道的授权。旧 Playbook 运行时会拒绝这个新增员工字段。应有意更新整套匹配的运行时资源，保留项目已有副本与本地修改。

| 审批响应策略 | 行为 |
| --- | --- |
| `inherit` | 保留 profile 行为；不代答原生审批请求，回执通过 `waiting_approval` 暴露待处理状态，由用户在 Hermes 中解决。等待仍受任务超时限制。 |
| `approve` | 仅对实际发出的原生审批请求回答 `once`，不持久保存 `always` 或会话级批准。 |
| `deny` | 对实际发出的原生审批请求回答 `deny`。 |

这些策略只控制 **Hermes 实际发出的请求**，不会覆盖 profile 的 `approvals.mode:off`、既有原生授权、硬性拒绝或子任务策略。`deny` 不是沙箱，也不保证一切工具动作均被禁止。需要更强限制时应配置 Hermes 本身；本包不授予或放宽宿主权限。项目 `permissions.dispatch` 仍须独立满足。

## 身份、结束与取消

运行时先保留 attempt，再在启动桥接器前写入 `logs/ATTEMPT.hermes.json`。桥接器提交任务前持久化唯一创建／提交 ID，随后保存 session/stored-session ID、admission ID、owner instance/profile/code SHA、authority epoch 和 generation。连接票据只保留在内存。`status`／`doctor` 展示 `external_receipt` 及其当前 `external_execution`；普通 attempt 日志保存最终回答和错误。明确传入的 `-l` 日志是另外创建且拒绝覆盖的副本。

每个 attempt 使用全新独占 session。正常完成须有准确 admission 的终态回执、保存的结果，以及可用的实时资源投影：没有列出的子任务，也没有仍在运行的登记进程。派工成功仍只进入 `reported`，验收继续走原有验证／证据流程。回执明确范围为 `admission-and-live-session-resources`，并标记 `entire_task_tree_proven:false`。这不证明任意未登记外部任务、副作用或所有可能的后代均已结束。

`playbook cancel --attempt ...` 仍是向活跃 supervisor 提出请求。Hermes 桥接器向准确 admission 发送 `prompt.cancel`，向本次独占 session 发送 `process.stop`，再轮询回执和资源。到达超时或取消请求后，supervisor 最多另外等待 30 秒清理，不杀 gateway。取消 ACK 不等于完成；观察到委派中断却没有 join 证明、资源投影不可用、结果未知或清理失败时，attempt 保留 `unknown`，继续占用并发、工作树和资源。杀掉本地桥接器不能补出缺失的结束回执。

允许一次有界重连，连接同一 owner，恢复已保存 session 并查询原 admission。如果提交 ACK 丢失，只允许通过精确匹配 `pending.input_id == submission_id` 恢复身份，不重新发送任务正文。owner／authority 变化或身份无法恢复仍为未知；不自动调用 `prompt.resolve_unknown`，不自动重试或释放占用。supervisor 丢失时，依据保存的 ID 在 Hermes 中核实，再由当前 Playbook 持有者显式对账；不能用时间过去或 viewer PID 消失推断完成。

未配置项目的旧 `dispatch.sh hermes` 保留既有 `-z` 员工路径及其原生自动审批；其超时文案改为 gateway 任务状态未知。该路径没有 admission 台账或受管取消保证。更新包不会改写项目已有副本或自定义 team 脚本。

## 五个原生总指挥命令

使用 `scripts/build-hermes-plugin.py --output /physical/staging/orchestrator-playbook` 构建插件，完整宿主契约见源码仓库 `adapters/hermes/README.md`。不要把普通五技能目录直接链接到 Hermes：0.23.1 不执行其调用策略字段。

插件只注册同名五个命令，复用规范中英正文与运行时，不含可被普通扫描发现的 `SKILL.md`，不注册模型工具或自动 hook。当前原生命令上下文缺少可验证的真人来源标记，因此每次调用必须先在当前会话选择界面选中 **Load**，才注入指令。取消、缺少交互界面、会话／目录不匹配或注入被拒绝均不加载。它信任宿主绑定的交互界面，不隔离任意同用户代码。

gateway/TUI 注入要求已有操作方设置 `plugins.entries.orchestrator-playbook.allow_gateway_injection: true`；插件不自行开启。构建、文件安装、插件启用、命令发现、消息排队和实际模型执行分别报告。假上下文和本地假网关的离线测试仅证明相应契约，原生安装／激活与真实付费试点须在各自获准范围内另行验证。
