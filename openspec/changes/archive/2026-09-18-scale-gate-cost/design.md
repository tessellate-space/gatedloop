# Design: scale-gate-cost

## Context

See `proposal.md` — Why. Constraints: the hot-set selection lives in `bin/gates` and
already drives two consumers (rules, live-check selection); the commit gate has one
entry point since `unblock-parallel-planning` (`gates discipline check-commit`, called
by both the PreToolUse hook and the git-layer hook); markers bind a gate name to an
exact tree; the shim is stdlib-only. Field data (#13): ~2–4 min × ≥2 runs/task ×
8–17 tasks of gate wall time, and token bloat from inline review + raw gate output.

## Goals / Non-Goals

**Goals:** per-task gate cost proportional to what the task touched, without ever
weakening what reaches `main`; deterministic scope selection (code, not judgement);
output hygiene as shim default rather than prompt folklore; keep the adopter opt-in
and the no-override manifest byte-for-byte compatible in behavior.

**Non-Goals:** task batching (deferred to `docs/candidates.md` — it blurs
done ⟺ committed, and task granularity is the schema's, axis B); scoping `verify`,
`integration`, or `live-check` (completion-grade gates are exactly where full truth is
the point); parallel gate execution; any change to what convention review judges.

## Decisions

### D1: Overrides live on the surface, selection stays in code

Manifest shape:

```yaml
surfaces:
  - name: frontend
    match: "frontend/**"
    gates:            # optional, per-surface overrides
      ci: "just ci-frontend"
      unit: "just unit-frontend"
```

`gates run ci` computes the staged diff's hot set with the existing selection and runs
the scoped command only when the hot set is exactly one surface declaring the
override. **Catch-all surfaces (pattern matching every path, e.g. `**`) are excluded
from the scope decision** — most field manifests declare one, and counting it would
make every diff "multi-surface" and silently disable scoping forever. `gates validate`
notes catch-all exclusion so the rule is visible, and rejects a `gates:` block naming
an undeclared gate.

**Rejected — scoped-oracle selection by union of hot scoped commands:** running N
scoped suites can cost more than the global gate, and "which ran" becomes a set,
muddying the marker. One-surface-or-full is predictable and auditable.

**Rejected — a separate `ci-<surface>` gate namespace at top level:** it duplicates
the surface list into the gate list and lets the two drift; the surface is the natural
owner of its own oracle.

### D2: Scope is recorded, and the merge ignores scoped greens

The marker payload and the ledger row gain a `scope` field (`full` or the surface
name). `discipline check-commit` accepts a fresh marker of either scope for the staged
tree — the per-commit guarantee is "this tree was tested by the declared oracle for
what it touched". The completion step (`verify`/pre-merge) requires `scope: full` on
the branch head. This is the whole safety argument: scoped oracles change *when* the
full suite runs (once per change instead of twice per task), never *whether* it runs
before integration.

### D3: Output capture in `gates run`, not in prompts

`gates run` writes the child's combined output to `.specloop/out/<gate>-<ts>.log`
(under the untracked `.specloop/`, consistent with the ledger), prints one summary
line on exit 0 (`ci[frontend] green in 84s — full output: <path>`), and dumps the file
to stderr on non-zero before exiting with the child's code. `--verbose` streams as
today. The exit-code contract is untouched, so hooks and markers see no difference.

**Rejected — teaching `| tail` in the skill:** it survives only as long as the prompt
is read carefully, truncates *failures* too (the one place full output matters), and
every adopter's agent has to relearn it. The shim owns process execution; it should
own output discipline.

### D4: Review delegation becomes a MUST, not an example

`skills/tdd-apply/SKILL.md` §review and `agents/tdd-implementer.md` state that the
convention review runs as the `convention-review` subagent and its verdict is recorded
via `gates review record` (harden 0.3); reviewing inline in the loop's own context is
named as the anti-pattern (#13's measured token driver). No mechanism change — the
agent and the recording command both exist; this pins the composition.

## Risks / Trade-offs

- **[A scoped green hides cross-surface breakage until completion]** By design — the
  full `ci` still stands between the branch and `main` (D2). The trade moves the
  discovery point for cross-surface regressions from "every commit" to "once per
  change", which is the entire cost saving; an adopter who wants earlier discovery
  simply declares no overrides.
- **[Two suites to keep honest]** A scoped `ci` that drifts from the global one (tests
  the wrong subset) gives false local confidence. → The oracle *bindings* are the
  adopter's (rejection test); Specloop's part is recording scope so the ledger shows
  exactly what evidence backed each commit.
- **[Output files accumulate]** `.specloop/out/` grows per run. → Keep last N per gate
  (small, in-shim rotation); untracked directory, never committed (#10 precedent).

## Open Questions

- Whether `unit` scoping should also consult the *working tree* diff (red-proof runs
  before staging) rather than the staged diff — decidable at implementation; the spec
  scenarios pin staged-diff behavior for `ci` only.
