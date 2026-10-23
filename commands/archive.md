---
name: "gatedloop: Archive"
description: Archive a completed change through OpenSpec, then commit the move
category: Workflow
tags: [workflow, archive]
---

Archive a completed change and leave no uncommitted move behind.

**This command owns exactly one step.** OpenSpec's `/opsx:archive` does the archiving —
selecting the change, checking artifacts are done, syncing delta specs, moving the
directory. It leaves the move in the working tree. gatedloop's loop ends *verified on
main*, which a dirty tree contradicts, so this command adds the commit and nothing else.

**Input**: Optionally a change name (e.g. `/gatedloop:archive add-auth`). Pass it straight
through; `/opsx:archive` handles inference and prompting when it is omitted.

**Already archived by the merge?** A change integrated with `gates merge` (or
`/gatedloop:merge`) was archived and committed as that command's step 6, before its one
push. There is nothing left for this command to do for it; say so and stop.

**Steps**

1. **Delegate the archive.** Run `/opsx:archive`, forwarding the change name if one was
   given. Do not re-implement any part of it — not the status check, not the spec sync,
   not the path derivation. If it stops or fails for any reason, stop here and report
   what it said; there is nothing to commit.

2. **Read back what moved.** Take the archive path from `/opsx:archive`'s own summary
   rather than assuming a layout — the change may live in a store or a non-default
   planning home, and the path is reported to you.

   **The move is three paths, not two.** Archiving also *promotes* the change's spec
   deltas into the OpenSpec root's `specs/` tree, which is outside both the change
   directory and the archive directory. The summary reports whether it did
   (`specsUpdated`). Miss it and you commit a change-dir rename while the spec baseline
   the archive just rewrote stays untracked — which is the failure this command exists
   to prevent, wearing a green light.

3. **Commit the move.**

   ```bash
   git add -A -- <archive path> <original change path> <openspec root>/specs
   git commit -m "archive change: <name>"
   ```

   `git add -A` across those paths records the whole move as one commit. Include the
   `specs` path whenever the summary says specs were updated; it may be newly created,
   so it can be untracked rather than modified.

4. **Verify the commit landed.** Confirm the working tree is clean with respect to the
   move — `git status --porcelain` must show **all three** paths clean, the promoted
   `specs` tree included. Checking only the two change paths is how this step passes
   while the spec baseline sits untracked. If the commit failed or any of the three is
   still dirty, say so plainly and stop — **never report a successful archive over an
   uncommitted move.** That is the whole guarantee this command exists to make.

**Output**

Report `/opsx:archive`'s summary as it gave it, then one added line: the commit SHA, or
the reason there is no commit.

**Maintenance note**

If this file ever grows a step that reproduces upstream behaviour rather than adding a
guarantee, it has become a fork of `/opsx:archive` and the `no-forked-upstream-assets`
rule rejects it. The delegation above is the whole of its content by design.
