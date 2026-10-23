# Tasks: scope-audit-to-branch-commits

## 1. Pin the defect and the invariant with failing tests

- [x] 1.1 Add a test to `tests/test_audit.py` that builds a throwaway repo, gates a
      commit on a change branch, lands a squash-like commit on `main`, fast-forwards
      the change branch onto it (after an initial audit so the cursor predates the
      move), runs `gates audit`, and asserts NO taint row is recorded for the adopted
      commit — verify it fails against current `bin/gates` (red).
- [x] 1.2 Add a test that, after the same adoption, creates a new local commit with
      no green-`ci` row and asserts `gates audit` still taints exactly that commit —
      verify it passes both before and after the fix (the preserved invariant).
- [x] 1.3 Add a test for the no-merge-target case: a repo whose default branch is
      neither `main` nor `master` and has no `origin/HEAD`, with a cursor-based walk
      containing an ungated commit — assert the commit still taints (behaviour
      unchanged, exemption never widens into a skip) — verify it passes before the
      fix so it pins today's behaviour.

## 2. Scope the walk in `bin/gates`

- [x] 2.1 In `_new_commits_to_audit`, resolve the merge target unconditionally and,
      when it resolves, exclude its ancestry from the walk (`git rev-list
      <base>..<head> --not <target>` semantics per design D1); keep today's range
      when no target resolves (D3); update the function docstring to state the
      exemption and its bound — verify tests 1.1–1.3 all pass (green) and
      `python3 -m unittest discover -s tests` is fully green.

## 3. Close out

- [x] 3.1 Run `./bin/gates validate` and `./bin/gates run ci` at the change head and
      verify both exit 0 (the shim's own gate covers the branching Python just
      changed).
