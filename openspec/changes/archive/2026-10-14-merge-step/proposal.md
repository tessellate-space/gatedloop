# Proposal: merge-step

## Why

Specloop gates the merge but does not perform it. `tdd-apply` 7.5 describes local
integration in three lines: check out the target, squash, commit. Everything else is
left to the adopter. #36's adopter runs integration as a 16-step recipe, driven by a
plain agent with a brief retyped for every dispatch, and every failure of their week
landed there. #35 names the merge step as the first role they had to hand-roll, and
asks (C) that the verify coverage check run inside it, so that it stops being
optional.

Stripped to what doesn't vary between projects, a merge is six steps:

1. prove the branch head;
2. integrate;
3. prove the merged tree;
4. record;
5. confirm the merged tree live;
6. archive.

Only step 2 depends on the integration mode. Only step 5 needs a project command, and
Specloop already binds project commands to abstract gate names. Owning these six steps
is the rejection test's core case: it makes "verified on main" enforceable instead of
leaving it as a sentence.

This change covers `local-squash-merge`, the mode this repo and #36's adopter use.
Pull-request mode is `merge-pull-request`, which reuses the same step sequence.

## What Changes

- **`gates merge <change>`** runs the six steps in code. It halts with the exact
  refusal on the first red, and in local mode nothing reaches the remote until every
  step has passed:
  1. **Prove the head.**
     - Commit any trailing ledger rows on the branch. This retires #36's "local
       changes would be overwritten" refusal when detaching.
     - Require the head's live-check marker, a green `verify` if declared, and
       acceptance where a policy is declared. None of this is new; it is the merge
       hook's own checks, run in code.
     - Print the acceptance brief's coverage: each scenario `covered` or
       `check by hand`.
  2. **Integrate.** Fetch, detach onto the target's tip, and `git merge --squash`. A
     conflict halts. The target is untouched, and the primary checkout is restored.
  3. **Prove the merged tree.** Run an unscoped `gates run ci` on the staged squash,
     then commit it.
  4. **Record.** `gates ledger record-merge` against the squash commit's real sha,
     committed at ledger grade.
  5. **Confirm.** If the new optional `confirm` gate is declared, run it on the
     merged tree. A red `confirm` stops the merge before the push, so nothing is
     published.
  6. **Archive and publish.** `openspec archive <change> --yes`, the archive commit,
     then one push of all three commits to the target. If the target moved since the
     fetch, retry from step 2 once, then halt.
- **One merge at a time per machine.** `gates merge` holds a `merge` lock using the
  serialized-gate mechanism, bounded like other serialized gates
  (`lock-and-ledger-hygiene`).
- **`confirm` is a new optional gate** in the gate contract. It is the project's
  "bring the merged tree up and smoke it" recipe. The plugin never reads its body.
  Undeclared, step 5 is skipped with a printed note.
- **A `/specloop:merge <change>` command** for a human to trigger it, and a
  `merge-runner` agent (Sonnet) for an orchestrator. The agent runs `gates merge`. On
  a squash conflict it may sync the target into the change branch and resolve a
  conflict that is purely mechanical, then re-run the head's gates and retry once. It
  halts on anything that needs judgement.
- **Who may trigger a merge is unchanged.** The declared process still decides:
  - `integration.requireApproval` and `approval.acceptance` still gate the merge, and
    `gates merge` enforces both in code;
  - `tdd-implementer` still never merges;
  - `tdd-apply` 7.5's local branch now calls `gates merge`.

## Capabilities

### New Capabilities

- `merge-step`: the six-step merge, its halting and publishing rules, the merge lock,
  and the merge-runner agent.

### Modified Capabilities

- `gate-binding`: the optional `confirm` gate.

## Impact

- `bin/gates`: `merge` subcommand, `merge` lock, `confirm` in the gate table and schema.
- New `commands/merge.md` and `agents/merge-runner.md`.
- `skills/tdd-apply/SKILL.md` 7.5; `commands/archive.md` notes that `gates merge`
  archives as its step 6.
- SETUP.md: the `confirm` gate, the merge step, and what stays the adopter's
  (environment recipes). `gates-init` offers to bind `confirm`, and `adoption-prompts`
  gains a `confirm-gate` item.
- `tests/`: each step's refusal, conflict and moved-target paths, run in temporary
  repositories with a bare remote.
- Depends on `hook-correctness` (integration-only merge gating) and
  `lock-and-ledger-hygiene` (the bounded lock). Ships in 0.5.0.
