# 结构化任务与验收（runtime API 2）

协议启用见[配置](configuration.zh.md)，获准命令的派发方式见[派发](dispatch.zh.md)。本协议核对协作声明、内容和证据，不授予模型调用、Git 操作或资源访问权限。下面路径均应根据本次加载的技能和用户项目解析。

## 登记任务并检查就绪

把完整 spec 写入 `PLAYBOOK_SPEC`。paths 指定相对任务工作树根目录的相关内容，即使命令在子目录执行也是如此。requirements 和 acceptance 是非空字符串数组，paths 也不能为空；选择有意义的范围，避免收集无关文件。

```json
{
  "requirements": ["为每条记录返回稳定标识"],
  "acceptance": ["离线测试覆盖重复标识"],
  "paths": ["src", "tests"],
  "dependencies": [],
  "resources": ["fixture-database"],
  "review": {"independent": false}
}
```

```bash
python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" task --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --epoch "$PLAYBOOK_EPOCH" --id "$PLAYBOOK_TASK" --spec "$PLAYBOOK_SPEC" --worktree "$PLAYBOOK_WORKTREE"
python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" readiness --project "$PLAYBOOK_PROJECT" --task "$PLAYBOOK_TASK"
```

新 spec 默认 reserved；应有意安排登记和预留，因为 reserved 任务持有的显式资源会阻塞其他卡。readiness 返回 `ready`、`blockers`、依赖绑定、spec 摘要／revision、建议性内容冲突和派发状态就绪信息，不自动启动。run 在预留锁内重新检查。修改要求保留 spec 历史，移除旧的当前验收／集成指针。不能修改执行中的任务，假装旧员工已收到新要求。

依赖形如 `{"task":"upstream-id","kind":"contract"}` 或 `{"task":"upstream-id","kind":"integrated"}`。contract 固定上游 spec revision／摘要，不声称上游实现已经存在或代码已独立验收。integrated 还要求完整的历史已验收集成结果出现在消费者实际起点。上游目标可以正常前进；当前发布适用性仍要求目标 HEAD／分支／内容完全匹配。已验收集成记录保留当时的依赖 ID，不随之后的任务指针改写。已提交结果要求验收提交位于消费者祖先链中，允许其上的下游修改；未提交结果还要求消费者工作树拥有对应验收内容。这一保守内容检查可能阻塞与未提交上游范围重叠的修改，应按获准流程先提交上游，或明确调整依赖契约。消费者丢失所依赖的基线时，即使自身范围文件没变，旧回执也不再适用。未知字段和依赖环会被拒绝。独占资源名称在整个项目跨工作树共用；unknown 占用不会按年龄自动释放。

## 实现结束后验证，再登记证据

实现 dispatch 结束后再排程受管重型验证。用 `readiness --task ID --action verify` 检查这一阶段，模型审查还需 `--worker ID`；readiness 默认检查 dispatch。顺序尝试沿用同一任务 ID。审查者声明在命令执行前冻结；若实际使用模型审查，还须通过文档中的派发／验证路径选择获准 worker，使其占用 agent 并发。只有 reviewer 标签不表示模型已运行，也不证明真实身份。

```bash
python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" run --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --epoch "$PLAYBOOK_EPOCH" --action verify --task "$PLAYBOOK_TASK" --reviewer "$PLAYBOOK_REVIEWER" --role reviewer -- "$PLAYBOOK_COMMAND"
```

从成功回执取得真实 attempt ID，再登记结果：

```bash
python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" evidence --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --epoch "$PLAYBOOK_EPOCH" --task "$PLAYBOOK_TASK" --attempt "$PLAYBOOK_ATTEMPT" --reviewer "$PLAYBOOK_REVIEWER" --role reviewer --note "$PLAYBOOK_NOTE"
python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" evidence --project "$PLAYBOOK_PROJECT" --operation status --task "$PLAYBOOK_TASK"
python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" task --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --epoch "$PLAYBOOK_EPOCH" --id "$PLAYBOOK_TASK" --state verified
```

只有成功完成的 verify 尝试能产生通过的机器证据；dispatch 成功仍是 reported。实际测试的要求／依赖和验证前后的相关内容必须与验收对象一致。证据只追加，独立回执通过摘要指针关联；status 报告过期、缺失或变化的材料。有 spec 的任务不能仅凭非空备注变为 verified。旧任务保留历史，并标为 `legacy-note-only`。

