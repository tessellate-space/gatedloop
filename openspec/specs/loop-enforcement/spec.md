# loop-enforcement Specification

## Purpose
The loop's guarantees are enforced by hooks and the durable ledger rather than stated in prompts. No commit happens without green `ci` on its tree, no merge without the live self-check on the incoming tree, no implementation before an attested approval, and any commit that slips past is detected after the fact, taints the change, and blocks the merge.

## Requirements

### Requirement: Gate hooks fire on the actual invocation, not a substring

A `PreToolUse` gate hook SHALL decide whether a command is a guarded invocation by
examining the command's parsed token structure, not by raw substring containment.
Specifically: the guarded verb MUST appear as the subcommand token of its program
(`merge` as git's subcommand, `archive` as openspec's, `new change` as openspec's),
with the program's global flags (for git: `-C <path>`, `-c <key>=<value>`,
`--git-dir=…`, `--work-tree=…`, pager flags) and leading environment assignments or
common wrappers skipped when locating that token. Compound commands (joined by
`&&`, `||`, `;`, `|`) SHALL be split into simple commands and each examined. A
token that merely *contains* the guarded phrase — a hyphenated sibling subcommand,
or prose inside a quoted argument — SHALL NOT trigger the gate. All Bash-matching
gate hooks SHALL share one matching implementation; per-hook ad-hoc patterns are
not permitted.

#### Scenario: A read-only merge-family query is not gated

- **WHEN** a session runs `git merge-base --is-ancestor A B` (or `git merge-tree`,
  `git merge-file`) with no fresh live-check marker present
- **THEN** the merge gate does not fire and the command proceeds, because
  `merge-base` is not the `merge` subcommand

#### Scenario: Quoted prose mentioning a guarded command is not gated

- **WHEN** a session runs a command whose quoted argument text contains the words
  "git merge" (for example `gh issue create --body "… git merge …"`)
- **THEN** no gate fires, because the phrase sits inside an argument token, not in
  command position

#### Scenario: A guarded invocation phrased with global flags is still gated

- **WHEN** a session runs `git -C /path/to/repo merge some-branch` (or
  `git -c core.editor=true merge …`) without the required fresh marker
- **THEN** the merge gate fires and denies it, because the subcommand token after
  git's global flags is `merge`

#### Scenario: A guarded invocation inside a compound command is still gated

- **WHEN** a session runs `cd /repo && git merge some-branch` without the required
  fresh marker
- **THEN** the merge gate fires and denies it, because each simple command in the
  compound is examined

#### Scenario: An unparseable command falls back conservatively

- **WHEN** a command string cannot be tokenized (for example unbalanced quotes) and
  it contains a guarded phrase as a substring
- **THEN** the gate still fires, preserving the raise-the-floor posture: parse
  failure never becomes a bypass

#### Scenario: Per-gate arguments are extracted from the matched command

- **WHEN** a gate needs an argument from the invocation (the change name after
  `openspec archive`, the branch name after `checkout -b` / `switch -c`)
- **THEN** the argument is read from the matched simple command's own tokens, never
  by scanning the whole command string for a flag that may belong to a different
  command

### Requirement: An archive-move commit is classified as what it is

The planning-grade commit classification SHALL treat the `archive` path segment
directly under the changes directory as the reserved archive namespace, never as a
change id. For a staged archive move, per-change OpenSpec validation SHALL NOT be
attempted against the literal segment `archive`, and SHALL NOT be attempted against
a change directory that the staged move removes from the working tree. Manifest
validation SHALL still run, and the merge-precedes-archive guarantee SHALL remain
enforced by the archive gate, not by this classification.

#### Scenario: An archive move commits at planning grade

- **WHEN** a change has been merged to the target branch, `openspec archive` has
  moved its directory under the changes directory's `archive/` namespace, and the
  session stages exactly that move and commits
- **THEN** the commit is allowed at planning grade — the manifest validates, no
  `openspec validate archive` is attempted, and no green `ci` marker is demanded
  for a pure planning-tree move

#### Scenario: Archiving an unmerged change is still denied

- **WHEN** a session attempts `openspec archive <change>` for a change not yet
  merged to the resolved target branch
- **THEN** the archive gate denies it, unchanged by this classification fix

### Requirement: Every enforcement denial names its unmet prerequisite and remedy

Every denial emitted by an enforcement hook or the discipline checks behind it
SHALL name the precise prerequisite that is unmet and the exact command that
satisfies it. A denial whose remedy can only be discovered by inspecting prior
commits or reading the enforcement source is a defect.

#### Scenario: A denied archive names the merge prerequisite and the remedy

- **WHEN** the archive gate denies `openspec archive <change>` because the change
  is not on the resolved target branch
- **THEN** the denial names the change and the target branch and states the
  satisfying action (merge the change branch to the target — and push, where the
  check reads the remote ref) before retrying

#### Scenario: A denied commit names the gate to run

- **WHEN** the commit gate denies a commit because no fresh marker matches the
  staged tree, or because a staged planning artifact fails validation
- **THEN** the denial names which check failed and the exact command to run
  (`gates run ci`, or the failing `openspec validate <change>`) before committing
  again

### Requirement: Commit is blocked unless CI passed on the tree being committed
A `git commit` SHALL be denied unless a fresh `ci` marker exists whose recorded tree matches the tree that would be committed (the staged index). The gate SHALL be an O(1) marker/hash comparison and SHALL NOT re-run CI.

#### Scenario: Commit after green CI on the same staged tree
- **WHEN** `gates run ci` passed and recorded the current index tree, and no tracked file changed since
- **THEN** the `PreToolUse` hook allows the `git commit`

#### Scenario: Commit attempted with no CI marker
- **WHEN** a `git commit` is attempted and no `ci` marker exists for the staged tree
- **THEN** the hook denies the commit (exit 2) and reports that `ci` must pass first

#### Scenario: Commit attempted after an edit invalidates the marker
- **WHEN** a tracked file is edited after a green `ci`, so the staged tree no longer matches the marker
- **THEN** the hook denies the commit — a marker cannot survive an edit

