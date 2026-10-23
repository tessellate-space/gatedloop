#!/usr/bin/env bash
# PreCompact: persist the current change + first unchecked task so a long
# unattended run that compacts mid-loop doesn't lose its place. This is a
# convenience snapshot, not the source of truth -- resumability already
# comes from git (done <=> committed: `git checkout <change>` + `openspec
# status` always finds the real first unchecked task). The state file just
# saves that lookup immediately after compaction, when context is thinnest.
# Ephemeral, per-worktree, under .git/ -- like the markers, never committed.
set -uo pipefail

if [ -n "${CLAUDE_PLUGIN_ROOT:-}" ]; then
  GATES="${CLAUDE_PLUGIN_ROOT}/bin/gates"
else
  GATES="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/bin/gates"
fi

cd "${CLAUDE_PROJECT_DIR:-$(pwd)}" 2>/dev/null || true

gitdir="$(git rev-parse --git-dir 2>/dev/null || echo .git)"
statedir="${gitdir}/gatedloop"
mkdir -p "${statedir}" 2>/dev/null || true
statefile="${statedir}/loop-state.json"

next="$("${GATES}" discipline next-task 2>/dev/null)"
if [ $? -ne 0 ] || [ -z "${next}" ]; then
  # Not on a change branch, or no unchecked task -- nothing to persist.
  rm -f "${statefile}" 2>/dev/null || true
  exit 0
fi

change="${next%%$'\t'*}"
task="${next#*$'\t'}"

python3 -c '
import json, sys, datetime
change, task, path = sys.argv[1], sys.argv[2], sys.argv[3]
data = {
    "change": change,
    "next_task": task,
    "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
}
with open(path, "w") as f:
    json.dump(data, f)
' "${change}" "${task}" "${statefile}" 2>/dev/null || true

exit 0
