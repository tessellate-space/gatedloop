# Running gatedloop at scale

> **Example — adapt to your team.** This page is a worked example, not a supported
> component. Every `gates` command and agent it names ships with gatedloop and is
> tested where it is implemented. The loop around them, the CI workflow and the forge
> settings are yours: they vary by team, which is exactly the axis gatedloop delegates
> rather than owns. Copy what fits, change the rest, and expect to own it.

gatedloop owns the loop's **evidence** and the commands that act on it. Many lanes at
once, a CI provider and a forge add three needs, and each one already has a
primitive:

| You need | The primitive | Yours to build |
|---|---|---|
| which changes are ready to run | `gates approval check <change>` | the selection loop and its ordering rules |
| tests written before code, by someone else | the `test-author` agent, `gates tests show` | dispatching it |
| one implementer per lane | the `tdd-implementer` agent, one `git worktree` each | the dispatcher |
| to see what each lane is doing | `ready`, `halt` and `merge` rows in the committed ledger | the poller or console |
| integration | `gates merge <change>` (local or pull-request mode) | when to call it |
| evidence a forge can read | `gates marker publish` / `gates marker check-remote` | the CI job that calls them |
| ledger facts for forge merges | `gates record-merged <sha>` | the CI job that calls it, and how its commit lands |
| to watch it all | `gates stats --outcomes` | where you look at it |
| a story of several changes, in order | `x-gatedloop-epic`, `gates epics`, `gates stats --epic` | the drain loop (§7) |
| planners handing plans to one orchestrator | `gates handoff <change>`, `gates approval attest --merged`, `gates record-merged` | the sessions, the messaging, the plan-check job (§8) |

## 1. Choosing what to run

A change is runnable when its plan is merged and approved, and nothing has finished it
yet. In pseudocode:

```text
for each name in `openspec list --json` → .changes[].name:
    `gates approval check <name>` exits non-zero        → skip: plan not merged + approved
    .gatedloop/runs/<name>.jsonl has a `ready` row         → skip: waiting to integrate
    .gatedloop/runs/<name>.jsonl has a `merge` row         → skip: done
    otherwise                                             → candidate
```

Read the ledger from the change branch when one exists (`git show
<name>:.gatedloop/runs/<name>.jsonl`), since that is where a lane commits. Ordering and
parallel-safety rules (two changes touching the same surface, a change that depends on
another) are your team's. This is the place they plug in: filter or sort the candidate
list before dispatch.

## 2. Authoring first, then one lane per change

For each candidate:

1. **Author the tests.** Dispatch the `test-author` agent with the change name, unless
   the project declares `loop.test-author: inline`. It writes into
   `.gatedloop/authored/<change>/` and hands off with `gates tests handoff`.
   `gates tests show <change> --json` reports `"handoff": true` once it has.
2. **Open a lane.** `git worktree add ../lanes/<change> -b <change> main` — branch name =
   change name, one worktree per lane, so lanes never share a checkout.
3. **Dispatch the implementer.** The `tdd-implementer` agent, given the change name and
   the worktree path. It runs the whole loop in that worktree and stops before the
   merge.

[`worktree-lanes.md`](worktree-lanes.md) covers what is per-worktree and what is shared,
and the `concurrency` block that bounds how long a lane waits for another's serialized
gate.

## 3. Watching the lanes

Each lane's state is a fact in its **committed** ledger, so a poller needs no memory
of the sessions it started. Read `.gatedloop/runs/<change>.jsonl` on the branch:

| Newest relevant row | The lane is |
|---|---|
| `ready`, newer than any `halt` | ready to integrate |
| `halt`, newer than the last `task-start` | halted — its `cause` and `detail` say why |
| anything else | in progress |

`tdd-implementer` records and commits the `ready` row (`gates ledger record-ready
<change>`) immediately before it reports READY TO MERGE, and commits a `halt` row
(`gates halt record`) before it reports a halt.

Route a halt by its cause. A `test-defect` detail (cause `oracle-conflict`, detail
starting `test-defect <N.M>:`) goes back to the `test-author` agent for that task, and
the lane is resumed at that task once the author re-hands it off. Everything else
(`weak-spec`, `missing-oracle`, `environment`, `stalled`, `other`) goes to a person.

