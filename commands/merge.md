---
name: "gatedloop: Merge"
description: Integrate a finished change with `gates merge` — locally in six gated steps with one push at the end, or under pull-request mode by handing a proven head to the forge
category: Workflow
tags: [workflow, merge]
---

Merge one finished change into the integration target, the way the project's process
declares, without retyping a recipe. **The shim does the merge.** `gates merge <change>`
reads the declared process and runs every step in code:

- **`local-squash-merge`** — prove the head, squash onto the target's tip, prove the
  merged tree, record the merge, confirm it live, archive and publish. Nothing reaches
  the remote until every step has passed.
- **`pull-request`** — prove the head the same way, push the branch, publish its markers
  as `gatedloop/*` commit statuses, and open or update the pull request with the
  acceptance brief as its body. The forge merges it: with squash auto-merge when nothing
  the declared process names stands in the way, otherwise after a human review.

This command shows the person what they are about to integrate, asks once, runs it, and
reports which step it ended on. It never performs a step itself.

**Input**: a change name (e.g. `/gatedloop:merge add-auth`). If none is given, run
`openspec list --json`, offer the changes whose branch exists, and ask which.

**Steps**

1. **Check the declared process.** Run `gates integration` and note `mode=` and
   `requireApproval=`: they decide what step 3 asks and which table step 5 reads.

2. **Show what is being accepted.** Run `gates acceptance brief <change>` and show its
   output exactly as printed — every spec scenario, `covered` or `check by hand`, and the
   gate verdicts recorded for the branch head's tree. The shim writes it; never trim,
   summarize or amend it. Then run `gates acceptance policy`. Under `acceptance=self` or
   `acceptance=review`, say what the missing acceptance means here, and how a human
   records it (`gates acceptance attest <change> --local`, or `--pr <n>` from the PR's
   approving review). Never record an acceptance for them.
   - local mode: `gates merge` refuses at step 1 until this exact tree is accepted;
   - pull-request mode: it opens the PR but leaves auto-merge off until it is. Under
     `acceptance=review` the acceptance can only come from that PR's review, so run
     `/gatedloop:merge <change>` again after it is recorded.

3. **Ask once.** With **AskUserQuestion** — local mode: merge `<change>` into the target
   now? Pull-request mode: push `<change>` and open (or update) its pull request now?
   Their yes is the human's presence at the merge. Stop on anything but a yes.

4. **Run it.** `gates merge <change>`, in the foreground, with the longest timeout the
   shell tool allows. Read its exit code in the same turn. Never background it, and never
   run any of its steps by hand instead.

5. **Report the outcome by exit code.** Quote the shim's own last `gatedloop:` lines, then
   one line of yours.

   Local mode:

   | Exit | Step | What it means | Offer |
   |---|---|---|---|
   | 0 | — | merged and published in one push; the primary is back where it was | `/gatedloop:start` for what's next |
   | 1 | 0–1 | a precondition or the head's proof refused (a marker, `verify`, taint, acceptance) | the remedy the refusal names, on the change branch |
   | 2 | 2 | the squash conflicts with the target; nothing changed | **sync** (below) |
   | 3 | 3 | the merged tree is red; nothing committed | fix it on the change branch after a sync |
   | 4 | 4 | the merge row could not be committed | the message, verbatim |
   | 5 | 5 | `confirm` ran and failed on the merged tree; nothing pushed, the failure is on the branch | the code, per the message |
   | 6 | 6 | the archive failed, or the target moved twice; nothing pushed | re-run once the target is quiet |
   | 75 | 3, 5 or — | a gate did not run, so nothing about the merged tree is known: `gatedloop: lock busy` (another merge holds the merge lock, or a lane's run holds the `ci` or `confirm` lock past its bound), or a declared precondition failed | lock busy: re-run the same command; a precondition: the project's environment, then re-run |

   A step that exited 75 did not run: say so plainly, distinct from a red merged tree or
   a red `confirm`. The message names the lock's holder or the failed precondition.

   Pull-request mode:

   | Exit | Step | What it means | Offer |
   |---|---|---|---|
   | 0 | — | handed to the forge: the PR URL, and either auto-merge enabled or waiting for review | the PR link; once the forge has merged it, `gates record-merged <squash sha>` (often the project's CI) records the merge and archives the change |
   | 1 | 0–1 | a precondition or the head's proof refused; nothing was pushed | the remedy the refusal names, on the change branch |
   | 2 | 2 | the push failed | the message, verbatim |
   | 3 | 3 | a status could not be published — the forge CLI is missing or unauthenticated, or the forge is down; the branch is pushed, no PR changed | fix what the message names (`gates doctor` shows it), then re-run |
   | 4 | 4 | opening or updating the PR, or enabling auto-merge, failed | the message, verbatim |
   | 75 | — | `gatedloop: lock busy` | re-run the same command |

6. **Sync on a conflict (local mode, exit 2), only if they say so.** Offer to merge the
   target into the change branch, where the branch lives (its own worktree when it has
   one), and resolve the conflict with them. Then re-run the head's gates on the branch —
   `gates run ci` with nothing staged, then `gates run live-check` — and offer to run
   `/gatedloop:merge <change>` again. Never resolve a conflict that needs a choice between
   two behaviours without asking which one they want.

**Guardrails**

- `gates merge` is the only way this command integrates. Never fall back to a
  hand-run squash, commit, push, PR or forge merge when it refuses: its refusal is the
  gate.
- Never pass anything to `gates merge` beyond the change name, and never edit the
  manifest to get past a step.
- In pull-request mode the forge merges, never this command: don't merge the PR or
  change its auto-merge setting.
- The target's environment — whatever brings the merged tree up for `confirm` — is the
  project's. If `confirm` keeps failing for environmental reasons, that is theirs to fix.
