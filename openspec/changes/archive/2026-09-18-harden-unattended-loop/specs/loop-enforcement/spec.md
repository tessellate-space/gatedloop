## ADDED Requirements

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
A `git merge` SHALL be denied unless a fresh `live-check` marker matches the current branch head.

#### Scenario: Merge after green live-check
- **WHEN** `gates run live-check` passed on the branch head and it has not advanced
- **THEN** the hook allows the `git merge`

#### Scenario: Merge attempted without a live-check marker
- **WHEN** a `git merge` is attempted with no matching `live-check` marker
- **THEN** the hook denies the merge and reports that the live self-check must pass first

### Requirement: The loop continues unattended without spinning
A `Stop` hook SHALL continue the loop when a change branch is checked out, `tasks.md` has unchecked tasks, and the tree is clean at a task boundary; and it SHALL NOT continue when already re-entered.

#### Scenario: More tasks remain
- **WHEN** the session stops with unchecked tasks and a clean tree on a change branch
- **THEN** the hook blocks the stop and directs continuation from the next unchecked task

#### Scenario: Runaway is prevented
- **WHEN** the `Stop` hook input has `stop_hook_active` set
- **THEN** the hook does not re-block, so it cannot infinite-loop

#### Scenario: Halted or blocked run does not spin
- **WHEN** the run halted or a gate is red (tree not clean at a task boundary)
- **THEN** the hook does not continue

### Requirement: Permission scaffolding is opt-in, personal, and enforces the pre-merge checkpoint
`/specloop:gates-init` SHALL offer — only with explicit confirmation — to write permission rules to `.claude/settings.local.json`, never to the shared `.claude/settings.json`.

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
`gates run <gate>` SHALL append one row to a durable, committed ledger recording the outcome, separate from the ephemeral enforcement marker. The ledger SHALL survive a squash-merge and SHALL NOT be stored anywhere that dies with the clone.

#### Scenario: A gate runs and is recorded
- **WHEN** `gates run <gate>` completes, whether it passed or failed
- **THEN** a row is appended to `.specloop/runs/<change>.jsonl` recording at least the gate, exit code, duration, change, task and tree

#### Scenario: The marker and the ledger are different stores
- **WHEN** the enforcement marker and the ledger row are both written for the same gate run
- **THEN** the marker is under `.git/` and never committed, and the ledger row is under `.specloop/runs/` and is committed with the change

#### Scenario: The ledger survives a squash-merge
- **WHEN** a change branch with several per-task ledger rows is squash-merged to `main`
- **THEN** every row is present on `main`, because the ledger is append-only and the squashed commit carries the file's final state

#### Scenario: Rows are keyed on durable identifiers
- **WHEN** a ledger row is written
- **THEN** it is keyed on `(change, task)` rather than a commit SHA, so it is not orphaned when branch commits stop being ancestors of `main`

#### Scenario: The merge is linked back to main history
- **WHEN** a change is merged
- **THEN** exactly one row is appended mapping the change to the resulting squash commit on `main`

### Requirement: The OpenSpec git discipline is enforced, not described
The ordering rules Specloop inherits from OpenSpec SHALL be enforced by hooks rather than stated in prompt prose.

#### Scenario: Proposing from a change branch is refused
- **WHEN** a proposal artifact would be authored while a change branch is checked out
- **THEN** the hook denies it and reports that proposals run on `main`, where other in-flight changes and the authoritative specs are visible

#### Scenario: Archiving before merging is refused
- **WHEN** an archive is attempted for a change that has not yet been merged to `main`
- **THEN** the hook denies it, preserving merge-then-archive ordering

### Requirement: Implementation cannot begin before the plan is merged and approved
The apply flow SHALL refuse to start implementation for a change whose artifacts are not present on `main`, or whose artifacts do not carry a populated approval.

#### Scenario: The plan has not been merged
- **WHEN** implementation is attempted for a change whose artifacts exist only on a local branch
- **THEN** it is refused, reporting that the plan must be reviewed and merged to `main` first

#### Scenario: The plan is merged but unapproved
- **WHEN** implementation is attempted for a change present on `main` whose `.openspec.yaml` has no populated `approved_by`
- **THEN** it is refused, because a merge proves the plan landed, not that a human agreed with it

#### Scenario: The plan is merged and approved
- **WHEN** the change's artifacts are present on `main` and its `.openspec.yaml` carries `approved_by`, `approved_at`, and an `approved_sha` matching the current artifact content
- **THEN** implementation proceeds and the approver is recorded in the run's ledger rows

#### Scenario: The plan was edited after approval
- **WHEN** implementation is attempted for a change whose artifact content no longer matches its recorded `approved_sha`
- **THEN** it is refused, because the approved content and the current content have diverged

#### Scenario: An unattended run cannot approve its own plan
- **WHEN** a headless run authors a plan and attempts to proceed to implementation in the same session
- **THEN** it is refused at the approval check, so the human checkpoint survives full automation

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
`tdd-implementer` SHALL end with a structured report so headless runs are queryable without parsing prose.

#### Scenario: Report is structured
- **WHEN** an autonomous run finishes or halts
- **THEN** its final report contains `change`, `tasks_done`, `tasks_total`, `branch`, `gates`, and `outcome` as parseable fields
