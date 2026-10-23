## Context

`bin/gates` computes one changed-file set — `git diff HEAD` + staged + untracked —
and feeds it to every consumer: `gates rules`, `gates surfaces`, and `gates run
live-check`. The set is correct for the per-task consumers and wrong for the
change-level one, which runs when the tree is clean and therefore selects nothing
(review F1, reproduced). The two consumers genuinely want different subjects:

```
task-level gates                     change-level gates
────────────────                     ──────────────────
subject: the current task's          subject: EVERYTHING the change
uncommitted diff                     touched = branch diff vs merge target
                                     ∪ working set
rules / surfaces / review scope      live-check (verify, eval hot-set input)
baseline today: working tree ✓       baseline today: working tree ✗ (empty)
```

Constraints: zero-dep-shim (stdlib only), fail-loud-gates, and the fix must not
require any prompt change — `tdd-apply` §7.5 already types bare `gates run
live-check`, and a prompt-remembered flag is the failure mode being removed.
`harden-unattended-loop`'s merge marker builds directly on this selection.

## Goals / Non-Goals

**Goals:**
- A clean tree on a change branch selects the change's true hot set.
- The distinction between the two baselines lives in code, keyed by what is being
  run, with the existing `--changed`/`--all` flags as explicit overrides.
- An empty change-level hot set is loud: it names the baseline and the merge
  target it diffed against.
- Rule-id resolution anchored to `### <id>` headings.
- Selection covered by tests, including the F1 reproduction.

**Non-Goals:**
- Markers, ledger, or any enforcement (that is `harden-unattended-loop`).
- Reading the declared integration process from `.gates.yaml`
  (`onboarding-asks-first` records it; harden consumes it). This change may *use*
  the merge target only to compute a diff, resolved generically.
- Changing what `gates rules`/`gates surfaces` select for the per-task review.

## Decisions

### D1: Baseline is selected by gate level, not by a flag

`cmd_run` on `live-check` computes the changed set as
`merge_base_diff(target) ∪ working_set`; everything else keeps `working_set`.
The union matters: a live-check run mid-change (dirty tree) must cover both what
is committed on the branch and what is in flight. `--changed`/`--all` continue to
override both paths unchanged.

Alternative rejected: one union baseline everywhere. It is simpler, but it makes
the per-task convention-review scope grow monotonically over the life of a change —
by the last task the review reads every rule the change ever touched, which
un-cheapens the deliberately cheap reviewer.

### D2: Merge target resolution is generic and observable

Resolve, in order: `origin/HEAD` (symbolic ref → the remote's default branch), a
local `main`, a local `master`; if none resolves, or `git merge-base` fails (no
merge base, detached HEAD, shallow clone), **fall back to the working-set baseline
and say so on stderr** — degraded selection must be visible, not silent. On the
target branch itself (`HEAD` == target), the merge-base diff is empty by
construction and the working set is the whole story, which is also the correct
behaviour for a repo that runs the loop directly on its default branch.

### D3: An empty change-level hot set reports its evidence

When `live-check` selects no surfaces, the message states the baseline kind
(merge-target diff vs override), the resolved target, and the number of files
considered. Exit code stays 0 — an empty hot set is legitimate (a docs-only change
on a project whose surfaces are all code) — but it is now diagnosable, and the
harden marker can later record the evidence rather than a bare green. Loudness is
the fix; refusing would break docs-only changes.

### D4: Rule-id resolution reuses the conventions parser

`_errors` resolves a rule-id by exact match against the heading ids
`parse_conventions_doc` returns (relaxed to also accept headings without the
`Applies to:`/`Rule:` metadata — resolution needs the heading, not the sync
metadata). The substring check is deleted. The is-it-an-id heuristic
(no spaces, ≤60 chars) is unchanged — inline prose rules stay a documented escape
hatch.

### D5: Glob semantics — document fail-hot, don't reimplement a matcher

Writing a correct `**`-aware matcher in stdlib is possible but is new
safety-critical surface for marginal gain, and the current error direction is
already the safe one (surfaces run hotter than declared, never colder). Decision:
keep `fnmatch`, state the fail-hot contract in `SETUP.md` where surfaces are
documented, and pin the direction with a test so a future "fix" cannot silently
flip it to under-matching. Revisit only if a real adopter manifest needs
separator-exact matching.

## Risks / Trade-offs

- **First honest run may be red.** Adopters whose live-check passed vacuously will
  see it actually run at the next change completion. That is the defect being
  fixed; the release note must name it so the sudden red is read as recovered
  coverage, not regression.
- **Merge-target guessing can be wrong** in unusual topologies (no remote, no
  main/master). D2's fallback keeps the old behaviour with a loud notice, so the
  failure mode is the status quo plus a diagnostic, never something new and quiet.
- **`main...HEAD` on a stale local main** under-reports if the target moved; using
  `origin/HEAD` first minimises this, and the union with the working set bounds the
  damage to already-merged files.
