#!/usr/bin/env bash
# PreToolUse on Bash: deny an `openspec archive` invocation for a change that
# hasn't been merged to the resolved target branch yet — merge precedes
# archive, every time (design D9). Generous command matching, not exact
# parsing (see design Risks): the change name is read as the first
# non-flag argument after `archive`.
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
change=""
eval "$(printf '%s' "$input" | python3 "${MATCHER}" openspec-archive 2>/dev/null)"

[ "${matched}" = "1" ] || exit 0

# No positional change name found (e.g. an interactive/inferred invocation)
# -- this hook has nothing concrete to check, so it does not guess or block.
[ -n "${change}" ] || exit 0

# Resolve the repository the guarded command will actually run in (design D1
# of worktree-native-loop): computed from the command itself, falling back
# to the hook's own `cwd`, then `CLAUDE_PROJECT_DIR`, then `pwd`.
effective_dir="$(printf '%s' "$input" | "${GATES}" hook git-cwd openspec-archive 2>/dev/null)"
if [ -n "${effective_dir}" ] && [ -d "${effective_dir}" ]; then
  cd "${effective_dir}" 2>/dev/null || true
fi
resolved_repo="$(pwd)"

if out="$("${GATES}" discipline check-archive "${change}" 2>&1)"; then
  exit 0
fi

echo "${out} (repository: '${resolved_repo}')" >&2
exit 2
