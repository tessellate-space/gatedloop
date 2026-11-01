## Why

err-full-scoping (0.10.0) made an unmatched changed path select the global gate. Every task commit stages its change's own `openspec/changes/<change>/tasks.md` tick, so for an adopter with per-surface overrides a task commit can no longer get a scoped `ci` (#122):

- with no surface covering `openspec/**`, the tick is an unmatched path, and the gate errs full;
- with `openspec/**` in a surface of its own, as SETUP.md advises, the tick makes a second hot surface, and the gate errs full again;
- with `openspec/**` in a code surface, that surface turns hot for every other surface's tasks.

So SETUP's remedy cannot work. In tessellate-space's ledgers (2026-10-15 to 10-31), 69 green per-task `ci` runs were scoped, with medians of 17–104 s against 199 s for a full run. Under 0.10.0 all of them run full, about 3 extra CPU-hours per two weeks on one machine. A tick cannot change what a test runs.

## What Changes

- When `gates run ci` or `gates run unit` selects its scope, the current change's own `openspec/changes/<change>/tasks.md` is left out of the changed paths, as the loop's `.gatedloop/` state already is. It neither counts as unmatched nor makes a surface hot.
- The current change is the one the branch resolves to, as the ledger already resolves it. Another change's `tasks.md`, and every other plan artifact, still counts as an ordinary path.
- Only the gate scope changes. The hot set `gates surfaces` and `gates rules` report, and so convention review's scope, is unchanged.
- SETUP.md "Scoped `ci`/`unit`" drops the remedy that cannot work and says the tick is not counted.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `gate-binding`: scoped-oracle selection leaves the loop's own state and the current change's `tasks.md` out of the diff it judges.

## Impact

- `bin/gates`: the `ci`/`unit` branch of `gates run`, where the scope paths are computed, plus one helper.
- `SETUP.md`: "Scoped `ci`/`unit`".
- `tests/`: new cases for `ci` and `unit`.
- Adopters with scoped overrides get scoped task commits back. Default-on, because it restores what 0.10.0 was meant to keep. Manifests with no `gates:` overrides are unaffected.
