## Why

The scoped `ci`/`unit` selection is meant to err full: a narrower command runs only when the diff provably belongs to one surface. Two adopter reports show it can pick an oracle narrower than the one declared.

- **#61.** The gate-binding spec says an unmatched changed file runs the global gate. `bin/gates` checks only the hot surfaces, so a diff with one surface's file plus a file no surface matches runs that surface's scoped command. Seen in #60: a staged `.gates.yaml`, `scripts/test-parallel` (both unmatched) and `CLAUDE.md` ran `ci[docs]`.
- **#45.** A task whose tests sit in two surfaces runs the global `unit`, as designed. When a surface's own `unit` override is not part of the global `unit`, the new test never runs, the required red reads green, and the red-before-green record is lost. The lane worked around it by moving files aside.

Both are a gate reporting green for code it did not run, which the status page lists as broken.

## What Changes

- Scoped selection runs the global gate whenever any changed path matches no surface, ignoring catch-all surfaces as today. This applies to `ci` and `unit`.
- A `unit` run whose working set spans several non-catch-all hot surfaces, with every changed path matched, runs each hot surface's `unit` override in turn, and the global `unit` once for the hot surfaces that declare none. The run is red if any command is red. The announced and recorded scope names every surface that ran.
- `ci` keeps the global fallback for multi-surface diffs. The global `ci` is the oracle the merge requires, so a union of scoped commands would only be a cheaper different oracle, not a fix.
- SETUP.md and the manifest schema's description of the overrides say so.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `gate-binding`: the scoped-oracle selection names the unmatched-path rule as enforced, and a multi-surface `unit` runs the union of the hot surfaces' oracles.

## Impact

- `bin/gates`: `_select_scoped_gate` and the scoped branch of `gates run` for `unit`.
- `SETUP.md` "Scoped `ci`/`unit`", and the `gates` override description in `schema/gates.schema.json`.
- `tests/`: new cases for both rules.
- Adopters with scoped overrides: some commits that ran a scoped `ci` now run the full one (#61), and some multi-surface `unit` runs now run more commands (#45). Both are default-on because they restore what the spec already promises; manifests with no `gates:` overrides are unaffected.
