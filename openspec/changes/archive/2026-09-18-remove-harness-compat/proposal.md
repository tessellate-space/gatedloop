## Why

`rename-to-gates` shipped `bin/harness` → `bin/gates` with a bounded, one-release
compatibility path (design D3): `bin/harness` forwards to `bin/gates` with a
deprecation notice, and the loader accepts a legacy `.harness.yaml` filename or
`harnessVersion` key with a loud warning. That path exists on purpose to avoid a
silent break — but an unbounded shim is exactly how the original `harness` name
survived long enough to become a three-way collision in the first place (see
`rename-to-gates` proposal.md). This change is the named follow-up that was opened
at the same time as the rename (task 4.3), so the expiry is a tracked change rather
than a memory. It should land once one release has shipped with the forwarder in
place, per the "one release" bound in the original design.

## What Changes

- **Delete `bin/harness`.** The forwarder is removed outright — invoking it becomes
  a plain `command not found`, no different from any other renamed binary.
- **Remove the legacy manifest fallback from `bin/gates`.** The loader stops
  recognizing `.harness.yaml` / `.harness.yml` / `.harness.json` as manifest
  filenames, and stops accepting a `harnessVersion` key in place of `gatesVersion`.
  A project that never migrated now fails with the same `no manifest found` /
  `gatesVersion must be 1` errors it would get for any other malformed manifest —
  loud, per `fail-loud-gates`, just no longer a special-cased warning.
- **Retire the compatibility requirements from the `gate-binding` spec.** The two
  "old name keeps working for one release" requirements are marked REMOVED; the
  "gate-binding seam is named for what it binds" requirement stands as-is.
- **Update the migration notes** in `README.md`/`SETUP.md`/`CLAUDE.md` that
  describe the forwarder and the fallback, since neither exists anymore.

## Capabilities

### Modified Capabilities
- `gate-binding`: the compatibility requirements are removed; the naming
  requirement is unchanged.

## Impact

- **Files removed**: `bin/harness`.
- **Files modified**: `bin/gates` (loader simplification), `README.md`, `SETUP.md`,
  `CLAUDE.md` (migration-note removal), `openspec/specs/gate-binding/spec.md` (via
  archive of this change's delta).
- **BREAKING for any adopter still on the old name.** By the time this lands, the
  one-release warning window (from `rename-to-gates`) has already told every such
  adopter exactly what to rename. This change is what makes that warning's
  deadline real.

## Non-goals

- Any further renaming. `gates`/`.gates.yaml` are the permanent names; this change
  only removes the migration scaffolding around their introduction.
