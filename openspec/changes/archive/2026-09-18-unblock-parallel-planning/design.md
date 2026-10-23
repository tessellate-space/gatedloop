# Design: unblock-parallel-planning

## Context

See `proposal.md` — Why. Three facts shape the approach:

- Every gate hook already parses its stdin JSON (for `tool_input.command` or
  `tool_input.file_path`) and then does `cd "${CLAUDE_PROJECT_DIR:-$(pwd)}"`. Claude
  Code sends a top-level `cwd` field in every hook input; the hooks simply ignore it
  today. The halted `harden-unattended-loop` run reproduced the failure with a fixture:
  the same hook input allows under the worktree's cwd and denies under the session
  root's, because markers live per-worktree under `.git/worktrees/<name>/specloop/`.
- The branch logic behind D9 already lives in the shim (`gates discipline
  check-propose`), not in the hook script — the hook is a thin adapter. That split is
  the pattern this change extends: judgement in testable stdlib Python, hooks as
  adapters.
- `enforce-at-the-effect` (apply-ready) adds a git `pre-commit` hook running the same
  marker check at the git layer. Git hooks execute in the repo that is committing, so
  they are worktree-correct by construction — but they must apply the same
  planning-grade selection this change introduces, or the two layers will disagree.

## Goals / Non-Goals

**Goals:** make every gate measure the repository the guarded command runs in; give
docs-only commits a gate proportional to what they can break; make the scaffold obey
the discipline its artifacts already obey; keep all new judgement inside `bin/gates`
where `tests/` can reach it.

**Non-Goals:** parallel implementers (one implementer owning the primary checkout and
the running stack remains the design); any change to marker format or ledger row
shape; the brace-glob matcher fix (issue #1); relaxing any gate for non-planning
files.

## Decisions

### D1: Resolve the repo from the hook input's `cwd`, in one shared helper

Each hook replaces `cd "${CLAUDE_PROJECT_DIR:-$(pwd)}"` with: parse top-level `cwd`
from the hook input JSON it already reads; `cd` there if present and a directory;
else fall back to `CLAUDE_PROJECT_DIR`; else `pwd`. The parse lives in the same
embedded `python3 -c` block each hook already runs (one JSON load, two fields out),
so no new process is spawned and no shared sourced file is introduced — hooks stay
self-contained, per `self-contained-plugin`.

**Rejected — a `--repo` flag threaded into the shim:** the shim already acts on its
own `cwd`; moving resolution into Python flags would leave the hook's `git
write-tree` (gate-commit) still running in the wrong directory. The `cd` is the fix.

**Rejected — documenting "worktrees unsupported":** the worktree is the designed
escape for #5, and `Agent(isolation: worktree)` produces this configuration in
practice today.

### D2: Planning-grade selection lives in the shim as `gates discipline check-commit`

`gate-commit.sh` currently calls `gates gate-marker check ci <tree>` directly. It
switches to one shim entry, `gates discipline check-commit <tree>`, which:

1. Classifies the staged diff (`git diff --cached --name-only`) against the planning
   set: the planning home (resolved from OpenSpec config, default `openspec/`) plus
   the manifest's `conventions.rules-doc` path.
2. Planning-only → run `gates validate` and `openspec validate --json` for any staged
   change dirs; both zero → allow (exit 0), else report the failing validation.
3. Otherwise → the existing `gate-marker check ci <tree>` compare, unchanged.

One entry point means `enforce-at-the-effect`'s git `pre-commit` hook calls the same
thing and the two enforcement layers cannot diverge. Classification is pure stdlib
(`git` subprocess + the existing matcher) and unit-testable with fixture indexes.

**Rejected — classification inside the hook script:** untestable from `tests/`, and
duplicated the moment the git-layer hook needs it.

**Rejected — a declared `planning` gate in `.gates.yaml`:** the planning set is not
stack-varying (it is OpenSpec's own layout plus one declared path), so delegating it
to the adopter adds a knob with no legitimate second value.

### D3: D9 admits `plan/*` branches based on the merge target

`gates discipline check-propose` allows authoring when the current branch is the
merge target (existing behavior) **or** matches `plan/*` **and** the merge target is
an ancestor of `HEAD` (`git merge-base --is-ancestor`). The ancestry condition is
what actually preserves D9's rationale — authoritative specs and in-flight changes
visible — rather than the branch name; the name check just keeps `check-implement`'s
change-branch gate from ever seeing a plan branch (plan branches never match a
`openspec/changes/<name>/` directory, by the existing `/specloop:propose` naming).

A stale plan branch (merge target moved ahead) is still allowed — authoring against a
slightly old base is a review problem, not a discipline violation — but the check
prints an advisory naming how far behind it is. Refusing would make every long review
block its own amendments.

### D4: The scaffold is gated by the same check, via a Bash matcher

A new thin hook (`hooks/gate-scaffold.sh`, `PreToolUse` on Bash) matches
`*"openspec new change"*` and calls `gates discipline check-propose --scaffold`,
which runs the D3 branch logic with no file argument. Same judgement, same message,
one step earlier — so a refusal happens before any directory exists. The refusal
message (both scaffold and authoring paths) ends by listing any change directory
that is untracked and unproposed (`git status --porcelain` ∩ `openspec/changes/*`)
with the `rm -r` to clean it, closing #7's debris half.

**Rejected — cleanup-on-refusal (auto-delete the stranded dir):** a hook that deletes
working-tree content on a heuristic is the wrong risk profile; naming it is enough.

### D5: Worktree marker stores stay separate — deliberately

With D1, each worktree reads and writes its own `.git/worktrees/<name>/specloop/`
markers. No sharing, no promotion: a green `ci` in one worktree says nothing about
another worktree's index. This is not a limitation to engineer around; it is the
marker's meaning (D2 of `harden-unattended-loop`: the marker binds a gate to an
exact tree in an exact repo).

## Risks / Trade-offs

- **[Planning-grade gate as a smuggling channel]** A commit touching only
  `openspec/**` can still delete another change's artifacts. → The scope is
  validation, not review: `openspec validate` runs per staged change dir, and
  convention review still applies through the normal loop. The gate never applied to
  *content* judgement before; this changes which oracle runs, not who reviews.
- **[`cwd` absent from hook input]** Older Claude Code versions or other entry points
  might omit it. → Explicit fallback chain (`cwd` → `CLAUDE_PROJECT_DIR` → `pwd`)
  keeps today's behavior exactly in the single-checkout case; a fixture test covers
  each rung.
- **[Hook changes need a new session]** The fix only takes effect after reinstall +
  new session. → Release note; `gates doctor` already reports the installed plugin
  version.
- **[Ordering with `enforce-at-the-effect`]** Both changes touch the commit gate. →
  D2's single entry point is the reconciliation: whichever lands second rewires its
  caller to `discipline check-commit` and changes nothing else.

## Open Questions

- Whether `gates doctor` should warn when it detects a worktree whose hook layer
  predates this fix (nice, not load-bearing — can be answered at implementation).