### Requirement: Merge is blocked unless the live self-check passed on the branch head
A `git merge` SHALL be denied unless a fresh `live-check` marker matches the current
branch head. When the manifest declares an acceptance policy, the merge SHALL
additionally be denied unless the ledger's latest `acceptance` row for the same tree
has verdict `accept` (see the acceptance-gate capability); when no acceptance policy is
declared, this additional check SHALL pass stating that acceptance is not required.
The existing `ask` permission rule on `git merge` SHALL remain: the ask is the human's
presence at the merge, the acceptance row is the human's recorded verdict on the
behaviour, and neither substitutes for the other.

#### Scenario: Merge after green live-check
- **WHEN** `gates run live-check` passed on the branch head and it has not advanced
- **THEN** the hook allows the `git merge`

#### Scenario: Merge attempted without a live-check marker
- **WHEN** a `git merge` is attempted with no matching `live-check` marker
- **THEN** the hook denies the merge and reports that the live self-check must pass first

#### Scenario: Merge without acceptance under a declared policy
- **WHEN** `approval.acceptance` is declared, the live-check marker matches and no taint
  is outstanding, but no `accept` row pins the incoming tree
- **THEN** the hook denies the merge and names the acceptance brief and attestation
  commands as the remedy

#### Scenario: Merge with acceptance under a declared policy
- **WHEN** `approval.acceptance` is declared and an `accept` row pins the incoming tree
  with no later `reject` for it
- **THEN** the hook allows the `git merge`, given the live-check and taint checks also
  pass

#### Scenario: Merge with no acceptance policy
- **WHEN** the manifest declares no `approval.acceptance`
- **THEN** the acceptance check passes without consulting the ledger and the merge is
  governed by the live-check, unscoped-`ci` and taint checks exactly as before

### Requirement: The loop continues unattended without spinning
A `Stop` hook SHALL continue the loop when a change branch is checked out, `tasks.md`
has unchecked tasks, the tree is clean at a task boundary, and the change's ledger
carries no recorded halt since the last task began; and it SHALL NOT continue when
already re-entered. A recorded halt is a `halt` row with no later `task-start` row for
the change: the shim's continue check SHALL treat that state as halted, so a halt the
implementer recorded takes effect and a halt it merely narrated does not. Starting a
task again (a new `task-start` row) SHALL be what lifts the halt, so a resumed run
continues normally.

#### Scenario: More tasks remain
- **WHEN** the session stops with unchecked tasks and a clean tree on a change branch,
  and the ledger holds no `halt` row after the latest `task-start`
- **THEN** the hook blocks the stop and directs continuation from the next unchecked task

#### Scenario: Runaway is prevented
- **WHEN** the `Stop` hook input has `stop_hook_active` set
- **THEN** the hook does not re-block, so it cannot infinite-loop

#### Scenario: Halted or blocked run does not spin
- **WHEN** the run halted or a gate is red (tree not clean at a task boundary)
- **THEN** the hook does not continue

#### Scenario: A recorded halt with a clean tree does not continue
- **WHEN** the session stops on a change branch with unchecked tasks and a clean tree,
  and the ledger's latest `halt` row for the change is newer than its latest
  `task-start` row
- **THEN** the continue check exits non-zero naming the recorded cause, and the hook
  hands control back instead of continuing

#### Scenario: An unrecorded halt is re-entered
- **WHEN** an implementer stops with unchecked tasks and a clean tree after writing a
  HALTED report but recording no `halt` row
- **THEN** the hook continues the loop exactly as for a task boundary — the halt did
  not take, because only the ledger can make it take

#### Scenario: Resuming lifts the halt
- **WHEN** a `task-start` row is appended after the `halt` row and the session later
  stops at a clean task boundary
- **THEN** the hook continues the loop again

### Requirement: Permission scaffolding is opt-in, personal, and enforces the pre-merge checkpoint
`/gatedloop:gates-init` SHALL offer — only with explicit confirmation — to write permission rules to `.claude/settings.local.json`, never to the shared `.claude/settings.json`.

#### Scenario: User opts in
- **WHEN** the user confirms permission scaffolding
- **THEN** rules are written to `.claude/settings.local.json`: `allow` for `gates *` / `openspec *` / `git commit *`, and `ask` for `git merge *`

#### Scenario: Merge always prompts a human
- **WHEN** the loop reaches `git merge`, even under an auto/accept permission mode
- **THEN** the `ask` rule forces a human confirmation, preserving "stop before the merge"

#### Scenario: User declines
- **WHEN** the user does not confirm
- **THEN** no permission file is written or modified

### Requirement: Every gate invocation is recorded in a durable ledger
`gates run <gate>` SHALL append one row to a durable, committed ledger recording the
outcome, separate from the ephemeral enforcement marker. The ledger SHALL survive a
squash-merge and SHALL NOT be stored anywhere that dies with the clone. Every row,
of every kind, SHALL carry a `session` value (`agent` or `human`) set by the ledger
writer from the presence of the Claude Code session marker.

#### Scenario: A gate runs and is recorded
- **WHEN** `gates run <gate>` completes, whether it passed or failed
- **THEN** a row is appended to `.gatedloop/runs/<change>.jsonl` recording at least the
  gate, exit code, duration, change, task, tree and session

#### Scenario: The marker and the ledger are different stores
- **WHEN** the enforcement marker and the ledger row are both written for the same gate run
- **THEN** the marker is under `.git/` and never committed, and the ledger row is under
  `.gatedloop/runs/` and is committed with the change

#### Scenario: The ledger survives a squash-merge
- **WHEN** a change branch with several per-task ledger rows is squash-merged to `main`
- **THEN** every row is present on `main`, because the ledger is append-only and the
  squashed commit carries the file's final state

#### Scenario: Rows are keyed on durable identifiers
- **WHEN** a ledger row is written
- **THEN** it is keyed on `(change, task)` rather than a commit SHA, so it is not
  orphaned when branch commits stop being ancestors of `main`

#### Scenario: The merge is linked back to main history
- **WHEN** a change is merged
- **THEN** exactly one row is appended mapping the change to the resulting squash
  commit on `main`

#### Scenario: Every row kind carries a session
- **WHEN** a row of any kind (gate, review, task-start, taint, merge, halt,
  intervention) is appended
