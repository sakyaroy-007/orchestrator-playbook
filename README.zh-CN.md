# Orchestrator Playbook（总指挥打法）

<img src="assets/icon.png" width="96" align="right" alt="Orchestrator Playbook icon">

[English](README.md) | **简体中文**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**一包五个显式技能入口，用于启动、继续和交接软件项目。**

v3 在任务卡与 worktree 流程上增加项目配置、会话归属、检查点和受管执行。总指挥计划、审查，执行者提交证据；验收与集成仍是独立决定。本源码仓库是技能包，不要为它初始化一套项目控制面。

| 入口 | 用途 |
|---|---|
| `playbook` | 选择操作；查看状态、诊断、配置或暂停项目 |
| `playbook-start` | 回答初始问题，启动新项目或接入已有项目 |
| `playbook-resume` | 由当前持有者会话继续已记录的工作 |
| `playbook-handoff` | 创建恢复检查点并准备正常交接 |
| `playbook-takeover` | 显式接收已准备的交接，或执行得到授权的中断恢复 |

五个入口都设置 `disable-model-invocation: true` 与 `allow_implicit_invocation: false`。每个生成目录都包含完整的运行时、参考资料和模板，单独安装一个也不依赖兄弟目录。技能选择方式、命令前缀和插件命名空间取决于客户端；上述名称**不代表各客户端的 slash 语法完全一致**。

## 首次使用

1. 从下面的安装策略中选**一种**，然后在客户端里打开目标项目目录。
2. 显式选择 **playbook-start** 即可，无须准备提示词。目标尚不明确时，agent 每轮问少量关键问题，推荐首个里程碑，在范围和验收明确后停止追问。已有目标也可以直接说，例如：“实现 CSV 导入，并覆盖格式错误行的测试。”**从未接入 v3 的旧项目**同样只需说：“用 playbook-start 接入当前项目。”它先读取并保留已有计划和工作；原先采用旧版 Playbook 打法的项目也走这条接入路径。
3. 核对一份具体推荐：实际项目路径、首个目标、复用文件、员工设置、并发／超时、权限和 minimal／standard 基座规模。接受其中的明确选择后，技能只询问缺失决定，不重复问卷。员工默认继承各自客户端的配置。
4. 没有持有者冲突时，start 记录策略和新的会话身份。基座助手先预览，再只创建缺失文件，包括根 README、配置指定的计划／员工／交接文件、首卡草稿和必要运行时副本。已有文档与不同版本的脚本保留；支持 Git、非 Git 和自定义规划路径。standard 另加可选规划资料。
5. agent 根据真实项目情况补全首卡，登记要求、内容路径、依赖与独占资源，检查 readiness 后才派发。生成草稿或尚不明确的测试命令不代表任务已就绪。

单独调用 **playbook** 会显示实际项目、本会话角色、阻塞、一个推荐和至多三个备选，保持只读。说“检查项目基座”可预览缺失文件；说“补齐缺失基座”才执行获准的只创建操作。选择框取决于宿主能力，不支持时用编号文本，并不承诺统一 GUI。详见[开局参考](references/bootstrap.zh.md)。

完成 v3 初始化不需要手动填一整套模板占位符。技能把已定选择转成具体配置与规划内容，已有文档仍作为起点。命令发现不证明已登录、已授权或支持所请求的参数。

已有 `.orchestrator` 目录需要用户明确选择接入。已有持有者时应通过 resume 或 takeover 处理冲突，即使两个会话使用同一客户端或模型。会话 ID 标识具体会话，不是产品名称；开启新对话不会悄悄继承旧对话的角色。

## 安装

选择插件安装、共享技能根目录或单客户端技能根目录。避免几种方式重复安装同一批入口，否则客户端可能发现重复项。下面是用户自行操作的安装步骤；构建和测试本仓库不会安装到全局目录，也不会连接模型服务。

### Claude Code 插件

适用于已经发布、包含 v3 的版本：

```text
/plugin marketplace add sakyaroy-007/orchestrator-playbook
/plugin install orchestrator-playbook@orchestrator-playbook
```

