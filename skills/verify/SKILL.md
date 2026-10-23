---
name: verify
description: Pre-archive gate — checks spec→acceptance coverage, then runs the project's acceptance suite via `gates run verify`. Reports all gaps at once; a change is not archive-ready until coverage is complete and the suite is green.
argument-hint: "[change-name]"
---

# Verify

Pre-archive gate. Runs its layers unconditionally and reports every gap at once. A change is not ready to archive until spec coverage is complete and the acceptance suite passes.

**Stack independence**: the executable layer runs through `gates run verify` — the project's `.gates.yaml` decides what that is (a BDD suite, contract tests, whatever). This skill never names a test runner.

**Input**: Optional change name. If omitted, auto-select via `openspec list --json` or prompt with **AskUserQuestion**.

---

## Layer 1: Spec → acceptance coverage
**Goal**: every `#### Scenario:` in the change's specs is represented by an acceptance scenario in the project's acceptance artifacts (e.g. `features/`).

1. Run `gates acceptance brief <name>` and read its coverage list. The match rule lives in the shim, not here: every `#### Scenario:` in the change's specs, per capability, marked `covered` when a same-titled acceptance scenario exists in the files the manifest's `acceptance.match` glob names, else `check by hand`. When `acceptance.match` is not declared the brief says so and marks every scenario `check by hand` — report that as the reason, not as N separate gaps.
2. Do not re-derive the list yourself (no searching spec or acceptance files by hand); the brief is the one deterministic answer, and a second reading could disagree with it.

Report per capability: `✓ covered` or `✗ N missing:` with the scenario names the brief marks `check by hand`.

## Layer 2: Acceptance suite
**Goal**: the declared acceptance suite passes.

```bash
gates run verify
```
- If the `verify` gate is not declared in `.gates.yaml`, note "no verify gate declared — coverage-only" and stop after Layer 1 (not a failure).
- Otherwise report pass/fail per scenario from the suite output.

---

## Final Verdict
Show after all layers, always. On success:
```
  Verification passed ✓
  Layer 1: Spec coverage    ✓  all scenarios represented
  Layer 2: Acceptance suite ✓  N scenarios passed
  Ready to archive — run /gatedloop:archive
```
On any failure, list which layer failed and the concrete next step; do NOT suggest `/gatedloop:archive`.

## Guardrails
- All layers always run — never stop at first failure (except the "no verify gate" coverage-only case).
- The verify skill reports; it does not fix. Direct fixes to the implementer.
- If no acceptance location is declared, or it matches no file, Layer 1 reports it clearly (the brief states which) rather than crashing.