- **THEN** it carries `session: "agent"` or `session: "human"`, decided by the writer
  and not by the caller

### Requirement: The OpenSpec git discipline is enforced, not described

The ordering rules gatedloop inherits from OpenSpec SHALL be enforced by hooks rather
than stated in prompt prose. The archive-follows-merge check SHALL accept a local
counterpart branch of the merge target that carries the change — the guarantee it
enforces is ordering, which a local merge proves — while printing a loud advisory
when the merge is not yet on origin, so a serialized merge lane needs no interim push
between each merge and its archive.

#### Scenario: Proposing from a change branch is refused

- **WHEN** a proposal artifact would be authored while a change branch is checked out
- **THEN** the hook denies it and reports that proposals run on `main`, where other
  in-flight changes and the authoritative specs are visible

#### Scenario: Archiving before merging is refused

- **WHEN** an archive is attempted for a change that has not yet been merged to the
  merge target on any counterpart, local or origin
- **THEN** the hook denies it, preserving merge-then-archive ordering

#### Scenario: Archiving a locally merged, unpushed change

- **WHEN** an archive is attempted for a change merged to the local counterpart of
  the merge target but not yet pushed to origin
- **THEN** the archive is allowed, with an advisory naming the unpushed merge and
  recommending a push before the session ends

### Requirement: Implementation cannot begin before the plan is merged and approved

The apply flow SHALL refuse to start implementation for a change whose artifacts are
not present on the merge target, or whose artifacts do not carry a populated
approval. Under approval policy `review`, the merge target SHALL be the origin ref —
the approval is anchored to the forge's approving review, and a purely local ref
cannot evidence it. Under approval policy `self`, a local counterpart branch of the
merge target SHALL be accepted when it carries the change, with a loud advisory that
the plan is not yet on origin and should be pushed before the session ends.

#### Scenario: The plan has not been merged

- **WHEN** implementation is attempted for a change whose artifacts exist only on a
  local change branch, not on any counterpart of the merge target
- **THEN** it is refused, reporting that the plan must be reviewed and merged to the
  merge target first

#### Scenario: The plan is merged but unapproved

- **WHEN** implementation is attempted for a change present on the merge target whose
  `.openspec.yaml` has no populated `approved_by`
- **THEN** it is refused, because a merge proves the plan landed, not that a human
  agreed with it

#### Scenario: The plan is merged and approved

- **WHEN** the change's artifacts are present on the merge target and its
  `.openspec.yaml` carries `approved_by`, `approved_at`, and an `approved_sha`
  matching the current artifact content
- **THEN** implementation proceeds and the approver is recorded in the run's ledger
  rows

#### Scenario: The plan was edited after approval

- **WHEN** implementation is attempted for a change whose artifact content no longer
  matches its recorded `approved_sha`
- **THEN** it is refused, because the approved content and the current content have
  diverged

#### Scenario: An unattended run cannot approve its own plan

- **WHEN** a headless run authors a plan and attempts to proceed to implementation in
  the same session
- **THEN** it is refused at the approval check, so the human checkpoint survives full
  automation

#### Scenario: Solo policy accepts a merged-but-unpushed plan

- **WHEN** approval policy is `self`, the change is merged and locally attested on
  the local counterpart of the merge target, but not yet pushed to origin
- **THEN** implementation proceeds, and the check prints an advisory that the plan is
  not on origin and should be pushed before the session ends

#### Scenario: Review policy does not accept a local-only merge

- **WHEN** approval policy is `review` and the change is present only on the local
  counterpart of the merge target, not on the origin ref
- **THEN** implementation is refused — a forge-anchored approval cannot be evidenced
  by a local ref

### Requirement: A plan is negotiated in a pull request
The authoring flow SHALL end by opening a pull request for the plan, so that review happens on a surface built for it rather than being left to chance.

#### Scenario: Artifacts are complete
- **WHEN** a change's plan artifacts are generated and validate
- **THEN** a pull request is opened whose body summarises what is proposed and what is deliberately left open

#### Scenario: The approval gate is reachable
- **WHEN** the loop later checks whether a plan is approved
- **THEN** a pull request exists that could have produced that approval, so the gate cannot deadlock on a condition the flow never creates

### Requirement: Approval is attested from the forge, never self-reported
Approval metadata SHALL be derived from the pull request's actual approving review, and SHALL NOT be authored by the model.

#### Scenario: The plan PR carries an approving review
- **WHEN** the plan pull request is merged and has a review in the `APPROVED` state
- **THEN** `approved_by` and `approved_at` are written from that review's author and timestamp, and `approved_sha` is computed over the artifact content at that moment

#### Scenario: The plan PR was merged without an approving review
- **WHEN** the plan pull request is merged with no review in the `APPROVED` state
- **THEN** no approval metadata is written, and the approval gate refuses implementation

#### Scenario: Attestation is unavailable
- **WHEN** the forge CLI is missing, unauthenticated, or offline at the moment approval would be recorded
- **THEN** the gate fails closed and reports why, and never falls back to an unattested or model-supplied value

#### Scenario: The model attempts to supply the value directly
- **WHEN** approval metadata would be written from any source other than the forge's review record
- **THEN** it is rejected, because a run that can write its own approval defeats the gate

### Requirement: The implementer emits a machine-readable final report
`tdd-implementer` SHALL end with a structured report so headless runs are queryable
without parsing prose. When the outcome is a halt, the report SHALL carry the cause
that was recorded in the ledger, and the ledger row SHALL be written before the report
is emitted — the report echoes the record; it is never the record. The report SHALL
also state whether a human acceptance step remains before the change can merge, read
from the declared policy, and the implementer SHALL generate the acceptance brief as
its last act before the report so the human's next step is already on screen.

#### Scenario: Report is structured
- **WHEN** an autonomous run finishes or halts
- **THEN** its final report contains `change`, `tasks_done`, `tasks_total`, `branch`,
  `gates`, `outcome`, `cause` and `acceptance` as parseable fields

#### Scenario: A halt names its cause
- **WHEN** the run halts
- **THEN** `gates halt record <cause> --task <N.M>` has already appended the `halt`
  row, and the report's `cause` equals that row's cause

