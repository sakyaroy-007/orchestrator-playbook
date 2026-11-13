#!/bin/bash
# init-plan.sh — 在目标仓库铺好 orchestrator-playbook 控制面（只新建，不覆盖）
#
#   init-plan.sh <主仓路径> [--project 名称] [--decider 拍板人] [--orchestrator 总指挥]
#                [--wt-base 目录] [--main 分支] [--handoff 交接文件] [--no-handoff]
#                [--orchestrator-file 手册.md] [--agents-md AGENTS.md] [--dry-run]
#
# 新建（已存在的一律跳过）：
#   .orchestrator/{TEAM.md,PLAYBOOK.md}
#   docs/plan/{README,WORKER,status,tasks,questions,external}.md、docs/plan/decisions/ADR-001-协作与分支.md
#   docs/plan/{tasks,reviews}/、docs/plan/templates/{task-card,spike-card,review,ADR}.md
#   docs/changes/README.md、scripts/wt.sh、<交接文件>（默认 HANDOFF.md，相对仓库根；--no-handoff 不建）
# --orchestrator-file 给的话，用它作为 .orchestrator/PLAYBOOK.md 的正文（不渲染占位符）。
# --agents-md 给的话，把「执行者先读 WORKER.md / 你的身份只是 worker」片段幂等追加进该文件。
# 结束时打印：还没填的【待填】统计、下一步。兼容 macOS 自带 bash 3.2。
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd -P)"
TPL="$SKILL_DIR/templates"

die() { echo "init-plan: $*" >&2; exit 1; }
usage() { sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-1}"; }

[ $# -ge 1 ] || usage 1
case "$1" in -h|--help) usage 0 ;; esac
repo_arg="$1"; shift

project=""; decider="拍板人"; orchestrator="总指挥"; wt_base=""; main=""; handoff="HANDOFF.md"
orch_file=""; agents_md=""; no_handoff=0; dry=0
need() { [ $# -ge 2 ] && [ -n "$2" ] || die "$1 需要一个值"; }
while [ $# -gt 0 ]; do
  case "$1" in
    --project)      need "$@"; project="$2"; shift 2 ;;
    --decider)      need "$@"; decider="$2"; shift 2 ;;
    --orchestrator) need "$@"; orchestrator="$2"; shift 2 ;;
    --wt-base)      need "$@"; wt_base="$2"; shift 2 ;;
    --main)         need "$@"; main="$2"; shift 2 ;;
    --handoff)      need "$@"; handoff="$2"; shift 2 ;;
    --no-handoff)   no_handoff=1; shift ;;
    --orchestrator-file) need "$@"; orch_file="$2"; shift 2 ;;
    --agents-md)    need "$@"; agents_md="$2"; shift 2 ;;
    --dry-run)      dry=1; shift ;;
    -h|--help)      usage 0 ;;
    *)              die "未知参数：$1" ;;
  esac
done

# ---- 定位与校验 ----
[ -d "$repo_arg" ] || die "目录不存在：$repo_arg"
root="$(cd "$repo_arg" && pwd -P)"
top="$(git -C "$root" rev-parse --show-toplevel 2>/dev/null)" || die "不是 git 仓库：$root"
top="$(cd "$top" && pwd -P)"
[ "$top" = "$root" ] || die "请指向仓库根目录：$top"
common="$(git -C "$root" rev-parse --path-format=absolute --git-common-dir)"
[ "$(cd "$common" && pwd -P)" = "$root/.git" ] || die "这是一个 worktree；请指向主检出（$(dirname "$common")）"

[ -n "$project" ] || project="$(basename "$root")"
slug="$(printf '%s' "$project" | LC_ALL=C tr '[:upper:]' '[:lower:]' \
        | LC_ALL=C sed -e 's/[^a-z0-9][^a-z0-9]*/-/g' -e 's/^-//' -e 's/-$//')"
