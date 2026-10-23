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
the commit, and the pull request, and nothing else.

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

5. **Commit the artifacts.** Every `git commit` is hook-gated on a fresh `ci` marker
   matching the staged tree (design D1) — this commit is no exception, so run the gate
   first:
   ```bash
   git add openspec/changes/<name>
   gates run ci
   git commit -m "propose: <name>"
   ```

6. **Push and open the pull request**, body summarizing what is proposed and what is
   deliberately left open (design D11 — a reviewer who has to reconstruct the argument
   from four markdown files will approve without reading):
   ```bash
   git push -u origin plan/<name>
   gh pr create --title "propose: <name>" --body "<summary>"
   ```
   If `gh` is unavailable, push the branch and print the compare URL
   (`https://github.com/<owner>/<repo>/compare/main...plan/<name>`) with instructions to
   open the PR by hand — do not fail the command over a missing forge CLI it doesn't
   otherwise depend on.

7. **Return to `main`** (`git checkout main`) so the working tree is left where step 1
   found it — clean, on `main`, ready for the next command.

**Output**

Report the change name, the plan branch, and the PR URL (or the compare URL and manual
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
