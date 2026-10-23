# Proposal: worktree-native-loop

## Why

A week of field evidence (#15, #16, #17, #18) shows adopters running the loop the way
it was always meant to scale — N implementer/author agents in isolated git worktrees
feeding one serialized merge lane — and paying a folklore tax for it: hooks that
validate the wrong checkout, marker retry loops, forced branch renames, filler delta
specs written just to commit a backlog proposal, and 4+ interim pushes per merge
session. Every one of these was worked around by hand and rediscovered by every new
agent. The pattern held (#15: zero collisions, zero false "safe" verdicts across 25
changes), so the frictions are worth fixing rather than documenting around: the
multi-worktree lane becomes a first-class supported pattern.

## What Changes

- **Hooks resolve the repo of the git invocation, not the session** (#17 item 7): all
  gate hooks currently trust the hook input's `cwd` — the harness *session* cwd. A
  background agent whose shell resets cwd per call issues `cd <worktree> && git
  commit` (or `git -C <worktree> …`); the hook then checks the *primary* checkout's
  clean index and denies with "no ci marker". The effective directory is now resolved
  from the guarded command itself (`git -C`, `GIT_DIR`/`GIT_WORK_TREE` assignments,
  the last `cd` before the git token), with the session cwd only as a fallback. The
  branchy parsing lands in the shim as a tested subcommand, not in bash.
- **Marker contention diagnosed and closed** (#16 item 1): markers already live under
  the per-worktree git dir, so the observed "single-slot, last-write-wins" contention
  is the session-cwd defect above — mis-resolved checks all read one checkout's
  marker store. The cwd fix removes the observed contention; on top of it, markers
  become tree-keyed (one file per recorded tree, small LRU per gate) so a lane
  alternating between trees never clobbers its own still-valid marker.
- **Accepted propose/scaffold branch patterns become manifest-declared** (#16 item
  2): an optional manifest block declares additional accepted branch globs; absent,
  behavior is exactly today's (merge target + `plan/*`). The shares-history-with-
  target guard stays for every non-target branch.
- **Stage-appropriate planning-grade validation** (#16 item 3): a deliberately
  proposal-only change is a legitimate backlog state. The planning-grade commit path
  validates a change at the stage it is at instead of demanding delta specs that
  don't exist yet — never silently, always naming the stage it validated.
- **check-implement / check-archive accept a sound local merge target** (#17 item 6):
  check-archive's guarantee is *ordering* (merge precedes archive), which a local
  counterpart of the merge target proves — accepted with a loud "not on origin yet —
  push before ending the session" advisory. check-implement keeps requiring origin
  under approval policy `review` (the attestation is anchored to the forge PR) and
  accepts the local counterpart under policy `self`.
- **Opt-in cross-worktree gate mutex** (#18 item 3): an optional manifest block names
  gates to serialize machine-wide; `gates run` takes a stdlib file lock under the
  *common* git dir (shared by all worktrees) around the gate command, with a visible
  waiting heartbeat. Absent from the manifest, nothing locks.
- **The worktree-lane pattern is documented as supported** (#15): a docs page records
  the N-worktrees / one-merge-lane topology, stop-before-merge discipline, and the
  load-bearing property that per-worktree directory basenames namespace tooling that
  derives project names from the directory. `gates run` gains a one-line,
  stack-agnostic fresh-worktree hint (pointing only at the adopter's own manifest,
  never naming a package manager) when a gate fails in a worktree with no prior
  gate history.

**Ordering**: this change lands after `fix-marker-mechanics` and
`harden-hook-matching` — all three touch the same hooks and marker code, and this
change's hook edits assume harden-hook-matching's subcommand-token matching is in
place.

## Capabilities

### New Capabilities

- `worktree-lanes`: the supported multi-worktree lane pattern — its documented
  topology and properties, and the fresh-worktree hint from `gates run`.

### Modified Capabilities

- `parallel-planning`: repo resolution for gate enforcement moves from the hook
  input's cwd to the guarded command itself; accepted propose/scaffold branches
  become manifest-declarable; planning-grade validation becomes stage-appropriate
  (proposal-only is committable). (Capability introduced by the merged, not-yet-
  archived `unblock-parallel-planning`.)
- `loop-enforcement`: the gate marker store becomes tree-keyed (multiple recent
  trees per gate, LRU-pruned); check-implement/check-archive accept a sound local
  counterpart of the merge target instead of unconditionally requiring origin.
  (Capability introduced by the merged, not-yet-archived `harden-unattended-loop`.)
- `gate-binding`: the manifest may declare machine-level serialization for named
  gates, enforced by `gates run` with zero-dep file locking.

## Impact

- `hooks/gate-commit.sh`, `gate-merge.sh`, `gate-scaffold.sh`, `gate-archive.sh`,
  `gate-implement.sh`, `gate-propose.sh` — cwd resolution replaced by a shim call.
- `bin/gates` — new hook cwd-resolution subcommand; tree-keyed marker read/write/
  check/prune; `discipline check-commit` stage detection; `discipline
  check-implement`/`check-archive` local-counterpart acceptance; `run` mutex
  acquisition and fresh-worktree hint; manifest validation for the two new blocks.
- `schema/gates.schema.json` — two optional blocks (accepted propose branches; gate
  serialization).
- `tests/` — the new branching shim code (command cwd parsing, marker LRU, stage
  detection, local-counterpart logic, lock behavior) is stdlib-tested.
- `templates/gates.yaml.template`, `SETUP.md`, `AUTOMATION.md`, new `docs/` page —
  document the new blocks and the supported worktree-lane pattern.
- Not touched: marker freshness vs the run's own ledger row and skip-verdict markers
  (owned by `fix-marker-mechanics`); hook command matching (owned by
  `harden-hook-matching`); merge-queue primitive, archive path-segment validation,
  `gates stats`, two-tier ci, changed-file context for ci (#16 items 4–5, #18 items
  1–2, 4–5 remain open).

Refs #15, Refs #16, Refs #17, Refs #18.
