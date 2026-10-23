# fix-marker-mechanics

## Why

A week of real use (issues #9, #10, #14, #16, #17) showed the gate-marker mechanics
turning every merge into a chase: a green gate appends its own ledger row *after*
recording the marker's tree hash, so committing the row the design says to commit
stales the marker it depends on (tdd-apply §5h is literally unfollowable — no ledger
file was ever committed in 46 task commits of `harden-unattended-loop`); a
legitimately-skipped live-check (docs-only diff, or no live-check declared anywhere)
writes no marker, so `gate-merge` denies every merge with no honest way to satisfy it —
a contract violation at the composition level ("skipped cleanly" upstream, permanent
denial downstream); two surfaces binding the same live-check recipe run it twice
back-to-back (wasted wall-clock, and non-idempotent suites produce flaky failures that
look real); and `gate-merge` compares the marker against the merging checkout's HEAD
tree while the guidance says to refresh it on the branch head, which for a squash-merge
flow can never match. Each defect costs a full extra suite run or an unmergeable state;
the field reports say the surrounding mechanics are sound and worth keeping exactly as
they are.

## What Changes

- **Ledger-excluded marker trees.** The tree hash a marker records — and the hash a
  marker check compares against — excludes `.specloop/runs/**` (the durable ledger).
  Normalization happens at both ends inside `bin/gates` (`_write_marker` /
  `gate-marker check`); hooks keep passing raw trees and are otherwise unchanged. A
  gate's own ledger row can no longer stale the marker it just wrote, killing the
  marker chase at task commits, at merge time, and in serialized merge lanes
  (#10, #14 item 3, #16 item 5, #17 item 1).
- **Ledger-grade commits.** A staged diff consisting *solely* of `.specloop/runs/**`
  paths is allowed by `discipline check-commit` with an explicit printed verdict —
  requiring a fresh `ci` marker over a delta the marker hash cannot even see proves
  nothing (the merge-row commit in tdd-apply §7.5 step 5 stops re-triggering the chase).
- **Recorded skip verdicts.** A `gates run live-check` that resolves zero checks —
  empty hot set, hot surfaces without a `live-check`, or the gate undeclared on any
  surface — writes a marker carrying `verdict: "skip"` plus the evidence the current
  skip message prints (baseline kind, merge target, files considered), and a ledger
  row. `gate-merge` accepts a skip marker on a matching tree; a *missing* marker still
  denies, so "skipped" stays distinguishable from "never ran", and a declared
  live-check that ran red still writes nothing (#9, #14 item 1, #17 item 2). The
  design comment guarding the current no-marker skip (bin/gates ~2738) is answered,
  not deleted — see design.md D2.
- **Recipe dedupe.** Identical live-check commands across hot surfaces in a single run
  (including `--all`) run once, attributed to every surface that binds them
  (#14 item 2, #17 item 3).
- **Merge validates the incoming ref's head tree.** `gate-merge` resolves the ref
  being merged from the `git merge` invocation and checks the live-check marker
  against *that* head's tree (falling back to the checkout's HEAD tree), matching how
  the marker is recorded — on the branch head — and the misleading "run live-check on
  the branch head first" guidance becomes true (#17 item 5).
- **Followable prompts.** `skills/tdd-apply/SKILL.md` §5h and
  `agents/tdd-implementer.md` are updated to the new mechanics: "stage the ledger row
  with the commit" becomes an executable instruction rather than a denial loop (#10).

## Capabilities

### New Capabilities

(none — every fix tightens behavior the `gate-binding` capability already owns)

### Modified Capabilities

- `gate-binding`: the marker freshness compare becomes ledger-blind
  (`.specloop/runs/**` excluded from recorded/compared tree hashes); the existing
  "empty change-level hot set is reported with evidence" requirement is extended so
  the evidence is *recorded* as a skip verdict the merge gate accepts, not only
  printed; identical live-check recipes dedupe within one run; the merge gate
  validates the incoming ref's head tree; ledger-only staged diffs earn a
  ledger-grade commit verdict.

## Impact

- `bin/gates`: marker write/check normalization, live-check skip verdict + dedupe,
  `discipline check-commit` ledger-grade rung, marker payload gains
  `verdict`/`evidence` fields, ledger row gains a `verdict` key.
- `hooks/gate-merge.sh`: resolve the incoming merge ref's tree; corrected denial
  guidance. (Which *commands* trigger the hook is sibling `harden-hook-matching`'s
  scope — this change only decides which tree a fired hook validates.)
- `skills/tdd-apply/SKILL.md` (§5h, §7.5 step 5), `agents/tdd-implementer.md`.
- `tests/`: the shim's marker/skip/dedupe behavior joins the oracle-backed suite.
- **Ordering**: independent of siblings `worktree-native-loop` (marker keying across
  worktrees), `harden-hook-matching` (hook command matching), and
  `scope-audit-to-branch-commits` (taint scoping). Compatible with the merged-but-
  unimplemented `scale-gate-cost`, whose marker/ledger `scope` field is additive and
  orthogonal to this change's `verdict` field; whichever is implemented second carries
  both fields, and tree normalization applies identically to scoped markers.
- **Not breaking** for adopters: markers are ephemeral per-worktree files, so no
  stored state migrates; a pre-existing marker without `verdict` is read as a pass.
