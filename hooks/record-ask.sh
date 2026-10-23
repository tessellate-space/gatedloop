#!/usr/bin/env bash
# PreToolUse on AskUserQuestion: record a human turn in the loop as an
# `intervention` ledger row with cause `ask` (escalation-outcomes design D4).
# The interactive loop's "pause and ask" IS a question-tool call, so the tool
# call is the event, and this hook sees it without the prompt having to
# remember to record it.
#
# It only records -- it never denies or alters the tool call. It always exits
# 0: a recording failure is reported on stderr and swallowed, because it must
# never block the human turn it was trying to record. Off a change branch
# (the merge target, onboarding's many questions) it is a silent no-op.
set -uo pipefail

if [ -n "${CLAUDE_PLUGIN_ROOT:-}" ]; then
  GATES="${CLAUDE_PLUGIN_ROOT}/bin/gates"
else
  GATES="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/bin/gates"
fi

input="$(cat)"

# The first question's text, truncated to 200 characters -- the detail a
# reader of the outcomes view needs to see what was asked, not the whole form.
question="$(printf '%s' "$input" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    d = {}
qs = (d.get("tool_input") or {}).get("questions") or []
q = qs[0].get("question", "") if qs and isinstance(qs[0], dict) else ""
print(str(q)[:200])
' 2>/dev/null)"

# Resolve the repository the session acts on (design D1 of
# worktree-native-loop): a tool call with no shell command, so `gates hook
# git-cwd` (no kind) falls through to the hook's own `cwd`, then
# `CLAUDE_PROJECT_DIR`, then `pwd` -- the same rungs every other hook uses.
effective_dir="$(printf '%s' "$input" | "${GATES}" hook git-cwd 2>/dev/null)"
if [ -n "${effective_dir}" ] && [ -d "${effective_dir}" ]; then
  cd "${effective_dir}" 2>/dev/null || true
fi

# A change branch is one with a change directory of the same name (branch
# name = change name). Anything else -- the merge target, a detached HEAD, an
# unrelated branch -- is not the loop's timeline, so nothing is recorded.
branch="$(git branch --show-current 2>/dev/null)"
case "${branch}" in
  ""|main|master) exit 0 ;;
esac
[ -d "openspec/changes/${branch}" ] || exit 0

if ! out="$("${GATES}" intervention record ask --change "${branch}" --detail="${question}" 2>&1)"; then
  echo "gatedloop: could not record the question as an intervention (the question proceeds): ${out}" >&2
fi
exit 0
