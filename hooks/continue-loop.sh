#!/usr/bin/env bash
# Stop hook (command-type -- prompt-type hooks don't exist for Stop, design
# D3): continue the loop instead of handing control back when a change
# branch is checked out, tasks.md has an unchecked task, and the tree is
# clean at a task boundary. Bounded by the same thing that bounds the loop
# today -- the gates -- so a halted/gate-blocked run (dirty tree) doesn't
# continue, plus two explicit guards against runaway: `stop_hook_active`
# (Claude Code re-invokes a Stop hook with this set when its own prior
# block already triggered another turn -- refusing to re-block here is
# what makes an infinite loop structurally impossible) and a per-session
# continue cap as defense-in-depth.
set -uo pipefail

if [ -n "${CLAUDE_PLUGIN_ROOT:-}" ]; then
  GATES="${CLAUDE_PLUGIN_ROOT}/bin/gates"
else
  GATES="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/bin/gates"
fi

input="$(cat)"

stop_hook_active="$(printf '%s' "$input" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    d = {}
print("true" if d.get("stop_hook_active") else "false")
' 2>/dev/null)"
session_id="$(printf '%s' "$input" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    d = {}
print(d.get("session_id") or "none")
' 2>/dev/null)"

cd "${CLAUDE_PROJECT_DIR:-$(pwd)}" 2>/dev/null || true

# Layer-3 post-hoc audit (enforce-at-the-effect D6/D7): walk the change branch's
# new commits and taint the durable ledger for any with no green-ci record -- a
# commit that slipped layers 1-2 (e.g. --no-verify, or a stripped CLAUDECODE).
# Runs on EVERY stop -- continue or handoff, re-invocation or not -- so a bypass
# committed in any turn is caught. Detection only: it emits no decision:block and
# so cannot spin the loop, and its stdout is discarded so it never pollutes the
# continuation-decision JSON emitted below (its loud report goes to stderr, and
# the taint it records blocks the merge regardless of whether stderr is surfaced).
"${GATES}" audit >/dev/null || true

# token-ledger D1: cost the task in flight (or, with none, the unattributed
# bucket) up to this stop, so a halted or abandoned task is costed too. On
# every stop, re-invocations included, and before the continue decision: the
# usage row it appends never counts as a dirty tree there. Counts only, read
# from the hook input's transcript; nothing here can block or fail the stop.
transcript="$(printf '%s' "$input" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    d = {}
p = d.get("transcript_path") if isinstance(d, dict) else None
print(p if isinstance(p, str) else "")
' 2>/dev/null)"
if [ -n "${transcript}" ]; then
  "${GATES}" usage record --transcript "${transcript}" >/dev/null 2>&1 || true
else
  "${GATES}" usage record >/dev/null 2>&1 || true
fi

if [ "${stop_hook_active:-false}" = "true" ]; then
  exit 0
fi

# Defense-in-depth cap, independent of the stop_hook_active guard above:
# never continue more than 50 times in one session, tracked per-worktree
# under .git/ (ephemeral, like the markers -- never committed).
MAX_CONTINUES=50
gitdir="$(git rev-parse --git-dir 2>/dev/null || echo .git)"
countdir="${gitdir}/gatedloop/stop-continues"
mkdir -p "${countdir}" 2>/dev/null || true
countfile="${countdir}/${session_id}"
count=0
[ -f "${countfile}" ] && count="$(cat "${countfile}" 2>/dev/null || echo 0)"
case "${count}" in ''|*[!0-9]*) count=0 ;; esac
if [ "${count}" -ge "${MAX_CONTINUES}" ]; then
  exit 0
fi

next_task="$("${GATES}" discipline check-continue 2>/dev/null)"
rc=$?
if [ ${rc} -ne 0 ]; then
  exit 0
fi

echo $((count + 1)) > "${countfile}" 2>/dev/null || true

python3 -c 'import json, sys; print(json.dumps({"decision": "block", "reason": sys.argv[1]}))' \
  "continue from: ${next_task}"
exit 0
