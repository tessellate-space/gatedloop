# Proposal

## Why

The 2026-10-22 competitive survey put multi-host reach at the top of what every comparable tool has and this plugin lacks. The honest position is narrower than "Claude Code only" and the documentation does not say it: the shim, the manifest and the ledger already run on any host, and the git layer is where enforcement could hold anywhere. Today it does not. The git `pre-commit` hook is inert unless `CLAUDECODE` is set, so an agent on any other host commits ungated, and there is no git-layer equivalent of the merge gate at all: a raw merge into the target followed by a push reaches the shared history with no check on any host. The plugin's strongest claim, that every gate is enforced in code, is true on one host and for one of two actions.

## What Changes

- **Agent sessions are declared, not hard-coded.** `discipline.agent-env` in `.gates.yaml` lists the environment variables whose presence marks an agent session; default `[CLAUDECODE]`. The git-layer hooks enforce when any is set and stay a transparent no-op otherwise. An adopter running another host adds that host's variable; the prompts never name one.
- **A `pre-push` hook gates the merge target.** A push that updates the merge target's ref is denied unless the pushed commit is proven: a `merge` ledger row recording that commit (what `gates merge` writes), or the same incoming-tree checks the merge gate makes, evaluated against the pushed tree. Pushes of other branches, deletions and pushes outside an agent session are untouched. `gates merge`'s own final push passes by construction.
- **Install and diagnose both hooks.** `gates hook install` installs `pre-push` beside `pre-commit` through the same owner detection and composition rules; the installed hooks record the shim's path as a last fallback so they resolve the shim outside a plugin environment. `gates doctor` gains a `git-push-hook` row. The recurring hook-refresh adoption item covers both hooks, and one new item offers the push hook to projects that already have the commit hook.
- **The layers are documented per host.** AUTOMATION.md states, in one table, which guarantee holds at the tool-hook layer (Claude Code), the git layer (any host), and the forge (any forge with statuses), and the README's requirements say which hosts run which layer.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `loop-enforcement`: git-layer scoping is declared through `discipline.agent-env`; a push to the merge target is gated at the git layer; both hooks install through one path; coverage per layer and host is documented.

## Impact

- `bin/gates`: `discipline agent-session`, `discipline check-push`, `hook install` for two hooks, `doctor` row, schema key.
- `templates/git-hooks/pre-commit`, new `templates/git-hooks/pre-push`.
- `schema/gates.schema.json`: `discipline.agent-env`.
- `adoption/catalog.json`: the refresh item's detector and one new item.
- `commands/gates-init.md`: the offer covers both hooks.
- AUTOMATION.md, SETUP.md, README.md; tests.

Rejection test: authors nothing; names no stack command (an environment variable name in the manifest is the adopter's binding); makes two stated guarantees enforceable where they are not today: on any host, and at the push that shares history.
