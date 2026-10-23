# Design: worktree-native-loop

## Context

See proposal.md for motivation. The current state that shapes this design:

- Every gate hook (`hooks/gate-*.sh`) resolves its working repository the same way:
  `cd` to the hook input's `cwd` field, else `CLAUDE_PROJECT_DIR`, else the hook
  process's own pwd. The hook input's `cwd` is the harness **session** cwd. A
  background agent's Bash shell resets cwd every call, so its git commands carry
  their own directory (`cd <worktree> && git commit …`, `git -C <worktree> …`) while
  the session cwd stays at the base checkout. The hook therefore evaluates the wrong
  repository: `git write-tree` reads the primary checkout's (clean) index, and
  `bin/gates`' `_repo_root()` (`git rev-parse --show-toplevel` from the process cwd)
  resolves the primary checkout, so `_markers_dir()` reads the primary's marker
  store. The denial is always "no ci marker", and no re-run from the worktree can
  ever satisfy it.
- Markers already live under the **per-worktree** git dir (`git rev-parse --git-dir`,
  deliberately not `--git-common-dir`). Cross-worktree marker sharing is already
  impossible when the resolution above is correct. Each gate has exactly one marker
  file (`<gate>.json`) holding one tree — a single slot.
- `_propose_branch_verdict()` hard-codes the accepted set: the merge target's name,
  `main`/`master`, or `plan/*` sharing history with the target.
