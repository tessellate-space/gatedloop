# gate-preconditions

## Why

A gate whose environment is down reads exactly like a gate that failed: `gates run
<gate>` returns the same red exit either way, and the real signal is buried in
connection-refused noise from the gate body (issue #12). The failure class is
second-class in the one place it matters most — an autonomous `tdd-implementer`
that hits a red `live-check` retries the gate or "investigates" the code, when the
only right move was "boot the environment first". The oracle cannot currently say
which. Adopters can (and do) prefix guard recipes onto their gate bodies, but that
keeps the distinction invisible to the shim, the ledger, and the loop.

This passes the rejection test: it makes a stated guarantee enforceable (the
oracle's verdict becomes machine-readable for one more failure class) and it binds
no stack command — `requires:` is itself just a command the adopter supplies.

## What Changes

- **Manifest**: gate values and surface `live-check` values gain an optional
  mapping form `{run: <cmd>, requires: <cmd>}`. Scalar command strings stay fully
  backward compatible (a scalar means `{run: <scalar>}` with no precondition).
  `schema/gates.schema.json` and `gates validate` accept the new shape; a mapping
  with a missing/empty `run`, an empty `requires`, or unknown keys fails loud.
- **Parsing**: `bin/gates` resolves either shape through one normalizer on both
  YAML paths. `_mini_yaml` (the PyYAML-less fallback) is extended for exactly the
  subset this needs so a mapping-form manifest can never silently degrade to a
  literal string that gets executed as a shell command (see design.md D1).
- **Run semantics**: when `requires` is declared, the shim runs it first. On
  non-zero it reports `precondition '<cmd>' failed (exit N) — gate '<gate>' was
  not run`, exits via a distinct reserved exit code, runs no gate body, writes
  **no marker**, and writes no ledger row claiming the gate was exercised — it
  writes a distinguishable precondition-failure row instead (design.md D3). The
  same semantics apply per hot surface inside `gates run live-check`.
- **Loop guidance**: `skills/tdd-apply/SKILL.md` and `agents/tdd-implementer.md`
  learn one universal rule: precondition-failed means fix the environment, never
  the code. The implementer must not retry the gate or investigate the code;
  unattended, it HALTs and reports the precondition failure verbatim.
- **Tests**: stdlib-only `unittest` coverage for the new branching Python —
  `_mini_yaml`/PyYAML agreement on the mapping form, validate accept/reject,
  run-time precondition semantics (distinct exit, no marker, ledger row shape),
  and the live-check path.
- **Docs**: `SETUP.md`'s gate contract and `templates/gates.yaml.template`
  document the mapping form and the reserved exit code.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `gate-binding`: `gates run` gains precondition semantics — a declared
  `requires` command runs before the gate body; its failure is a distinct,
  machine-readable outcome (reserved exit code, no marker, a discriminated
  ledger row) rather than a gate failure. Validation accepts the mapping form
  and rejects malformed ones loudly.
- `manifest-parsing`: the stdlib fallback parses the gate/live-check mapping
  form identically to PyYAML; a flow mapping must never silently parse as a
  string on a PyYAML-less machine.

## Impact

- `bin/gates` — normalizer for gate/live-check specs, `_mini_yaml` flow-mapping
  subset, `_errors` validation, `cmd_run` (gate and live-check branches).
- `schema/gates.schema.json` — mapping form for gate values and `live-check`.
- `skills/tdd-apply/SKILL.md`, `agents/tdd-implementer.md` — the universal
  precondition rule.
- `tests/` — new stdlib-only test module(s).
- `SETUP.md`, `templates/gates.yaml.template` — adopter-facing contract docs.
- No hook changes, no new commands, no ledger schema migration (one additive
  row shape). Fully backward compatible: every existing `.gates.yaml` keeps its
  exact behavior.

## Ordering

Independent of all sibling in-flight changes — it assumes none of them and none
of them assume it. It can land before or after any of them.

Refs: https://github.com/radub21/specloop/issues/30
