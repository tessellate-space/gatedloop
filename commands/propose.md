---
name: "gatedloop: Propose"
description: Author a change through OpenSpec, then open a pull request for the plan
category: Workflow
tags: [workflow, propose]
---

Author a change's plan and leave it somewhere a human can argue with it.

**This command owns exactly one step.** OpenSpec's `/opsx:propose` does the authoring —
generating the proposal, design, specs, and tasks. It leaves the artifacts on the
working tree. A plan is not finished when its artifacts are written — it is finished
when a human has reviewed it and agreed (design D11) — so this command adds the branch,
the commit, and the pull request, and — before the commit — the plan's check and,
when the project opts in, its loop (`plan-preflight`), which judge the plan before it
asks for approval.

**Input**: A short description of the change, forwarded straight through to
`/opsx:propose`; it handles inference and prompting.

**Why this exists**: `harden-unattended-loop` D10 refuses to start implementation until
a change's plan is present on `main` **and** carries a populated, still-matching
approval (`gates discipline check-implement`, hook-enforced at `git checkout -b
<change-name>`). Nothing produces that approval unless the authoring flow ends
somewhere a human can grant it — this command is that somewhere.

**Steps**

1. **Preflight.** Confirm the working tree is on the merge target (`main`/`master`) —
   or, per `unblock-parallel-planning` design D3, on a `plan/*` branch based on it — and
   clean. OpenSpec loses sight of other in-flight changes and the authoritative specs
   from any other branch, so the scaffold step (`openspec new change`, design D4) is
   hook-denied anywhere else (`gates discipline check-propose`, design D9) — a refusal
   there never leaves a stranded change directory. Writing a plan artifact is denied
   only from inside that change's implementation (`hook-correctness` D5).

2. **Delegate the authoring.** Run `/opsx:propose`, forwarding the description. Do not
   re-implement any part of it — not artifact generation, not the schema choice, not
   validation. If it stops or fails, stop here and report what it said; there is
   nothing to branch or commit. This step runs on the merge target or an already-based
   `plan/*` branch, so it never touches the `check-propose` hook.

3. **Read back the change name** from `/opsx:propose`'s own summary — never assume a
   layout, the same discipline `/gatedloop:archive` uses reading `/opsx:archive`'s
   summary.

