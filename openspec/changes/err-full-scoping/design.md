## Context

`_select_scoped_gate(m, gate, changed)` in `bin/gates` returns a surface's override only when exactly one non-catch-all surface is hot and it declares the gate; otherwise the global gate. `ci` scopes off the staged diff and `unit` off the working set (`_working_set_files`). Neither checks whether every changed path is matched by some surface, although the gate-binding requirement and SETUP.md both list "an unmatched changed file" as a full-gate case (#61).

For `unit`, the multi-surface case falls back to the global gate. That is err-full only if the global `unit` is a superset of every override, which nothing checks and #45 shows is false in the field. The `unit` gate is also the red half of red-before-green, so a too-narrow `unit` does not just under-test: it records a false green where the loop requires a red.

## Goals / Non-Goals

**Goals:**
- No scoped selection runs narrower than the spec's err-full rule allows.
- A multi-surface `unit` run exercises every hot surface's declared oracle.

**Non-Goals:**
- Changing the `ci` multi-surface fallback (D3).
- Checking from command strings whether one command covers another (D5).
- Scoping `live-check`, `verify` or other gates.

## Decisions

### D1. An unmatched path selects the global gate

`_select_scoped_gate` returns the global gate when any path in `changed` is matched by no non-catch-all surface. Catch-all surfaces are left out of this test as they are left out of the one-surface count: a `match: "**"` surface matches every path, so counting it would hide every unmatched path, and most field manifests declare one.

The scope announcement for this case says why: `ci[full] — <path> matches no surface`, naming the first such path in sorted order.

*Alternative considered:* count catch-all-only paths as matched. Rejected: it is today's behaviour in the common manifest shape, which is #61.

### D2. A multi-surface `unit` runs the union of oracles

When `gate == "unit"`, every changed path is matched (D1), and two or more non-catch-all surfaces are hot, the selection returns a list of specs:

- each hot surface's `unit` override, in the manifest's surface order;
- the global `unit` once, if any hot surface declares no override.

Identical command strings run once (the live-check dedupe rule, fix-marker-mechanics D3). The extra arguments a caller passes (`gates run unit -- …`) are appended to each command.

Preconditions (`requires`) are all checked before any command runs, as live-check does; any failure is the precondition-failed outcome and nothing runs. The commands then run in order under one lock acquisition. All run even after a red, so the output shows every surface's verdict; the exit code is the first non-zero one, else 0. One ledger row and at most one record are written for the invocation, so the attempt budget counts it as one attempt.

The recorded and announced scope is the surface names joined with `+` in run order, with `full` for the global component: `unit[frontend+e2e]`, or `unit[frontend+full]`. Scope is a free string to every reader today (only `ci` markers compare it to `full`), so no reader changes.

*Alternative considered:* a `gates validate` warning instead (#45's second option). Rejected as the fix: see D5.

### D3. `ci` keeps the global fallback

A multi-surface `ci` still runs the global `ci`. The global `ci` is, by the gate-binding contract, the oracle the merge requires on the head and the merged tree, so it is the full statement of "green". A surface override narrows it; a union of narrowings is still a narrowing, and replacing the global run with it would make a multi-surface commit's evidence weaker than today's. If an adopter's override checks something the global `ci` does not, the merge would miss it too, and that is a manifest defect the per-task gate cannot repair.

`unit` differs because the loop reads it for a red: a run that omits the new test is not a weaker green but a false verdict about the task.

### D4. Default-on

Both changes apply without a manifest key. They narrow nothing and restore what gate-binding and SETUP.md already state; an opt-in would leave the documented guarantee false by default. A manifest without `gates:` overrides selects exactly as before, because both rules only ever replace a scoped command.

### D5. No `gates validate` warning

Whether a global `unit` covers a surface's override cannot be read from two opaque command strings, and a heuristic (substring match on paths) would be wrong both ways. With D2, coverage no longer matters for correctness. `gates validate` is left unchanged.

## Risks / Trade-offs

- [A unit run across surfaces costs more than one global run when overrides overlap the global] → identical strings dedupe; the global runs at most once; overlap is the adopter's to trim.
- [Commits touching an unmatched path now pay a full `ci`] → the intended cost; the message names the path so the adopter can add it to a surface.
- [Several commands under one lock lengthen its hold] → same as live-check's single acquisition; the lock is per gate, not per surface.

## Migration Plan

None beyond the release note: adopters may see `ci[full]` where they saw a scoped run, and `unit[a+b]` runs.

## Open Questions

None.