- `discipline check-commit`'s planning-grade path runs `openspec validate <change>
  --type change` per staged change dir. OpenSpec rejects a change with zero deltas
  (unless `skip_specs`), so a deliberately proposal-only backlog entry cannot pass.
- `_resolve_merge_target()` prefers `origin/HEAD` (e.g. `origin/main`).
  `check-implement` and `check-archive` both test change presence against that ref,
  so a merged-but-unpushed change fails both until an interim push.
- Sibling changes: `harden-hook-matching` replaces the hooks' substring command
  matching with subcommand-token matching (this change's hook edits build on its
  tokenizer); `fix-marker-mechanics` owns marker freshness against the run's own
  ledger row and skip-verdict markers. **This change lands after both.**

## Goals / Non-Goals

**Goals:**

- A gate check always evaluates the repository the guarded command acts on.
- Concurrent worktree lanes are contention-free by construction, and the design
  states which fix removes the *observed* contention.
- The lane pattern needs zero undocumented rituals: no branch renames, no filler
  delta specs, no interim pushes where a local ref is sound, no marker-chase
  boilerplate in agent briefs.
- Every new knob is manifest-declared, schema-validated, default-off, and stdlib-only.

**Non-Goals:**

- Marker freshness vs the run's own ledger row, and markers for skip verdicts
  (`fix-marker-mechanics`).
- Hook command matching (`harden-hook-matching`).
- A merge-queue primitive, archive path-segment validation, `gates stats`, a
  two-tier ci contract, changed-file context for `ci` (#16 items 4–5, #18 items 1–2,
  4–5 — deliberately left open).
- Distributed (multi-machine) locking. The mutex serializes one machine.

## Decisions

### D1 — Resolve the guarded command's repository from the command itself, in the shim

The hooks stop treating the hook input's `cwd` as where git will run. A new shim
subcommand (working name `gates hook git-cwd`) reads the hook JSON on stdin and
prints the effective directory, resolved with this precedence:

1. `git -C <dir>` on the guarded git invocation (repeatable; git applies them in
   order, so the resolution composes them the same way).
2. `GIT_DIR` / `GIT_WORK_TREE` assignments prefixed to the command (`GIT_DIR=…
   git …` or an `env` wrapper) — `GIT_WORK_TREE` (or `GIT_DIR`'s parent for a
   `.git`-suffixed path) names the tree under check.
3. The last `cd <dir>` in the compound command *before* the guarded token, resolved
   left-to-right against the hook input's `cwd` (each `cd` chains off the previous).
4. The hook input's `cwd`.
5. `CLAUDE_PROJECT_DIR`, then the process pwd — today's fallbacks, unchanged.

Each `gate-*.sh` replaces its inline `cd "$hook_cwd"` block with one call to this
subcommand and `cd`s to the answer. Why the shim and not bash: this is branchy,
quoting-sensitive parsing (`shlex` territory), and the repo's standing rule is that
branching Python gets tests while shell stays trivial. It also reuses the tokenizer
`harden-hook-matching` introduces for subcommand matching — one command parser, two
consumers, which is why this change is sequenced after it.

*Alternative considered*: have the hook pass the raw command through to
`discipline check-*` and let each check resolve internally. Rejected: every check
would need the same resolution anyway, and the hook still needs the directory for
its own `git write-tree` / `rev-parse` evidence gathering. One subcommand, printed
once, keeps the contract inspectable (`echo '<hook json>' | gates hook git-cwd`).

*Non-goal within D1*: `cd` targets computed from shell variables or substitutions
are not evaluated; resolution falls through to the next rung. Fail-through here is
safe because the fallback is today's behavior, and the deny message still names the
repository it evaluated so a mis-resolution is visible, not silent.

### D2 — The observed marker contention is D1's bug; tree-keying is hardening, not the fix

The diagnosis #16 item 1 asked for: markers are already per-worktree
(`_markers_dir()` hangs off `git rev-parse --git-dir`), so two correctly-resolved
lanes cannot contend. The observed "single-slot across worktrees, last-write-wins,
stale-marker retry loops" happens when hook checks — and any `gates run` whose
process cwd is the session cwd — all resolve the *primary* checkout: every lane
then reads and writes the primary's one `<gate>.json` slot. **D1 removes the
observed contention.** The design says this plainly so the fix is not attributed to
the marker layout change.

Independently, the single slot *within* one worktree is still real friction: the
serialized merge lane alternates between trees (pre-merge head, post-ledger-row
tree, next branch's head), and each green overwrites the last. So markers become
tree-keyed:

- Layout: `<git-dir>/specloop/markers/<gate>/<tree>.json` (payload as today).
- Check: the requested tree's file exists → pass. Miss → today's messages,
  unchanged wording contract ("no marker" / "stale — re-run").
- Write: create the tree's file, then prune the gate's directory to the 8 most
  recent by recorded timestamp. Eviction is silent and safe: the cost is one
  re-run, exactly the pre-existing contract.
- Migration: none. Markers are an ephemeral cache under `.git/`; old single-slot
  `<gate>.json` files are ignored and cleaned opportunistically on the first new
  write. One re-run per worktree migrates the world.

*Alternative considered*: one `<gate>.json` holding a tree→timestamp map. Rejected:
concurrent writers within a worktree (rare but possible) would need read-modify-
write locking; one-file-per-tree makes every write atomic for free.

LRU depth 8 is a constant, not a knob — no observed lane pattern needs more than
three live trees, and a knob would be surface area with no second legitimate value.

### D3 — Accepted propose branches: a declared pattern list that tightens nothing and loosens explicitly

Manifest block (optional, schema-validated):

```yaml
discipline:
  propose-branches:      # fnmatch globs, matched against the branch name
    - "plan/*"           # today's default, listed for clarity
    - "worktree/*"
