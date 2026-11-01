# Changelog

Every release of the Specloop plugin, newest first. Claude Code updates an
installed plugin only when its `version` changes, so a change on `main` reaches
adopters in the first release after it. The procedure that writes this file is
in [RELEASING.md](RELEASING.md).

Sections from 0.5.0 on are drafted by `scripts/release cut` and edited before
`scripts/release publish`. The three below were backfilled from their release
commits (`2898ba5`, `9fe73de`, `7abcdb5`); only 0.4.0 is tagged.

## 0.11.0 — 2026-11-01

Task commits get their scoped `ci` back, the merge checks the plan is still the approved one, a lane can no longer sync main past the hooks, and gatedloop now states which of its surfaces you may build on and checks them in ci.

**Scoped task commits work again**

- **scope-own-tasks** (#127). Fixes #122.
  - **The change's own `tasks.md` no longer counts toward scope selection.** In 0.10.0 every task commit's `[x]` tick either matched no surface or added a second hot surface, so a task commit always ran the full `ci`. Another change's `tasks.md` still counts, and nothing is exempt on `main` or a plan branch.
  - **The 0.10.0 advice to add `openspec/**` to a surface is withdrawn.** It couldn't work. If you added it, you can remove it.

**The loop, hardened from an adopter's report**

- **loop-hardening** (#119). Fixes #101, #108, #109, #110, #111 and #112.
  - **`gates merge` and every acceptance writer refuse a change whose plan changed after approval.** Before step 1 the merge compares the recorded `approved_sha` with the plan on the merge tree. `record-merged` writes no acceptance for a stale plan. Re-attest the amended plan to go on.
  - **A plain `git merge origin/main` inside a lane is denied.** Git runs no pre-commit hook for a merge commit, so the sync reached the branch unchecked and only showed up as a taint at merge time. Sync with `git merge --no-commit origin/main`, then `gates run ci`, then `git commit`, or rebase. The implementer prompts now say so. A taint refusal names the commits it found.
  - **The hooks resolve `cd ~/…`, `cd $HOME/…` and subshell `cd` targets. A `cd` target they still can't resolve is denied** instead of being judged by the session's directory.
  - **A conflicted or unparseable `.gates.yaml` fails in one line.** The commit hook used to report it as "branch is shared with another worktree".
  - **Re-handoffs:** placement accepts a file's content as it is on main, so a re-handoff after main changed an existing test places. A full handoff that would drop already-placed tasks is refused.
  - **The READY report's gate block comes from the ledger:** `gates ledger record-ready` prints `ci`, `review` (`clean`, `findings`, `partial` or `none`) and `live_check`, so a report can't claim a review that never ran.

**What you may build on**

- **stability-contract** (#118).
  - **`docs/stability.md`** says which surfaces are covered: the `gates` subcommands and flags, the exit codes, the `gatedloop/<gate>` statuses, the `.gates.yaml` keys, the `handoff --json` and `stats --json` keys, and the ledger row. It also sets the deprecation policy: warn, keep it one more release, then remove it with migration steps. While the version is 0.x a removal may ship in a minor; from 1.0, only in a major.
  - **Every ledger row carries `"v": 1`.** A row without `v` reads as version 1. A row written by a newer plugin makes the reading command exit 1, naming the file and both versions, instead of being misread.
  - **ci runs on Ubuntu and macOS, Python 3.9 and 3.13.** A weekly run watches OpenSpec's latest release. `gates doctor` warns when OpenSpec is outside the supported range, which is 1.14.3.

**Upgrading**

1. **Update the plugin** (`/plugin update gatedloop@gatedloop`) and start a new session, because hooks load at session start. The git-layer hooks didn't change, so there's no need to re-run `gates hook install`.
2. **Check every in-flight change's approval** before its next merge: `gates approval check <change>`. A change whose plan was amended without a re-attest is now refused at merge. Re-attest it.
3. **Tell lane agents and scripts how to sync main:** `--no-commit`, then ci, then commit, or rebase. A plain merge is now denied.
4. **If you added `openspec/**` to a surface on 0.10.0's advice, you can drop it.**
5. No new settings; `/gatedloop:upgrade` has nothing new to ask.

## 0.10.0 — 2026-11-01

A scoped `ci` or `unit` no longer runs narrower than it should, lettered task ids work everywhere, a lane can sync its branch without a hook refusal, and two role commands set up the planner/orchestrator split.

**Scoped gates err full, as documented**

- **err-full-scoping** (#99). Fixes #61 and #45.
  - **A changed file that no surface matches runs the full gate.** A diff holding one surface's file and one unmatched file used to run that surface's scoped `ci`. Catch-all surfaces (`match: "**"`) still don't count as a match, and `.gatedloop/` bookkeeping is never treated as unmatched. The message names the unmatched path.
  - **A `unit` run spanning several surfaces runs each surface's own `unit`**, plus the global `unit` once for any of them that declares none. It is red if any of them is red, and it counts as one attempt. It used to fall back to the global `unit` alone, which could skip a surface's tests and record a false green.
  - `ci` across several surfaces still runs the full `ci`.
  - **You may see more full runs.** A change's own `tasks.md` is an unmatched path, so if no surface covers `openspec/**`, every task commit now runs the full `ci`. Add `openspec/**` to a surface to scope those commits again (SETUP, "Scoped `ci`/`unit`").

**Smaller fixes**

- **friction-fixes** (#100). Fixes #46, #44 and #47.
  - **Lettered task ids (`1.2a`) are read everywhere**: oracle tags, the test author's brief, completion ticks and the approval digest. `gates tests show` no longer crashes on them, and every task listing sorts `1.2`, `1.2a`, `1.9`, `1.10`.
  - **A switch-then-merge passes the merge hook** when it lands on a change branch, e.g. `git checkout my-change && git merge --ff-only origin/main`. A merge into the target stays gated, and so does a switch the hook can't resolve; the refusal says to run the merge as its own command.
  - **`convention-review` reports a missing test only when no task in the change holds one**, so a `NO-TESTS` on a "write the test" task whose test another task holds is no longer a finding.

**Role commands**

- **role-commands** (#98).
  - **`/gatedloop:planner`** proposes in its own worktree and, once the plan PR merges, sends `gates handoff` to the orchestrator session.
  - **`/gatedloop:orchestrator`** verifies each handoff, dispatches one `tdd-implementer` per change, merges on READY and reports. It asks for the lane count; there is no default.
  - Both restate their role on every run, so re-running the command after a compaction puts the session back in its role.

**Upgrading**

1. **Update the plugin** (`/plugin update gatedloop@gatedloop`) and start a new session, because hooks load at session start.
2. **Check your surfaces** if you declare scoped `ci` or `unit` overrides: add `openspec/**` (and any other path that should stay scoped) to a surface, or accept the full runs.
3. No new settings; `/gatedloop:upgrade` has nothing new to ask.

## 0.9.0 — 2026-10-28

Each task can now declare the gate that proves it, every task's token cost is recorded, a solo project's merge counts as its acceptance, and the earlier `specloop` names stop working.

**The plan declares each task's oracle**

- **task-oracle** (#86). Fixes #56.
  - **A task line may end with `[oracle: <gate>]`**, `[oracle: <gate> characterization]` or `[oracle: none]`. `gates validate` checks every tag. `ci`, `live-check`, `eval` and `confirm` can't be oracles.
  - **The test author no longer guesses a task's kind.** `gates tests brief` prints each declared oracle, and the handoff refuses a held test that contradicts its tag. The author stops with `weak-spec` when it thinks a tag is wrong, and the 0.8.0 interim rule ("declare an e2e task `CHARACTERIZATION`") is retired.
  - **The lock and the attempt budget read the tagged gate.** An e2e task tagged `[oracle: integration]` goes red under `integration`, not `unit`. An untagged task works as before.
  - **A tag can't be changed quietly.** A tagged plan's approval covers its tags, and the lock refuses a tag that differs from the one on the merge target. Untagged plans hash as before.
  - **Opt-in.** `loop.task-oracle: required` makes the handoff refuse untagged tasks. The default is `optional`. `/gatedloop:upgrade` and `gates-init` offer a `rules.tasks` line that asks the planner to tag.
  - `convention-review` judges a `NO-TESTS` or `CHARACTERIZATION` reason against the task's tag (#47).

**What a task cost**

- **token-ledger** (#67):
  - **Usage rows, on by default.** The commit hook records, per task, the tokens the session spent on it (input, output, cache read, cache write, per model), and the Stop hook records the task in flight. Only counts are stored, never transcript content. A session with no readable transcript records null counts with the reason.
  - **`gates stats`** reports tokens per task, per change and per model, says what went unrecorded, and rolls tokens up with `--epic`.
  - **`economics.prices`** (with `economics.currency`) maps a model to per-million-token prices, and `gates stats --cost` prints a figure. The plugin ships no price list.
  - **`loop.token-budget`** caps a change's recorded tokens. Once usage reaches it, task-bearing `gates run unit|ci` refuses and names a new halt cause, `budget`. `/gatedloop:upgrade` offers it, recommending record-only.

**Acceptance through a merged pull request**

- **merged-acceptance** (#87). Fixes #75.
  - **`gates acceptance attest <change> --merged <pr>`**, under `approval.acceptance: self`, records the owner's merge of the implementation PR as the acceptance. The row is pinned to the merge commit's tree.
  - **`gates record-merged`** writes that row in the same commit as the merge row and the archive, so `gates stats --outcomes` reads the change as accepted.
  - **`gates record-merged` re-attests a merged plan amendment** whose approval no longer matches, where it used to skip it as already approved.
  - In pull-request mode under `self`, `gates merge` says the owner's merge will count as the acceptance.

**The earlier name**

- **remove-specloop-forwarders** (#80). **This is a breaking change** for a project that never migrated.
  - Nothing reads the earlier `specloop` names. A project that still holds `.specloop/` is refused by every command except `gates doctor` and `gates migrate-name`.
  - `gates marker publish` posts only `gatedloop/<gate>`. A branch protection rule that still requires `specloop/ci` stops passing.
  - The `specloop` forwarder plugin and its marketplace entry are gone.

**Upgrading**

1. **Still on the earlier name?** Run `gates migrate-name` on 0.8.x before updating. It lists the branch-protection contexts to rename to `gatedloop/<gate>`.
2. **Update the plugin** (`/plugin update gatedloop@gatedloop`) and start a new session, because hooks load at session start.
3. **Re-run `gates hook install`** if you installed the git-layer hook. The installed copy predates usage recording, and `gates doctor` reports it as `stale-copy`.
4. **Run `/gatedloop:upgrade`.** It offers the token budget and the oracle tags. Both are optional.

## 0.8.0 — 2026-10-27

The authored-test lock no longer leaves a finished change unable to merge, and the git layer reaches beyond Claude Code.

**The authored-test lock**

- **unblock-authored-lock** (#66). Fixes #56 and #49.
  - **A ledger-only commit skips the lock** in both commit hooks, so `gates merge` can commit its own rows at steps 1 and 5. `gates discipline check-commit --verdict-file` gives the hooks the verdict as a token.
  - **A halt at a completed task no longer cancels its placement.** A task counts as completed once its `[x]` was committed before the row.
  - **A test defect at a completed task reopens it.** The red run recorded at its first placement stays the record, so no second red run is demanded against committed code.
  - **A new defect kind, `green`,** for placed tests that pass before any implementation. It records what was seen rather than an untrue `setup` or `assertion` claim. The author answers by re-declaring the task (`CHARACTERIZATION` or `NO-TESTS`) or by rewriting its tests. It has a cap of one, then an `oracle-conflict` halt.
  - **Failed attempts are counted from the task's latest placement**, so a test-defect cycle no longer spends the attempt budget. `gates attempt restart` accepts the task's placed tests at their placed content.
  - The merge's head proof (`gates tests check --ref`) applies the same rules, so a change stuck under 0.7.0 can merge. A completed task that never had its red run gets `gates tests defect <task> --kind green`. The author re-declares it, it is placed again, and `unit` runs green.

**Enforcement**

- **git-layer-enforcement** (#52):
  - **`discipline.agent-env`** names the variable your agent host sets (default `CLAUDECODE`). The git hooks enforce wherever it is set, so an agent on another host is gated too, and a human's own commits and pushes are left alone.
  - **An opt-in `pre-push` hook** denies a push that updates the merge target unless the pushed commit is proven. `gates hook install` offers it, `--commit-only` declines it until `--push`, and a decline sticks. `gates doctor` reports both hooks.
  - `AUTOMATION.md` now has a guarantee-by-layer table for each host.

**The earlier name**

- **defer-earlier-name-expiry** (#65): the earlier `specloop` names keep working, with the warning, through 0.8.x. They now stop working in **0.9.0**, not 0.8.0, so this fix could ship without waiting on their removal. Statuses are still posted under both names.

**Other changes**

- README: where gatedloop sits in the lifecycle and what the agent cannot do, and loop-diagram labels that GitHub no longer clips.
- Restored `#NN` references and fixture numbers that the export from the private archive had rewritten to `specloop PR N`.

**Upgrading**

1. **Update the plugin** (`/plugin update gatedloop@gatedloop`) and start a new session, because hooks load at session start.
2. **Re-run `gates hook install`** if you installed the git-layer hook. The installed copy predates both the lock fix and the agent-env change. `gates doctor` reports it as `stale-copy`. `/gatedloop:upgrade` offers the new push hook.
3. **Not using Claude Code?** Set `discipline.agent-env` in `.gates.yaml` to the variable your agent host sets.

## 0.7.0 — 2026-10-23

Specloop is now **gatedloop**, and this is its first public release.

**The rename**

- **rename-to-gatedloop**:
  - **What's renamed:** the plugin, the marketplace and the command namespace (`/gatedloop:*`), and every identifier gatedloop owns:
    - `.gatedloop/`;
    - `x-gatedloop-*` change metadata;
    - `gatedloop/<gate>` commit statuses;
    - `gatedloop.*` rule ids;
    - hook markers and message prefixes.

    `gates` and `.gates.yaml` keep their names.
  - **Earlier names still work, loudly, through 0.7.x.** Each command warns once and names the fix. Statuses are posted under both names, so branch protection doesn't break mid-migration.
  - **`gates migrate-name`** moves a project across. `gates doctor` and `/gatedloop:upgrade` say when one is due.
  - **Existing installs** get a `specloop` forwarder plugin that prints the switch-over steps and no longer runs the loop.
  - **Expiry:** the earlier names stop working in 0.8.0.

  Closes #31.

**Gates**

- **test-lock-remote-check** (specloop PR 146):
  - `gates tests check --ref <commit>` checks the authored-tests lock at a commit.
  - `gates merge` refuses a branch whose authored tests were changed.
  - `gates marker publish tests` posts a `gatedloop/tests` status for branch protection.

**Going public**

- **public-status** (specloop PR 147): the README opens with an honest status paragraph and a quickstart. `docs/status.md` replaces the field guide; the invite-only trial is over and the `field-trial` capability is retired. `docs/topology.md` shows the setup the maintainer runs, as an example to adapt.
- **go-public-migration** (specloop PR 148): the maintainer tooling that created this repository from a clean copy of the private one, with every issue moved and its references remapped.

**Upgrading from Specloop**

1. **Switch your plugin install.** In Claude Code:
   1. `/plugin update specloop@specloop`, which shows the forwarder's notice;
   2. `/plugin marketplace add tessellate-space/gatedloop`;
   3. `/plugin install gatedloop@gatedloop`;
   4. `/plugin uninstall specloop@specloop` and `/plugin marketplace remove specloop`.
2. **Migrate each project.** Run `gates migrate-name` in it, and commit the result.
3. **Update branch protection.** If it requires `specloop/ci`, change it to `gatedloop/ci`. Both are posted until 0.8.0.

## 0.6.0 — 2026-10-22

Planning and orchestrating at scale, a loop that stops for the right reasons, and
OpenSpec 1.14. Seven OpenSpec changes, driven mostly by field reports from an adopter
running a long-lived orchestrator over several implementer lanes.

**Planning and orchestration**

- **planner-handoff** (specloop PR 133): under `approval.plan: self`, merging the plan PR is the
  approval. `gates approval attest <change> --merged <pr>` takes the merger and time
  from the forge and the sha over the plan as merged. `gates record-merged` attests a
  merged `plan/<change>` PR in its one commit, so the manual attest step disappears in
  pull-request mode. `gates handoff <change>` refuses unless the plan is approved on
  the target, then prints a payload for a planner session to send to the
  orchestrator. `docs/running-at-scale.md` gains the planner/orchestrator contract and
  an example plan-check job. Approval values are now always quoted, so a value with
  ` #` survives YAML. Closes #41.
- **epic-linkage** (specloop PR 125): a story of several changes is a first-class epic.
  - **Linkage.** An epic is an ordinary change that its children name in
    `x-specloop-epic`, and the link is validated.
  - **Guarantees.** An epic is never implemented, and archives only after every
    child.
  - **Visibility.** `gates epics` and `gates stats --epic` show each child's state,
    and so does the session brief.
  - **Draining** an epic is a documented example, not a command. Closes #22.

**The loop**

- **retry-budget** (specloop PR 119): the attempt cap is enforced in code. Failed attempts are
  counted from the ledger, and each leaves a four-field note that a resumed or
  restarted agent reads. One fresh restart from a clean tree is allowed before a task
  escalates as `stalled`. Configure it with `loop.attempts` and `loop.fresh-restarts`;
  `gates stats --outcomes` counts restarts and recoveries. Closes #27.
- **authored-test-kinds** (specloop PR 134):
  - **Characterization tasks.** A task can be declared `characterization`, and its
    tests must then pass before implementation.
  - **Defect kinds.** Test defects are `setup` (cap 3) or `assertion` (cap 2), so
    fixture mistakes no longer spend the behaviour budget.
  - **Warm-up.** A cold-lane warm-up belongs in a gate's `requires`.
  
  Closes #42.
- **merge-lane-friction** (specloop PR 138):
  - **Not run, not red.** A merge step whose `ci` or `confirm` could not run (busy
    lock, failed precondition) is reported as not run and exits 75, never as a red
    merged tree.
  - **Lock priority.** A waiting merge takes the serialized lock before other
    waiters, bounded by `concurrency.merge-wait-seconds`.
  - **Permission scaffolding** now asks on `gates merge`, not on every `git merge`.
  
  Closes #43; addresses #44.

**Setup and compatibility**

- **openspec-1-14-compat** (specloop PR 123): OpenSpec 1.14 fails `validate --strict` on unknown
  `.openspec.yaml` keys.
  - **Approval keys** are now `x-specloop-approved-{by,at,sha}`. The old spelling is
    still read, and `gates approval migrate` renames it.
  - **Non-interactive runs.** Every `openspec` call runs with `OPEN_SPEC_INTERACTIVE=0`.
  - **Tested version:** OpenSpec 1.14.3.
  
  Closes #39.
- **gates-on-path** (specloop PR 132): the session brief adds the plugin's `bin/` to PATH through
  `CLAUDE_ENV_FILE` as a fallback. `gates doctor` gains `gates-on-path`, and the
  misleading `plugin-registered` row becomes `shim-location`. Closes #40.

**Upgrade notes**

- **Run `/specloop:upgrade` once after updating.** It offers:
  - migrating approval keys (`gates approval migrate`);
  - the retry budget;
  - replacing an old `ask: Bash(git merge *)` permission rule with `Bash(gates merge *)`.
- **Tested OpenSpec version:** 1.14.3. Older versions still work, and `gates doctor`
  warns.
- **Quoted approval values:** approvals written from now on have quoted values. Both
  spellings and both forms are read.

### Other changes

- 0.5 follow-ups (specloop PR 114):
  - the merge gate's audit now checks the incoming change, not the current branch, so
    an unaudited commit in a lane can't slip through;
  - the test suite no longer depends on the host's environment;
  - it passes on Python 3.9.
- Regenerated the repository's own OpenSpec commands and skills for 1.14.3 (specloop PR 120).
- Docs pass for 0.6.0 (specloop PR 140).

## 0.5.0 — 2026-10-19

Tests worth keeping, a merge Specloop performs, and upgrades that ask what's new.
Fourteen OpenSpec changes, most from field reports by an adopter running several
unattended lanes in parallel.

**Tests**

- **test-quality-rule** (specloop PR 97): a built-in `specloop.test-quality` rule that every
  convention review applies. The RED step asks its questions against your own
  `conventions.rules-doc`, and every behaviour task names its oracle.
- **split-test-author** (specloop PR 101): a Sonnet `test-author` agent writes every task's failing
  tests for the whole change before implementation starts. The tests are held and
  placed per task, and the commit hook locks them. A red run is enforced after
  placement, and the implementer can't weaken a test it didn't write.
  `loop.test-author: separate` is the default; `inline` keeps the same lock.

**Merging**

- **merge-step** (specloop PR 105): `gates merge <change>` merges in six steps in code: prove the
  head, squash, unscoped `ci`, an optional new `confirm` gate, record, archive. It
  pushes once, behind a merge lock. Each refusal exits with its step number and puts
  the checkout back. Adds `/specloop:merge` and the `merge-runner` agent.
- **merge-pull-request** (specloop PR 108): in `integration.mode: pull-request`, `gates merge`
  publishes `specloop/<gate>` commit statuses (`gates marker publish` /
  `check-remote`) and hands the PR to the forge. `gates record-merged <sha>` records
  a forge merge and archives the change. `docs/running-at-scale.md` gives an example
  CI setup to adapt.
- **acceptance-gate** (specloop PR 82): an opt-in `approval.acceptance` gate in which a human
  accepts the working behaviour, pinned to the exact tree that merges. Ships with a
  generated acceptance brief.
- **cross-worktree-evidence** (specloop PR 111): a merge run from the primary checkout counts
  the markers the lane recorded in its own worktree. Hook install and `doctor` find
  git's shared hooks directory from any worktree. `--git-dir` and `--work-tree` are
  resolved. Fixes #38.

**Enforcement and lanes**

- **hook-correctness** (specloop PR 100): hook matching ignores redirections, heredoc bodies and
  `--help`. Only integration merges are gated. Editing a file never clears gate
  evidence, a stale-marker denial names what changed, and a branch checked out in
  two worktrees can't be committed to.
- **lock-and-ledger-hygiene** (specloop PR 102): the gate lock waits on a bounded, rate-limited
  schedule, and `gates lock status` shows it. The git pre-commit hook runs the same
  `discipline check-commit` as the tool hook.
- **escalation-outcomes** (specloop PR 80): a closed set of halt causes, `intervention` ledger
  rows, a halt-aware Stop hook, and `gates stats --outcomes`.
- **schema-declared-flow** (specloop PR 99): a schema declares its loop with
  `specloop: { flow: regression-first }`. A schema is implementable when it has an
  `apply` block with `tracks`. Dispatch no longer needs PyYAML.

**Upgrading**

- **adoption-prompts** (specloop PR 104) and **adoption-followups** (specloop PR 107): after a plugin
  update, the session brief says when there are new settings to decide.
  `/specloop:upgrade` asks one question per setting and records each answer in
  `.specloop/adoption.json`, so nothing is asked twice. This release asks about
  acceptance, the test author, test conventions, runner strictness, schema flow, the
  `confirm` gate, and refreshing an outdated copy of the git hook.
- **release-procedure** (specloop PR 81) and **release-docs-sync** (specloop PR 98): this repo's own
  `scripts/release` and docs check, which keep README and SETUP in step with what
  ships.

**Upgrade notes**

- Run `/specloop:upgrade` once after updating. If you installed the git hook
  directly (no hook manager), let it refresh the hook: the copy installed by 0.4.0
  runs the older check.
- `hooks/clear-ci-marker.sh` is gone. Editing a file no longer clears gate evidence.

### Other changes

- Wrote the four placeholder spec purposes and pointed links at the moved repo (specloop PR 76).
- Drew the loop as a diagram in the README (specloop PR 79).
- Docs pass for 0.5.0 (specloop PR 113).

## 0.4.0 — 2026-09-29

Workflow packs and a checkout-independent marker key.

- **workflow-packs** (specloop PR 62): the apply flow dispatches on the change's schema;
  guided schema install available at any time; schema inspection before
  trust; the bugfix and architecture packs.
- **fix-normalize-tree-checkout-dependence** (specloop PR 61): the ledger-normalized
  marker key no longer depends on the current checkout, so squash-merges stop
  being denied with identical hashes (fixes #21).

Planned, not in this release: escalation-outcomes (specloop PR 72), acceptance-gate (specloop PR 73).

## 0.3.0 — 2026-09-18

The field-fix release. Eight OpenSpec changes, implemented test-first by
tdd-implementer agents and landed through one serialized merge lane (specloop PR 48,
specloop PR 51-specloop PR 57):

- **harden-hook-matching**: hooks match the subcommand token, archive moves
  commit at planning grade, every denial names its remedy.
- **fix-marker-mechanics**: ledger-blind marker trees, skip verdicts, recipe
  dedupe, incoming-ref merge check, ledger-grade commits.
- **scope-audit-to-branch-commits**: the reflog audit exempts merge-target
  ancestry.
- **gate-preconditions**: `requires` probes, exit 75 for a down environment.
- **scale-gate-cost**: surface-scoped ci/unit, full ci as the merge floor,
  quiet-on-green output, review delegation as a MUST.
- **worktree-native-loop**: N implementers in worktrees feeding one merge lane
  is first-class.
- **gates-stats**: `gates stats` gate-economics report and playbook.
- **remove-harness-compat**: `bin/harness` and the legacy manifest fallback are
  gone.

This repo now declares `approval.plan=self`.

## 0.2.0 — 2026-09-07

The enforcement layer is complete on `main` (specloop PR 36).

- **harden-unattended-loop** closure: `gates review record` writes the
  convention review's verdict to the ledger; `gates task start` / `gates task
  changed` record the tree each task starts from; plan-approval attestation
  verified end to end against real PRs.
- Also released: the already-merged unblock-parallel-planning,
  expand-brace-globs and solo-approval-mode.

Version-gated plugin updates mean every content-bearing merge needs a bump from
now on.
