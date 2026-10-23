# Design: merge-pull-request

## Context

The first draft of this change also shipped a GitHub Actions workflow template, bot
follow-up PRs, merge-queue jobs, a protection-bypass token option, and an installer
in `gates-init`. That was withdrawn after a scope review (specloop PR 95's closing comment).
A team's CI and forge setup vary by team, which is the axis Specloop delegates rather
than owns. What remains:

- **Evidence that travels:** D1.
- **The loop's own finish in pull-request mode:** D2.
- **One command that turns a forge merge into ledger facts:** D3.
- **Readiness as a ledger fact:** D4.
- **A worked example** of assembling an orchestrator and CI from these: D5.

GitHub is the forge through `gh`, which `approval attest --pr` already uses.

## Decisions

### D1. Markers as statuses

- **`gates marker publish <gate> [--sha S]`.** `S` defaults to HEAD.
  - It requires a green local marker keyed on `_normalize_tree(S^{tree})`.
  - It posts, via `gh api repos/{owner}/{repo}/statuses/S`:
    - `state=success`;
    - `context=specloop/<gate>`;
    - `description="tree <hash>"`;
    - `target_url` set to the CI run when `GITHUB_RUN_ID` is present.
  - A skip-verdict live-check publishes `"tree <hash> (skip: no hot surface)"`.
- **`gates marker check-remote <gate> <sha>`** requires the latest `specloop/<gate>`
  status to be `success`, with its hash equal to `_normalize_tree(<sha>^{tree})`.
- **Owner and repo** come from `gh repo view --json nameWithOwner`.
- **Missing `gh`, or unauthenticated:** fail loud, naming it. `doctor` gains a `gh`
  row that warns only under `integration.mode: pull-request`.

A status posted from a laptop is self-reported. Protection that requires the statuses
with CI as their expected source is what makes them evidence. SETUP.md says this, and
the example (D5) does it.

### D2. `gates merge`, pull-request branch

`merge-step` D2's steps 0–1, then:

```
git push -u origin <change>
gates marker publish live-check ; gates marker publish ci
gh pr view <change> || gh pr create --head <change> --title "<change>: <title>" \
                                    --body "<gates acceptance brief output>"
(update: gh pr edit --body …)
requireApproval=false and acceptance satisfied → gh pr merge <change> --squash --auto
otherwise → print URL, exit 0 "waiting for review"
```

It takes the same `merge` lock, and exits 0 when it has handed off to the forge.
`tdd-apply` 7.5's two pull-request branches collapse to `gates merge <change>`.
`merge-runner` treats a handed-off PR as success.

### D3. `gates record-merged <sha>`

1. Resolve the pull request: `gh api repos/{o}/{r}/commits/<sha>/pulls`, and take
   `head.ref` from the first merged one.
2. **Skip with a note and exit 0** when:
   - there's no PR;
   - `head.ref` is not a directory-backed active change (`hook-correctness` D6);
   - the change is already archived.
3. `gates ledger record-merge <change> --sha <sha>`.
4. `openspec archive <change> --yes`.
5. One commit, `archive change: <change>`, holding the ledger row, the archive move
   and `openspec/specs`. It is ledger-grade and planning-grade, so it's allowed
   without a `ci` marker.
6. Print what was committed. Never push. Whether the commit lands by a direct push
   or a follow-up PR is the caller's CI's decision, shown both ways in D5.

The command is the whole of what this repo's maintainer has been doing by hand. It is
also what a CI job calls after a push to the target.

### D4. The `ready` row

`gates ledger record-ready <change>` appends `{"gate": "ready", "exit": 0, ...}`,
using the existing row shape with no new fields. `tdd-implementer`, immediately before
its READY TO MERGE report:
1. runs `record-ready`;
2. commits the ledger at ledger grade, with the message "record ready";
3. then reports.

A halted run records its `halt` row instead, which already exists. So a reader can
tell ready from halted from in-progress using only the committed ledger:

| Row | Meaning |
|---|---|
| a `ready` row newer than any `halt` | ready |
| a `halt` row newer than the last `task-start` | halted |
| otherwise | in progress |

`gates stats --outcomes` isn't changed here. It already reads merges and halts.

### D5. `docs/running-at-scale.md`

This is a worked example, clearly headed "Example — adapt to your team". It covers:

1. **Choosing what to run.** Loop over `openspec list --json`, keeping changes where
   `gates approval check <change>` passes and no `ready` or merge row exists. Ordering
   and parallel-safety rules are the team's; the doc shows where they plug in.
2. **Authoring first.** Dispatch `test-author` for the change (`split-test-author`),
   then create a worktree (`git worktree add`) and dispatch `tdd-implementer` with the
   change name and the worktree path.
3. **Watching.** Read the change's committed ledger for `ready` and `halt` rows, and
   route a `test-defect` halt back to the author.
4. **Finishing.** Run `gates merge <change>` from the lane's worktree, in either mode.
   Remove the worktree after the merge.
5. **CI (pull-request mode).** A sample GitHub Actions workflow of about 30 lines:
   - on `pull_request`: `gates run ci` and `gates marker publish ci`;
   - on `push` to `main`: `gates record-merged $GITHUB_SHA`, then either a push or a
     follow-up PR;
   - how the shim is fetched at the plugin version the project pins;
   - the branch-protection settings, with `specloop/*` statuses from GitHub Actions
     as the expected source.
6. **Watching outcomes:** `gates stats --outcomes`.

Every Specloop command in the example is a shipped, tested command. The orchestration
glue and the workflow are the adopter's.

### D6. This repository

This repo follows D5:
- `.gates.yaml` gains `integration: { mode: pull-request, requireApproval: true }`,
  because the maintainer merges after review;
- `.github/workflows/specloop.yml` is adapted from the sample. Its `push` job runs
  `gates record-merged` and opens a follow-up PR;
- the existing mirror workflow is untouched.

The implementer can't change branch protection. Its report lists the settings for
the maintainer to apply.

## Risks

- **The follow-up PR triggers `record-merged` again when it merges.** Its head branch
  names no change, so D3's step 2 skips it. A test covers this.
- **Forge outages block pull-request-mode merges at `marker publish`.** Local mode is
  unaffected, and the message names the forge.

## Out of scope

- Shipped CI templates, installers, merge-queue jobs and bypass tokens: withdrawn,
  and left to adopters, with D5 as the guide.
- Orchestration (`gates dispatch`, lane lifecycles): withdrawn with specloop PR 95. #37 and #22
  stay open.
- Forges other than GitHub.