插件清单指向 `skills/` 下五个目录。本地清单检查使用 `claude plugin validate .`；清单验证不等于实际技能发现或执行者运行测试。已发布版本见 [Releases](https://github.com/sakyaroy-007/orchestrator-playbook/releases)。

### Codex 与其他客户端

仓库包含 `.codex-plugin/plugin.json` 与 `.agents/plugins/marketplace.json`。客户端支持插件时，使用该版本提供的安装流程。已通过本机 Codex `skills/list` 协议和 DSH 原生文件系统 provider 验证独立目录发现，未调用模型；尚未实测这两端的插件安装流程或活动对话加载，安装界面与调用语法可能不同。通用市场目录指向整个包，再由包的插件清单选择 `skills/`。

支持独立技能目录的客户端，可安装五个生成目录。如果目标客户端确实扫描 `~/.agents/skills`，可以使用这个共享根目录；仅供 Claude 使用时选 `~/.claude/skills`。其他单客户端根目录需要查阅对应客户端文档。模型凭据与私有客户端配置不放进本包。

在已审阅、包含生成产物的检出目录中，下面示例安装到共享根目录，并拒绝任何已存在的目标，包括悬空符号链接：

```bash
python3 -I scripts/build-skills.py --check || exit 1
skill_root="${HOME}/.agents/skills"
for name in playbook playbook-start playbook-resume playbook-handoff playbook-takeover; do
  if [ -e "$skill_root/$name" ] || [ -L "$skill_root/$name" ]; then
    printf 'Already exists; review before replacing: %s\n' "$skill_root/$name" >&2
    exit 1
  fi
done
mkdir -p "$skill_root"
for name in playbook playbook-start playbook-resume playbook-handoff playbook-takeover; do
  cp -R "skills/$name" "$skill_root/$name" || exit 1
done
```

技能安装器列出多个入口时，选择这五个。根目录 `SKILL.md` 是保留的 `orchestrator-playbook` 兼容入口；把整个仓库当作一个旧式技能安装，不等于装好了五个新入口。升级需明确操作：审阅新版本和本地改动，再替换选定的安装。本包没有自动升级器。

### Hermes 原生命令

Hermes 当员工不需要安装这些总指挥技能。在 Hermes 内担任总指挥时，使用 `python3 -I scripts/build-hermes-plugin.py --output /physical/staging/orchestrator-playbook` 构建专用原生插件。它复用五个规范入口，不把普通 `SKILL.md` 暴露给模型技能发现；每次命令须在当前会话选择 **Load**，gateway／TUI 注入还需要操作方审核宿主权限。详见[适配指南](adapters/hermes/README.md)与[员工配置](references/hermes.zh.md)。构建不安装、不启用、不授予权限。本开发版本有离线契约测试，真实插件／前端和付费模型执行仍待验证。

## 继续与交接

- **继续：** 在持有者会话显式选择 `playbook-resume`，读取记录中的任务与现场差异。恢复对话不会自动重复派发或测试。
- **暂停：** 通过 `playbook` 暂停，先持久化停止新增工作，再创建检查点；即使快照失败也保持暂停，并单列恢复不完整的事实。保留员工与成果。
- **交接：** 旧会话调用 `playbook-handoff`，保存当前工作与任务记录，准备交接，并停止旧持有者的受管修改。返回带实际项目路径的可复制接任短句；新 agent 自行读取交接 ID。检查点不会提交或推送源文件。
- **撤回／取消：** 让 `playbook` 撤回尚未接收的交接，旧 ID 失效并回到 paused；也可取消指定 attempt。取消请求由 live supervisor 执行，实际结束确认前保留资源占用；孤儿执行仍标 unknown。
- **接手：** 指定的新会话显式调用 `playbook-takeover`。有效的已准备交接加上这次调用足以授权认领，不再重复问同一个确认。只有状态、机器、基线与恢复内容检查通过，才变更归属。
- **持有者意外中断：** 先查看状态和诊断。恢复需要用户要求停止或替换旧会话，并使用明确的恢复参数。等待时间不是授权证据；运行中或状态未知的尝试必须先核实，再决定是否重试。

项目策略保存在 `.orchestrator/config.json`。本地归属、执行尝试与恢复副本保存在**共享 Git common directory**，所有关联 worktree 共用一个持有者和锁。非 Git 项目使用 `.orchestrator/local/`、串行工作和本地恢复快照，不获得 worktree、提交、合并或推送能力。本地恢复数据不属于正常 Git 发布内容，可能包含未提交工作的副本。

检查点不收录 Git 忽略的未跟踪文件，交接前需明确归档其中必要的证据。当前上限为单文件 64 MiB、总计 256 MiB、10,000 个文件。未合并索引、dirty submodule、特殊文件，以及超量、不可读或变化中的内容都会阻止完整检查点；已取得的部分恢复数据会保留，不会把它报成交接成功。

## 配置与授权

配置覆盖执行者、继承／固定／建议的模型与 effort、agent 和重任务并发、超时、尝试次数、Git 偏好、审查级别与计划路径。CLI 和状态流转详见[配置说明](references/configuration.zh.md)与[生命周期说明](references/lifecycle.zh.md)。

权限值是 `allow`、`ask` 或 `deny`，缺少授权不等于允许。用户明确回答可以一次性授权常规本地工作，不必每张卡重复确认。`ask` 和 `deny` 不执行被守卫的动作。允许推送不等于允许部署或发布；允许清理也仍须检查脏工作、未合并修改、运行中的执行者和需保留的证据。

`inherit` 使用每个执行者自己的默认配置；`fixed` 必须有已验证的客户端能力映射；`recommend` 在选择落实前只是提议。适配器支持明确选择模型，并在检查 CLI help 后传入 Claude effort、Codex reasoning effort 或 DSH reasoning-effort 临时覆盖。profile 覆盖支持 Codex 和 DSH；DSH 必须明确选择一个非交互 profile，模型与思考仍可继承该 profile 的设置。Hermes 通过公开 gateway 协议选择模型／思考／profile，明确配置审批响应策略并持久跟踪 admission，完成与取消的限制见 [Hermes 参考](references/hermes.zh.md)。Claude profile 覆盖仍不支持。参数映射与传参测试不证明已登录、模型可用或实际思考行为。项目配置里不存凭据。

局部变更使用 `configure --patch FILE`，例如 `{"limits":{"agents":3}}`，保留未给出的设置；`--config FILE` 仍用于有意完整替换。schema 1 旧项目仍可读取，明确启用 `runtime_api:2` 后使用扩展协议，不静默改变旧策略摘要。旧运行时会拒绝该标记，避免忽略新约束。

## 任务、证据与集成

派发前登记 task spec 并检查 readiness。依赖区分固定的上游契约与已出现在消费者实际基线中的集成结果；显式独占资源在整个项目跨工作树共用。总指挥选择就绪任务，不代表自动调度或重试。

员工负责实现与获准的轻量检查；dispatch 结束后，总指挥通过受管验证排程重型测试和独立审查。不可覆盖回执把要求、依赖、相关字节／模式及材料绑定到实际验证 attempt，后续变化会使旧证据不再适用。派发成功仍只标 reported。人工证据须由审查策略明确允许，并保持人工标记。

集成记录把已验收参与任务与实际目标、明确关联的组合验证绑定。合并成功不代表整体通过。可选的集成分支推送门槛检查当前已验收结果，同时保留原权限与节奏要求。声明参与关系和源提交祖先关系不能证明语义完整纳入，这一限制保持可见。完整命令见[任务／证据／集成参考](references/work-protocol.zh.md)。

## 运行时诊断

无需初始化项目即可运行 `python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" version`，查看实际执行路径、包／runtime API／schema 版本、能力与必要文件摘要。已初始化项目使用 `doctor --project "$PLAYBOOK_PROJECT"` 比较当前包、项目副本与 `.orchestrator/runtime-manifest.json`。缺失、不同或来源未知都明确呈现，诊断不覆盖或升级文件。当前源码返回 `3.1.0-dev.1` 和 `release_status:development-unreleased`，与已发布的 3.0.0 正式版分别记录；应同时比较摘要与版本字符串，识别本地修改。

## 合作边界

首版协调的是**同一台 POSIX 机器上遵守协议的会话**。受管操作在 OS 锁下检查会话身份和 epoch；短时受守卫修改在子命令执行期间持有同一把锁。受管派发先登记执行尝试与资源槽，再启动进程。进程成功只代表已返回结果，不自动成为已验收或已集成。

协议无法拦截客户端任意 shell/edit 工具、原始 Git 命令、无关进程或不遵守流程的客户端。`PLAYBOOK_GUARDED` 仅避免适配器递归，不是安全隔离边界。受版本控制的 `TEAM.md`、进程退出码或过旧时间戳，都不能证明归属或安全接管。

本版未提供多机自动接管、客户端原生对话恢复、自动升级、硬费用限制、自动发布，也未验证所有客户端的模型／effort 参数映射。并发和超时是执行控制，不是硬花费上限。运行时测试使用临时项目和假执行者命令；原生客户端加载和付费任务执行需要另行验证。

## 旧版兼容

根目录 `SKILL.md` / `SKILL.zh.md`、`agents/openai.yaml` 以及原有 `scripts/init-plan.sh`、`scripts/wt.sh`、`scripts/dispatch.sh` 路径保留。未配置的项目仍可使用 v2 手工铺模板、填占位符的流程。这种 legacy 用法**不会**产生 v3 归属、策略、执行尝试记录或受管操作保证。先通过 `playbook-start` 接入，再将项目视为 v3 managed。

## 开发与打包

运行时需要 Python **3.9+** 标准库和支持文件锁的 POSIX 平台；Git 项目需要 Git。shell 适配器还使用 Bash（兼容 macOS Bash 3.2）、Git、Perl 或 `timeout` 及标准 Unix 工具。只有实际派发才需要对应客户端，测试不调用真实客户端。

| 路径 | 用途 |
|---|---|
| `skill-src/<name>.md` / `.zh.md` | 英文与中文入口源文件，不直接作为技能发现 |
| `skills/<name>/` | 生成的独立安装入口及完整运行资源 |
| `scripts/playbook.py`、`scripts/playbook_work.py` | 策略、生命周期、执行、任务／证据／集成协议与诊断 |
| `scripts/playbook-foundation.py` | 基座只读检查与受管的只创建初始化／补齐 |
| `scripts/policy-dispatch.py` | 受管派发前应用已批准的执行者配置 |
| `scripts/build-skills.py`、`scripts/check-manifests.py` | 确定性生成、漂移与本地清单检查 |
| `references/`、`templates/` | 参考资料与计划模板的源文件 |
| `tests/`、`scripts/selftest.sh`、`.github/workflows/ci.yml` | 离线回归与 CI |
| `AGENTS.md`、`docs/v3-implementation.md`、`docs/v3-next-implementation.md` | 维护约定与实现合同 |

```bash
python3 -I scripts/build-skills.py
python3 -I scripts/build-skills.py --check
python3 -I scripts/check-manifests.py
python3 -I -m unittest discover -s tests
bash scripts/selftest.sh
claude plugin validate .
```

CI 在 push、pull request 和手动触发时以仓库只读权限运行，矩阵为 Ubuntu 24.04／macOS 15 Intel × Python 3.9／3.13；另用固定 Claude Code 2.1.323 检查原生插件清单，不请求模型。指定提交的远端结果见 [Actions 记录](https://github.com/sakyaroy-007/orchestrator-playbook/actions)。[发布验证](docs/v3-release-validation.md)记录最终包的检查；[开发阶段报告](docs/v3-next-validation.md)保留较早的本地检查与安装边界；[试点规程](docs/v3-pilot.md)包含离线覆盖和另行限定范围的真实客户端方案。

`--output` 指定独立技能根目录，可暂存而不改动 `skills/`。目标应使用没有符号链接祖先的物理路径；系统临时目录是别名时，可通过 `pwd -P` 取得物理路径。生成器只复制明确列入允许清单的运行脚本，以及 `references/` 和 `templates/` 中的 Markdown 资源，不复制整个仓库、`.git`、生成器或测试。

每个生成技能都有 `.playbook-generated.json`，记录受管文件、摘要与权限。构建预先检查全部五个目标，拒绝无标记技能目录、符号链接、路径冲突和被本地改写的生成文件，保留其他文件与兄弟目录。过期生成文件只有仍符合已记录的摘要和权限才会删除。请修改源文件，再重新生成；不要直接编辑生成副本。`--check` 不写入，发现漂移或不安全输入时以非零退出。写入按文件原子替换，整个构建不是跨文件事务，中断后应检查现场再重跑。

MIT，见 [LICENSE](LICENSE)。
