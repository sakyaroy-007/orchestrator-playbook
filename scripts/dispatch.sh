#!/bin/bash
# dispatch.sh — 把派发口令交给一个执行者 agent，无人值守地跑：指定工作目录、限时、落日志
#
#   dispatch.sh <执行者> <worktree> "<口令>" [-t 秒] [-m 模型] [-q] [-l 日志文件] [-- 透传给执行者 CLI 的参数…]
#   dispatch.sh <执行者> <worktree> --precheck [同上选项]     预检：执行者只报 pwd 和分支，脚本自动比对
#
# 执行者：claude | codex | hermes | dsh。其他 CLI agent 照着下面的 case 加一段即可。
# dsh（DeepSeek Harness）：默认用 headless profile；profile 名可用 DISPATCH_DSH_PROFILE 覆盖。
#       dsh 的 -m 必须写 provider/model，会转成一次性 --patch 覆盖 agent-default-model。
# 日志：用 -l 指定；不指定则写到 $DISPATCH_LOG_DIR/<时间>-<卡号>-<执行者>-<pid>.log
#       （DISPATCH_LOG_DIR 默认 ~/.local/state/orchestrator-playbook/logs）。
#       日志末尾的 "#dispatch| 结束 rc=…" 表示已跑完；脚本输出的最后一行是日志路径。
# 退出码：与执行者相同。超时为 142（perl 限时）或 124（timeout 限时）；预检不通过为 3；用法错误为 2。
# 模型：不传 -m 时用执行者自己的默认配置。用哪个模型由你决定，skill 只给推荐（见 references/dispatch.md）。
# 权限：本脚本不替你放宽任何权限。无人值守需要的权限，放在 -- 后面透传，例如：
#       claude … -- --permission-mode acceptEdits
#       codex  … -- --sandbox workspace-write --add-dir <主仓>/.git   （沙箱受限时，要放行主仓的 .git，worktree 才能提交）
# 测试用：可以用 DISPATCH_BIN_CLAUDE / DISPATCH_BIN_CODEX / DISPATCH_BIN_HERMES / DISPATCH_BIN_DSH 把执行者命令换成桩。
# 兼容 macOS 自带的 bash 3.2。
set -euo pipefail

die() { echo "dispatch: $*" >&2; exit 2; }
usage() { sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }

[ $# -ge 3 ] || usage
worker="$1"; wt_arg="$2"; shift 2
precheck=0; task=""
if [ "$1" = "--precheck" ]; then precheck=1; shift; else task="$1"; shift; fi
[ "$precheck" -eq 1 ] || [ -n "$task" ] || die "口令不能为空"

tmo=""; model=""; quiet=0; log=""
while [ $# -gt 0 ]; do
  case "$1" in
    -t) [ $# -ge 2 ] || die "-t 需要秒数"; tmo="$2"; shift 2 ;;
    -m) [ $# -ge 2 ] || die "-m 需要模型名"; model="$2"; shift 2 ;;
    -q) quiet=1; shift ;;
    -l) [ $# -ge 2 ] || die "-l 需要日志文件路径"; log="$2"; shift 2 ;;
    --) shift; break ;;
    *)  die "未知参数：$1（透传给执行者 CLI 的参数放在 -- 后面）" ;;
  esac
done
# 剩下的 "$@" 原样透传给执行者 CLI

[ -d "$wt_arg" ] || die "worktree 不存在：$wt_arg"
wt="$(cd "$wt_arg" && pwd)"
wt_phys="$(cd "$wt_arg" && pwd -P)"
branch="$(git -C "$wt" branch --show-current 2>/dev/null || true)"
if [ -z "$tmo" ]; then
  if [ "$precheck" -eq 1 ]; then tmo=300; else tmo=7200; fi
fi
[[ "$tmo" =~ ^[0-9]+$ ]] && [ "$tmo" -gt 0 ] || die "-t 要写正整数秒：$tmo"
if [ "$precheck" -eq 1 ]; then
  task="只执行 pwd 和 git branch --show-current 这两条命令，原样输出结果，不做别的。"
fi

