## 多 agent 协作（orchestrator-playbook）

- 先读 `docs/plan/WORKER.md` 和分配的一张任务卡；实际路径以 `.orchestrator/config.json` 的 paths 为准。
- 执行者只在获准工作目录和文件范围内写。Git 通常使用 `{{WT_BASE}}/<卡号>`，非 Git 串行。
- 未经项目授权，禁止 push；commit/merge/cleanup 也依 config permissions/git。单卡只能收窄权限，不能新增授权。
- 拍板人是 {{DECIDER}}。总指挥以共享运行时具体 session/epoch 为准，TEAM.md 是摘要，改文件或同名客户端不能认领角色。
- 新会话只读核查 `{{HANDOFF}}` 与 status/doctor，先确认在途/孤儿成果，不自动重放。resume 不夺权，takeover 按显式交接/恢复流程。
- 计划/卡描述意图，运行时记录所有权和尝试，真实代码/命令输出提供成果证据。未配置旧项目不享有 v3 运行时保证。
