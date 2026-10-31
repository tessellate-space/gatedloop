#!/usr/bin/env bash
# PreToolUse on Bash: deny a `git merge` INTO the integration target unless a
# fresh `live-check` marker matches the INCOMING tree (a merge into any other
# branch is not integration and passes -- hook-correctness D2). Converts "live-check blocks the merge"
# (skills/tdd-apply/SKILL.md §7.5) into an invariant (design D1).
#
# O(1) hash compare via `gates gate-marker check` — never re-runs live-check
# under the hook. The marker records the branch-HEAD commit's tree, ledger-
# blind NORMALIZED (`.gatedloop/runs/**` stripped before hashing, so a staged
# ledger row can never stale it -- `fix-marker-mechanics` design D1); by the
# time `gates run live-check` runs at change completion, every task is
# already committed, so HEAD's tree is what would be merged from the branch
# itself. A marker can also carry a `verdict: "skip"` (a resolved-empty
# live-check, e.g. a docs-only diff or no `live-check` declared anywhere) --
# `gate-marker check` reports it as satisfied, naming the verdict, not a
# silent pass (design D2).
#
# The tree checked is the INCOMING one, not the current HEAD (design D4):
# this hook extracts the merge SOURCE ref from the `git merge` invocation
# (the trailing non-flag argument) and tries its tree first, falling back to
# the current HEAD tree -- correct for the run-after-fast-forward case, and
# what this hook always checked before this design landed. A denial names
# every tree tried. A sequencer step (`--continue`) has no ref and checks
# HEAD's tree; any other merge with no single parsable ref (an octopus) is
# denied as such (hook-correctness D1).
#
# The same tree must also carry a fresh, UNSCOPED `ci` marker (scale-gate-cost
# D2): a per-task commit may ride a surface-scoped `ci` green, the merge never
# does.
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
ref=""
ref_parse=""
switch_before="1"
switch_branch=""
eval "$(printf '%s' "$input" | python3 "${MATCHER}" git-merge 2>/dev/null)"

[ "${matched}" = "1" ] || exit 0

# Resolve the repository the guarded command will actually run in (design D1
# of worktree-native-loop): computed from the command itself, falling back
# to the hook's own `cwd`, then `CLAUDE_PROJECT_DIR`, then `pwd`.
effective_dir="$(printf '%s' "$input" | "${GATES}" hook git-cwd git-merge 2>/dev/null)"
if [ -n "${effective_dir}" ] && [ -d "${effective_dir}" ]; then
  cd "${effective_dir}" 2>/dev/null || true
fi
resolved_repo="$(pwd)"

# hook-correctness D2: only a merge INTO the integration target is gated.
# Syncing the target into a change branch, or one branch into another, needs
# no marker (none could ever exist for it). Only an explicit
# `not-integrating` skips the checks -- an error keeps the merge gated -- and
# never when the same command switches branches before merging, since the
# checkout seen here is then not the one the merge lands on.
#
# friction-fixes D5: when the command switches first, the branch the switch
# names decides instead (`merge-scope --branch`). A switch the matcher could
# not resolve to one branch leaves `switch_branch` empty and the merge gated,
# and every denial below then says how to get past it.
if [ "${switch_before}" = "1" ] && [ -n "${switch_branch}" ]; then
  merge_scope="$("${GATES}" discipline merge-scope --branch "${switch_branch}" 2>/dev/null)"
  if [ "${merge_scope}" = "not-integrating" ]; then
    exit 0
  fi
else
  merge_scope="$("${GATES}" discipline merge-scope 2>/dev/null)"
  if [ "${merge_scope}" = "not-integrating" ] && [ "${switch_before}" = "0" ]; then
    exit 0
  fi
fi

deny() {
  if [ "${switch_before}" = "1" ] && [ -z "${switch_branch}" ]; then
    echo "gatedloop: this command switches branches before merging, and the hook could not tell which branch the merge lands on; run the merge as its own command after the switch." >&2
  fi
  exit 2
}

# hook-correctness D1: a merge that names no single incoming ref is denied
# for THAT reason. Falling back to HEAD's tree here used to report a "stale"
# marker for a live-check that was green all along.
if [ "${ref_parse}" = "failed" ]; then
  echo "gatedloop: merge denied — no incoming ref could be parsed from the command. Run the merge as a bare \`git merge --squash <change>\` line." >&2
  deny
fi

head_tree="$(git rev-parse --verify --quiet HEAD^{tree} 2>/dev/null)"
if [ -z "${head_tree}" ]; then
  echo "gatedloop: could not resolve HEAD's tree in '${resolved_repo}' — denying the merge until the git state is resolved." >&2
  deny
fi

# design D4 (see header): try the incoming ref's tree first, then HEAD's.
source_tree=""
if [ -n "${ref}" ]; then
  source_tree="$(git rev-parse --verify --quiet "${ref}^{tree}" 2>/dev/null)"
fi

