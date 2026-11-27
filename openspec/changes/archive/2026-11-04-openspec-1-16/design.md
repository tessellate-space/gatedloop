# Design

## Context

The stability-contract change (archived `2026-11-01-stability-contract`) introduced `OPENSPEC_MIN` and `OPENSPEC_MAX_TESTED`, both `1.14.3`, the OS × Python × OpenSpec ci matrix, and the weekly `openspec-latest` canary. Its D6 said a widening is "a one-line edit to the two constants, plus the matrix entry that proves it"; its D7 made the doctor warn outside the range. This change is the first widening. The evidence is in #137: the canary on 1.16.0 passed `gates doctor` (only the range warning) and `gates run ci`, full suite included, and `openspec validate --all --strict` agrees across both versions.

## Goals / Non-Goals

**Goals:** declare 1.16.0 as tested, prove it in pull-request ci, and state the same range everywhere.

**Non-Goals:** raising `OPENSPEC_MIN`; reacting to 1.16's stricter validation in shipped prompts or the shim; testing 1.15.x separately (it lies inside the range and the canary passed through it).

## Rejection test

It makes a stated guarantee enforceable: the declared range is what the doctor and ci check. Ours.

## Decisions

### D1. `OPENSPEC_MAX_TESTED` becomes `1.16.0`; `OPENSPEC_MIN` stays `1.14.3`

The one-line widening stability-contract D6 anticipated. Keeping the minimum avoids forcing an upgrade on adopters, and 1.14.3 is still what the status-posting leg runs. No other shim behaviour changes: the doctor's range comparison (stability-contract D7) already handles a range wider than one version. The test that ties the constants to `docs/stability.md` keeps them in step with D3.

### D2. One extra ci leg, by `include`; the status leg stays on the minimum

`.github/workflows/gatedloop.yml`'s `ci` matrix keeps `openspec: ['1.14.3']` and adds `include: [{os: ubuntu-24.04, python: '3.13', openspec: '1.16.0'}]`, so legs go 4 → 5, not 8. Crossing both versions with every OS and Python would double the run for little signal: OS and Python variation is already covered on the minimum, and the canary covers latest weekly.

`PRIMARY` stays `os == ubuntu-24.04 && python == 3.13 && openspec == 1.14.3`, so the new leg differs from it only in `openspec` and evaluates false: it runs `gates run ci` and can fail the workflow run, but never runs `gates marker publish`. This deviates from stability-contract D6, which put the statuses on the max-tested leg. Keeping them on the minimum means branch protection reads the same context from the same environment as before, and the statuses don't move every time the range widens. The `record` job is gated on `push`, has no `needs` on `ci`, and installs its own pinned OpenSpec, so the matrix change cannot reach it. The matrix comment `OPENSPEC_MIN .. OPENSPEC_MAX_TESTED in bin/gates` stays true once it covers both values (the `include` sits under it).

### D3. The documented range reads "1.14.3 to 1.16.0"

`README.md` (status line, install prerequisites, OpenSpec prerequisite), `SETUP.md` (prerequisite 1), `docs/status.md` (header line and Upstream coupling) and `docs/stability.md` (the declared range). SETUP's prerequisite adds that OpenSpec 1.16's npm install needs Node.js 22.12+, and the standalone binary does not. `docs/status.md`'s Upstream coupling already records a `validate --strict` break, so it gains one sentence: 1.16's `--strict` also fails a scenario with no WHEN/GIVEN or THEN step.

### D4. No change for 1.16's scenario-step check or inline-fence fix

No shipped prompt runs `openspec validate --strict`, and the commit hook's and plan-check's validation of a planning commit is this repository's and adopters' own spec content, which the new check judges correctly. The shim reads `#### Scenario:` titles only, never the steps, so the step check cannot change what it collects. The shim never treated fences when collecting scenarios, so 1.16 no longer opening a fence on a line that starts with inline triple-backtick code brings OpenSpec closer to the shim, not further. 1.15's `--json` output is stated unchanged, and its `/opsx:verify` change touches a prompt we hold no copy of.

## Risks / Trade-offs

- **macOS or Python 3.9 on 1.16 is untested in pull-request ci.** Accepted: the canary runs latest weekly, and an OS-specific OpenSpec break would also show on the minimum leg on the next widening.
- **Node.js floor.** Our workflows set `node-version: 22`, which resolves to the latest 22.x, above 22.12.

## Migration

None. Adopters on 1.15 or 1.16 stop seeing the doctor warning after the patch release.