#### Scenario: A completed run has no cause
- **WHEN** the run ends `READY TO MERGE`
- **THEN** `cause` is `null`

#### Scenario: Acceptance is required
- **WHEN** the run ends `READY TO MERGE` and the manifest declares
  `approval.acceptance`
- **THEN** `acceptance` is `"required"`, and the acceptance brief was printed
  immediately before the report

#### Scenario: Acceptance is not required
- **WHEN** the manifest declares no acceptance policy
- **THEN** `acceptance` is `"not-required"`, and the brief is still printed as
  information for the human who merges

### Requirement: Commit enforcement operates at the git layer, catching every commit-creating path

Commit enforcement SHALL act on the commit object being created, not on the phrasing
of the invocation. A git `pre-commit` hook SHALL deny any commit — created by any path
(`git commit`, a subprocess spawned from another program, a wrapper script, or a
library that talks to git directly) — unless a fresh `ci` marker exists whose recorded
tree matches the tree that would be committed (`git write-tree` of the staged index).
The check SHALL be the same O(1) marker/hash comparison the tool-invocation hook uses
and SHALL NOT re-run CI.

#### Scenario: An indirectly-created commit is gated

- **WHEN** a commit is created inside an agent session through a path that carries no
  `git commit` command string (for example a Python subprocess), and no green `ci`
  marker matches the staged tree
- **THEN** the git `pre-commit` hook denies the commit, so the invocation-string
  matcher's blind spot no longer lets an ungated commit through

#### Scenario: A gated commit through any path is allowed

- **WHEN** `gates run ci` passed and recorded the staged index tree, and a commit is
  then created by any path against that same tree
- **THEN** the git `pre-commit` hook allows it, because the marker matches the tree
  being committed

#### Scenario: The hook never re-runs CI

- **WHEN** the git `pre-commit` hook fires
- **THEN** it performs only a marker/tree comparison and never invokes the `ci` gate
  itself, so it cannot exceed a hook timeout

### Requirement: Git-layer commit enforcement is scoped to agent sessions

The git `pre-commit` hook SHALL enforce only when an agent session is present in the
environment, and SHALL be a transparent no-op otherwise. An agent session is present
when any variable named in `discipline.agent-env` is set; the default list is
`[CLAUDECODE]`. This scoping is deliberate and SHALL NOT be treated as a silent skip:
the gate exists to hold an autonomous loop to its invariant, and outside a session no
such loop is running the commit.

#### Scenario: A commit inside a session is enforced

- **WHEN** a commit is attempted and `CLAUDECODE` is present in the environment
- **THEN** the git `pre-commit` hook applies the marker check

#### Scenario: A human or CI commit is not gated

- **WHEN** a commit is made from a plain terminal, an IDE, or a CI runner, with
  `CLAUDECODE` absent from the environment
- **THEN** the git `pre-commit` hook is a no-op and the commit proceeds unhindered

#### Scenario: Another host's agent is declared

- **WHEN** `.gates.yaml` declares `discipline.agent-env: [CLAUDECODE, OTHER_HOST_VAR]`
  and a commit is attempted with only `OTHER_HOST_VAR` set
- **THEN** the git `pre-commit` hook applies the marker check

#### Scenario: An invalid declaration

- **WHEN** `discipline.agent-env` is not a list of non-empty variable names
- **THEN** `gates validate` fails naming the key

### Requirement: The git-layer commit hook installs without clobbering an existing hook

Installation of the git `pre-commit` hook SHALL be performed by deterministic shim
code (`gates hook install`), not by prompt prose. It SHALL detect who owns the hook
path — a hook manager (husky, lefthook, the `pre-commit` framework), a `core.hooksPath`
redirect, or a bare existing `.git/hooks/pre-commit` — and SHALL compose with it where
a safe composition is determinable, and refuse-and-instruct where it is not. It SHALL
NEVER overwrite an existing hook or hook-manager configuration, with one exception: a
direct copy of a gatedloop hook template whose body differs from the shipped template
SHALL be replaced with the shipped template, after its previous body is saved beside
it.

#### Scenario: An existing hook is present

- **WHEN** `gates hook install` runs in a repository that already has a `pre-commit`
  hook or a recognized hook manager
- **THEN** it composes the `gates` check into the existing flow without overwriting
  what is there

#### Scenario: The hook topology cannot be classified safely

- **WHEN** `gates hook install` cannot determine a safe way to compose with the
  existing hook setup
- **THEN** it refuses to modify anything and reports how to wire the check by hand,
  rather than clobbering

#### Scenario: No hook is present

- **WHEN** `gates hook install` runs in a repository with no existing `pre-commit`
  hook and no hook manager
- **THEN** it installs the shipped hook template directly

#### Scenario: A stale direct copy is present

- **WHEN** `gates hook install` runs and the hook path holds a direct copy of an
  earlier gatedloop template
- **THEN** it saves the old body to `pre-commit.gatedloop-prev` beside the hook,
  writes the shipped template in its place, keeps it executable, and names both paths

#### Scenario: A current direct copy is present

- **WHEN** `gates hook install` runs and the hook path holds a byte-identical copy of
  the shipped template
- **THEN** it changes nothing and says the hook is already installed

### Requirement: Onboarding offers git-layer enforcement with the adopter's consent

`/gatedloop:gates-init` SHALL offer to install the git `pre-commit` hook as a
default-yes step, SHALL NOT install it silently, and SHALL complete onboarding
normally if the adopter declines.

#### Scenario: The adopter accepts the offer

- **WHEN** onboarding reaches the hook-install step and the adopter confirms
- **THEN** it runs `gates hook install` and reports the result

#### Scenario: The adopter declines the offer

- **WHEN** onboarding reaches the hook-install step and the adopter declines
- **THEN** no git hook is installed or modified, and onboarding completes normally

### Requirement: An ungated commit is detected after the fact and taints the change

