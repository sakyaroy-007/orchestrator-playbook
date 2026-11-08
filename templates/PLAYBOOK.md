# {{PROJECT}} 总指挥手册

> 本文件把 orchestrator-playbook 实例化到本项目。换总指挥时，新的 holder 先读这里。
> 当前 holder 与授权见 `.orchestrator/TEAM.md`。

## 1. 角色

- 拍板人：{{DECIDER}}
- 总指挥：{{ORCHESTRATOR}}（holder 以 `TEAM.md` 为准）
- 执行者：见 `TEAM.md` 花名册

## 2. 派发通道与预检

- 通道：【待填：`scripts/dispatch.sh <执行者> <worktree> "<口令>"` / 子代理 / 人工转派 / 群聊】
- 预检：【待填：`scripts/dispatch.sh <执行者> <worktree> --precheck`】
- 日志：【待填】

## 3. 模型推荐

> 模型由拍板人 / 总指挥自选；这里只写本项目的推荐，不绑定任何供应商或路由服务。

- 高风险卡（钱 / 鉴权 / 隔离 / 数据安全）：【待填】
- 普通卡：【待填】
- 执行者默认配置：【待填】

## 4. 共享资源与锁

| 资源 | 类型 | 锁 / 串行方式 | 备注 |
|---|---|---|---|
| 【待填】 | 端口 / 常驻服务 / 真机 / 凭据目录 | | |

## 5. 热点文件与迁移

- 热点文件：见 `docs/plan/status.md` 的「热点文件锁」。
- 迁移：每张卡最多新增一个 revision；合并时由总指挥重排，保证只有一个 head。

## 6. 本项目额外红线

- 【待填】
