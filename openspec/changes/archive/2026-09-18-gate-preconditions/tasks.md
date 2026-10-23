# gate-preconditions — tasks

## 1. Parsing and normalization

- [x] 1.1 Extend `_scalar` in `bin/gates` to parse a single-level inline flow
  mapping with scalar values (top-level-comma split, quote-aware; first
  unquoted colon per entry), failing loudly on the unsupported subset (nested
  flow structures); verify with new unittest cases showing `_mini_yaml` and
  PyYAML produce identical structures for block and flow forms, including
  quoted values containing commas and colons (design D1).
- [x] 1.2 Add the `_gate_spec(value) -> (run, requires)` normalizer (scalar →
  `(value, None)`, mapping → `(run, requires)`) and route `cmd_run` (named-gate
  and live-check branches) and `cmd_surfaces`' live-check display through it;
  verify existing tests still pass and a mapping-form gate prints/runs its
  `run` command (design D2).

## 2. Validation and schema

- [x] 2.1 Extend `_errors` in `bin/gates`: accept the mapping form for gate and
  `live-check` values (`run` required non-empty string, `requires` optional
  non-empty string, unknown keys rejected naming gate/surface and key) and
  reject any string gate/live-check value beginning with `{` as an unparsed
  mapping; verify with unittest accept/reject cases and `./bin/gates validate`
  on this repo's manifest staying green (design D1/D2).
- [x] 2.2 Update `schema/gates.schema.json` so gate values and `live-check`
  are `oneOf` string or `{run, requires}` with `additionalProperties: false`;
  verify the JSON is valid and `./bin/gates run ci` is green (design D6).

## 3. Run semantics

- [x] 3.1 Implement the precondition path in `cmd_run` for named gates: run
  `requires` first; on non-zero print `specloop: precondition '<cmd>' failed
  (exit N) — gate '<gate>' was not run` to stderr, skip the gate body, write no
  marker, append the discriminated ledger row (`exit: 75`,
  `outcome: "precondition-failed"`, `precondition`, `precondition_exit`,
  `tree: null`), and return 75; verify with unittests asserting exit code,
  marker absence, and ledger row shape, plus an untouched-scalar regression
  case (design D3).
- [x] 3.2 Implement the precondition path in the `live-check` branch: normalize
  each hot surface's spec, run all declared `requires` first; on any failure
  report each failed precondition, run no probe bodies, write no marker, append
  one discriminated `live-check` ledger row, exit 75; when all pass, probe
  execution is unchanged; verify with unittests for the fail and pass paths
  (design D4).
- [x] 3.3 Extend the ledger comment block in `bin/gates` to document the
  precondition-failure row shape and the reserved exit 75; verify
  `python3 -m unittest discover -s tests` is green and taint-resolution tests
  still pass (a precondition row can never resolve a taint) (design D3).

## 4. Loop guidance

- [x] 4.1 Add the universal rule to `skills/tdd-apply/SKILL.md`: exit 75 /
  precondition-failed means the environment was absent — fix or boot the
  environment, never the code; never retry the gate unchanged or read the
  report as a test failure; surface it to the user as an environment problem;
  verify the prompt names no stack command (stack-agnostic-prompts) via
  convention review (design D5).
- [x] 4.2 Add the same rule to `agents/tdd-implementer.md` with the unattended
  behavior: HALT at the task boundary with a clean tree and report the shim's
  precondition message verbatim; verify wording matches the skill's rule and
  convention review is clean (design D5).

## 5. Adopter-facing docs

- [x] 5.1 Document the mapping form, the reserved exit code 75, and the
  fast-probe guidance in `SETUP.md`'s gate contract; verify the examples match
  the issue's shape and validate against the new schema (design D3 risk notes).
- [x] 5.2 Add a commented mapping-form example to
  `templates/gates.yaml.template`; verify the fresh template still validates
  via the existing template unittest (design D6).
