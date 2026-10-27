# Proposal

## Why

`rename-to-gatedloop` kept every earlier `specloop` name working, loudly. Its design (D7) set the expiry at 0.8.0 and named this change; `defer-earlier-name-expiry` moved it to 0.9.0 so the #56 fix could ship in 0.8.0, so the expiry has a plan rather than a memory. The precedent is `rename-to-gates` D3: a forwarder with no stated end is how an old name survives long enough to become a problem.

## What Changes

In 0.9.0:
- **Read-both is removed.** The shim reads only the new spellings: `.gatedloop/`, `x-gatedloop-*`, `gatedloop/<gate>`, `gatedloop.*` rule ids, `gatedloop` hook markers and a schema's `gatedloop:` flow block. A project still holding `.specloop/` is refused, and the refusal names `gates migrate-name`.
- **Dual status posting ends.** `gates marker publish` posts only `gatedloop/<gate>`.
- **The forwarder plugin is removed.** That covers `forwarder/specloop/`, its marketplace entry and its version field in `scripts/release`.
- **The earlier-name warning is removed**, and so are the doctor `name` row's read-both wording and the `rename` adoption item's earlier-name detail.
- **`gates migrate-name` stays one more release** (D7), so a late adopter can still move across. Its own removal is a later change.
- **The allow-list test shrinks** to what remains: `gates migrate-name` and its tests, the migration notes, and the archived changes.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `plugin-positioning`: the earlier name is no longer read; a project still on it is refused and pointed at the migration command.

## Impact

- `bin/gates`: the earlier-name region shrinks to `gates migrate-name`.
- `forwarder/` and `.claude-plugin/marketplace.json`.
- `scripts/release`.
- `adoption/catalog.json`.
- The read-both tests.
- README, SETUP and RELEASING's migration notes.

This repository must have run `gates migrate-name` on itself before this change lands.
