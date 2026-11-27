# Proposal

## Why

OpenSpec 1.16.0 is out, and gatedloop declares a supported range of `1.14.3` to `1.14.3`, so `gates doctor` warns every adopter who upgrades (#137). The `openspec-latest` canary passed `gates doctor` and the full `gates run ci` on 1.16.0, and `openspec validate --all --strict` gives this repository the same findings under 1.14.3 and 1.16.0. The range is stale, not wrong.

## What Changes

- `OPENSPEC_MAX_TESTED` in `bin/gates` becomes `1.16.0`; `OPENSPEC_MIN` stays `1.14.3`. No other shim behaviour changes.
- The pull-request `ci` matrix gains one OpenSpec 1.16.0 leg (ubuntu-24.04, Python 3.13), five legs in all. The leg that posts `gatedloop/ci` and `gatedloop/tests` stays on 1.14.3.
- `README.md`, `SETUP.md`, `docs/status.md` and `docs/stability.md` state the range as 1.14.3 to 1.16.0. SETUP notes that 1.16's npm install needs Node.js 22.12+.
- No change for 1.16's strict scenario-step check or its inline-fence fix (design D4).

Ships as a patch release.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `public-contract`: the ci requirement states how the highest tested OpenSpec version is covered (one added leg) and which leg publishes statuses.

## Impact

- `bin/gates` (one constant), `.github/workflows/gatedloop.yml`, `README.md`, `SETUP.md`, `docs/status.md`, `docs/stability.md`.
- Adopters: `gates doctor` stops warning on OpenSpec 1.15 and 1.16.
