#!/usr/bin/env bash
# PreToolUse on Write: deny authoring a plan artifact (anything under
# openspec/changes/<name>/ but tasks.md) from inside that change's
# implementation (design D9). The change is read from the written path and
# its state -- a branch ahead of the target, or a task-start ledger row --
# never from HEAD, so a detached merge checkout or a plan/* branch can still
# plan (hook-correctness D5). tasks.md is excluded: flipping its checkboxes
# during implementation is normal activity on the change's own branch --
# `gates discipline check-propose` makes that distinction, not this script.
set -uo pipefail

if [ -n "${CLAUDE_PLUGIN_ROOT:-}" ]; then
  GATES="${CLAUDE_PLUGIN_ROOT}/bin/gates"
else
  GATES="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/bin/gates"
fi

input="$(cat)"
file_path=""
eval "$(printf '%s' "$input" | python3 -c '
import json, shlex, sys
try:
    d = json.load(sys.stdin)
except Exception:
    d = {}
print("file_path=" + shlex.quote(d.get("tool_input", {}).get("file_path", "")))
' 2>/dev/null)"

[ -n "${file_path}" ] || exit 0

# Resolve the repository this Write call is targeting (design D1 of
# worktree-native-loop): this hook fires on a Write tool call, which carries
# no shell command to derive a directory from, so `gates hook git-cwd` (no
# kind) falls straight through to the hook's own `cwd`, then
# `CLAUDE_PROJECT_DIR`, then `pwd` -- identical to before this design, kept
# as one code path so both hook kinds share the same fallback rungs.
effective_dir="$(printf '%s' "$input" | "${GATES}" hook git-cwd 2>/dev/null)"
if [ -n "${effective_dir}" ] && [ -d "${effective_dir}" ]; then
  cd "${effective_dir}" 2>/dev/null || true
fi
resolved_repo="$(pwd)"

# Make the path repo-relative for the shim's matcher, best-effort.
rel="${file_path#"${resolved_repo}/"}"

if out="$("${GATES}" discipline check-propose "${rel}" 2>&1)"; then
  exit 0
fi

echo "${out} (repository: '${resolved_repo}')" >&2
exit 2
