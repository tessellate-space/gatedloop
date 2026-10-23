# Tasks: worktree-native-loop

## 1. Command-derived repository resolution (D1)

- [x] 1.1 Add the `gates hook git-cwd` subcommand: read hook JSON on stdin, resolve
      the effective directory by the D1 precedence (`git -C`, `GIT_DIR`/
      `GIT_WORK_TREE` prefix, last `cd` before the guarded token chained against the
      hook cwd, hook cwd, `CLAUDE_PROJECT_DIR`, pwd), print it; verify with unit
      tests in `tests/` covering each rung, compound commands, quoting, repeated
      `-C`, and the fall-through on unevaluable `cd` targets
- [x] 1.2 Replace the inline `cd "$hook_cwd"` block in all six `hooks/gate-*.sh`
      with a call to `gates hook git-cwd`; verify each hook by piping crafted hook
      JSON (session cwd = primary, command `cd <worktree> && git commit`) and
      observing the check evaluate the worktree
- [x] 1.3 Make every deny message name the repository that was evaluated; verify the
      message text in a hook-JSON pipe test from both a primary and a secondary
      worktree

## 2. Tree-keyed markers (D2)

- [x] 2.1 Rework marker read/write/check to the `markers/<gate>/<tree>.json` layout
      with LRU prune to 8 per gate and opportunistic cleanup of legacy single-slot
      files; verify with unit tests: two trees both green, eviction of the 9th
      oldest, legacy file ignored, `gate-marker clear` clears both layouts
- [x] 2.2 Confirm the check/deny message contract is unchanged (`no marker` /
      `stale — re-run`) and that `gate-marker check <gate> <tree>` passes for any
      retained tree; verify via the existing marker tests plus a new
      alternate-trees test
- [x] 2.3 End-to-end: in a scratch repo with two worktrees, run a green gate in
      each, then commit from each via `cd <worktree> && git commit`; verify neither
      lane's marker satisfies or invalidates the other's and no retry loop occurs

## 3. Declared propose-branch patterns (D3)

- [x] 3.1 Add the optional `discipline.propose-branches` block to
      `schema/gates.schema.json` and manifest validation (reject non-list, empty
      entries); verify with `gates validate` fixture tests for valid, absent, and
      malformed blocks
- [x] 3.2 Extend `_propose_branch_verdict` to accept declared patterns (fnmatch,
      replacing the `plan/*` default when present, merge target always accepted,
      shares-history guard retained); verify with unit tests: default behavior
      unchanged when absent, declared pattern accepted, orphan branch matching a
      pattern refused, refusal message names the permitted set

## 4. Stage-appropriate planning-grade validation (D4)

- [x] 4.1 Implement the per-staged-change stage classification in `discipline
      check-commit` (delta content or `skip_specs` → full `openspec validate`;
      proposal-only → manifest valid + `openspec status` readable, allow message
      names the stage; status unreadable → deny naming the read failure); verify
      with unit tests for all three classes and a mixed multi-change staging
- [x] 4.2 End-to-end: scaffold a proposal-only change, stage only it, and verify the
      commit gate allows it with the `proposal-only` message and no filler delta
      spec; add delta content and verify full validation applies again

## 5. Local merge-target acceptance (D5)

- [x] 5.1 Add local-counterpart resolution (origin ref first, local `<name>` branch
      fallback when target is `origin/<name>`) and wire it into `discipline
      check-archive` with the unpushed-merge advisory; verify with unit tests in a
      scratch repo: merged-local-unpushed allowed with advisory, unmerged refused,
      merged-on-origin allowed silently
- [x] 5.2 Wire policy-dependent acceptance into `check-implement`/`_approval_check`:
      `review` requires the origin ref, `self` accepts the local counterpart with
      the push advisory; verify with unit tests for both policies against a
      local-only merged plan
- [x] 5.3 Update the deny/advisory wording and AUTOMATION.md's description of the
      implement/archive gates; verify by reading the messages from the unit tests
      and the doc cross-reference

## 6. Cross-worktree gate mutex (D6)

- [x] 6.1 Add the optional `concurrency.serialize` block to
      `schema/gates.schema.json` and manifest validation (names must be declared
      gates or `live-check`; reject non-list); verify with `gates validate` fixture
      tests
- [x] 6.2 Implement lock acquisition in `gates run` for serialized gates:
      `fcntl.flock` on `<git-common-dir>/specloop/locks/<gate>.lock`, holder
      pid/ts written on acquire, heartbeat on stderr while waiting, lock held only
      around the gate command, loud unlocked degrade without `fcntl`; verify with
      unit tests (lock scope, no-declaration no-lock) and a two-process contention
      test asserting serialization and the waiting notice
- [x] 6.3 Verify a killed holder frees the lock (spawn, kill -9, reacquire) in a
      test or scripted check

## 7. Docs and the fresh-worktree hint (D7)

- [x] 7.1 Implement the fresh-worktree hint in `gates run`'s failure path (no prior
      gate history in this worktree's git dir → one stack-agnostic line pointing at
      the adopter's manifest, once per worktree, exit code untouched); verify with
      unit tests: first failure hints, second does not, established worktree never
      hints, hint names no tool
- [x] 7.2 Write `docs/worktree-lanes.md` per D7 (topology, per-worktree vs repo-wide
      state, both new manifest blocks, local-vs-origin acceptance map,
      push-after-merge hygiene, directory-basename namespacing property); verify it
      answers each #15/#39/#40 lane friction without any undocumented workaround
      and link it from SETUP.md, AUTOMATION.md, and README
- [x] 7.3 Document the two new manifest blocks in `templates/gates.yaml.template` as
      commented-out examples; verify the template still passes `gates validate`
      unmodified

## 8. Change-level verification

- [x] 8.1 Run the full suite (`python3 -m unittest discover -s tests`) and `gates
      validate`; verify green
- [x] 8.2 Scripted lane rehearsal in a scratch repo: two worktree lanes commit
      gated work concurrently, a proposal-only backlog entry commits alone, a
      declared branch pattern authors without rename, a serialized gate blocks its
      twin with a visible heartbeat, and an unpushed local merge archives with the
      advisory; verify each behaves per the specs' scenarios