The `Stop` hook SHALL audit commits created since the last audited point by joining
each commit's tree to the durable ledger's green-`ci` rows for the change. A commit
whose tree has no matching green-`ci` row SHALL be reported loudly, naming the
offending commit, and SHALL record a taint on the change's durable ledger. This is
detection after the effect, not prevention, and SHALL NOT be presented as prevention.

The audit SHALL scope itself to the change branch's own commits: a commit already
reachable from the resolved merge target SHALL be exempt from tainting, because it
was gated by its own change before landing there. Merge-target ancestry SHALL be the
only exemption — authorship, committer identity, or timestamps SHALL NOT exempt a
commit. When no merge target can be resolved, the audit SHALL keep its current
behaviour and consider every commit in the walk (erring toward auditing more, never
toward silently skipping any).

The same walk SHALL classify a commit whose matching green-`ci` rows were all written
outside an agent session as a `human-commit` intervention (see the escalation-record
capability); classification is additive to tainting and never replaces it. The merge
gate SHALL run this audit before its taint check, so a commit created after the last
session stop is tainted or classified before the merge decision is made.

#### Scenario: All commits are gated

- **WHEN** the audit runs and every new commit's tree matches a green-`ci` ledger row
  for the change
- **THEN** no taint is recorded and nothing is reported as an incident

#### Scenario: A commit has no green-CI record

- **WHEN** the audit finds a new commit whose tree matches no green-`ci` ledger row
  (it slipped the invocation and git-layer hooks)
- **THEN** the audit reports the offending commit loudly and records a taint on the
  change's ledger

#### Scenario: The audit does not re-report the same commit

- **WHEN** the audit runs again after a commit was already audited
- **THEN** it only considers commits new since the last audited point and does not
  re-report an already-audited commit

#### Scenario: Adopted merge-target commits do not taint

- **WHEN** the change branch is fast-forwarded (or otherwise updated) onto a moved
  merge target and the audit runs, so commits already reachable from the merge
  target enter the range since the last audited point
- **THEN** those adopted commits are exempt and record no taint, even though their
  trees have no green-`ci` ledger row for this change

#### Scenario: A local ungated commit still taints after adoption

- **WHEN** after adopting merge-target commits, a new commit is created on the change
  branch without a green-`ci` ledger row for its tree
- **THEN** the audit taints that commit exactly as before — merge-target ancestry
  exempts only commits already on the merge target, never new local commits

#### Scenario: No merge target resolves

- **WHEN** the audit runs in a repository where no merge target can be resolved
- **THEN** the walk since the last audited point is unchanged from today and every
  commit in it is audited — the exemption never widens into a silent skip

#### Scenario: The merge gate audits before deciding

- **WHEN** a merge is attempted after a commit landed on the change branch since the
  last session stop
- **THEN** the merge gate runs the audit first, so that commit is tainted (no green
  record) or classified (human-gated) before the taint check that follows

### Requirement: A tainted change cannot be merged until it is re-verified

The merge gate SHALL refuse a change carrying an unresolved taint, in addition to its
existing green-`live-check`-on-head requirement. A taint SHALL be resolvable by
re-running `ci` green on the current branch head, which SHALL append a resolution to
the durable, append-only ledger rather than deleting the incident record.

#### Scenario: A tainted change is blocked at the merge

- **WHEN** a merge is attempted for a change whose ledger carries an unresolved taint
- **THEN** the merge gate denies it and reports that the change must be re-verified

#### Scenario: Re-verifying the head clears the taint

- **WHEN** `gates run ci` passes green on the current branch head of a tainted change
- **THEN** the taint is resolved (a resolution row is appended, and the incident row
  remains in history) and the merge is no longer blocked on that basis

### Requirement: The forge merge path is covered by documented branch protection for pull-request modes

For `pull-request` integration modes, project documentation SHALL state that forge
branch protection is required, because the forge merge path (`gh pr merge` or a
forge-UI merge) has no local git-hook equivalent and is not covered by the commit or
merge hooks. gatedloop SHALL NOT implement a forge-side merge gate itself. Where
`approval.acceptance: review` is declared, the documentation SHALL state that the
required review on the default branch is the acceptance review — the one `gates
acceptance attest --pr` reads — so that the forge path and the local path require the
same human act.

#### Scenario: A pull-request mode is documented

- **WHEN** an adopter configures `integration.mode: pull-request`
- **THEN** the documentation names branch protection on the default branch as a
  requirement and states which checks/reviews to protect

#### Scenario: The local merge path is distinguished from the forge path

- **WHEN** the documentation describes enforcement coverage
- **THEN** it states plainly that the local `git merge` path is covered by the merge
  gate while the forge merge path is covered only by branch protection

#### Scenario: Acceptance under review on the forge path

- **WHEN** an adopter configures `approval.acceptance: review` with
  `integration.mode: pull-request`
- **THEN** the documentation states that the protected branch's required review is the
  acceptance review, and that `gates acceptance attest --pr` records it into the
  ledger so the outcomes view can see it

### Requirement: A denied gate call is a loop violation, not an invitation to rephrase

The loop prompts (`skills/tdd-apply/SKILL.md`, `agents/tdd-implementer.md`) SHALL state
that a denied gate call means the gate is unsatisfied, and that rephrasing the
invocation to get past the denial is a loop violation rather than a solution.

#### Scenario: The norm is stated in the loop prompts

- **WHEN** a reader consults the loop's skill or agent prompt
- **THEN** it finds the explicit norm that a denial is to be satisfied, not rephrased
  around

### Requirement: The gate marker store keys recorded evidence by tree

A gate's recorded green evidence SHALL be keyed by the tree it was recorded for, with
a bounded number of recent trees retained per gate, rather than a single slot that
each new run overwrites. A marker check SHALL pass when the requested tree is among
the recorded trees for that gate, so a lane alternating between trees (for example a
serialized merge lane) never invalidates its own still-valid evidence by recording a
newer one. The retained set SHALL be pruned oldest-first, and a tree evicted from it
SHALL simply require a re-run — eviction is never an error. Marker storage SHALL
remain per-worktree and outside version control.

#### Scenario: Two trees stay green in one lane

- **WHEN** a gate passes green on tree A, then passes green on tree B, and a guarded
  command then acts on tree A again
- **THEN** the marker check for tree A still passes — recording B did not overwrite A

