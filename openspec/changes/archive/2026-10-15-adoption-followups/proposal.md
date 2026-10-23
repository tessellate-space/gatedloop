# Proposal

## Why

Two 0.5.0 changes added something an adopter who is upgrading has to decide or act on.
Both deferred their upgrade prompt until `adoption-prompts` landed:

- **`lock-and-ledger-hygiene` changed the git `pre-commit` template.** It now runs the same
  `gates discipline check-commit` as the tool-level hook. A repo that took the direct
  install (no hook manager) has a *copy* of the old template under `.git/hooks/`, and
  it keeps that copy forever. Worse, `gates hook install` sees the copy, reports
  "already installed — nothing to do", and leaves the stale body in place. So the
  `/specloop:upgrade` action the design names (re-run the hook-install step) would do
  nothing today. A composed install (husky, or a hand-wired snippet) delegates to the
  shipped template at run time and is never stale.
- **`merge-step` added the optional `confirm` gate.** A project that binds a
  live-check should be asked whether it wants a post-merge smoke check before the push.

A second gap shows up once a hook-refresh item exists. Under the current rules an
`adopted` decision applies forever. A refresh is not a one-time choice, though: the
next release that changes the template needs the same act again, and a recorded
`adopted` from 0.5.0 would hide it.

## What Changes

- **A recurring item kind.** A catalogue item may set `"recurs": true`. For such an
  item the detector alone decides whether the project has acted, so an `adopted`
  record is ignored. A `declined` record applies only at the version it was recorded
  at, the way `later` already does.
- **A new detector kind, `git-hook-current`.** The project has acted when:
  - no direct copy of the template is installed; or
  - the installed copy's body equals the shipped template.
  A composed snippet always counts as current.
- **A new predicate kind, `git-hook-copy`.** It holds when the hook path holds a
  direct copy of a Specloop template.
- **`gates hook install` refreshes a stale direct copy.** When the hook path holds a
  direct copy whose body differs from the shipped template, it saves the old body to
  `pre-commit.specloop-prev` beside it, writes the current template, and says so. A
  foreign hook is still never overwritten, and neither is any hook-manager config.
- **`gates doctor`** reports a stale direct copy as a warning, naming the remedy.
- **Two catalogue items, both `since: 0.5.0`:**
  - `git-hook-refresh`: recurring, detector `git-hook-current`, applies when
    `git-hook-copy` holds, and its action runs `gates hook install`;
  - `confirm-gate`: detector `manifest-key gates.confirm`, applies when `surface-key
    live-check` holds, and its action binds the gate through `gates-init`'s confirm
    offer. The `merge-step` design said `gates.live-check`, which is not a manifest
    key; live-checks are declared per surface. This is the same correction specloop PR 103 made
    for `runner-strictness`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `upgrade-adoption`: the closed detector/predicate sets grow by one kind each;
  recurring items change how a recorded decision applies.
- `loop-enforcement`: the no-clobber hook installer may replace its own stale direct
  copy, keeping the previous body.

## Impact

- `bin/gates`:
  - adoption detector, predicate and decision-application code;
  - `_hook_install`;
  - `_hook_state` / `doctor_checks`.
- `adoption/catalog.json`: two items.
- `commands/upgrade.md`: a recurring item is offered again after a declined record
  from an older version; one sentence.
- `SETUP.md`, `README.md`: the upgrade section mentions the refresh;
  `RELEASING.md`: a template change needs no new item (the recurring item covers it).
- Tests: `tests/` for each kind, the decision rule and the installer.