[ -n "$slug" ] || slug="project"
[ -n "$wt_base" ] || wt_base="${root}-wt"
case "$wt_base" in /*) ;; *) die "--wt-base 要写绝对路径：$wt_base" ;; esac
if [ -z "$main" ]; then
  main="$(git -C "$root" symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null | sed 's#^origin/##')" || main=""
  [ -n "$main" ] || main="$(git -C "$root" branch --show-current 2>/dev/null)" || main=""
  [ -n "$main" ] || main="main"
fi
case "$handoff" in /*|../*|*/../*) die "--handoff 写相对仓库根的路径（不能出仓库）：$handoff" ;; esac
if [ -n "$orch_file" ] && [ ! -f "$orch_file" ]; then die "--orchestrator-file 不存在：$orch_file"; fi
if [ -n "$agents_md" ]; then
  case "$agents_md" in /*|../*|*/../*) die "--agents-md 写相对仓库根的路径：$agents_md" ;; esac
fi
today="$(date +%Y-%m-%d)"

# A configured project's scaffolding is a managed metadata mutation. Preview
# remains read-only; actual writes must not alter another owner's prepared state.
if [ "$dry" -eq 0 ] && { [ -e "$root/.orchestrator/config.json" ] || [ -e "$common/orchestrator-playbook" ]; }; then
  runtime="$SKILL_DIR/scripts/playbook.py"
  [ -f "$runtime" ] || die "configured scaffolding requires the matching playbook.py"
  if [ "${PLAYBOOK_GUARDED:-}" != 1 ]; then
    [ -n "${PLAYBOOK_SESSION:-}" ] && [ -n "${PLAYBOOK_EPOCH:-}" ] \
      || die "set PLAYBOOK_SESSION and PLAYBOOK_EPOCH from start/resume before scaffolding"
    guarded_args=("$root" --project "$project" --decider "$decider" --orchestrator "$orchestrator" --wt-base "$wt_base" --main "$main" --handoff "$handoff")
    [ "$no_handoff" -eq 0 ] || guarded_args+=(--no-handoff)
    [ -z "$agents_md" ] || guarded_args+=(--agents-md "$agents_md")
    if [ -n "$orch_file" ]; then
      orch_file="$(cd "$(dirname "$orch_file")" && pwd -P)/$(basename "$orch_file")"
      guarded_args+=(--orchestrator-file "$orch_file")
    fi
    exec python3 -I "$runtime" guard --project "$root" \
      --session "$PLAYBOOK_SESSION" --epoch "$PLAYBOOK_EPOCH" --action scaffold \
      -- bash "$SKILL_DIR/scripts/init-plan.sh" "${guarded_args[@]}"
  fi
fi

# ---- 渲染与落盘 ----
render() {  # render <模板文件>：替换 {{占位符}} 后输出到 stdout（值经环境变量传入 perl，特殊字符安全）
  P_PROJECT="$project" P_SLUG="$slug" P_DECIDER="$decider" P_ORCH="$orchestrator" \
  P_ROOT="$root" P_WT="$wt_base" P_MAIN="$main" P_DATE="$today" P_HANDOFF="$handoff" \
  perl -pe '
    s/\{\{PROJECT\}\}/$ENV{P_PROJECT}/g;   s/\{\{SLUG\}\}/$ENV{P_SLUG}/g;
    s/\{\{DECIDER\}\}/$ENV{P_DECIDER}/g;   s/\{\{ORCHESTRATOR\}\}/$ENV{P_ORCH}/g;
    s/\{\{ROOT\}\}/$ENV{P_ROOT}/g;         s/\{\{WT_BASE\}\}/$ENV{P_WT}/g;
    s/\{\{MAIN\}\}/$ENV{P_MAIN}/g;         s/\{\{DATE\}\}/$ENV{P_DATE}/g;
    s/\{\{HANDOFF\}\}/$ENV{P_HANDOFF}/g;
  ' "$1"
}

created=""; skipped=""
place() {  # place <源文件> <目标相对路径> <render|raw> [chmod 模式]
  local src="$1" rel="$2" how="$3" mode="${4:-}" dst="$root/$2"
  [ -f "$src" ] || die "模板缺失：$src"
  if [ -e "$dst" ]; then
    skipped="${skipped}  = ${rel}
"
    return 0
  fi
  created="${created}  + ${rel}
"
  [ "$dry" -eq 0 ] || return 0
  mkdir -p "$(dirname "$dst")"
  if [ "$how" = "render" ]; then render "$src" > "$dst.tmp.$$"; else cp "$src" "$dst.tmp.$$"; fi
  mv "$dst.tmp.$$" "$dst"
  if [ -n "$mode" ]; then chmod "$mode" "$dst"; fi
  return 0
}

keep_dir() {  # 空目录放 .gitkeep，让 git 记住它
  local rel="$1"
  if [ -d "$root/$rel" ] && [ -n "$(ls -A "$root/$rel" 2>/dev/null)" ]; then return 0; fi
  created="${created}  + ${rel}/.gitkeep
"
  [ "$dry" -eq 0 ] || return 0
  mkdir -p "$root/$rel" && : > "$root/$rel/.gitkeep"
  return 0
}

place "$TPL/TEAM.md"           .orchestrator/TEAM.md      render
if [ -n "$orch_file" ]; then
  place "$orch_file"           .orchestrator/PLAYBOOK.md  raw
else
  place "$TPL/PLAYBOOK.md"     .orchestrator/PLAYBOOK.md  render
fi
place "$TPL/plan-README.md"    docs/plan/README.md        render
place "$TPL/WORKER.md"         docs/plan/WORKER.md        render
place "$TPL/status.md"         docs/plan/status.md        render
place "$TPL/tasks.md"          docs/plan/tasks.md         render
place "$TPL/questions.md"      docs/plan/questions.md     render
place "$TPL/external.md"       docs/plan/external.md      render
if [ -n "$(find "$root/docs/plan/decisions" -maxdepth 1 -name 'ADR-001-*' 2>/dev/null | head -1)" ]; then
  skipped="${skipped}  = docs/plan/decisions/ADR-001-*（已有 ADR-001）
"
else
  place "$TPL/ADR-001.md"      "docs/plan/decisions/ADR-001-协作与分支.md" render
fi
place "$TPL/task-card.md"      docs/plan/templates/task-card.md   render
place "$TPL/spike-card.md"     docs/plan/templates/spike-card.md  render
place "$TPL/review.md"         docs/plan/templates/review.md      render
place "$TPL/ADR.md"            docs/plan/templates/ADR.md         render
place "$TPL/changes-README.md" docs/changes/README.md     render
if [ "$no_handoff" -eq 1 ]; then
  skipped="${skipped}  = ${handoff}（--no-handoff）
"
else
  place "$TPL/HANDOFF.md"      "$handoff"                 render
fi
place "$SKILL_DIR/scripts/wt.sh" scripts/wt.sh            raw 755
place "$SKILL_DIR/scripts/playbook.py" scripts/playbook.py raw 755
place "$SKILL_DIR/scripts/playbook_work.py" scripts/playbook_work.py raw 755
keep_dir docs/plan/tasks
keep_dir docs/plan/reviews

# --agents-md：把片段幂等写进 AGENTS.md（有标记块就替换，没有就追加）
if [ -n "$agents_md" ]; then
  dst="$root/$agents_md"
  snippet="$(render "$TPL/AGENTS-snippet.md")"
  if [ "$dry" -eq 0 ]; then
    mkdir -p "$(dirname "$dst")"
    if [ -f "$dst" ] && grep -q 'orchestrator-playbook:start' "$dst"; then
      SNIPPET="$snippet" perl -0777 -i -pe \
        's/<!-- orchestrator-playbook:start -->.*?<!-- orchestrator-playbook:end -->/<!-- orchestrator-playbook:start -->\n$ENV{SNIPPET}\n<!-- orchestrator-playbook:end -->/s' "$dst"
      created="${created}  ~ ${agents_md}（替换已有的 orchestrator-playbook 片段）
"
    else
      { printf '\n<!-- orchestrator-playbook:start -->\n%s\n<!-- orchestrator-playbook:end -->\n' "$snippet"; } >> "$dst"
      created="${created}  ~ ${agents_md}（追加片段）
"
    fi
  else
    created="${created}  ~ ${agents_md}（追加 / 替换片段）
"
  fi
fi

# ---- 报告 ----
[ "$dry" -eq 0 ] || echo "（dry-run：下面是将要发生的事，没有写任何文件）"
echo "控制面 → $root"
echo "  项目 $project · slug $slug · 集成分支 $main · worktree 根 $wt_base · 交接文件 $handoff"
echo "  拍板人 $decider · 总指挥 $orchestrator"
echo "新建："
if [ -n "$created" ]; then printf '%s' "$created"; else echo "  （无）"; fi
if [ -n "$skipped" ]; then echo "已存在，跳过："; printf '%s' "$skipped"; fi

if [ -n "$agents_md" ]; then
  echo "已写入 ${agents_md}：标记块 <!-- orchestrator-playbook:start/end --> 之间是生成的片段。"
else
  echo "加进 AGENTS.md 的片段（执行者的客户端会自动读 AGENTS.md，靠它知道先读 WORKER.md）："
  render "$TPL/AGENTS-snippet.md" | sed 's/^/    /'
fi

if [ "$dry" -eq 0 ]; then
  echo
  echo "还没填的【待填】（文件: 处数）："
  scan="$root/docs/plan $root/.orchestrator"
  if [ "$no_handoff" -eq 0 ]; then scan="$scan $root/$handoff"; fi
  todo="$( { grep -rc '【待填' $scan 2>/dev/null || true; } | grep -v ':0$' | sed "s#^$root/#  #" || true)"
  if [ -n "$todo" ]; then echo "$todo"; else echo "  （无）"; fi
fi

cat <<EOF

下一步：
  1. 填【待填】：派第一张卡前，WORKER.md、status.md、.orchestrator/TEAM.md 必须清零
     grep -rn '【待填' docs/plan/WORKER.md docs/plan/status.md .orchestrator/
  2. 核对 .orchestrator/TEAM.md 的 holder 和授权；执行者靠它知道回报给谁、自己不是总指挥
  3. 每个 worktree 要独立环境时，写 scripts/wt-setup.sh <worktree路径>；v3 在创建完成后按获准流程单独执行，legacy 会自动调用
  4. git add .orchestrator docs/plan docs/changes scripts/wt.sh scripts/playbook.py scripts/playbook_work.py$( [ "$no_handoff" -eq 0 ] && printf ' %s' "$handoff" ) && git commit -m "docs(plan): 铺控制面（orchestrator-playbook）"
EOF
