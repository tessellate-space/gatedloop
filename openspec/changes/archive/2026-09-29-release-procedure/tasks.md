# release-procedure — Tasks

## 1. `check` (design D6, spec "one value across every manifest field")

- [x] 1.1 Add `tests/test_release.py` with a helper that builds a throwaway git repo containing copies of the two manifests. Cover: three agreeing fields and matching tag → `check` exits 0; one marketplace field differing → non-zero, stderr lists all three fields and values; fields at `0.3.0` with tag `v0.4.0` → non-zero, naming both; no tags → agreement-only; a non-semver value → non-zero. Load `scripts/release` by path the way the shim tests load `bin/gates`. Verify the tests fail because the script is absent.
- [x] 1.2 Create `scripts/release` (stdlib, executable, `#!/usr/bin/env python3`), with argparse subcommands and `check` implemented. Verify 1.1 passes.

## 2. `status` (design D3)

- [x] 2.1 Add to `tests/test_release.py`: after tagging, a commit touching only `openspec/` or `docs/` → `status` exits 0, "current"; a commit touching `hooks/` → exits 1, suggests `patch`; adding an archive directory whose `specs/x/spec.md` has `## ADDED Requirements` → suggests `minor` and lists the change; `--json` prints one document with `tag`, `shipped_commits`, `archived_changes`, `suggested`. Verify they fail.
- [x] 2.2 Implement `status` with the `SHIPPED_PATHS` constant, the two git queries and the level rule. Verify 2.1 passes, then run `scripts/release status` against this repo and confirm it reports what landed since `v0.4.0`.

## 3. `cut` (design D4)

- [x] 3.1 Add tests: `cut minor` at `0.4.0` sets three fields to `0.5.0`, leaves the JSON byte-identical apart from the three values, and inserts a `## 0.5.0 — <date>` section above the previous top section. The section lists the archived change with its first `## Why` sentence, then non-bookkeeping shipped subjects. Nothing is committed. Refusals: dirty tree, not on `main`, nothing unreleased, and an existing section for that version each exit non-zero and change nothing. Verify they fail.
- [x] 3.2 Implement `cut`, including the exactly-three-replacements assertion and the date via `datetime.date.today()` (overridable by an env var for tests). Verify 3.1 passes.

## 4. `publish` (design D4)

- [x] 4.1 Add tests using a bare repo as `origin` and a `gh` stub on `PATH`. A full publish produces one `Release X.Y.Z` commit, an annotated `vX.Y.Z` tag on the remote, and a stub call to `gh release create vX.Y.Z --title "Specloop X.Y.Z" --notes-file <file>` whose notes equal the section. A `gh auth status` failure exits non-zero with no commit. An existing tag exits non-zero with no commit. An unexpected changed path exits non-zero naming it. A push failure after the commit (unreachable remote) exits non-zero, creates no tag, and prints the resume command. Verify they fail.
- [x] 4.2 Implement `publish` with preconditions first, then commit → tag → push commit → push tag → `gh release create`, with per-step resume messages. Verify 4.1 passes.

## 5. Reminder hook (design D5)

- [x] 5.1 Add tests: `status --hook` prints valid SessionStart JSON (`hookSpecificOutput.additionalContext`) with the one-line reminder when work is unreleased; it prints nothing and exits 0 when current; it prints nothing and exits 0 outside a git repo. Implement `--hook`. Verify.
- [x] 5.2 Create `.claude/settings.json` with the SessionStart hook from design D5. Verify by starting a session in this repo (or piping the documented hook input into the command) and seeing the line. Confirm `hooks/hooks.json` is unchanged.

## 6. Wiring and docs (design D6)

- [x] 6.1 Edit `.gates.yaml`: `ci` runs `python3 scripts/release check` between the unit tests and `claude plugin validate .`. Update the manifest's header comment to say `ci` now also covers version consistency. Verify `./bin/gates run ci` is green.
- [x] 6.2 Write `CHANGELOG.md` with sections for 0.4.0 (`2898ba5`), 0.3.0 (`9fe73de`) and 0.2.0 (`7abcdb5`), taken from those commit bodies, newest first, in the `## X.Y.Z — YYYY-MM-DD` format `cut` writes. Verify `cut` inserts correctly above it in a throwaway copy.
- [x] 6.3 Write `RELEASING.md`: when to release, the four subcommands in order, the shipped-path list and the level rule, what to do on a partial publish, and that adopters get updates only on a version bump. Add a "Releasing" bullet to CLAUDE.md's Commands section. Verify every command in both files runs.

## 7. Closure

- [x] 7.1 Run `python3 -m unittest discover -s tests` and `./bin/gates validate`, and confirm both are green.
- [x] 7.2 On `main` after merge, dry run: `scripts/release status` lists exactly the shipped work since `v0.4.0`. Do not cut a release as part of this change. The first scripted release is the maintainer's call.