4. **Cut a plan branch — `plan/<change-name>`, not `<change-name>`.** The
   implementation branch (created later, by `/gatedloop:tdd-apply`'s own `git checkout
   -b <change-name>`) is a DIFFERENT branch from this one, deliberately: `gates
   discipline check-implement` gates that exact branch name on the plan already being
   merged and approved, and this step runs before either is true. Naming the plan
   branch `plan/<change-name>` keeps the two from colliding — `check-implement` only
   recognizes a branch name that matches a real `openspec/changes/<name>/` directory,
   and `plan/<change-name>` does not.

5. **Check the plan, then run the plan loop** (`plan-preflight`). Always run:
   ```bash
   gates plan check <name>
   ```
   It runs no model, records nothing, and reports what the handoff would refuse after
   approval anyway. On a finding, amend the plan's artifacts and run it again. Then read
   `preflight` from `gates plan check <name> --json`: under `skip`, go to step 6. Under
   `run`, run the loop below on `plan/<name>`. The shim counts the rounds and computes
   every exit; never count or declare them yourself.

   a. **The tier.** `gates plan tier <name> --json`. When its `floor` is `light` and its
      classifier block says `provider: builtin` with no verdict yet (`tier` and
      `unavailable` both null), dispatch the `plan-review` agent for
      `<name>` with the lens `gatedloop.blast-radius`, write the JSON object it returns
      to a file, and run `gates plan classify <name> --verdict <file>`. A refused
      verdict names its errors: dispatch the lens once more. When no valid verdict can
      be had, run `gates plan classify <name> --unavailable <cause>`; the tier is then
      the floor.
   b. **Open a round.** `gates plan round <name>`. A static finding opens no round and
      costs none: amend and run it again. Exit 1 on a spent budget is the **stalled**
      exit, and on a recorded question it is the **question** exit: go to (g). On
      success it prints the round, the tier and the checkers the round runs.
   c. **The lenses.** `gates plan brief <name>` lists the lenses this round runs.
      Dispatch one `plan-review` run per lens, in parallel, each told the change and its
      lens id. Write each report to a file and record it:
      `gates plan record <name> --checker lens:<lens-id> --verdict clean|findings|question --report <file>`.
      `question` is for a finding only a human can answer, with its options in the
      report. If any lens had a finding or a question, the round ends here: go to (f).
   d. **Full tier only, once every lens is clean: the test author.** Dispatch the
      `test-author` agent in **preflight mode** for `<name>`: it reads
      `gates tests brief <name> --preflight`, authors only the stale tasks into the
      preflight store and ends with `gates tests handoff <name> --dry-run`. Record its
      result with `gates plan record <name> --checker test-author --verdict ... --report <file>`
      (`findings` for a `blocked: weak-spec` return). Then
      `gates plan record <name> --checker dry-run`: the shim runs the dry run itself and
      records its exit. A finding or a refusal ends the round: go to (f).
   e. **Full tier only: the authored-set review.** Dispatch the `convention-review`
      agent in authored-set mode, told it is a **preflight** for `<name>`. A finding
      against a test goes back to the test author for one revision of that task within
      the round (it ends with `gates tests handoff <name> --dry-run` again), then to one
      more review. Record the review's verdict with
      `gates plan record <name> --checker authored-review --verdict ... --report <file>`,
      never with `gates review record`. A finding against the plan ends the round.
   f. **Save the store, then amend.** After every round, `gates plan save <name>`
      snapshots the preflight store onto `gatedloop/preflight/<name>` and prints the push
      command. Then read `gates plan status <name>`. **green**: the loop is done.
      **amended** (a light pass whose lens had findings): amend the plan against them;
      the single pass is spent, so the loop ends there. **open**: amend the plan against
      the round's findings and go to (b). A finding is a reason to change the plan,
      never a reason to edit a held test or a recorded row.
   g. **A question or a stall stops the loop.** Do not open another round. The PR opens
      as a draft (step 7), with the question and its options, or the stall, at the top
      of its body. After a human answers or decides, amend as they said, record it with
      `gates plan resume <name> --reason "<what was decided>"`, and go to (b).

   **On an update to an open plan PR** (an amendment after review), run a new loop only
   when the plan's content moved: when the current `digests` that
   `gates plan status <name> --json` prints differ from its last round's (after a green
   loop it says so as `green_round_moved`). Record the review with
   `gates plan resume <name> --reason "<what the review changed>"` and go to (b). An edit
   that moves neither digest (prose outside a `Plan tier:` line in the proposal, say)
   runs none.

6. **Commit the artifacts**, with the change's ledger when the loop wrote rows to it
   (the record of which checkers ran on which content travels with the plan). Every
   `git commit` is hook-gated on a fresh `ci` marker matching the staged tree (design
   D1) — this commit is no exception, so run the gate first:
   ```bash
   git add openspec/changes/<name>
   git add .gatedloop/runs/<name>.jsonl   # when it exists
   gates run ci
   git commit -m "propose: <name>"
   ```
   Never stage the preflight store: its held tests travel only on their snapshot branch.

7. **Push and open the pull request**, body summarizing what is proposed and what is
   deliberately left open (design D11 — a reviewer who has to reconstruct the argument
   from four markdown files will approve without reading). When the loop ran, push its
   snapshot branch with the plan branch, put the output of
   `gates plan status <name> --markdown` in the body (a recorded question, with its
   options, at the top), and open the PR as a **draft** unless the loop ended green:
   ```bash
   git push -u origin plan/<name>
   git push origin gatedloop/preflight/<name>    # when gates plan save made it
   gh pr create --title "propose: <name>" --body "<summary>" [--draft]
   ```
   When a later loop on the same PR ends green, update the body's status block and mark
   the PR ready (`gh pr ready`). If the forge CLI cannot open drafts, open the PR
   normally with the status at the top of its body. If `gh` is unavailable, push the
   branches and print the compare URL
   (`https://github.com/<owner>/<repo>/compare/main...plan/<name>`) with instructions to
   open the PR by hand — do not fail the command over a missing forge CLI it doesn't
   otherwise depend on.

8. **Return to `main`** (`git checkout main`) so the working tree is left where step 1
   found it — clean, on `main`, ready for the next command.

**Output**

Report the change name, the plan branch, the plan loop's state (from `gates plan
status <name>`, when it ran), and the PR URL (or the compare URL and manual
instructions if `gh` was unavailable). State plainly that implementation cannot start
until the PR is reviewed, merged, and its approval attested (`gates approval attest
<name> --pr <n>`, run once the PR carries an `APPROVED` review) — this command does not
do either.

**Planning alongside an implementer (`unblock-parallel-planning`)**

An implementer holding the primary checkout on a change's implementation branch no
longer serializes planning behind it. Run this command in a **second git worktree**
checked out on a `plan/*` branch based on the merge target (a fresh one, or an
existing one from an earlier session) instead of the primary checkout's own branch —
every gate hook resolves the repository from the command's own working directory
(design D1), so the implementer's markers and the planning worktree's are never
confused, and `check-propose`/`check-implement` never mistake a `plan/*` branch for a
change branch. A stale plan branch (the merge target has moved since it was cut) is
still allowed; the discipline check prints an advisory naming how far behind, rather
than refusing an in-progress review's own amendments.

**Maintenance note**

If this file ever grows a step that reproduces upstream behaviour rather than adding a
guarantee, it has become a fork of `/opsx:propose` and the `no-forked-upstream-assets`
rule rejects it. The delegation in step 2 is the whole of its authoring content by
design; everything else here is the PR guarantee upstream doesn't make.
