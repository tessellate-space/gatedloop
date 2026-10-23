## Why

The `PreToolUse` gate hooks match commands by raw substring, so they fire on text
that merely *contains* the guarded phrase: `gate-merge.sh` denies `git merge-base`
(a read-only query the loop itself needs) and even a `gh issue create` whose quoted
body mentions "git merge" (issue #8, issue #17 item 4). Separately, the
planning-grade commit gate parses `openspec/changes/<segment>` and validates each
segment as a change id, so an archive-move commit — whose paths live under
`openspec/changes/archive/…` — validates the literal segment `archive` and always
fails; the working escape was discovered by archaeology, not by reading the denial
(issue #16 item 4). Both defects tax every unattended run with retry loops and
boilerplate ("expect false denials"), which is exactly the cost the enforcement
layer was built to remove.

## What Changes

- **One shared command matcher for all Bash gate hooks.** A new stdlib-only helper,
  `hooks/_gate_match.py` (precedent: `hooks/_session_brief.py`), replaces the five
  ad-hoc `case "$cmd" in *"…"*)` substring patterns in `gate-commit.sh`,
  `gate-merge.sh`, `gate-archive.sh`, `gate-implement.sh`, and `gate-scaffold.sh`.
  It tokenizes the command, splits on shell operators, skips git global flags
  (`-C <path>`, `-c <k=v>`, `--git-dir`, …) and leading env assignments/wrappers,
  and matches the actual subcommand **token**: `merge` matches, `merge-base` /
  `merge-tree` / `merge-file` do not, and quoted prose is one argument token that
  can never sit in subcommand position. It also extracts per-gate arguments (the
  change name after `archive`, the branch after `-b`/`-c`) from the *matched*
  simple command instead of scanning the whole string.
- **Conservative fallback preserved.** When tokenization fails (unbalanced quotes),
  the matcher falls back to the current substring behavior — it still fires. The
  generous-matcher rationale from `harden-unattended-loop` (raise the floor against
  accidents, not a jail) is kept; only the false positives on non-invocations go.
- **Archive-move commits classify correctly.** `gates discipline check-commit`
  treats `archive` under `openspec/changes/` as the reserved archive segment, never
  a change id, and skips per-change `openspec validate` for a change directory the
  staged move has removed from the working tree. Manifest validation still runs;
  merge-precedes-archive stays enforced by `check-archive` where it belongs.
- **Every denial names its remedy.** Each denial emitted by `hooks/*.sh` and the
  `gates discipline` checks they call names the precise unmet prerequisite and the
  command that satisfies it (the marker messages — "run `gates run ci`" — are the
  model). No prerequisite may be discoverable only by archaeology.
- **Tests for the matcher.** `hooks/_gate_match.py` and the archive-move
  classification are branching Python, so they get stdlib `unittest` coverage in
  `tests/` (prompts stay untested; branching Python does not).

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `loop-enforcement`: gate hooks fire on the actual invocation token, not a raw
  substring (new requirement); an archive-move commit is classified and validated
  as what it is (new requirement); every enforcement denial names the unmet
  prerequisite and its satisfying command (new requirement). Existing requirements
  are unchanged — this narrows *when* the hooks fire and *what* they say, not what
  they guarantee.

## Impact

- `hooks/_gate_match.py` — new shared matcher (stdlib-only, plugin-relative).
- `hooks/gate-commit.sh`, `hooks/gate-merge.sh`, `hooks/gate-archive.sh`,
  `hooks/gate-implement.sh`, `hooks/gate-scaffold.sh` — matching and argument
  extraction delegated to the shared helper; denial messages audited.
  (`hooks/gate-propose.sh` matches a Write `file_path`, not a command — untouched.)
- `bin/gates` — `_staged_change_dirs` / `check-commit` archive-segment fix;
  denial-message audit across the `discipline` checks.
- `tests/` — new unit coverage for the matcher and the archive-move classification.
- Issues: fixes #8, #16 item 4, #17 item 4.
- Ordering: independent of the sibling changes; `worktree-native-loop` also touches
  `hooks/*.sh` (cwd resolution) and should land after this change or rebase on it.
  Marker freshness semantics (`fix-marker-mechanics`) and audit scoping
  (`scope-audit-to-branch-commits`) are explicitly out of scope here.
