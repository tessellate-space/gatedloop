# Design: advisory-rewrite-paths

## Context

`_task_oracle_problems` returns `(errs, warns)` for every change. Its three kinds of warning are:

1. a `rewrites:` path absent from the working tree;
2. a `rewrites:` path that `_is_test_path` does not recognise;
3. a tag on a task line the parser does not read.

`_plan_check_findings` (bin/gates ~8734) turns every warning into an `oracle-warning` finding. `_plan_check` exits 1 on any finding, and `_plan_round` refuses to open a round on any finding.

## Decisions

### D1. Only the test-path warning becomes advisory

- **The split.** `_plan_check_findings` returns `(findings, advisories)`. A warning that ends with "does not look like a test path — the test author will read its content" becomes an advisory with kind `rewrite-not-test-path`, carrying the same task, path and detail. It is matched on that fixed suffix of the message `_task_oracle_problems` emits.
- **Why the other two stay findings.** Warning 1 predicts the `rewrite-absent` refusal once the path is also absent at `HEAD`. Warning 3 means a tag is silently ignored. Both are plan defects.
- **Why not widen `_is_test_path`.** Widening it would still leave other unusual paths blocked. The warning's message already says what it means: the author will read the file. Nothing is refused.

### D2. Output

- **`gates plan check`**
  - Text: each advisory is printed as `advisory: <task> <path>: <detail>` after the findings. The exit status depends on findings only. With advisories and no findings, it prints the advisories followed by the usual "is clean" line.
  - JSON: the document gains `advisories` (a list, possibly empty), in the same shape as `findings`. No existing key changes.
- **`gates plan round`** prints each advisory to stdout as `advisory: <task> <path>: <detail>`, matching `plan check`. Advisories come after any findings and are printed whether or not the round opens. The round opens when there are no findings.

The new key is additive. `plan check --json` is not a pinned contract document, so `tests/contract.json` is unchanged.
