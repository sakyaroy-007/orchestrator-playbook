#!/bin/bash
# selftest.sh — orchestrator-playbook 脚本端到端自测（init-plan.sh + wt.sh 全生命周期，只在 /tmp 临时仓库里跑）
set -u
S="${1:-$(cd "$(dirname "$0")/.." && pwd -P)}"
T="$(mktemp -d /tmp/opb-e2e.XXXXXX)"; T="$(cd "$T" && pwd -P)"
pass=0; fail=0
ok()   { pass=$((pass+1)); echo "  ✓ $1"; }
bad()  { fail=$((fail+1)); echo "  ✗ $1"; }
check(){ local d="$1"; shift; if "$@" >/dev/null 2>&1; then ok "$d"; else bad "$d"; fi; }
refuse(){ local d="$1"; shift; if "$@" >/dev/null 2>&1; then bad "${d}（本应拒绝）"; else ok "$d"; fi; }
export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t

echo "[1] init-plan.sh"
git init -q -b main "$T/demo" && git -C "$T/demo" commit -q --allow-empty -m init
bash "$S/scripts/init-plan.sh" "$T/demo" --dry-run >/dev/null
check "dry-run 不写文件" test "$(ls -A "$T/demo")" = ".git"
bash "$S/scripts/init-plan.sh" "$T/demo" --project "Demo Proj" --decider 拍板人A --orchestrator 主脑B > "$T/init.out"
for f in docs/plan/README.md docs/plan/WORKER.md docs/plan/status.md docs/plan/tasks.md docs/plan/questions.md \
         docs/plan/external.md "docs/plan/decisions/ADR-001-协作与分支.md" docs/plan/templates/task-card.md \
         docs/plan/templates/spike-card.md docs/plan/templates/review.md docs/plan/templates/ADR.md \
         .orchestrator/TEAM.md .orchestrator/PLAYBOOK.md \
         docs/changes/README.md HANDOFF.md scripts/wt.sh docs/plan/tasks/.gitkeep docs/plan/reviews/.gitkeep; do
  check "生成 ${f}" test -f "$T/demo/${f}"
done
check "无残留 {{占位符}}" sh -c "! grep -rq '{{' '$T/demo/docs' '$T/demo/.orchestrator' '$T/demo/HANDOFF.md'"
check "占位符已替换（拍板人/主脑/路径）" sh -c "grep -q '总指挥是 主脑B' '$T/demo/docs/plan/WORKER.md' && grep -q '拍板人是 拍板人A' '$T/demo/docs/plan/WORKER.md' && grep -q '$T/demo-wt/<卡号>' '$T/demo/docs/plan/WORKER.md'"
check "TEAM.md 写入 holder" grep -q '当前总指挥（holder）：主脑B' "$T/demo/.orchestrator/TEAM.md"
check "WORKER.md 有防误认声明" grep -q '都不代表你是总指挥' "$T/demo/docs/plan/WORKER.md"
check "wt.sh 可执行" test -x "$T/demo/scripts/wt.sh"
check "报告列出【待填】" grep -q 'docs/plan/WORKER.md:' "$T/init.out"
bash "$S/scripts/init-plan.sh" "$T/demo" > "$T/init2.out"
check "重复运行全部跳过" sh -c "grep -A1 '^新建' '$T/init2.out' | grep -q '（无）'"
refuse "拒绝非仓库根" bash "$S/scripts/init-plan.sh" "$T/demo/docs"
refuse "拒绝 --handoff 出仓库" bash "$S/scripts/init-plan.sh" "$T/demo" --handoff ../x.md
refuse "拒绝不存在的 --orchestrator-file" bash "$S/scripts/init-plan.sh" "$T/demo" --orchestrator-file "$T/nope.md"

echo "[1b] init-plan.sh 新选项"
git init -q -b main "$T/opt" && git -C "$T/opt" commit -q --allow-empty -m init
echo "# 我自己的总指挥手册" > "$T/opt/PLAYBOOK-src.md"
bash "$S/scripts/init-plan.sh" "$T/opt" --project Opt --no-handoff --orchestrator-file "$T/opt/PLAYBOOK-src.md" --agents-md AGENTS.md > "$T/opt.out"
check "--no-handoff 不建交接文档" test ! -e "$T/opt/HANDOFF.md"
check "--orchestrator-file 原样写入" grep -q '我自己的总指挥手册' "$T/opt/.orchestrator/PLAYBOOK.md"
check "--agents-md 追加标记块" grep -q 'orchestrator-playbook:start' "$T/opt/AGENTS.md"
check "AGENTS 片段含 worker 身份提醒" grep -q '禁止 push' "$T/opt/AGENTS.md"
bash "$S/scripts/init-plan.sh" "$T/opt" --agents-md AGENTS.md >/dev/null
check "--agents-md 幂等（只有一块）" test "$(grep -c 'orchestrator-playbook:start' "$T/opt/AGENTS.md")" -eq 1