```

- Absent → exactly today's accepted set (merge target + `plan/*`). Present → the
  merge target and the declared patterns (declaring replaces the `plan/*` default
  rather than appending; an adopter who wants both lists both — explicit beats
  merged-by-magic).
- The merge target is always accepted and cannot be de-declared: proposing on main
  is upstream's own rule, not ours to make configurable.
- The shares-history-with-target guard applies to every non-target branch,
  declared or default — a pattern admits a *name*, never an orphan history.
- `gates validate` rejects a non-list, empty-string entries, and absolute-path-like
  patterns, loudly.

*Alternative considered*: a regex. Rejected: the manifest already speaks fnmatch
globs (surfaces), and two pattern dialects in one file is a trap.

### D4 — Stage-appropriate planning-grade validation, keyed on what the change claims

The planning-grade path in `discipline check-commit` classifies each staged change
directory before choosing its validation:

- **Has delta content** (any file under the change's `specs/`, or `.openspec.yaml`
  sets `skip_specs: true` — both mean "openspec validate can judge this"): run
  `openspec validate <change> --type change` exactly as today.
- **Proposal-only** (no `specs/` content, no `skip_specs`): a legitimate backlog
  state. Validation is: manifest valid (as today) + `openspec status --change
  <name> --json` succeeds and reports the artifacts that do exist as recognized by
  the schema. The allow message names the stage: `planning-grade commit allowed
  (proposal-only: <change>)` — an auditor reading the ledger/transcript sees what
  was and wasn't validated.
- **Status unreadable**: deny, naming the failed read. Missing evidence is never a
  pass (fail-loud-gates).

Why not `skip_specs: true` as the escape hatch for backlog entries: that flag
declares "this change will never have deltas", which is false for a backlog
proposal that will grow them — agents writing a false flag to pass a gate is the
exact honesty failure #16 reported (filler delta specs), relocated.

### D5 — Origin reachability: split by what each gate actually guarantees

`check-archive` and `check-implement` look similar (both test change presence on
the merge target) but guarantee different things, so they diverge:

- **check-archive** guarantees *ordering* — merge precedes archive. A local
  counterpart branch of the merge target (local `main` when the target resolves to
  `origin/main`) that contains the change proves the ordering. Accepted, with a
  loud advisory: `merged locally but not on origin — push before ending the
  session`. This removes the 4+ interim pushes per serialized merge session.
- **check-implement** guarantees *a reviewed, attested plan exists*. Under approval
  policy `review`, the attestation is anchored to the forge PR's approving review;
  a local ref cannot evidence that, and accepting one would let a lane launder a
  self-approved plan — origin stays required, and the canonical flow for `review`
  adopters remains "push the plan, get the review, then implement" (documented as
  such). Under policy `self` (solo-approval-mode), local attestation is already the
  legitimate writer, so the local counterpart is accepted with the same push
  advisory.
- Local counterpart resolution: only when the resolved target is `origin/<name>`
  and a local branch `<name>` exists; the check tries the origin ref first (it is
  the stronger evidence) and falls back to the local counterpart. When both are
  missing the message is today's.
- Push-after-merge is documented as recommended hygiene either way (D7's doc): the
  local acceptance is a serialization convenience, not a durability claim — an
  unpushed merged change still dies with the laptop.

### D6 — Cross-worktree mutex: lock the command, in the common git dir, stdlib-only

Manifest block (optional, schema-validated):

```yaml
concurrency:
  serialize: [ci, live-check]   # gates to serialize machine-wide
```

- `gates validate` rejects names not declared as gates (`live-check` counts as
  declarable — it is a gate in the contract table) and any non-list shape.
- `gates run <gate>` for a serialized gate acquires an exclusive `fcntl.flock` on
  `<git-common-dir>/specloop/locks/<gate>.lock` before executing the gate command
  and releases it immediately after — marker writes, ledger rows, and taint
  resolution happen outside the lock. The common git dir is shared by all
  worktrees of a repo: machine-level serialization per repo, zero deps, and a
  crashed holder frees the lock automatically (flock dies with the fd).
- While blocked, a heartbeat on stderr every few seconds: `waiting for gate 'ci' —
  held by pid <n> since <ts>` (holder pid/ts written into the lock file on
  acquisition, informational only). A waiting lane is visibly waiting, never hung.
- Platforms without `fcntl` (Windows): degrade loudly — print that serialization
  is unavailable and run unlocked. A gate must never fail for want of a lock.
- `live-check --all` and per-surface runs take the same single gate-level lock; no
  per-surface granularity (the point is "one heavy suite per machine").

*Alternative considered*: locking inside the hooks. Rejected: hooks are checks,
not executions — the thundering herd is `gates run`, and Specloop sees every gate
start there (#18's own observation).

*Alternative considered*: a lock directory under `/tmp` keyed by repo path hash.
Rejected: the common git dir is already the canonical per-repo shared location,
survives nothing it shouldn't, and needs no hashing scheme.

### D7 — One docs page owns the lane pattern; the shim owns one hint

- `docs/worktree-lanes.md` records: the supported topology (N worktrees, one
  serialized merge lane in the primary checkout, stop-before-merge); what is
  per-worktree (index, branch, marker store) vs repo-wide (ledger, attestation,
  merge target, the D6 lock); the branch-pattern and mutex manifest blocks; where
  a local merge target is accepted vs where origin is required (D5), with
  push-after-merge as recommended hygiene; and the namespacing property from #15 —
  tooling that derives project/instance names from the directory basename is
  automatically namespaced per worktree (compose project names being the observed
  example, named as an *adopter-side* example in docs, which are not shipped
  prompts — while shared caches keyed on content still deduplicate). SETUP.md and
  AUTOMATION.md link to it; README gets one line.
- The fresh-worktree hint lives in `gates run`'s failure path: gate exited
  non-zero AND this worktree's git dir has no recorded gate history (no marker
  store and no prior hint stamp) → append one line: `hint: this worktree looks
  fresh — its dependencies may not be installed yet; your project's setup lives in
  your own gates (.gates.yaml)`, then stamp the git dir so the hint prints at most
  once per worktree. Stack-agnostic by construction: it can only ever point at the
  adopter's manifest. Exit code untouched.

### D8 — Sequencing and shared surfaces

This change edits the same six hooks as `harden-hook-matching` and the same marker
code as `fix-marker-mechanics`. It is sequenced last of the three; its tasks assume
token-based command matching exists (D1 reuses that tokenizer) and rebase over the
marker-freshness fix rather than the reverse. If either sibling is descoped, D1/D2
still stand alone — the dependency is textual (merge conflicts), not semantic,
except for D1's tokenizer reuse, which would then be authored here.

## Risks / Trade-offs

- **[D1] Command parsing can misread exotic shell** (substitutions, aliases,
  functions computing the target dir) → resolution falls through to the hook cwd —
  today's exact behavior — and the denial message names the repository evaluated,
  so a mis-resolution is diagnosable in one read, not a relaunch round. The rungs
  it does handle (`-C`, env prefix, literal `cd`) cover every invocation shape in
  the field reports.
- **[D2] Tree-keyed markers accept an older green tree** — a lane can commit tree A
  after later work on tree B went red → this is not a weakening: the contract has
  always been "this exact tree passed", and tree A did. Freshness-vs-ledger
  semantics stay with `fix-marker-mechanics`.
- **[D3] A loose declared pattern (e.g. `*`) widens where proposals can be
  authored** → the shares-history guard and the merge-target invariant still hold;
  the knob only relaxes a *naming* convention, and it is the adopter's declared
  choice in a schema-validated block, not drift.
- **[D5] Accepting a local counterpart weakens nothing but can surprise** — an
  adopter may archive against a local main that origin later rejects (protected
  branch, force-push race) → the advisory names the unpushed state every time, and
  `review`-policy implement gating still anchors to the forge.
- **[D6] flock is advisory** — a gate command that spawns its own unrelated copies
  isn't serialized → out of scope: the mutex serializes Specloop-started gate
  runs, which is the thundering herd that was measured.
- **[D6] A long-held lock delays lanes silently misconfigured to serialize `unit`**
  → the heartbeat names the holder, and the block is opt-in per gate.
- **[Scope] Seven items in one change** → they are one theme (the lane pattern)
  with one shared code surface (hooks + shim + schema + docs); splitting would
  re-create the cross-change hook-edit contention this repo just lived through.

## Open Questions

None — the deliberately-deferred items are listed as non-goals with their owning
issues, not as unknowns.
