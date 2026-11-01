## Context

`gates run ci` scopes off the staged diff, and `gates run unit` off the working set. Both pass the paths to `_select_scoped_gate`, `_first_unmatched_path` and, for `unit`, `_unit_union` (err-full-scoping D1, D2). `_first_unmatched_path` already skips `.gatedloop/`, because every task commit stages a ledger row. The change's own `tasks.md` is in the same position: tdd-apply 5h stages its `[x]` with every task's code (done ⟺ committed). But it is skipped nowhere, so it is either unmatched or a second hot surface (#122).

## Goals / Non-Goals

**Goals:**
- A task commit wholly inside one scoped surface runs that surface's `ci` again, whatever the manifest says about `openspec/**`.
- The same holds for `unit` off the working set.

**Non-Goals:**
- Changing the hot set used for convention review, live-check or `gates surfaces`.
- Exempting any other plan artifact.
- Detecting whether a `tasks.md` edit is tick-only (D2).

## Decisions

### D1. "Own" is the change the branch resolves to

The exempt path is `openspec/changes/<change>/tasks.md`. Here `<change>` is what `_resolve_change_name(root, None)` returns: the current branch, when `openspec/changes/<branch>/` exists. That is the same resolution the ledger row for the run uses. On `main`, a `plan/*` branch, a docs branch or a detached HEAD there is no change, so nothing is exempt.

Another change's `tasks.md` stays an ordinary path, unmatched unless a surface covers it. A task commit never stages another change's ticks, so such a path means the diff reaches outside the change, and err-full is the right answer.

*Alternative considered:* exempt every `openspec/changes/*/tasks.md`. Rejected: it widens the exemption to paths no task commit stages.

### D2. The whole file is exempt, not only tick-only diffs

Scope selection only chooses which test command runs. The content of `tasks.md` is never test input. Its plan-level integrity is held elsewhere:
- the approval digest covers oracle tags;
- the lock refuses a tag that differs from the merge target's;
- the merge always runs the unscoped `ci`.

A non-tick edit to `tasks.md` therefore loses nothing by not widening the scope. Detecting tick-only diffs would mean parsing a staged diff for one file, and would add a code path with its own edge cases, such as a tick and an edit in one commit. It would gain nothing.

*Alternative considered:* exempt only when the staged diff of the file changes `[ ]` to `[x]` and nothing else. Rejected for the reason above.

### D3. One filter, applied before every scope decision

A helper, `_scope_paths(root, changed)`, returns `changed` minus the current change's `tasks.md`. `gates run` applies it once to the staged diff (`ci`) or working set (`unit`). The filtered list then feeds `_select_scoped_gate`, the unmatched-path announcement and `_unit_union`, so all three judge the same paths. `_first_unmatched_path` keeps its own `.gatedloop/` skip.

If the filtered list is empty, as with a tick-only commit, the existing rule applies: an empty diff runs the global gate. That is err-full and rare.

`hot_surfaces` itself is not changed, so `gates surfaces`, `gates rules` and live-check selection still see the tick (Non-Goals).

### D4. `unit` gets the same treatment

The working set holds the tick from the moment tdd-apply 5f flips it, so the `unit` green and final runs hit the same defect. The filter is applied to both gates.

### D5. SETUP.md correction

"Scoped `ci`/`unit`" currently ends: "A change's own `openspec/changes/<change>/tasks.md` is: every task commit stages it, so with no surface covering `openspec/**` each task commit runs the global `ci`. Add `openspec/**` to a surface (a `docs` one, say) to scope those commits."

It is replaced by a sentence saying that the current change's `tasks.md` is not counted either, since every task commit stages its tick, and that another change's `tasks.md` still is.

### D6. Default-on, no manifest key

This restores the scoped behaviour that 0.9.x had and that err-full-scoping meant to keep. err-full-scoping's own design excluded `.gatedloop/` for the same reason. No adopter gains anything from a full `ci` caused by a tick. Manifests without `gates:` overrides never scope, so they are unaffected.

## Risks / Trade-offs

- [A `tasks.md` edit rides a scoped `ci`] → it cannot change a test's input, and the merge's unscoped `ci` still runs (D2).
- [A project whose tests read the live `tasks.md`] → its full `ci` still runs at the merge; a per-task scoped run would miss it until then, as for any path its surface doesn't own. No such adopter is known.