人工证据必须由 `review.allow_manual:true` 明确允许。使用 `evidence --manual --reviewer NAME --role reviewer --artifact RELATIVE_PATH --note TEXT`，它标为人工证据，不能冒充测试命令。`--result passed|failed` 默认 passed。项目 `review.independent:true` 或任务要求独立审查时，审查者必须区别于已记录的实现参与者。任务可加强此要求，不能削弱项目策略。这两个策略字段未提供时均视为 false；读取旧策略不会插入字段。

内容指纹有界比较字节、模式、删除和符号链接身份，不比较 mtime，不跟随目录符号链接。Git 范围包括已跟踪与未忽略的未跟踪内容；常见未跟踪缓存、`.env` 和 ignored 内容会排除并报告。非 Git 使用保守排除。摘要不证明被排除内容已测试。可以另行登记明确归档的材料；artifact 必须是普通文件，祖先不能有符号链接。需要的排除证据应明确记录，不能假装快照已覆盖。

任务更新和交接保留持有者／实现参与者来源，并在验证 attempt 上冻结。事后换持有者不能把被拒绝的自审改称独立审查。仅暂存或提交已存在的删除不会改变内容指纹；真实内容变化仍会使旧证据失效。

共享 runtime 内完整的验证日志是权威证据，包括适配器在 quiet 模式下的 stdout／stderr；用户另存日志只是副本。权威日志删除或变化会使证据失效。显式 artifact 必须保留在记录路径，应在验证和登记前完成必要归档。

## 集成一组已验收任务

参与任务须为 verified，且回执当前适用。填写实际目标工作树、集成 ID 和任务 ID。额外 paths 用于组合检查，参与任务的范围始终包含在内。

```bash
python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" integration --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --epoch "$PLAYBOOK_EPOCH" --operation begin --id "$PLAYBOOK_INTEGRATION" --tasks "$PLAYBOOK_TASK_A" "$PLAYBOOK_TASK_B" --target "$PLAYBOOK_TARGET" --paths integration-tests
```

begin 记录事实，不授予合并权限。执行另行获准的集成方式，再用稳定的组合验证任务 ID 关联本次集成：

```bash
python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" run --project "$PLAYBOOK_TARGET" --session "$PLAYBOOK_SESSION" --epoch "$PLAYBOOK_EPOCH" --action verify --task "$PLAYBOOK_ASSEMBLY_TASK" --integration "$PLAYBOOK_INTEGRATION" --reviewer "$PLAYBOOK_REVIEWER" --role reviewer -- "$PLAYBOOK_COMMAND"
python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" integration --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --epoch "$PLAYBOOK_EPOCH" --operation finish --id "$PLAYBOOK_INTEGRATION" --attempt "$PLAYBOOK_ATTEMPT" --note "$PLAYBOOK_NOTE"
python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" integration --project "$PLAYBOOK_PROJECT" --operation status --id "$PLAYBOOK_INTEGRATION"
```

finish 核对明确关联的成功尝试、相关内容与目标 HEAD／分支，以及参与任务仍适用的要求／依赖；记录组合结果与真实合并事实后，将参与任务标为 integrated。测试后目标变化会使当前发布结论不适用。finish 固定范围内结果是否已提交，后续源树变化不能改写这个历史事实。依赖校验保留已验收结果，并检查实际消费者基线。集成通过后，获准清理来源工作树不会使没有显式 artifact 的机器回执失效；共享日志、依赖记录和实际集成目标仍须通过校验。参与关系明确标为声明，保留 `semantic_inclusion_proven:false`：源提交祖先关系与摘要不能证明所有预期行为已纳入，dirty 修改及 squash／rebase 尤其如此。组合测试失败时保留已合并成果与证据，不能记为通过。

若项目要求集成分支推送前必须有已验收组合结果，begin 可加 `--require-push`。该门槛只用于配置中的集成分支。记录门槛后，受守卫 push 使用明确的 `git push REMOTE SOURCE:DESTINATION`；含糊包装、默认／通配／force／删除形式会被拒绝。源提交必须等于已验收结果，目标工作树须干净。明确的备份目标仍受原推送权限和节奏限制，但不会因此获得或要求发布验收。这里的操作不授予发布或部署权限。