#### Scenario: An evicted tree requires a re-run

- **WHEN** more trees have been recorded for a gate than the retention bound keeps,
  and a guarded command acts on the oldest, evicted tree
- **THEN** the marker check fails with the standard stale-marker message naming the
  re-run, and one green re-run restores it

#### Scenario: Markers do not leak across worktrees

- **WHEN** two worktrees of the same repository each record markers for the same gate
- **THEN** each worktree's checks read only its own store, and neither can satisfy or
  invalidate the other's

### Requirement: Hook matching ignores redirections, heredoc bodies and help invocations

The command matcher SHALL NOT take a redirection token as an argument, SHALL NOT scan
the body of a heredoc for guarded invocations, and SHALL NOT treat a guarded command
carrying `--help` or `-h` as a guarded invocation. When a merge invocation matches but
no incoming ref can be parsed, the merge denial SHALL say that no ref was parsed rather
than reporting a stale marker.

#### Scenario: A squash merge with a trailing redirection

- **WHEN** the command is `git merge --squash <change> 2>&1`
- **THEN** the matcher extracts `<change>` as the incoming ref

#### Scenario: A heredoc mentions a gated command

- **WHEN** a command's heredoc body contains a guarded invocation as text
- **THEN** no hook treats it as that invocation

#### Scenario: A help invocation

- **WHEN** the command is `openspec archive --help 2>&1`
- **THEN** the archive hook does not treat it as archiving a change

#### Scenario: No ref can be parsed

- **WHEN** a merge invocation matches and its incoming ref cannot be extracted
- **THEN** a denial names that as the reason and does not mention a stale marker

### Requirement: Only integration merges are gated

The merge hook SHALL gate only a merge whose destination is the integration target. A
merge into any other branch SHALL pass the hook without a marker check.

When the same command switches branches before it merges, the hook SHALL judge the destination from the branch that switch names. A switch to a named branch other than the integration target's SHALL pass. A switch the hook cannot resolve to one named branch SHALL keep the merge gated, and the denial SHALL say to run the merge as its own command after the switch.

#### Scenario: Syncing the target into a change branch

- **WHEN** a change branch is checked out and the integration target is merged into it
- **THEN** the merge hook allows it without requiring a live-check marker

#### Scenario: Integrating a change

- **WHEN** the integration target is checked out and a change branch is merged into it
- **THEN** the merge hook applies its marker checks as before

#### Scenario: Switching to a change branch and syncing it

- **WHEN** one command runs `git checkout my-change && git merge --ff-only origin/main`
- **THEN** the merge hook allows it without requiring a live-check marker

#### Scenario: Switching to the target and merging

- **WHEN** one command runs `git checkout main && git merge --ff-only my-change`
- **THEN** the merge hook applies its marker checks as before

#### Scenario: A switch the hook cannot resolve

- **WHEN** one command runs `git checkout --detach origin/main && git merge my-change`
- **THEN** the merge hook applies its marker checks, and its denial says to run the merge as its own command after the switch

### Requirement: Editing a file never clears gate evidence

No hook SHALL clear a gate marker in response to a file write or edit. Gate markers
SHALL be invalidated only by their tree key no longer matching the tree being
committed or merged.

#### Scenario: A scratch file is written between the gate and the commit

- **WHEN** `gates run ci` passes, a file outside the staged set is written, and the
  commit is attempted with the same staged tree
- **THEN** the commit is allowed

#### Scenario: Another lane writes a file

- **WHEN** one worktree writes a file while another worktree holds a green marker
- **THEN** the other worktree's marker is unaffected

### Requirement: A stale-marker denial names what changed

When a commit is denied because the staged tree differs from the tree the `ci` marker
recorded, the denial SHALL list the paths that differ. When every differing path is
one newly staged since the marker was written, it SHALL say that those files were
staged after the gate ran.

#### Scenario: A new file staged after the gate

- **WHEN** `gates run ci` passed, a new file was then staged, and a commit is attempted
- **THEN** the denial names that file as staged after the gate ran and directs a
  re-run of the gate

### Requirement: The propose gate resolves proposal state without relying on HEAD

The propose gate SHALL decide whether a planning write is allowed from the change's
own state, whether its directory is tracked on the integration target, and SHALL
accept a detached HEAD. Every planning artifact path SHALL be treated consistently.

#### Scenario: Planning while the primary checkout is detached

- **WHEN** HEAD is detached for a merge step and a planning artifact is written for a
  change that is not in implementation
- **THEN** the write is allowed

#### Scenario: A tracked change directory

- **WHEN** a change directory is tracked on the integration target
- **THEN** the gate never describes it as untracked or unproposed

### Requirement: Only a branch that names an active change is a change

A branch SHALL be treated as a change, for ledger keying and every gate that resolves
a change from the branch, only when `openspec/changes/<branch>/` exists. A `--change`
value containing `/` SHALL be refused. On a detached HEAD with no `--change`, `gates
run` SHALL say that no ledger row was written.

#### Scenario: A planning branch

- **WHEN** `gates run ci` runs on a `plan/<name>` branch
- **THEN** no ledger row is written under `.gatedloop/runs/`

#### Scenario: A documentation branch

- **WHEN** `gates run ci` runs on a branch with no matching change directory
- **THEN** no ledger file is created for that branch

#### Scenario: A slash in an explicit change name

- **WHEN** `--change plan/<name>` is passed
- **THEN** the command refuses and names the bare change name to use instead

### Requirement: A branch checked out in more than one worktree cannot be committed to

The commit gates SHALL refuse a commit when the current branch is checked out in more
than one worktree. The implementer SHALL NOT force a checkout.

#### Scenario: A lane shares a branch with the primary

- **WHEN** a commit is attempted in a worktree whose branch is also checked out in
  another worktree
- **THEN** the commit is denied, naming both worktrees

### Requirement: Gate markers can be published as commit statuses and verified remotely