case "$worker" in
  claude) set -- "${DISPATCH_BIN_CLAUDE:-claude}" -p "$task" --output-format text ${model:+--model "$model"} "$@" ;;
  codex)  set -- "${DISPATCH_BIN_CODEX:-codex}" exec --skip-git-repo-check -C "$wt" ${model:+--model "$model"} "$@" "$task" ;;
  hermes) set -- "${DISPATCH_BIN_HERMES:-hermes}" ${model:+-m "$model"} "$@" -z "$task" --in "$wt" ;;
  dsh)
    dsh_bin="${DISPATCH_BIN_DSH:-}"
    if [ -z "$dsh_bin" ]; then
      if command -v dsh >/dev/null 2>&1; then dsh_bin="$(command -v dsh)"
      else die "找不到 dsh：装好 DeepSeek Harness 并让它出现在 PATH，或设置 DISPATCH_BIN_DSH"; fi
    fi
    dsh_patch=""
    if [ -n "$model" ]; then
      case "$model" in
        */*) dsh_provider="${model%%/*}"; dsh_model="${model#*/}" ;;
        *)   die "dsh 的 -m 要写 provider/model，例如 provider/model-name" ;;
      esac
      [ -n "$dsh_provider" ] && [ -n "$dsh_model" ] \
        || die "dsh 的 -m 要写 provider/model，例如 provider/model-name"
      dsh_patch="$(mktemp "${TMPDIR:-/tmp}/dispatch-dsh-model.XXXXXX")" || die "创建临时 patch 失败"
      printf -- '- id: agent-default-model\n  config:\n    provider: "%s"\n    model: "%s"\n' \
        "$dsh_provider" "$dsh_model" > "$dsh_patch"
      trap 'rm -f "$dsh_patch"' EXIT
    fi
    dsh_profile="${DISPATCH_DSH_PROFILE-headless}"
    set -- "$dsh_bin" ${dsh_profile:+--profile "$dsh_profile"} ${dsh_patch:+--patch "$dsh_patch"} "$@" "$task"
    ;;
  *)      die "未知执行者：${worker}（内置 claude / codex / hermes / dsh；其他 CLI agent 照着 case 分支加一段）" ;;
esac
command -v "$1" >/dev/null 2>&1 || die "找不到执行者命令：$1"

if [ -z "$log" ]; then
  suffix=""
  if [ "$precheck" -eq 1 ]; then suffix="-precheck"; fi
  log="${DISPATCH_LOG_DIR:-$HOME/.local/state/orchestrator-playbook/logs}/$(date +%Y%m%d-%H%M%S)-$(basename "$wt")-${worker}${suffix}-$$.log"
fi
mkdir -p "$(dirname "$log")"

run_limited() {  # run_limited <秒> <命令…>
  local secs="$1"; shift
  if command -v perl >/dev/null 2>&1; then
    perl -e 'alarm shift; exec @ARGV or die "exec failed: $!\n"' "$secs" "$@"
  elif command -v timeout >/dev/null 2>&1; then
    timeout "$secs" "$@"
  else
    echo "dispatch: ⚠️ 没有 perl 也没有 timeout，本次不限时" >&2
    "$@"
  fi
}

{
  echo "#dispatch| $(date '+%Y-%m-%d %H:%M:%S') 执行者=${worker} 模型=${model:-默认} 限时=${tmo}s 分支=${branch:-?}"
  echo "#dispatch| worktree=${wt}"
  echo "#dispatch| 口令=${task}"
} > "$log"
printf '==> [%s] %s%s\n    日志: %s\n' "$worker" "$(basename "$wt")" "${branch:+ (${branch})}" "$log"

start=$(date +%s)
set +e
( cd "$wt" && run_limited "$tmo" "$@" ) >> "$log" 2>&1
rc=$?
set -e
dur=$(( $(date +%s) - start ))

if [ "$rc" -eq 142 ] || [ "$rc" -eq 124 ]; then
  echo "#dispatch| 超时 ${tmo}s，已终止" >> "$log"
  echo "<== [超时 ${tmo}s，已终止]" >&2
fi
echo "#dispatch| 结束 rc=${rc} 用时=${dur}s" >> "$log"

if [ "$precheck" -eq 1 ]; then
  body="$(grep -v '^#dispatch|' "$log" || true)"
  if [ "$rc" -eq 0 ] \
     && { printf '%s\n' "$body" | grep -qF -- "$wt" || printf '%s\n' "$body" | grep -qF -- "$wt_phys"; } \
     && { [ -z "$branch" ] || printf '%s\n' "$body" | grep -qF -- "$branch"; }; then
    echo "预检通过：$worker 在 ${wt}（分支 ${branch:-无}）"
  else
    echo "预检失败（rc=${rc}）：输出里找不到 $wt 或分支 ${branch:-?}。别派正文，先看日志" >&2
    [ "$rc" -ne 0 ] || rc=3
  fi
fi

if [ "$quiet" -eq 0 ]; then
  echo "----- 输出（尾 40 行）-----"
  tail -40 "$log"
  echo "----- 结束 rc=${rc} 用时=${dur}s -----"
fi
echo "$log"
exit "$rc"