## 4. Finishing a lane

From the lane's worktree, run:

```bash
gates merge <change>
```

What it does depends on the declared `integration.mode`:

- **`local-squash-merge`** — the six gated steps: prove the head, squash onto the
  target, prove the merged tree, record the merge, `confirm` where declared, archive,
  and one push. Dispatch the `merge-runner` agent instead when an agent should handle a
  mechanical conflict.
- **`pull-request`** — prove the head the same way, push the branch, publish the head's
  `gatedloop/live-check` and `gatedloop/ci` statuses, and open or update the pull request
  with the acceptance brief as its body. It enables squash auto-merge only when
  `requireApproval` is false and any declared acceptance is satisfied; otherwise it
  prints the PR's URL and stops, exit 0, waiting for review.

Remove the worktree once the change is integrated: `git worktree remove
../lanes/<change>`.

## 5. CI, in pull-request mode

Statuses posted from a laptop are self-reported. What makes them evidence is branch
protection that requires them **from your CI provider**. The sample below is GitHub
Actions, about thirty lines; adapt the install steps to what your `ci` gate needs.

```yaml
# .github/workflows/gatedloop.yml — EXAMPLE: adapt to your team; not a supported template.
name: gatedloop
on:
  pull_request:
  push:
    branches: [main]
permissions:
  contents: write       # record job: push the follow-up branch
  pull-requests: write  # record job: open the follow-up PR
  statuses: write       # both jobs: post gatedloop/* statuses
env:
  GATEDLOOP_VERSION: v0.5.0   # the plugin version your project pins
  GH_TOKEN: ${{ github.token }}
jobs:
  ci:
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { ref: "${{ github.event.pull_request.head.sha }}", fetch-depth: 0 }
      - run: git clone -q --depth 1 --branch "$GATEDLOOP_VERSION" https://github.com/tessellate-space/gatedloop "$RUNNER_TEMP/gatedloop" && echo "$RUNNER_TEMP/gatedloop/bin" >> "$GITHUB_PATH"
      # install what your ci gate needs here
      - run: gates run ci && gates marker publish ci
      - run: gates marker publish tests    # the authored-test lock at the head; posts failure and exits 1 when it is broken
  record:
    if: github.event_name == 'push'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: git clone -q --depth 1 --branch "$GATEDLOOP_VERSION" https://github.com/tessellate-space/gatedloop "$RUNNER_TEMP/gatedloop" && echo "$RUNNER_TEMP/gatedloop/bin" >> "$GITHUB_PATH"
      # install the OpenSpec CLI (record-merged archives through it) and what your ci gate needs
      - run: git config user.name "github-actions[bot]" && git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
      - run: gates record-merged "$GITHUB_SHA"
      - name: Land the record through a follow-up PR
        run: |
          [ "$(git rev-parse HEAD)" = "$GITHUB_SHA" ] && exit 0   # nothing was recorded
          gates run ci                                            # never push a red record
          branch="gatedloop/record-merged-${GITHUB_SHA::7}"
          git push origin "HEAD:refs/heads/$branch"
          gates marker publish ci --sha "$(git rev-parse HEAD)"   # the follow-up PR's required status; only after the push
          gates marker publish tests --sha "$(git rev-parse HEAD)"
          gh pr create --head "$branch" --base main --title "$(git log -1 --format=%s)" --body "Recorded by \`gates record-merged $GITHUB_SHA\`."
```

Notes on the sample:

- **The head, not the merge preview.** On `pull_request`, Actions checks out a merge
  commit by default. The status has to land on the PR's head sha, so check that out.
- **Fetching the shim.** The plugin's `bin/gates` is a standalone Python script, so the
  job clones the plugin at the version the project pins and puts `bin/` on PATH. Keep
  `GATEDLOOP_VERSION` equal to the version your team installs.
