#!/bin/bash
# wt.sh — 一卡一 worktree 一分支（orchestrator-playbook；只由总指挥运行）
#
#   wt.sh new  <卡号> <slug> [--from <分支>]   从 main（或 --from）切 t/<号>-<slug>，建 worktree，跑 scripts/wt-setup.sh（如有），打印预检与派发口令
#   wt.sh ls                                   列出 worktree，以及每个 t/* 分支相对 main 的落后 / 领先、最后提交、有无未提交改动
#   wt.sh path <卡号>                          打印 worktree 路径
#   wt.sh rm   <卡号> [--force]                合并后清理（未合并或有未提交改动时拒绝，除非 --force）
#
# 卡号：T-003 → 分支 t/003-<slug>；S-01 → t/s01-<slug>；其他前缀 X-12 → t/x12-<slug>
# 主仓定位：WT_ROOT → 本脚本所在仓库的主检出 → 当前目录所在仓库的主检出（每次都会打印，核对一眼）
# 可选环境变量：WT_BASE worktree 根（默认 <主仓>-wt）· WT_MAIN 集成分支（默认 main）
# 兼容 macOS 自带 bash 3.2（不用关联数组；set -u 下不展开空数组）。
set -euo pipefail

die() { echo "wt: $*" >&2; exit 1; }

main_checkout_of() {  # main_checkout_of <目录>：打印该目录所在仓库的主检出路径；不在仓库里返回 1
  local common
  common="$(git -C "$1" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)" || return 1
  common="$(cd "$common" && pwd -P)" || return 1
  case "$common" in
    */.git) dirname "$common" ;;
    *) return 1 ;;  # bare 仓库不支持
  esac
}

resolve_root() {
  if [ -n "${WT_ROOT:-}" ]; then
    (cd "$WT_ROOT" && pwd -P) || die "WT_ROOT 不存在：$WT_ROOT"
    return 0
  fi
  # 先看当前目录：从项目里调用时，永远以项目为准，
  # 避免 skill 自身恰好装在一个 git 仓库里时被误认成主仓。
  main_checkout_of "$(pwd)" && return 0
  main_checkout_of "$(dirname "$0")" && return 0
  die "找不到主仓：cd 到项目里再跑，或设 WT_ROOT=<主仓路径>"
}

ROOT="$(resolve_root)"
WT_BASE="${WT_BASE:-${ROOT}-wt}"
MAIN="${WT_MAIN:-main}"

git_root() { git -C "$ROOT" "$@"; }

check_id() {
  [[ "$1" =~ ^[[:upper:]]+-[[:digit:]]+$ ]] || die "卡号格式应为 T-003 / S-01 这类：$1"
}

num_of() {  # T-003 → 003；S-01 → s01；BUG-7 → bug7
  local prefix="${1%%-*}" num="${1#*-}"
  if [ "$prefix" = "T" ]; then
    echo "$num"
  else
    echo "$(printf '%s' "$prefix" | LC_ALL=C tr '[:upper:]' '[:lower:]')$num"
  fi
}

branch_of() {  # 已存在的 worktree 里读分支名
  git -C "$WT_BASE/$1" branch --show-current 2>/dev/null || true
}

