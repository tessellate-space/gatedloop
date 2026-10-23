# The worktree-lane pattern

This page documents a supported topology: N implementer or author agents, each in
its own git worktree, feeding one serialized merge lane in the primary checkout. A
week of field evidence (issues #15–#18) showed this pattern used at scale before it
was ever documented — zero marker collisions, zero false "safe" verdicts across 25
changes — so it is written down here as intended usage, not folklore an agent has to
rediscover per session.

## The topology

```
              worktree A (agent 1)         worktree B (agent 2)
              branch: change-a             branch: change-b
              own index, own markers       own index, own markers
                     |                             |
                     |     task commits, gated      |
                     v                              v
              ┌───────────────────────────────────────────┐
              │        primary checkout (repo root)        │
              │   the ONE serialized merge lane: merges,   │
              │   archives, plan reviews happen here only  │
              └───────────────────────────────────────────┘
```

- One worktree per concurrent agent. An implementer works its own change branch to
  completion inside its own worktree, exactly as the single-checkout loop always
  worked — nothing about `skills/tdd-apply/SKILL.md` or `agents/tdd-implementer.md`
  changes per lane.
- One serialized merge lane in the **primary checkout**: merges, archives, and plan
  review/approval all happen there, one at a time. This is a discipline, not a lock
  gatedloop enforces on merges themselves — the mutex (below) is for gate *commands*,
  not for the act of merging.
- **Stop-before-merge, unchanged.** `agents/tdd-implementer.md` always stops before
  the merge; a worktree lane changes nothing about that boundary. The lane pattern
  is what makes stopping there practical at scale: an implementer's worktree can sit
  idle at "ready to merge" while the merge lane works through other changes without
  blocking the implementer from starting its next task elsewhere.

## What's per-worktree vs repo-wide

| State | Scope | Why |
|---|---|---|
| The working tree and index | per-worktree | `git worktree` gives each lane its own checkout and staging area by construction. |
| The current branch | per-worktree | Two worktrees can never have the same branch checked out at once — git itself enforces this. |
| Gate markers (`gates gate-marker`) | per-worktree | Markers live under `git rev-parse --git-dir`, which is per-worktree. Two lanes never satisfy or invalidate each other's marker (verified end-to-end: `tests/test_worktree_lane_e2e.py`). |
| The durable ledger (`.gatedloop/runs/<change>.jsonl`) | repo-wide (tracked, committed) | It's a versioned file, not an ephemeral cache — every lane's task commits carry their own ledger rows into the same file history. |
| Plan approval / attestation | repo-wide | `.openspec.yaml`'s `approved_by`/`approved_sha` live in the change's own tracked files, resolved against the merge target — not per-worktree state. |
| The resolved merge target | repo-wide | `origin/HEAD` (or local `main`/`master`) is a property of the repository, not of any one worktree. |
| The cross-worktree gate lock (`concurrency.serialize`, below) | repo-wide | Deliberately: it lives under `git rev-parse --git-common-dir`, the one git-dir every worktree of a repo shares. |

## What used to be folklore, now fixed

- **Gate hooks resolve the command's own repository, not the session's.** A
  background agent's shell resets its working directory between calls, so its own
  commands carry their own directory signal (`cd <worktree> && git commit …`, or
  `git -C <worktree> …`). Every gate hook now resolves the directory from that
  signal first — `git -C`, a `GIT_DIR`/`GIT_WORK_TREE` assignment, or the last `cd`
  before the guarded command — falling back to the session's own directory only when
  the command carries none. A denial always names the repository it evaluated, so a
  mis-resolution is diagnosable from the message alone, not a relaunch round.
- **Markers survive a lane alternating between trees.** A serialized merge lane
  moves between several trees in short order (a pre-merge head, the tree just after
  a ledger row is appended, the next branch's head). Markers are keyed by tree, with
  a small bounded history retained per gate — recording a new tree's marker never
  invalidates an older one that's still valid.
- **No forced branch renames.** Proposal authoring is permitted on the merge target
  or a `plan/*` branch by default; a manifest block (below) can declare additional
  accepted patterns for a project's own naming convention, without renaming
  anything to fit a hardcoded name.
- **No filler delta specs.** A deliberately proposal-only backlog entry — a plan
  with no delta specs yet — commits at its own stage: manifest validity plus a
  readable status, not a full spec-validation it never claimed to satisfy.
- **No interim push ritual.** Archiving and (under a self-approval policy)
  implementing both accept a sound **local** counterpart of the merge target that
  carries the change, not only the origin ref — see the acceptance map below.

## The two manifest blocks this pattern adds

Both are optional; absent, behavior is exactly what it was before this pattern
existed.

```yaml
discipline:
  propose-branches:      # fnmatch globs accepted for proposal authoring,
    - "plan/*"           # REPLACING the plan/* default when declared (not
    - "worktree/*"        # appending to it) -- the merge target is always
                          # accepted and cannot be de-declared.

concurrency:
  serialize: [ci, live-check]   # gate names (or "live-check") to serialize
                                 # machine-wide with a stdlib file lock, held
                                 # only around the gate command itself.
```

- `discipline.propose-branches` lets an adopter name its own worktree-branch
  convention (e.g. `worktree/*`) as accepted for authoring, without inventing a
  second, unrelated meaning for `plan/*`. Every accepted branch, declared or
  default, still has to share history with the merge target — a pattern admits a
  *name*, never an orphan history.
- `concurrency.serialize` exists for the rare gate that genuinely can't run twice at
  once on one machine (a resource-heavy live-check suite is the common case). It is
  opt-in per gate; nothing serializes unless declared. A lane waiting on the lock
  prints a notice at once and then at most every 30 s, naming the holder's pid, its
  liveness and hold age, and the wait so far — visibly waiting, never silently hung.
  The wait ends at `concurrency.max-wait-seconds` (default 480) with exit 75 and
  `gatedloop: lock busy`, never running the gate. A crashed holder frees the lock
  automatically (the lock dies with the process's file descriptors, no manual
  cleanup).

## Where local acceptance applies, and where origin is still required

| Gate | Guarantee | Local counterpart accepted? |
|---|---|---|
| `check-archive` (merge precedes archive) | Ordering only | **Yes, always** — a local counterpart of the merge target that carries the change proves the ordering just as well as origin, with a loud "not yet pushed" advisory. |
| `check-implement` under approval policy `review` | A forge-anchored approving review | **No** — a purely local ref cannot evidence a PR review; origin is unconditionally required. |
| `check-implement` under approval policy `self` | A locally attested plan | **Yes** — local attestation is already the legitimate writer under this policy, so the same local-counterpart fallback applies. |

**Push-after-merge remains recommended hygiene either way.** Local acceptance is a
serialization convenience for a single merge lane working through several changes in
one sitting — it is not a durability claim. An unpushed merged change still dies
with the laptop; the loud advisory exists precisely so that never happens silently.

## The directory-basename namespacing property

Some of an adopter's own tooling derives a project or instance name from the
current directory's basename — a common pattern for anything that needs to avoid
colliding with another instance of itself on the same machine. Because each
`git worktree add` checkout gets its own directory (and therefore its own
basename), that class of tooling is **automatically namespaced per worktree** — two
lanes running the same declared gate command never collide with each other, or with
a developer's own already-running instance of the same tooling, purely because they
sit in different directories. This is a property of the pattern worth knowing
about, not a gatedloop feature: whether a project's own tooling actually derives its
name this way is the adopter's choice, declared in its own `.gates.yaml` commands —
gatedloop names no such tool itself. Content-addressed shared caches (keyed on what's
being built, not on which directory built it) still deduplicate normally across
lanes; only instance-identity naming benefits from the basename split.

## Setting up a second lane

1. `git worktree add <path> -b <change-name>` from the primary checkout (or check
   out an existing change branch into a fresh worktree the same way).
2. Start a session in the new worktree's directory. Nothing else to configure — gate
   markers, the ledger, and merge-target resolution all work exactly as in a single
   checkout, because they were designed to from the start (see the scope table
   above); this pattern only fixes the resolution bugs that used to require a
   workaround.
3. Work the change to completion, exactly as `skills/tdd-apply/SKILL.md` describes,
   stopping before the merge.
4. Merge, archive, and any plan review happen in the primary checkout — the one
   serialized lane — same as always.

See `AUTOMATION.md`'s "Update (`worktree-native-loop`)" section for the enforcement
detail behind the local-acceptance map, and `SETUP.md` for the full `.gates.yaml`
contract these two blocks extend.
