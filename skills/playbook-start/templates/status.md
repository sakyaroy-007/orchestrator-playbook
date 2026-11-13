# 进度看板

> 维护标签 {{ORCHESTRATOR}}，观察日期 {{DATE}}。这是可读摘要，实际 owner/epoch/尝试以共享运行时 status 为准，不能靠改看板抢位。
> 配置 `.orchestrator/config.json` · revision：【待填】。配置 paths 优先于默认路径，单卡不能覆盖策略或扩权。

## 现场与策略

- owner session / client / epoch / 生命周期状态：【待填】。
- 基线 HEAD/分支/worktree 或非 Git 快照：【待填】。
- dirty / 未跟踪 / ignored / 未推与保留成果：【待填】。
- 集成线建议 `{{MAIN}}`，实际以 config.git 为准；远端：【待填：无则写无，不含凭据】。
- 员工与模式：config workers，继承员工自己设置；实际能力/登录证据见 TEAM.md。
- agent / heavy-job / 超时 / 尝试上限：config limits；非 Git 串行，不固定四并发。
- 许可、merge 方法、push 节奏和 cleanup 保留：config permissions/git，已定选择不重复问。
- 需要审查的范围与影响：【待填：按 review 策略，不机械全量/逆序】。

## 当前任务

| 卡 / 尝试 | 员工 ID | 状态 | worktree / 分支 / 基线 | 命令 / 日志 / 验收证据 | 缺口 / 下一步 |
|---|---|---|---|---|---|
| 【待填：无则写无】 | | reserved/running/reported/verified/integrated/blocked/unknown | | | |

待展开/可派/返工是规划标签，不能替代运行时事实。exit 0 只表示 reported；verified 需验收，integrated 需真实整合。孤儿/未知/在途先核查，不因没通知就重复派发。

## 热点文件与共享资源

| 文件 / 资源 | 负责卡 | 预留/锁机制与所有者证据 | 允许操作 / 恢复安排 |
|---|---|---|---|
| 【待填：无则写无；不能默认写空闲】 | | | |

worktree 不隔离端口/数据/服务；锁年龄不证明可删除。

## 本阶段出口与交接

- 可验收目标与真实结果：【待填】。
- 未做 / 失败 / 未验证：【待填】。
- 已准备交接以运行时 handoff ID 为准；旧 owner prepared 后停止共享写入。
- 清理保留 dirty/未合并/ignored/运行中/未知/证据成果，无法证明 squash 整合时保留核对。