`gates marker publish <gate>` SHALL post a `gatedloop/<gate>` commit status on a commit
whose ledger-normalized tree matches a green local marker for that gate, carrying that
tree hash. `gates marker publish tests` SHALL instead evaluate the authored-test lock
against the commit's tree and post `gatedloop/tests` as success only when the lock
holds, carrying the same tree hash; a change with no authored tests publishes success
saying so. `gates marker check-remote <gate> <sha>` SHALL succeed only when that
status exists, is successful, and names the normalized tree of `<sha>` itself. Both
SHALL fail loud when the forge CLI is unavailable.

#### Scenario: Publishing a green marker

- **WHEN** `gates marker publish live-check` runs on a head whose tree has a green
  live-check marker
- **THEN** a `gatedloop/live-check` success status appears on the head's sha, carrying
  that tree hash

#### Scenario: A status for a different tree

- **WHEN** a `gatedloop/ci` status on a sha names a tree other than that sha's normalized
  tree
- **THEN** `check-remote` fails and names both trees

#### Scenario: No local marker

- **WHEN** `gates marker publish ci` runs with no green `ci` marker for the head's tree
- **THEN** it refuses and posts nothing

#### Scenario: The forge CLI is missing

- **WHEN** the forge CLI is not installed or not authenticated
- **THEN** both commands exit non-zero naming the missing prerequisite, and `gates
  doctor` reports it as a warning where pull-request mode is declared

#### Scenario: Publishing the lock

- **WHEN** `gates marker publish tests` runs on a head whose placed tests all match
  their placed content and whose placed tasks have their red runs recorded
- **THEN** a `gatedloop/tests` success status appears on the head's sha, carrying the
  tree hash

#### Scenario: Publishing a broken lock

- **WHEN** `gates marker publish tests` runs on a head where a placed test was edited
  past the commit hooks
- **THEN** it posts a failure status naming the path, and exits non-zero

### Requirement: Scale is documented as an example built from shipped primitives

The documentation SHALL include a worked example of running parallel lanes and a CI
integration using only commands and agents gatedloop ships. The example SHALL mark its
orchestrator loop and CI workflow as examples for the adopter to adapt, not as
supported components. It SHALL direct pull-request-mode adopters to require the
`gatedloop/*` statuses from their CI provider as the expected source.

#### Scenario: An adopter wants lanes and CI

- **WHEN** an adopter reads the scale documentation
- **THEN** it shows selection, authoring, lane dispatch, readiness, merge in both modes,
  status publishing and forge-merge recording, each through a named gatedloop command,
  with the orchestration and workflow presented as the adopter's own

### Requirement: A merge counts evidence recorded in the incoming branch's worktree

When a merge brings in a local branch that is checked out in another worktree, the
merge gate SHALL accept a marker from that worktree's marker store as well as from
the store of the worktree the merge runs in. A marker counts only if it matches the
incoming ref's tree, exactly as one in the merging worktree's own store must. The
same lookup SHALL serve the merge hook and `gates merge`. A denial SHALL name every
store it read. The commit gate SHALL NOT consult another worktree's store.

#### Scenario: Merging from the primary after proving the lane

- **WHEN** the change branch is checked out in a lane worktree, `gates run
  live-check` and an unscoped `gates run ci` passed green in the lane on the branch
  head, and `git -C <primary> merge --squash <change>` is issued from any working
  directory
- **THEN** the merge hook finds both markers in the lane's store and allows the merge

#### Scenario: The lane holds uncommitted work

- **WHEN** the lane's markers were recorded on a tree that the change branch's head
  does not point at
- **THEN** the merge hook denies the merge, naming the primary's store and the lane's
  store as the places it looked

#### Scenario: A commit in the primary is not vouched for by the lane

- **WHEN** the lane holds a green `ci` marker for a tree and the same tree is staged
  in the primary checkout, which has no marker of its own
- **THEN** the commit gate in the primary denies the commit

### Requirement: Hook installation and inspection use git's effective hooks directory

`gates hook install`, `gates doctor`'s hook check and the adoption hook detectors
SHALL locate the `pre-commit` hook in the directory git itself runs hooks from, as
`git rev-parse --git-path hooks` reports it. They SHALL NEVER read or write a linked
worktree's private git directory. Run from any worktree of a repository, they SHALL
report the same hook state.

#### Scenario: Doctor run from a linked worktree

- **WHEN** the hook is installed in the repository and `gates doctor` runs in a
  linked worktree
- **THEN** the hook row reports it installed, as it does in the primary checkout

#### Scenario: Install run from a linked worktree

- **WHEN** `gates hook install` runs in a linked worktree of a repository with no
  hook
- **THEN** it writes the hook to the repository's shared hooks directory, names that
  path, and the hook fires for a commit in the primary checkout

### Requirement: gatedloop's change metadata uses OpenSpec's tool-metadata prefix

The approval keys SHALL be written to `.openspec.yaml` as `x-gatedloop-approved-by`,
`x-gatedloop-approved-at` and `x-gatedloop-approved-sha`, which OpenSpec reserves for
tool metadata. Every reader SHALL accept the earlier spellings `approved_by`,
`approved_at` and `approved_sha`, preferring the new ones. Other requirements naming
the earlier spellings refer to these keys.

#### Scenario: Attesting writes the new keys

- **WHEN** `gates approval attest <change> --local` runs on a change whose
  `.openspec.yaml` carries `approved_by`
- **THEN** the file carries the three `x-gatedloop-approved-*` keys and none of the
  earlier ones, and `openspec validate <change> --strict` reports no unrecognized key

#### Scenario: An approval written by 0.5.0

- **WHEN** a change merged to the target carries only `approved_by`, `approved_at`
  and `approved_sha`
- **THEN** `check-implement` accepts its approval exactly as before

### Requirement: Old-spelled approval keys can be migrated and are diagnosed

`gates approval migrate [<change>]` SHALL rename the earlier approval keys to the new
spelling in each active change's `.openspec.yaml`, keeping values, without changing
the approval sha. `gates doctor` SHALL warn when an active change carries an earlier
spelling, naming the change and the command.

#### Scenario: Migrating an active change

- **WHEN** `gates approval migrate` runs and one active change carries `approved_by`
- **THEN** that file is rewritten to the new keys with the same values, and
  `gates approval check` still passes for it

#### Scenario: Doctor on an unmigrated change

