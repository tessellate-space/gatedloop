# Proposal: merge-pull-request

## Why

`merge-step` owns local integration. Teams that integrate through pull requests, like
#36's second column and this repository, still hit three gaps. Specloop can close
them without becoming anyone's CI:

- **Evidence doesn't travel.** Gate markers live under `.git/` on the machine that ran
  the gate. Nothing the forge or a CI job can read says which tree passed which gate.
- **Nothing records the merge.** A merge in the forge's UI never writes the ledger's
  merge row, so `gates stats --outcomes` shows every PR-merged change as in progress.
  This repo's maintainer has recorded that row by hand after every merge.
- **An orchestrator can't see "ready" without session memory** (#37). The
  implementer's READY exists only in its report.

**Scope.** Checked against Specloop's charter (discussion on specloop PR 95): the plugin owns the
loop's evidence and the commands that act on it. The team's CI, forge configuration
and orchestration vary by team, so they stay the adopter's. This change therefore
ships primitives plus a documented example of wiring them up. It ships no workflow
template and no orchestrator.

## What Changes

- **Markers travel as commit statuses.**
  - `gates marker publish <gate> [--sha]` posts a `specloop/<gate>` status on a commit
    whose ledger-normalized tree has a green local marker. The status carries that
    tree hash.
  - `gates marker check-remote <gate> <sha>` verifies one: the status must exist, be
    successful, and name the sha's own normalized tree.
  - Both commands go through the forge CLI, an optional dependency that `doctor`
    checks when pull-request mode is declared.
- **`gates merge <change>` in pull-request mode** is the loop's own finish:
  - it proves the head, as in local mode, and commits trailing ledger rows;
  - it pushes the branch and publishes the head's markers;
  - it opens or updates the PR with the acceptance brief as its body;
  - it enables squash auto-merge only when neither `requireApproval` nor a declared
    acceptance policy stands in the way. Otherwise it prints the PR URL and stops.

  `tdd-apply` 7.5's pull-request prose becomes this one call.
- **`gates record-merged <sha>`** is a command any CI can call after a push to the
  target:
  - it finds the change a squash commit came from, through its PR's head branch;
  - it records the merge row against the real sha;
  - it archives the change, and commits both locally.

  Pushing that commit is the caller's job, and it skips commits that aren't changes.
- **Ready is a ledger fact.** `gates ledger record-ready <change>` appends a `ready`
  row. `tdd-implementer` records and commits it, at ledger grade, immediately before
  its READY report. An adopter's orchestrator or console reads lane state from the
  committed ledger.
- **A documented example: "Running Specloop at scale"** (`docs/running-at-scale.md`).
  It shows how to build an orchestrator and CI from what ships, without Specloop
  owning either:
  1. selection with `gates approval check`;
  2. the authoring phase, then `tdd-implementer`, in one worktree per lane;
  3. reading `ready` and `halt` rows;
  4. `gates merge` in either mode;
  5. publishing statuses;
  6. a sample GitHub Actions workflow that calls `gates run ci`, `gates marker
     publish` and `gates record-merged`;
  7. `gates stats --outcomes` to watch it all.

  The sample is marked as an example to adapt, not a supported template.
- **This repository follows its own example.** Its `.gates.yaml` declares
  `integration: { mode: pull-request, requireApproval: true }`. A workflow adapted
  from the example calls `gates record-merged` after each merge. The manual
  merge-row step goes away.

## Capabilities

### Modified Capabilities

- `merge-step`: pull-request mode, recording forge merges, and the ready row.
- `loop-enforcement`: markers published and verified remotely.

## Impact

- `bin/gates`:
  - `marker publish` and `marker check-remote`;
  - the pull-request branch of `gates merge`;
  - `record-merged`;
  - `ledger record-ready`;
  - a `gh` row in `doctor`.
- Prompts:
  - `skills/tdd-apply/SKILL.md` 7.5: pull-request branches;
  - `agents/tdd-implementer.md`: records `ready`;
  - `agents/merge-runner.md`: pull-request mode.
- Docs:
  - new `docs/running-at-scale.md`;
  - SETUP.md's pull-request section and branch-protection guidance, requiring the
    `specloop/*` statuses from the CI source;
  - a README pointer.
- This repo: `.gates.yaml` `integration:`, and `.github/workflows/specloop.yml` adapted
  from the example.
- Depends on `merge-step`. Ships in 0.5.0.