- **The follow-up PR, or a direct push.** `gates record-merged` commits the merge row and
  the archive locally and never pushes. The sample opens a follow-up PR from a
  `gatedloop/record-merged-<sha>` branch, which names no change, so when it merges and
  this job runs again, `record-merged` skips it. A PR opened with the workflow's token
  triggers no new workflow run, so the job publishes that branch's `gatedloop/ci` and
  `gatedloop/tests` itself.
  Where your protection lets this job push to `main`, replace the last step with
  `git push origin HEAD:main`.
- **`gatedloop/live-check`** is published by `gates merge` from where the lane ran. To
  require it from CI as well, run `gates run live-check && gates marker publish
  live-check` in the `ci` job, against whatever environment your live-check needs.

**Branch protection** on `main` (Settings → Branches, or a ruleset):

- Require a pull request before merging.
- Require status checks to pass, with `gatedloop/ci` required and its expected source set
  to GitHub Actions, so a status posted from a laptop does not satisfy it. Require
  `gatedloop/tests` beside it the same way, in two steps: add the publish step first,
  then require the status, or every open PR waits on a status nothing posts. Add
  `gatedloop/live-check` the same way only if CI publishes it.
- Under `requireApproval: true`, require at least one approving review. Under
  `approval.acceptance: review`, that review is the acceptance: record it with
  `gates acceptance attest <change> --pr <n>`, then run `gates merge <change>` again,
  which updates the PR and, where nothing else stands in the way, enables auto-merge.
- Allow auto-merge in the repository settings, if you want `gates merge` to use it.
- Let the workflow open the follow-up PR: Settings → Actions → General → "Allow GitHub
  Actions to create and approve pull requests".
- Squash merging must be allowed: `gates record-merged` finds the change through the
  squash commit's pull request.

## 6. Watching outcomes

```bash
gates stats --outcomes --all
```

Per change: `merged`, `halted` or `in-progress`, and whether it ran hands-off. With
`gates record-merged` in CI, a change merged in the forge counts as merged without
anyone recording it by hand. `docs/gate-economics.md`, "Reading the outcomes view", says
what the view cannot see.

## 7. Draining an epic

> **Example — adapt to your team.** The loop below is yours to build and own; it adds
> no command. Every command it calls ships with gatedloop.

An epic is an ordinary change that its children name in their own `.openspec.yaml`
(`x-gatedloop-epic: <epic>`; SETUP.md, "Epics"). Two guarantees hold whatever your
orchestrator does: the epic itself can never be implemented (`gate-implement.sh`
refuses its branch), and it archives only once every child is archived
(`gate-archive.sh`). Within those, a drain is a loop over `gates epics --json`:

```text
loop:
    doc   = `gates epics --json`; epic = the entry whose .epic is <epic>
    epic.drained                                        → archive the epic; stop
    any child in state `halted`                         → stop: route it by its cause (§3)
    for each child in state `ready`                     → hand it to `merge-runner` (§4)
    pick the next child in state `approved` that your coordination check passes
        (your own command, e.g. one that refuses two lanes on the same surface)
                                                        → author its tests, open its lane,
                                                          dispatch `tdd-implementer` (§2),
                                                          within your lane ceiling
    nothing to start and nothing ready                  → wait for a lane to report
```

- **Where it reads.** `gates epics` reads the ledgers and change directories of the
  checkout it runs in. A lane commits its `ready` and `halt` rows on its own branch,
  so until a child merges, the primary checkout shows it as `approved`. Read a running
  lane's state from its branch (§3), or run `gates epics` in a checkout that has
  those rows.
- **Order.** `gates epics` lists children by name, not by dependency. If one child
  needs another merged first, that is your coordination check's business.
- **Lane ceiling.** How many children run at once is yours too; the manifest has no
  key for it.
- **Archiving the epic.** Archive it the way you archive any change. Run before its
  last child is archived, the archive hook refuses it and lists each open child with
  its state, so archiving last is the only order that works.

`gates stats --epic <epic>` gives the economics per child and in total: tasks done of
total, gate runs, gate time, red runs and halts by cause.

## 8. Planners and one orchestrator

> **An example to adapt.** The commands below ship and are tested; the sessions, the
> messaging between them and the CI job are yours.

Planning and orchestrating implementation can run in separate Claude Code sessions:
any number of planner sessions, and exactly one orchestrator. Plan PRs carry the work
between them, and the forge is the checkpoint.