echo "[2] wt.sh new / 钩子 / --from / 坏输入"
cd "$T/demo"
printf '#!/bin/bash\nset -e\necho "setup:$1" > "$1/.setup-marker"\n' > scripts/wt-setup.sh && chmod +x scripts/wt-setup.sh
echo ".setup-marker" > .gitignore
git add -A && git commit -qm "docs(plan): 铺控制面"
scripts/wt.sh new T-001 first-card > "$T/new1.out" 2>&1
check "T-001 worktree 已建" test -d "$T/demo-wt/T-001"
check "T-001 分支名 t/001-first-card" test "$(git -C "$T/demo-wt/T-001" branch --show-current)" = "t/001-first-card"
check "wt-setup.sh 钩子已执行" grep -q "setup:$T/demo-wt/T-001" "$T/demo-wt/T-001/.setup-marker"
check "打印派发口令（含中文标点无报错）" grep -q '派发口令（启动目录必须是' "$T/new1.out"
check "派发口令含 WORKER.md 与卡路径" grep -q "读 $T/demo/docs/plan/WORKER.md 和 $T/demo/docs/plan/tasks/T-001.md" "$T/new1.out"
scripts/wt.sh new S-01 spike-x >/dev/null 2>&1
check "S-01 → t/s01-spike-x" test "$(git -C "$T/demo-wt/S-01" branch --show-current)" = "t/s01-spike-x"
scripts/wt.sh new T-002 second --from t/001-first-card > "$T/new2.out" 2>&1
check "--from 起点告警" grep -q '起点不是 main' "$T/new2.out"
refuse "拒绝小写卡号" scripts/wt.sh new t-3 x
refuse "拒绝非法 slug" scripts/wt.sh new T-003 Bad_Slug
refuse "拒绝重复卡号" scripts/wt.sh new T-001 dup
refuse "拒绝不存在的起点" scripts/wt.sh new T-004 x --from nope

echo "[3] wt.sh ls / path / 从 worktree 内调用 / 从 skill 原件调用"
scripts/wt.sh ls > "$T/ls.out" 2>&1
check "ls 列出 3 条 t/* 分支" test "$(grep -c '^t/' "$T/ls.out")" -eq 3
check "path 正确" test "$(scripts/wt.sh path T-001)" = "$T/demo-wt/T-001"
check "worktree 内的副本定位到主仓" sh -c "cd '$T/demo-wt/T-002' && ./scripts/wt.sh ls | grep -q '主仓: $T/demo（'"
check "skill 原件按当前目录定位主仓" sh -c "cd '$T/demo' && bash '$S/scripts/wt.sh' ls | grep -q '主仓: $T/demo（'"
check "WT_ROOT 覆盖" sh -c "cd / && WT_ROOT='$T/demo' bash '$S/scripts/wt.sh' path T-001 | grep -q 'demo-wt/T-001'"

echo "[4] wt.sh rm：未合并拒绝 / 合并后清理 / 脏拒绝 / --force"
(cd "$T/demo-wt/T-001" && echo x > a.txt && git add a.txt && git commit -qm "T-001: x")
refuse "未合并时拒绝删除" scripts/wt.sh rm T-001
git merge -q --no-ff t/001-first-card -m "merge T-001"
check "合并后清理成功" scripts/wt.sh rm T-001
check "分支已删" sh -c "! git show-ref --verify --quiet refs/heads/t/001-first-card"
echo y > "$T/demo-wt/S-01/b.txt"
refuse "有未提交改动时拒绝" scripts/wt.sh rm S-01
check "--force 强删" scripts/wt.sh rm S-01 --force
check "ls 中只剩 T-002" test "$(scripts/wt.sh ls | grep -c '^t/')" -eq 1

echo "[5] 已有控制面的项目（只补缺）"
git init -q -b main "$T/old" && mkdir -p "$T/old/docs/plan/decisions" && echo legacy > "$T/old/docs/plan/WORKER.md" \
  && echo adr > "$T/old/docs/plan/decisions/ADR-001-旧的.md" && echo h > "$T/old/00_交接.md" \
  && git -C "$T/old" add -A && git -C "$T/old" commit -qm init
bash "$S/scripts/init-plan.sh" "$T/old" --handoff 00_交接.md > "$T/old.out"
check "不覆盖已有 WORKER.md" test "$(cat "$T/old/docs/plan/WORKER.md")" = "legacy"
check "已有 ADR-001 不再新建" test "$(ls "$T/old/docs/plan/decisions" | wc -l | tr -d ' ')" = "1"
check "指定了交接文件就不建 HANDOFF.md" test ! -e "$T/old/HANDOFF.md"
check "AGENTS 片段引用指定的交接文件" grep -q '每次开工先读 `00_交接.md`' "$T/old.out"
check "缺的文件照常补上（status.md）" test -f "$T/old/docs/plan/status.md"

