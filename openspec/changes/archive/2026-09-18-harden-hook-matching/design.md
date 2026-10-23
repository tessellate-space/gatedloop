## Context

See proposal.md — Why. The current state, concretely:

- Five Bash gate hooks each carry an ad-hoc `case "$cmd" in *"…"*)` substring
  pattern: `gate-commit.sh` (`git commit`), `gate-merge.sh` (`git merge`),
  `gate-archive.sh` (`openspec archive`), `gate-implement.sh`
  (`git checkout -b` / `git switch -c`), `gate-scaffold.sh` (`openspec new
  change`). Each also duplicates the same inline-Python JSON parse of the hook's
  stdin, and two of them (`gate-archive.sh`, `gate-implement.sh`) extract an
  argument by scanning the whole token list rather than the matched command.
- `harden-unattended-loop`'s design accepted "generous, not exact" matching as a
  deliberate risk posture: the string layer raises the floor against accidents;
  the effect layer (git `pre-commit`, `enforce-at-the-effect`) is the real jail
  for commits. That posture is kept — the defect is not generosity, it is firing
  on text that is *not an invocation at all*.
- `gates discipline check-commit`'s planning-grade rung derives change ids with
  `parts[2]` of any `openspec/changes/<x>/…` path (`_staged_change_dirs`) and
  runs `openspec validate <x> --type change` per id. An archive move stages
  deletions under `openspec/changes/<name>/**` and additions under
  `openspec/changes/archive/<dated-name>/**`, so validation runs against the
  literal id `archive` (always fails — not a change) and against `<name>` (also
  fails — its directory was just moved away). The only working escape — staging
  the `.specloop/runs/**` ledger row to force the diff mixed and ride the `ci`
  marker instead — is undocumented archaeology.
- Constraints that bind everything here: `zero-dep-shim` (stdlib only),
  `plugin-relative-paths` (`${CLAUDE_PLUGIN_ROOT}`), `fail-loud-gates` (denials
  are explicit, never silent), and hook timeouts (the hooks stay O(1); nothing
  here re-runs a gate).

## Goals / Non-Goals

**Goals:**

- One shared, tested matcher used by every Bash gate hook; zero per-hook pattern
  logic left behind.
- No false fire on: hyphenated sibling subcommands (`merge-base`, `merge-tree`,
  `merge-file`), guarded phrases inside quoted arguments, or guarded phrases in
  comments/heredoc text that tokenize as arguments.
- No lost fire on: git global flags before the subcommand, compound commands,
  leading env assignments or trivial wrappers, or an untokenizable string
  (conservative fallback).
- Archive-move commits pass the planning-grade rung on their own merits, with the
  merge-precedes-archive guarantee untouched where it already lives.
- Every denial message names the unmet prerequisite and its satisfying command.

**Non-Goals:**

- Defeating deliberate evasion. The effect layer (git `pre-commit`) remains the
  backstop for commits; for the other gates the posture stays "floor against
  accidents". A determined `bash -c "$(base64 -d …)"` is out of scope, exactly as
  `harden-unattended-loop` recorded.
