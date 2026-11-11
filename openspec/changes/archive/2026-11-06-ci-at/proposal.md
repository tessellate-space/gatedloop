# Proposal: ci-at

## Why

The commit hooks require a green `ci` marker for every task commit, and most diffs that
are not confined to one scoped surface pay the full `ci` for it. A field report (#162,
an adopter on gatedloop 0.11.0) counted hundreds of `ci` runs in two weeks, most of
the time at full scope. Most of those runs came from per-task commits made
before the change was READY. No red `ci` in that window caught a defect that one full
`ci` at READY would have missed and that the task's `unit` run had not already caught.
`ci` is serialized machine-wide, so every per-task full run blocks every other lane.
The full, unscoped `ci` already has the last word at READY and at the merge
(gate-economics §4). This change lets a project choose *when* that full run happens.
It does not change *whether* it happens.

## What Changes

- **`loop.ci-at: task | ready`** (default `task`, opt-in). Under `ready`, on a branch
  that names an active change, a task commit is allowed on a green `unit` marker for
  the staged tree plus the convention review. A green `ci` marker still allows it too.
  `gates validate` refuses `ready` when no global `unit` gate is declared.
- The commit check allows a commit on a `unit` marker with a new verdict token, `unit`.
  Its allow line names the mode, and both commit hooks print it. Both hooks run the
  same check and the same authored-test lock after it.
- **The full `ci` moves to READY.** Under `ready`, `gates ledger record-ready` refuses
  (exit 1, no row) unless a green unscoped `ci` row names the head's tree. `gates merge`
  is unchanged: it proves an unscoped `ci` on the head and runs a full `ci` on the merged
  tree.
- **The audit reads the evidence the mode accepts.** Under `ready`, the reflog audit and
  the merge's read-only check also accept a green `unit` row for a commit's tree. A
  unit-gated task commit is gated, not tainted. A commit with neither row still taints.
- **The attempt budget follows the commit gate.** Under `ready`, a red `unit` run after
  a task's RED run counts where a red `ci` counts today. `gates stats --outcomes` counts
  a restart as recovered on a green `unit` under `ready`.
- `gates task start` and `gates tests handoff` name the commit gate in effect, so the
  loop runs that gate without reading the manifest.
- **`loop.ci-scope: single | union`** (default `single`, opt-in). Under `union`, a
  staged diff that hits two or more non-catch-all surfaces, every one of which declares
  a `ci` override, runs the union of those overrides instead of the full `ci`. An
  unmatched path, or a hot surface without an override, still runs the full `ci`. A
  union marker satisfies a commit and never the READY or merge requirement.
- `skills/tdd-apply/SKILL.md` and `agents/tdd-implementer.md` state the per-task gate
  under each mode, and the unscoped `ci` before `record-ready` under `ready`.
- Two adoption items, `ci-at` and `ci-scope`, so `/gatedloop:upgrade` offers both. The
  `surface-key` predicate accepts a dotted key (`gates.ci`).
- SETUP.md, AUTOMATION.md, README.md and `docs/gate-economics.md` document both keys.

Nothing changes for a project that sets neither key. The only output difference is a
stderr line from `gates task start` and `gates tests handoff` that names the commit gate.

## Rejection test

| Question | Answer |
|---|---|
| Does it author an artifact? | No. |
| Does it know a stack command? | No. It moves when the abstract `ci` gate runs and selects among overrides the adopter already declared. Every invocation stays `gates run <gate>`. |
| Does it make a stated guarantee enforceable? | It keeps one enforced: the full `ci` still gates READY (now refused in code under `ready`, where today it is only reported) and the merge. The audit and the commit hooks enforce the per-task gate the mode names. |
| Does it get a team running faster? | **Yes.** Per-task full `ci` runs were about 70 % of `ci` time in the field report, and `ci` is serialized machine-wide. |

Against the single question: the commit phase stays at `close`. The gate the hook holds
changes, and the guarantee moves to READY and the merge, where it is already enforced.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `loop-enforcement`: `loop.ci-at` is declared and validated. A commit may be gated on
  `unit` under `ready`, the audit accepts that evidence, `record-ready` requires the
  full `ci` under `ready`, and the shim names the commit gate in effect.
- `gate-binding`: `loop.ci-scope` is declared and validated, and selects union-scoped
  `ci`. A union marker is a scoped marker. The commit check's `unit` verdict is the
  same at both commit layers.
- `retry-budget`: under `ready`, a red `unit` run counts toward the failed-attempt
  count.
- `escalation-record`: a restart's recovery is read from the commit gate in effect.
- `upgrade-adoption`: the `ci-at` and `ci-scope` items, and dotted `surface-key`
  predicates.

## Impact

- `bin/gates`: loop-key validation, `cmd_run` (unit marker, ci union),
  `_check_commit_verdict`, `cmd_ledger record-ready`, `_GreenCiMatcher` and its two
  callers, `_attempt_state`, restart recovery in the outcomes view, `cmd_task start`,
  `gates tests handoff`, and the adoption `surface-key` predicate.
- `hooks/gate-commit.sh`, `templates/git-hooks/pre-commit`: the `unit` token and
  gate-neutral denial lines. Adopters refresh the git-layer copy through the existing
  `git-hook-refresh` item.
- `schema/gates.schema.json`, `adoption/catalog.json`.
- `skills/tdd-apply/SKILL.md`, `agents/tdd-implementer.md`.
- SETUP.md, AUTOMATION.md, README.md, `docs/gate-economics.md`.
- No new subcommand, flag, ledger field or exit code, so `tests/contract.json` does not
  change. Target release: 0.12.0.
