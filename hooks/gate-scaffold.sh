#!/usr/bin/env bash
# PreToolUse on Bash: deny an `openspec new change` invocation on a branch
# where proposal authoring itself would be refused (design D4). The same
# D9/D3 branch discipline `gate-propose.sh` applies to artifact writes fires
# one step earlier here, before any change directory exists — a refused
# scaffold must never leave a stranded directory on the working tree
# (issue #7). Generous command matching, not exact parsing (see design
# Risks): anything that isn't an `openspec new change` invocation passes
# through untouched.
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
eval "$(printf '%s' "$input" | python3 "${MATCHER}" openspec-scaffold 2>/dev/null)"

[ "${matched}" = "1" ] || exit 0

# Resolve the repository the guarded command will actually run in (design D1
# of worktree-native-loop): computed from the command itself, falling back
# to the hook's own `cwd`, then `CLAUDE_PROJECT_DIR`, then `pwd`.
effective_dir="$(printf '%s' "$input" | "${GATES}" hook git-cwd openspec-scaffold 2>/dev/null)"
if [ -n "${effective_dir}" ] && [ -d "${effective_dir}" ]; then
  cd "${effective_dir}" 2>/dev/null || true
fi
resolved_repo="$(pwd)"

if out="$("${GATES}" discipline check-propose --scaffold 2>&1)"; then
  exit 0
fi

echo "${out} (repository: '${resolved_repo}')" >&2
exit 2