echo "[6] dispatch.sh（桩，不调用真实 agent）"
B="$T/stubbin"; mkdir -p "$B"
printf '#!/bin/sh\npwd\ngit branch --show-current\n' > "$B/ok"; chmod +x "$B/ok"
printf '#!/bin/sh\necho /elsewhere\necho t/wrong\n' > "$B/bad"; chmod +x "$B/bad"
printf '#!/bin/sh\nsleep 10\n' > "$B/slow"; chmod +x "$B/slow"
printf '#!/bin/sh\nprintf "ARGV: %%s\\n" "$@"\n' > "$B/argv"; chmod +x "$B/argv"
export DISPATCH_LOG_DIR="$T/dlogs"
WT2="$T/demo-wt/T-002"
DISPATCH_BIN_CLAUDE="$B/ok" "$S/scripts/dispatch.sh" claude "$WT2" --precheck -q >/dev/null 2>&1
check "预检通过 rc=0" test "$?" -eq 0
DISPATCH_BIN_CLAUDE="$B/bad" "$S/scripts/dispatch.sh" claude "$WT2" --precheck -q >/dev/null 2>&1
check "预检失败 rc=3" test "$?" -eq 3
DISPATCH_BIN_CLAUDE="$B/slow" "$S/scripts/dispatch.sh" claude "$WT2" test -t 2 -q >/dev/null 2>&1
check "超时 rc=142" test "$?" -eq 142
"$S/scripts/dispatch.sh" nope "$WT2" x -q >/dev/null 2>&1
check "未知执行者 rc=2" test "$?" -eq 2
DISPATCH_BIN_CLAUDE="$B/argv" "$S/scripts/dispatch.sh" claude "$WT2" "do" -q -- --model M1 >/dev/null 2>&1
check "透传 -- 之后的参数" sh -c "grep -q 'ARGV: --model' \$(ls -t '$DISPATCH_LOG_DIR'/*.log | head -1)"
check "日志有结束标记" sh -c "grep -q '#dispatch| 结束 rc=0' \$(ls -t '$DISPATCH_LOG_DIR'/*.log | head -1)"

echo "[7] dispatch.sh dsh 分支（桩）"
printf '#!/bin/sh\nprintf "ARGV: %%s\\n" "$@"\n' > "$B/dsh"; chmod +x "$B/dsh"
export DISPATCH_LOG_DIR="$T/dlogs2"
DISPATCH_BIN_DSH="$B/dsh" "$S/scripts/dispatch.sh" dsh "$WT2" "干活" -q >/dev/null 2>&1
check "dsh: 默认 headless profile" sh -c "grep -q 'ARGV: --profile' \$(ls -t '$DISPATCH_LOG_DIR'/*.log | head -1) && grep -q 'ARGV: headless' \$(ls -t '$DISPATCH_LOG_DIR'/*.log | head -1)"
check "dsh: 口令在最后" sh -c "grep '^ARGV: ' \$(ls -t '$DISPATCH_LOG_DIR'/*.log | head -1) | tail -1 | grep -q 'ARGV: 干活'"
DISPATCH_BIN_DSH="$B/dsh" "$S/scripts/dispatch.sh" dsh "$WT2" "干活" -m provider/model-x -q >/dev/null 2>&1
check "dsh: -m 转 --patch" sh -c "grep -q 'ARGV: --patch' \$(ls -t '$DISPATCH_LOG_DIR'/*.log | head -1)"
DISPATCH_BIN_DSH="$B/dsh" "$S/scripts/dispatch.sh" dsh "$WT2" "干活" -m nomodel -q >/dev/null 2>&1
check "dsh: -m 缺 provider/ 拒绝 rc=2" test "$?" -eq 2
DISPATCH_BIN_DSH="$B/dsh" DISPATCH_DSH_PROFILE=tui "$S/scripts/dispatch.sh" dsh "$WT2" "干活" -q >/dev/null 2>&1
check "dsh: profile 可覆盖" sh -c "grep -q 'ARGV: tui' \$(ls -t '$DISPATCH_LOG_DIR'/*.log | head -1)"
unset DISPATCH_LOG_DIR
refuse "拒绝不存在的 worktree" "$S/scripts/dispatch.sh" claude "$T/nope" "x" -q
unset DISPATCH_LOG_DIR

echo
echo "结果：$pass 通过，$fail 失败（测试目录 ${T}）"
[ "$fail" -eq 0 ] && rm -rf "$T"
exit "$fail"