- **WHEN** an active change carries `approved_sha`
- **THEN** `gates doctor` warns, naming the change and `gates approval migrate`

### Requirement: The shim runs OpenSpec non-interactively

Every `openspec` process the shim starts SHALL have `OPEN_SPEC_INTERACTIVE=0` in its
environment.

#### Scenario: A hook validates a change

- **WHEN** a planning-grade commit check runs `openspec validate`
- **THEN** the process environment carries `OPEN_SPEC_INTERACTIVE=0`

### Requirement: A push to the merge target is gated at the git layer

Inside an agent session, a git `pre-push` hook SHALL deny a push that updates the merge target's branch unless the pushed commit is proven: a `merge` ledger row records that commit, or the merge gate's incoming-tree checks hold for the pushed commit's tree. Pushes of any other branch, deletions, and pushes outside an agent session SHALL pass untouched. The hook SHALL NOT run any gate.

#### Scenario: The shim's own merge push

- **WHEN** `gates merge` completed its steps and pushes the target
- **THEN** the hook finds the merge row for the pushed commit and allows the push

#### Scenario: A raw merge pushed without proof

- **WHEN** an agent merges a branch into the target by hand and pushes, with no merge row and no live-check marker for the pushed tree
- **THEN** the hook denies the push naming the unmet check and `gates merge` as the remedy

#### Scenario: A feature branch push

- **WHEN** an agent pushes a change branch in pull-request mode
- **THEN** the hook does nothing and the push proceeds

#### Scenario: A human push

- **WHEN** the target is pushed with no agent-env variable set
- **THEN** the hook is a no-op

### Requirement: Both git-layer hooks install and are diagnosed through one path

`gates hook install` SHALL install the `pre-push` hook beside `pre-commit` under the same owner detection, composition and refuse-and-instruct rules, and SHALL write the installing shim's path into each hook as the last fallback for resolving the shim. `gates doctor` SHALL report a `git-push-hook` row with the same states as the commit hook's row.

#### Scenario: A fresh install

- **WHEN** `gates hook install` runs in a repository with no hooks and no manager
- **THEN** both templates are installed, executable, and `gates doctor` reports both wired

#### Scenario: Only the commit hook is present

- **WHEN** a repository has the current `pre-commit` template and no `pre-push`
- **THEN** `gates doctor` reports the push hook absent, and the adoption catalogue offers to install it

#### Scenario: The recorded shim path is gone

- **WHEN** the shim path written into a hook no longer exists and neither the plugin root nor PATH resolves the shim
- **THEN** `gates doctor` reports the hook as stale and the refresh item offers to reinstall it

### Requirement: Enforcement coverage is documented per layer and host

Project documentation SHALL state, for each guarantee the loop makes, which layer enforces it: the tool-hook layer (Claude Code sessions), the git layer (any host, inside a declared agent session), or the forge (branch protection and published statuses). It SHALL say plainly which guarantees hold on a host other than Claude Code.

#### Scenario: An adopter on another host reads the docs

- **WHEN** an adopter runs the loop from a host that is not Claude Code
- **THEN** the documentation tells them the shim, the ledger, the commit and push gates and the forge statuses hold, and that the tool-hook denials (implement, scaffold, propose, archive, the Stop audit) do not

### Requirement: The push hook is opt-in and a decline sticks

The `pre-push` hook SHALL be installed only with the adopter's consent. `gates hook install --commit-only` SHALL install or refresh the `pre-commit` hook alone and record the `git-push-hook` adoption item as `declined`. While that item is recorded `declined`, a plain `gates hook install` SHALL skip `pre-push` and say how to add it; `gates hook install --push` SHALL install it and record `adopted`.

#### Scenario: Installing the commit hook only

- **WHEN** an adopter runs `gates hook install --commit-only`
- **THEN** only the `pre-commit` hook is installed or refreshed, and the `git-push-hook` item is recorded `declined`

#### Scenario: A re-install after a decline

- **WHEN** the `git-push-hook` item is recorded `declined` and an adopter runs `gates hook install`
- **THEN** only the `pre-commit` hook is installed or refreshed, the output says the push hook was skipped and names `gates hook install --push`, and no `pre-push` hook is written

#### Scenario: Opting back in

- **WHEN** an adopter who declined runs `gates hook install --push`
- **THEN** the `pre-push` hook is installed and the `git-push-hook` item is recorded `adopted`

#### Scenario: The doctor respects a decline

- **WHEN** the `git-push-hook` item is recorded `declined` and no `pre-push` hook is installed
- **THEN** `gates doctor` reports the `git-push-hook` row as ok, naming the decline, and does not warn

### Requirement: The git-layer hooks act only inside a declared agent session

The `pre-commit` and `pre-push` hooks SHALL check anything only when a variable named in `discipline.agent-env` (default `[CLAUDECODE]`) is set. Otherwise each SHALL exit 0 without checking, so commits and pushes made by a human in a terminal, from an IDE, or by a CI runner are untouched, whether or not the hooks are installed.

#### Scenario: A human commits and pushes the target

- **WHEN** no `discipline.agent-env` variable is set and a human commits code and pushes the merge target with both hooks installed
- **THEN** neither hook checks anything, and the commit and the push proceed

#### Scenario: A CI runner pushes

- **WHEN** a CI job without any `discipline.agent-env` variable set pushes any branch, the merge target included
- **THEN** the `pre-push` hook exits 0 without checking

### Requirement: Plan approval is unchanged by the git-layer hooks

This change SHALL NOT alter how a plan is approved. `approval.plan: self` local attestation, `review`, and a merge of the plan's pull request as its approval SHALL work exactly as before. The push gate SHALL check only a pushed commit's merge proof (a merge row or the incoming-tree checks), never how the change's plan was approved.

#### Scenario: A self-attested plan

- **WHEN** a project declares `approval.plan: self` and a maintainer runs `gates approval attest <change> --local`
- **THEN** the approval is recorded and checked exactly as before this change

#### Scenario: The push gate does not read the approval

- **WHEN** a change merged by `gates merge` is pushed to the target
- **THEN** the push gate allows it on its merge row alone, whatever approval policy the project declares
