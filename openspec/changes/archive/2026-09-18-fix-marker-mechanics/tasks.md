# fix-marker-mechanics — Tasks

## 1. Ledger-normalized marker trees (design D1)

- [x] 1.1 Add a `_normalize_tree(root, tree)` helper to `bin/gates` that strips `.specloop/runs/**` from a tree object via a temporary `GIT_INDEX_FILE` (read-tree → `git rm --cached -r --ignore-unmatch .specloop/runs` → write-tree), returning the input hash unchanged on any plumbing failure (fail-safe strict, never fail-open); verify with a unit test that a tree differing only in `.specloop/runs/` normalizes to the same hash and a tree differing elsewhere does not.
- [x] 1.2 Apply normalization in `_write_marker` (record the normalized tree) and in `_check_marker_and_report` (normalize the tree argument before comparing), keeping the compare a single hash equality; verify with a test that staging a ledger row after a marker write still checks fresh and that any other edit checks stale.
- [x] 1.3 Add a regression test reproducing issue #10's sequence — green `ci` → stage task files + `tasks.md` flip + the run's own ledger row → `gate-marker check ci $(git write-tree)` — and verify it passes.

## 2. Recorded skip verdicts (design D2, issues #9/#37.1/#40.2)

- [x] 2.1 Extend the marker payload with `verdict` ("pass"/"skip", absent reads as pass) and, for skips, an `evidence` object (baseline kind, resolved merge target, files considered); update the empty-check-set path of `cmd_run` live-check to write a skip marker on the current head tree and append a ledger row with the same verdict, replacing the no-marker design comment with one stating D2's answer; verify with a test that a docs-only changed set writes a skip marker carrying the printed evidence.
- [x] 2.2 Make `_check_marker_and_report` report a matching skip marker as satisfied, naming the verdict and its evidence in the success line; verify with tests that a tree-matching skip satisfies, a missing marker still denies, and a mismatched-tree skip denies.
- [x] 2.3 Add the undeclared-gate regression for issue #9: in a manifest with no `live-check` on any surface, `gates run live-check` exits 0, writes a skip marker, and a subsequent `gate-marker check live-check <head-tree>` passes; verify the declared-probe-ran-red case still writes no marker.
- [x] 2.4 Extend `LEDGER_ROW_FIELDS` with `verdict` (None on non-live-check rows) and document the field beside the row-shape comment, noting the union rule with `scale-gate-cost`'s `scope` (design D7); verify a skip run appends a row with `verdict: "skip"` and other gates append `verdict: None`.

## 3. Recipe dedupe (design D3, issues #14.2/#40.3)

- [x] 3.1 Dedupe the resolved `(surface, live-check command)` list by exact command string in `cmd_run` (first-declaration order kept), logging each execution with every surface that binds it; verify with a test that two hot surfaces sharing one command produce exactly one execution attributed to both, and distinct commands still each run under `--all`.
- [x] 3.2 Document the dedupe rule (string equality is recipe identity) in SETUP.md's live-check section; verify the section states that identically-spelled commands run once per invocation.

## 4. Merge gate validates the incoming tree (design D4, issue #17.5)

- [x] 4.1 In `hooks/gate-merge.sh`, extract the merge source ref from the `git merge` invocation (trailing non-flag argument), resolve `<ref>^{tree}`, and check the live-check marker against it, falling back to the current HEAD tree when no ref resolves; a denial names every tree tried; verify by exercising the hook with a squash-merge command JSON where only the branch-head marker exists.
- [x] 4.2 Correct the denial guidance to "run `gates run live-check` on the change branch's head" and keep the taint check after the marker check; verify the fallback path (e.g. `git merge --continue`) still checks the HEAD tree and the messages match the new semantics.

## 5. Ledger-grade commits (design D5)

- [x] 5.1 Add the ledger-grade rung to `discipline check-commit`: a non-empty staged diff consisting solely of `.specloop/runs/**` paths is allowed with an explicit printed verdict; empty diffs and mixed diffs keep today's behavior; verify with tests covering ledger-only (allowed), mixed (full requirement), and empty (full requirement) staged diffs.

## 6. Prompt and doc alignment (design D6, issue #10)

- [x] 6.1 Update `skills/tdd-apply/SKILL.md` §5h with the one-line reason the staged ledger row cannot stale the marker, and simplify §7.5 step 5's merge-row commit to rely on the ledger-grade rung; verify no step instructs an action the gates would deny and no stack-specific command appears.
- [x] 6.2 Align `agents/tdd-implementer.md` with the same mechanics (commit-the-row guidance now executable; no stale-marker workaround prose); verify by reading the diff against §5h for consistency.
- [x] 6.3 Update the marker design comments in `bin/gates` (markers section header, live-check skip path) and `hooks/gate-merge.sh`'s header to describe normalized trees, skip verdicts, and incoming-ref validation; verify comments and behavior agree.

## 7. Closure

- [x] 7.1 Run the full suite (`python3 -m unittest discover -s tests`) and `./bin/gates validate`; verify green.
- [x] 7.2 End-to-end check in a throwaway repo: docs-only change merges after a recorded skip; a task commit staging its own ledger row passes the commit gate; a squash-merge passes on a branch-head marker; verify each against the spec scenarios in `specs/gate-binding/spec.md`.