cmd_new() {
  local id="${1:-}" slug="${2:-}" from="$MAIN"
  [ -n "$id" ] && [ -n "$slug" ] || die "用法：wt.sh new <卡号> <slug> [--from <分支>]"
  shift 2
  while [ $# -gt 0 ]; do
    case "$1" in
      --from) [ $# -ge 2 ] || die "--from 需要分支名"; from="$2"; shift 2 ;;
      *) die "未知参数：$1" ;;
    esac
  done
  check_id "$id"
  [[ "$slug" =~ ^[a-z0-9][a-z0-9-]*$ ]] || die "slug 只允许小写字母 / 数字 / 连字符：$slug"
  git_root rev-parse --verify --quiet "${from}^{commit}" >/dev/null || die "起点不存在：$from"

  local wt="$WT_BASE/$id" branch
  branch="t/$(num_of "$id")-$slug"
  [ ! -e "$wt" ] || die "已存在：$wt"
  if git_root show-ref --verify --quiet "refs/heads/$branch"; then die "分支已存在：$branch"; fi
  [ -f "$ROOT/docs/plan/WORKER.md" ] || echo "wt: ⚠️ $ROOT/docs/plan/WORKER.md 不存在——还没铺控制面？（init-plan.sh）" >&2

  mkdir -p "$WT_BASE"
  git_root worktree add -b "$branch" "$wt" "$from" >/dev/null
  echo "主仓:     $ROOT"
  echo "worktree: $wt"
  echo "branch:   ${branch}（基于 $from $(git_root rev-parse --short "$from")）"
  if [ "$from" != "$MAIN" ]; then
    echo "⚠️ 起点不是 ${MAIN}：在卡和看板备注里写明；合并前先更新到 $from 的最终版本并复跑验收。"
  fi

  if [ -x "$wt/scripts/wt-setup.sh" ]; then
    echo "准备环境：scripts/wt-setup.sh …"
    (cd "$wt" && ./scripts/wt-setup.sh "$wt") \
      || die "wt-setup.sh 失败；worktree 已建好（${wt}），修好后手动重跑：cd $wt && ./scripts/wt-setup.sh $wt"
  fi

  cat <<EOF

预检口令（先发这句；预期输出 $wt 和 ${branch}）：
只执行 pwd 和 git branch --show-current，原样输出结果，不做别的。

派发口令（启动目录必须是 ${wt}）：
读 $ROOT/docs/plan/WORKER.md 和 $ROOT/docs/plan/tasks/$id.md，在 worktree ${wt}（分支 ${branch}）里执行，完成后按 WORKER.md 第 5 节模板回报。
EOF
}

cmd_ls() {
  echo "主仓: ${ROOT}（集成分支 ${MAIN}）"
  git_root worktree list
  echo
  local b counts wt dirty last
  for b in $(git_root for-each-ref --format='%(refname:short)' 'refs/heads/t/'); do
    counts="$(git_root rev-list --left-right --count "$MAIN...$b")"
    wt="$(git_root worktree list --porcelain | awk -v ref="refs/heads/$b" \
          '$1=="worktree"{p=substr($0,10)} $1=="branch" && $2==ref {print p}')"
    dirty=""
    if [ -n "$wt" ] && [ -n "$(git -C "$wt" status --porcelain 2>/dev/null)" ]; then
      dirty=" · ⚠️ 有未提交改动"
    fi
    last="$(git_root log -1 --format='%h %<(40,trunc)%s' "$b")"
    printf '%-34s 落后 %s · 领先 %s · %s%s\n' "$b" "${counts%%	*}" "${counts##*	}" "$last" "$dirty"
  done
}

cmd_path() {
  local id="${1:-}"
  check_id "$id"
  [ -d "$WT_BASE/$id" ] || die "不存在：$WT_BASE/$id"
  echo "$WT_BASE/$id"
}

cmd_rm() {
  local id="${1:-}" force=0
  check_id "$id"
  [ "${2:-}" = "--force" ] && force=1
  local wt="$WT_BASE/$id"
  [ -d "$wt" ] || die "不存在：${wt}（若目录被手动删了，跑 git -C $ROOT worktree prune）"
  local branch
  branch="$(branch_of "$id")"
  [ -n "$branch" ] || die "读不到 $wt 的分支"

  if [ "$force" -eq 0 ]; then
    [ -z "$(git -C "$wt" status --porcelain)" ] || die "$id 有未提交改动（看 git -C $wt status）；确认要丢弃请加 --force"
    git_root merge-base --is-ancestor "$branch" "$MAIN" || die "$branch 尚未合入 ${MAIN}；确认要丢弃请加 --force"
    git_root worktree remove "$wt"
    git_root branch -d "$branch" >/dev/null
  else
    git_root worktree remove --force "$wt"
    git_root branch -D "$branch" >/dev/null
  fi
  echo "已清理 ${id}（${branch}）"
}

case "${1:-}" in
  new)  shift; cmd_new "$@" ;;
  ls)   shift; cmd_ls ;;
  path) shift; cmd_path "$@" ;;
  rm)   shift; cmd_rm "$@" ;;
  *)    sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;;
esac
