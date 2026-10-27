# Proposal

## Why

The fix for #56 and #49 (`unblock-authored-lock`) has to reach adopters soon. `main` already carries `git-layer-enforcement`, which adds a capability, so the next release is a minor: 0.8.0. 0.8.0 is also the announced expiry of the earlier `specloop` names. Cutting it on time would mean landing `remove-specloop-forwarders` first, and RELEASING.md forbids cutting 0.8.0 without it. The maintainer chose to release the fix in 0.8.0 now and move the expiry one release later, to 0.9.0. Moving a removal date later costs adopters nothing.

## What Changes

- The earlier names are read, with the warning, through 0.8.x. The warning and every adopter-facing statement name **0.9.0** as the release in which they stop working.
- Dual status posting (`specloop/ci` beside `gatedloop/ci`) and the Claude Code forwarder last as long as the read-both readers.
- `remove-specloop-forwarders` is retargeted to 0.9.0 (amended in the same plan PR, then re-attested). Its content is unchanged.
- RELEASING.md's expiry rule names 0.9.0.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `plugin-positioning`: the earlier name is read loudly through 0.8.x, and the warning names 0.9.0.

## Impact

- `bin/gates`: `EARLIER_EXPIRY`, and the test that pins the warning's tail.
- README.md, SETUP.md, CHANGELOG.md (the next section only, so 0.7.0's history stays as written), `docs/status.md`, RELEASING.md, CLAUDE.md, and the `adoption/catalog.json` migrate-name item's text. The `git-push-hook` item's `since: 0.8.0` is a different fact and stays.
- Rejection test: it authors no artifact and names no stack command. It keeps a stated guarantee true: the removal date adopters were told stays a fact rather than a broken promise.