**Roles.**

- **Planners** author and propose, and nothing else. Each one works in its own
  worktree (`git worktree add ../plans/<change> -b plan/<change> main`), so a planner
  never shares a checkout or an index with the orchestrator. A planner never
  dispatches a lane.
- **The orchestrator** is the only session that dispatches. It runs §1–§7: it selects,
  dispatches the author and the implementers, merges and archives.

**The flow.**

1. A planner runs `/gatedloop:propose`, which opens the plan PR from `plan/<change>`.
2. A person reviews and merges it.
3. Under `approval.plan: self` in pull-request mode, the record job (§5) runs
   `gates record-merged` on the squash. It sees the `plan/<change>` head and attests the
   plan from the merge: the merger's login marked `(merged #<n>)`, the merge time, and a
   sha over the plan in the merge commit. That commit lands through the same follow-up
   PR as any record. Without that job, run `gates approval attest <change> --merged <n>`
   on the target. Under `review`, attest from the approving review with `--pr <n>`.
4. Once the approval is on the target, the planner runs `gates handoff <change> --json`.
   It exits 1 with the reason unless the plan is approved there and unchanged since.
   On success it prints the payload, and the planner's agent sends it to the
   orchestrator with its own messaging tool (for example, a session addressed by a
   stable name). gatedloop sends nothing.
5. The orchestrator runs the payload's `verify` command, `gates approval check
   <change>`, and queues the change only if it passes. The message is a doorbell, not
   evidence.

```json
{"handoff": 1, "change": "add-thing", "schema": "spec-driven",
 "target": "origin/main", "target_head": "<sha>",
 "approval": {"by": "alice (merged #42)", "at": "<merge time>", "sha": "<plan sha>"},
 "epic": null, "tasks": {"done": 0, "total": 7},
 "verify": "gates approval check add-thing"}
```

The payload carries no dependency list. Ordering between changes is your queue's
business, or an epic's (§7).

**Recovery.** Nothing depends on the message arriving. The queue can always be derived
from git: the changes §1 calls candidates, which are approved on the target and held
by no lane. A lost or late doorbell delays a change and loses nothing.

**The plan-check job.** It runs on pull requests whose diff is planning-only, meaning
every changed path is under `openspec/` or is the rules-doc. That is the same set the
shim commits at planning grade, so the job needs none of your `ci` stack. It
validates each changed change, validates the manifest, and writes the approval sha to
the job summary, so the content an approval will pin is visible before the merge.

```yaml
# .github/workflows/plan-check.yml — EXAMPLE: adapt to your team; not a supported template.
name: plan-check
on:
  pull_request:
env:
  GATEDLOOP_VERSION: v0.5.0   # the plugin version your project pins
jobs:
  plan-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - run: git clone -q --depth 1 --branch "$GATEDLOOP_VERSION" https://github.com/tessellate-space/gatedloop "$RUNNER_TEMP/gatedloop" && echo "$RUNNER_TEMP/gatedloop/bin" >> "$GITHUB_PATH"
      # install the OpenSpec CLI here
      - name: Validate and pin a planning-only diff
        run: |
          git diff --name-only "origin/${{ github.base_ref }}...HEAD" > changed.txt
          if grep -qv -e '^openspec/' -e '^docs/conventions.md$' changed.txt; then   # your rules-doc
            echo "not planning-only: gatedloop/ci covers this PR"; exit 0
          fi
          gates validate
          for c in $(sed -n 's#^openspec/changes/\([^/]*\)/.*#\1#p' changed.txt | grep -vx archive | sort -u); do
            [ -d "openspec/changes/$c" ] || continue
            openspec validate "$c" --strict
            echo "- \`$c\`: approval sha \`$(gates approval sha "$c")\`" >> "$GITHUB_STEP_SUMMARY"
          done
```

The job runs on every PR and passes at once when the diff is not planning-only, so it
can be required without blocking a change PR, which always touches `openspec/` (its
`tasks.md`). Require the `plan-check` check in branch protection, alongside
`gatedloop/ci`. Planning PRs then run in CI concurrently, with no wait on any lane's
`ci` lock.
