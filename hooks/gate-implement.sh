#!/usr/bin/env bash
# PreToolUse on Bash: deny cutting a change's implementation branch
# (`git checkout -b <name>` / `git switch -c <name>`) unless the change's
# plan is BOTH merged to the resolved target branch and carries a populated,
# still-matching approval (design D10). Only fires for a name that is
# actually a known OpenSpec change -- `gates discipline check-implement`
# makes that distinction, so an ordinary unrelated branch checkout is never
# touched by this hook.
set -uo pipefail

if [ -n "${CLAUDE_PLUGIN_ROOT:-}" ]; then
  GATES="${CLAUDE_PLUGIN_ROOT}/bin/gates"
  MATCHER="${CLAUDE_PLUGIN_ROOT}/hooks/_gate_match.py"
else
  HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  GATES="${HOOK_DIR}/../bin/gates"
  MATCHER="${HOOK_DIR}/_gate_match.py"
fi

input="$(cat)"
matched="0"
branch=""
eval "$(printf '%s' "$input" | python3 "${MATCHER}" implement-branch 2>/dev/null)"

[ "${matched}" = "1" ] || exit 0
[ -n "${branch}" ] || exit 0

# Resolve the repository the guarded command will actually run in (design D1
# of worktree-native-loop): computed from the command itself, falling back
# to the hook's own `cwd`, then `CLAUDE_PROJECT_DIR`, then `pwd`.
cwd_rc=0
effective_dir="$(printf '%s' "$input" | "${GATES}" hook git-cwd implement-branch 2>/dev/null)" || cwd_rc=$?
# loop-hardening D8: exit 3 is a `cd` the resolver could not evaluate. The
# hook cannot know which repository the command runs in, so it denies rather
# than judge this session's checkout in its place.
if [ "${cwd_rc}" = "3" ]; then
  printf '%s' "$input" | "${GATES}" hook git-cwd implement-branch >/dev/null
  echo "gatedloop: branch denied — the repository this command runs in could not be resolved." >&2
  exit 2
fi
if [ -n "${effective_dir}" ] && [ -d "${effective_dir}" ]; then
  cd "${effective_dir}" 2>/dev/null || true
fi
resolved_repo="$(pwd)"

if out="$("${GATES}" discipline check-implement "${branch}" 2>&1)"; then
  exit 0
fi

echo "${out} (repository: '${resolved_repo}')" >&2
exit 2
