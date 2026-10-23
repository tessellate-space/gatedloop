## 1. Test scaffold

- [x] 1.1 Add a stdlib-only `unittest` module (e.g. `tests/test_manifest.py`) that
  loads `bin/harness` by path via `importlib.util.spec_from_file_location`, exposing
  `_mini_yaml`, `_load`, and `_errors` for the tests below. No new dependency.
- [x] 1.2 Document the run command (`python3 -m unittest`) in `CLAUDE.md`'s Commands
  section alongside the existing `./bin/harness` invocations.

## 2. Finding 1 — parser colon handling (red → green)

- [x] 2.1 Write a failing test: a manifest whose surface declares a block-list prose
  rule `- "Prefer composition: avoid deep inheritance"` parses (through `_mini_yaml`)
  to `rules == ["Prefer composition: avoid deep inheritance"]` with no dict element.
- [x] 2.2 Add the inline-flow variant (`rules: ["Prefer composition: avoid deep
  inheritance"]`) and, guarded on PyYAML being importable, an assertion that
  `_mini_yaml` output equals PyYAML output for that manifest.
- [x] 2.3 Add a guard test: a genuine block-list mapping item (`- name: all`) still
  parses to a mapping.
- [x] 2.4 Implement D1 in `parse_list`: replace the quote-blind `":" in rest` test
  with a "colon outside quotes" predicate (reusing `_strip_comment`'s quote-tracking
  approach) so a fully-quoted scalar item is parsed via `_scalar`. Make 2.1–2.3 pass.

## 3. Finding 2 — self-validating starter template (red → green)

- [x] 3.1 Write a failing test: the shipped `templates/harness.yaml.template`, parsed
  and passed to `_errors`, yields an empty error list.
- [x] 3.2 Implement D2: change the default surface's `rules` to a single inline-prose
  entry (self-validating; needs no rules-doc) and demote the rule-id +
  `conventions.rules-doc` form to commented guidance. Make 3.1 pass.
- [x] 3.3 Confirm the end-to-end path: `harness init` into a scratch repo followed by
  `harness validate` exits 0 (the `/specloop:harness-init` guarantee).

## 4. Cross-change note

- [x] 4.1 Record in `reposition-specloop`'s design/tasks (or its proposal's Impact)
  that it must reconcile this change's inline-prose template default with the new
  conventions source and remove the `docs/specloop-conventions.md` workaround — do
  not implement that reconciliation here.