- Marker freshness/self-invalidation semantics (`fix-marker-mechanics` owns the
  marker-chase and docs-only-diff items of #17/#39).
- Hook cwd/worktree resolution (`worktree-native-loop` owns #17 item 7).
- Audit scoping (`scope-audit-to-branch-commits`).
- Shell-language completeness. The matcher understands POSIX-ish tokenization and
  the common operators; it is not a bash parser.

## Decisions

### D1 — One Python helper under `hooks/`, not five shell patterns and not a shim verb

`hooks/_gate_match.py` (stdlib-only; precedent `hooks/_session_brief.py`) becomes
the single entry point for "does this hook input contain a guarded invocation, and
what are its arguments?". Each gate hook pipes its stdin JSON to it once:

```
eval "$(printf '%s' "$input" | python3 "${HOOK_DIR}/_gate_match.py" git-merge)"
# sets: matched=0|1, hook_cwd=…, and per-kind extras (change=…, branch=…)
```

The helper owns: JSON parse, `cwd` extraction, tokenization, operator split,
prefix skipping, subcommand-token match, and per-kind argument extraction. The
hooks keep only: resolve cwd, call the shim check, print the denial. Rationale:

- The matching logic is branching Python, which this repo tests (`tests/`);
  shell `case` patterns are untestable in the same harness and have already
  drifted five ways.
- Not a `gates` subcommand: the shim's contract is gates/manifest work in the
  *adopter's* repo; hook-input parsing is plugin-internal plumbing, and a shim
  verb would freeze it into the public CLI surface. A private, underscore-named
  helper matches `_session_brief.py`'s precedent. (Rejected alternative:
  `gates match <kind>` — public surface for nothing; rejected alternative:
  a sourced shell library — untestable, and quoting-correct token parsing in
  POSIX shell is exactly how this defect was born.)
- Output is `shlex.quote`d `name=value` lines for `eval`, the same convention the
  hooks already use for their inline JSON parse — no new idiom.

### D2 — Match the subcommand token, in command position, per simple command

The matcher tokenizes with `shlex.split(posix=True)`, then splits the token stream
into simple commands on the operator tokens `&&`, `||`, `;`, `|`, `&` (as shlex
emits them when unquoted). For each simple command it:

1. skips leading `NAME=value` assignment tokens and the wrappers `command`,
   `env` (with `env`'s own assignments), `nohup`, `time`;
2. requires the program token to be exactly the guarded program (`git`,
   `openspec`) — basename match, so `/usr/bin/git` also counts;
3. for git, skips global flags before the subcommand: `-C <arg>`, `-c <arg>`,
   `--git-dir[=…]`, `--work-tree[=…]`, `--namespace[=…]`, `-p`, `--paginate`,
   `--no-pager`, `--no-replace-objects`, `--bare`, `--literal-pathspecs`,
   `--exec-path[=…]`, and any other `--flag`/`--flag=value` before the first
   non-flag token (unknown `-x <arg>` pairs are the risk case — see Risks);
4. compares the resulting subcommand token by **exact equality**: `merge` is
   guarded; `merge-base` is a different token and passes. `openspec archive`
   requires the token after `openspec`(+flags) to be `archive`; `openspec new
   change` requires the consecutive tokens `new` then `change`.
5. extracts arguments from that same simple command's remaining tokens: first
   non-flag token after `archive` → `change`; token following `-b`/`-c` (or
   `-b<name>` glued) within a `checkout`/`switch` command → `branch`.

Quoted prose needs no special case: after `shlex.split`, a quoted `--body "… git
merge …"` is one argument token, which can never be in command position.

### D3 — Parse failure falls back to the substring floor

If `shlex.split` raises (unbalanced quotes, stray backslash), the matcher reports
`matched=1` whenever the old substring pattern would have — the current behavior,
verbatim. Direction of error is deliberate: a parse failure may hide a real
invocation, and a false denial costs a retry while a false pass costs the
invariant. This keeps `harden-unattended-loop`'s recorded posture intact and makes
the fallback the *only* place substring matching survives.

### D4 — `archive` is a reserved segment; moved-away change dirs skip validation

In `bin/gates`:

- `_staged_change_dirs` never yields the literal segment `archive`. Paths under
  `openspec/changes/archive/**` are still planning paths (the planning-grade rung
  still applies — `_is_planning_path` already covers them); they just never mint
  a change id to validate.
- For each remaining candidate id, if the staged diff removes the change
  directory and `openspec/changes/<id>/` no longer exists in the working tree
  (the archive move's source half), `openspec validate <id>` is skipped: the
  artifacts were validated across their whole life and the move is mechanical;
  validating a directory that is no longer there can only fail for the wrong
  reason. A change dir that *does* still exist validates exactly as today.
- The allowed-commit message says which rung passed and what was skipped and why
  (fail-loud in both directions: the skip is announced, never silent).

The merge-precedes-archive guarantee is *not* re-implemented here: it already
fires earlier, on the `openspec archive` invocation itself (`gate-archive.sh` →
`discipline check-archive`), which this change makes precise rather than
substring-triggered. (Rejected alternative: validate the archived copy under its
dated name — `openspec validate` addresses active changes, not archive entries,
and the archive gate already guaranteed the content when it let the move happen.
Rejected alternative: require the merge ledger row to be staged — that canonizes
the archaeology instead of removing it, and couples this rung to
`fix-marker-mechanics`' territory.)

### D5 — Denial-message audit: prerequisite + remedy, one convention

Every denial path in `hooks/*.sh` and `cmd_discipline` gets the same shape:
*what is unmet* (named concretely: the change, the branch, the gate, the tree) +
*the command that satisfies it*. Concretely: `check-archive`'s "has not been
merged" gains "merge branch '<change>' to '<target>' (and push, if '<target>' is
a remote ref), then re-run `openspec archive <change>`"; the planning-grade
validation failure names the failing `openspec validate <change>` invocation to
re-run; the marker messages already comply and are the template. The messages
stay in the scripts/shim next to their checks — no message catalog abstraction
for seven strings.

## Risks / Trade-offs

- **[Unknown git short flag with a separate argument]** `git -x foo merge` (some
  future/exotic global short flag) could mis-place the subcommand token →
  mitigation: the skip table covers all of git's current global flags; an
  unrecognized `-x` conservatively treats the *next* token as its argument only
  for flags known to take one, otherwise treats the next token as the
  subcommand candidate — and the fallback posture (D3) plus the effect layer
  bound the damage. Table drift is a one-line fix with a unit test.
- **[Aliases and wrappers still invisible]** `git mg` (alias) or a repo script
  wrapping `git merge` never matched before and still will not → mitigation:
  none needed; unchanged floor, and commits keep the git-layer backstop.
- **[`eval` of helper output]** the hooks `eval` generated assignments →
  mitigation: every value passes through `shlex.quote`, same as today's inline
  snippets; the helper emits a fixed, known set of variable names only.
- **[Skipped validation on the move's source half]** a corrupted change could be
  archived without a final validate → mitigation: the archive gate already
  verified merge-to-target before the move ran, and everything merged passed the
  commit gates on its way in; the skip is also announced in the allow message.
- **[Behavior shift for adopters who leaned on the old over-matching]** e.g. a
  prompt that "relied" on `git merge-base` being blocked → no known such use;
  the change is a strict reduction of false fires, and the spec scenarios pin
  the new boundary.

## Migration Plan

Ships as plugin content; hook changes take effect on the next session (Claude
Code reads hooks at session start). No manifest, schema, or adopter-facing
contract changes; no data migration. Rollback is reverting the commit.

## Open Questions

- Whether `gate-propose.sh`'s Write-path matching wants the same helper for its
  JSON/cwd parse (pure deduplication — its *matching* is path-based and not
  defective). Safe to decide at implementation time; default is to leave it
  untouched, per the proposal.
