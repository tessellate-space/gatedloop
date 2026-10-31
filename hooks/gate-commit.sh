#!/usr/bin/env bash
# PreToolUse on Bash: deny a `git commit` unless it satisfies `gates
# discipline check-commit` for the tree that would actually be committed.
# Converts "never commit on red ci" from a prompt instruction
# (skills/tdd-apply/SKILL.md §5f) into an invariant the model cannot violate
# (design D1 of harden-unattended-loop).
#
# The one entry point (design D2 of unblock-parallel-planning) classifies
# the staged diff: planning-only (openspec/** plus the manifest's declared
# conventions.rules-doc) is satisfied by manifest + OpenSpec artifact
# validation; anything else falls through to the O(1) marker compare this
# hook always used — never re-running `ci` itself, since a full suite under
# a hook timeout is unusable (AUTOMATION.md §1). The marker records `git
# write-tree` of the staged INDEX, not the working tree — tdd-apply stages a
# subset, never `git add .`, and a partial `git add` that silently drops
# files (task 0.6) must still be caught: the working tree can match a green
# `ci` while the index does not, and only the index is what gets committed.
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
eval "$(printf '%s' "$input" | python3 "${MATCHER}" git-commit 2>/dev/null)"

# Generous, not exact, command matching (design Risks: raises the floor
# against accidents, not a jail against a determined, differently-phrased
# bypass). Anything that isn't a git-commit invocation passes through
# (the shared matcher, `_gate_match.py`, decides this on the parsed
# command's subcommand token, not a raw substring -- design D1/D2 of
# harden-hook-matching).
[ "${matched}" = "1" ] || exit 0

# Resolve the repository the guarded command will actually run in (design D1
# of worktree-native-loop): computed from the command itself -- `git -C`, a
# `GIT_DIR`/`GIT_WORK_TREE` assignment, or the last `cd` before the git
# invocation -- falling back to the hook's own `cwd`, then
# `CLAUDE_PROJECT_DIR`, then this process's own `pwd`. This is what makes a
# background agent's `cd <worktree> && git commit …` evaluate the worktree,
# not the harness session's checkout.
effective_dir="$(printf '%s' "$input" | "${GATES}" hook git-cwd git-commit 2>/dev/null)"
if [ -n "${effective_dir}" ] && [ -d "${effective_dir}" ]; then
  cd "${effective_dir}" 2>/dev/null || true
fi
resolved_repo="$(pwd)"

# hook-correctness D7: a branch another worktree also holds is refused before
# any marker work -- the commit would move the ref under that checkout.
# loop-hardening D7: the shim's own output names the cause -- the worktrees
# holding the branch, or a manifest it could not parse -- so the hook adds
# no verdict of its own on top of it.
if ! wt_out="$("${GATES}" discipline check-worktree 2>&1)"; then
  echo "${wt_out}" >&2
  echo "gatedloop: commit denied in '${resolved_repo}' — see above." >&2
  exit 2
fi

tree="$(git write-tree 2>/dev/null)"
if [ -z "${tree}" ]; then
  echo "gatedloop: could not compute the staged tree (git write-tree failed) in '${resolved_repo}' — denying the commit until the git state is resolved." >&2
  exit 2
fi

# unblock-authored-lock D1: check-commit names the grade that allowed the
# commit in a one-token file, so the lock below is skipped on a ledger-grade
# verdict by reading that token, never by matching the printed line.
verdict_file="$(mktemp "${TMPDIR:-/tmp}/gatedloop-verdict.XXXXXX" 2>/dev/null)"
if [ -z "${verdict_file}" ]; then
  echo "gatedloop: could not create a temporary file for the commit verdict in '${resolved_repo}' — denying the commit." >&2
  exit 2
fi
trap 'rm -f "${verdict_file}"' EXIT

# token-ledger D1: an allowed commit costs the task it closes -- the hook
# input's transcript, read by the shim, counts only. The row is staged so it
# lands in this commit. Nothing here can deny the commit: every outcome of the
# record, a failure included, falls through to the allow that follows it.
record_usage() {
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
    "${GATES}" usage record --stage --transcript "${transcript}" >/dev/null 2>&1 || true
  else
    "${GATES}" usage record --stage >/dev/null 2>&1 || true
  fi
}

if out="$("${GATES}" discipline check-commit "${tree}" --verdict-file "${verdict_file}" 2>&1)"; then
  # A ledger-grade commit stages only `.gatedloop/runs/**`: a ledger row
  # cannot change a test, so the lock has nothing to judge in it. Its usage
  # is still recorded; the staged row keeps the commit ledger-only.
  if [ "$(cat "${verdict_file}" 2>/dev/null)" = "ledger" ]; then
    record_usage
    exit 0
  fi
  # split-test-author D4: the authored tests are locked wherever the marker
  # is checked -- a placed or held test edited, or no red run after
  # placement, denies the commit. Passes when no handoff exists.
  if tests_out="$("${GATES}" tests check 2>&1)"; then
    record_usage
    exit 0
  fi
  echo "${tests_out}" >&2
  echo "gatedloop: commit denied in '${resolved_repo}' — the authored tests are locked; see above." >&2
  exit 2
fi

echo "${out}" >&2
echo "gatedloop: commit denied in '${resolved_repo}' — run \`gates run ci\` and stage exactly what it tested, then commit again." >&2
exit 2