trees=("${head_tree}")
if [ -n "${source_tree}" ] && [ "${source_tree}" != "${head_tree}" ]; then
  trees=("${source_tree}" "${head_tree}")
fi

# cross-worktree-evidence D2: with a parsed ref, the marker check also reads
# the store of the worktree holding that branch, when it is another worktree
# -- a lane's green gates live in the lane's own store. A marker still counts
# only for the exact tree compared; a denial names every store it read.
ref_args=()
if [ -n "${ref}" ]; then
  ref_args=(--ref "${ref}")
fi

denial=""
ok="0"
matched_tree=""
for t in "${trees[@]}"; do
  if out="$("${GATES}" gate-marker check live-check "${t}" ${ref_args[@]+"${ref_args[@]}"} 2>&1)"; then
    ok="1"
    matched_tree="${t}"
    break
  fi
  denial="${denial}${out}"$'\n'
done

if [ "${ok}" != "1" ]; then
  printf '%s' "${denial}" >&2
  echo "gatedloop: merge denied in '${resolved_repo}' — run \`gates run live-check\` on the change branch's head; it must pass green before the merge." >&2
  deny
fi

# scale-gate-cost D2: "full ci is always the last word" — a per-task commit
# may ride a scoped marker, but the merge never does. `--require-scope full`
# refuses a marker whose recorded scope is a surface name (staging nothing
# and re-running `gates run ci` selects "full" per D1, so satisfying this is
# just that one call). Checked against the SAME tree the live-check marker
# matched (the incoming ref's tree, or HEAD's on fallback -- design D4), so
# both pieces of evidence speak about one tree. A project that never declares
# a scoped override always passes here, since every marker it ever writes is
# scope "full".
if ! ci_out="$("${GATES}" gate-marker check ci "${matched_tree}" --require-scope full ${ref_args[@]+"${ref_args[@]}"} 2>&1)"; then
  echo "${ci_out}" >&2
  echo "gatedloop: merge denied — the branch head needs an unscoped \`gates run ci\` (stage nothing, then run it) before the merge." >&2
  deny
fi

# Effect-layer taint (enforce-at-the-effect D7): even with a green live-check on
# the head, refuse a change whose ledger carries an unresolved taint. The Stop-hook
# reflog audit records a taint when it finds a commit with no green-ci record (a
# mid-branch bypass that lost per-task integrity, design D8). Cleared cheaply by one
# green `gates run ci` on the head, so blocking is not punitive.
#
# escalation-outcomes D5 part 3: run the audit HERE first. A commit created
# after the last session stop was never walked by the Stop hook's audit, so
# it would otherwise be neither tainted nor classified when the merge is
# decided. The audit is a rev-list plus a ledger read -- no gate re-run -- so
# it fits the hook budget; its own report and exit code are not the decision
# (the taint check below is), so both are discarded.
# With an incoming ref, the audit is of the change that ref names, run where
# its branch lives -- bare, it resolved the current branch (the target), so a
# merge from the primary audited nothing.
"${GATES}" audit ${ref_args[@]+"${ref_args[@]}"} >/dev/null 2>&1 || true
# merge-step (specloop PR 100): during an integrating merge the current branch is
# the target, which names no change, so a bare `taint check` never fired.
# With the incoming ref it reads THAT change's ledger as the ref carries it
# (the same function `gates merge` step 1 calls); a ref naming no change
# falls back to the current branch.
taint_rc=0
if [ -n "${ref}" ]; then
  taint_out="$("${GATES}" taint check --ref "${ref}" 2>&1)" || taint_rc=$?
else
  taint_out="$("${GATES}" taint check 2>&1)" || taint_rc=$?
fi
if [ "${taint_rc}" -ne 0 ]; then
  echo "${taint_out}" >&2
  echo "gatedloop: merge denied in '${resolved_repo}' — this change carries an unresolved taint; re-verify the head with \`gates run ci\`, then merge." >&2
  deny
fi

# >>> acceptance-gate D4
# Human acceptance of the increment, only where the manifest declares
# `approval.acceptance`. Checked against the SAME tree the live-check and
# unscoped-ci markers matched, so all four pieces of merge evidence speak
# about one tree. A ledger read (the latest `acceptance` row for the
# normalized tree), never a gate run. With no policy declared the check
# passes and prints only to stdout, which is discarded here -- so the hook's
# behaviour is byte-identical to before. The `ask` permission rule on
# `git merge` stays: the ask is the human's presence at the merge, the
# accept row is the human's recorded verdict on the behaviour.
if ! acc_out="$("${GATES}" acceptance check "${matched_tree}" 2>&1)"; then
  echo "${acc_out}" >&2
  echo "gatedloop: merge denied in '${resolved_repo}' — the declared acceptance policy requires a human to accept this tree first: \`gates acceptance brief <change>\`, then \`gates acceptance attest <change>\`." >&2
  deny
fi
# <<< acceptance-gate D4

exit 0
