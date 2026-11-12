# Proposal: advisory-rewrite-paths

## Why

An adopter's plans rewrite end-to-end assets: Gherkin feature files, step definitions and a fixture. Each such task carries a `rewrites:` clause naming the asset. `gates validate` warns that such a path "does not look like a test path" and still passes, which is what SETUP.md promises. `gates plan check`, however, turns every oracle warning into a finding, exits 1 on any finding, and `gates plan round` refuses to open a round on the same findings. Under `loop.plan-preflight: run`, a plan that rewrites an end-to-end scenario therefore can never open a round. The only way past is to drop the clause, and with it the author's view of the file.

`plan check`'s stated purpose is to report "what the handoff would refuse". The handoff does not refuse a non-test `rewrites:` path: it checks only that the path exists at `HEAD` and that a full file is held for it. So this warning predicts nothing, and it should not block.

Rejection test: this makes a stated guarantee (validate warns without failing) hold on the plan path too. It authors no artifact and names no stack command.

## What Changes

- `gates plan check` and `gates plan round` report the "does not look like a test path" warning as an **advisory**, not a finding:
  - it is printed;
  - it does not set the exit status;
  - it does not stop a round from opening.
- `plan check --json` gains `advisories: [{kind, task, path, detail}]` with kind `rewrite-not-test-path`.
- Every other oracle warning stays a finding, unchanged:
  - a path absent from the working tree;
  - a tag on an unparsed task line.
- `gates validate` is unchanged.

Widening the heuristic itself (to `features/`, `steps/`, `fixtures/`, or to the paths a gate-owning surface covers) is left out. It needs its own decision, and with the warning advisory it no longer blocks anyone.

## Capabilities

### Modified Capabilities

- `plan-preflight`: plan checks report what the handoff would refuse, and only that blocks.

## Impact

- `bin/gates`: `_plan_check_findings`, `_plan_check_doc`, `_plan_check` and `_plan_round`.
- `tests/test_plan_preflight_check.py`: two existing tests are rewritten. One pins the old exit 1; the other pins the JSON key set.
- `SETUP.md`: the `plan check` prose and its JSON shape, the `plan round` paragraph, and the command reference.
- Ships as a patch release (0.12.2), or with 0.13.0 if that is cut first.
