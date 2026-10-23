# Tasks: expand-brace-globs

## 1. The expander (design D2)

- [x] 1.1 Red: unit tests for expansion — no braces (pass-through), single group,
      multiple groups, nested groups, unbalanced `{` (error), empty group / empty
      alternative (error), expansion cap exceeded (error)
- [x] 1.2 Implement the recursive expander in `bin/gates`, stdlib-only, errors carrying
      the offending pattern text

## 2. Load-time integration (design D1, D3)

- [x] 2.1 Red: selection tests — a surface with `match: "{bin,tests}/**"` goes hot for
      a file under either directory; `gates rules` returns its rules (fixture mirrors
      this repo's own `.gates.yaml` shapes)
- [x] 2.2 Expand patterns where surfaces are loaded; `_matches` receives only
      brace-free patterns; loader raises the named error on an invalid pattern instead
      of degrading to empty selection
- [x] 2.3 `gates validate` runs the expander over every `match`, collecting all
      failures and naming surface + pattern (existing all-errors-at-once style)

## 3. Prove it on this repo

- [x] 3.1 `./bin/gates surfaces` and `./bin/gates rules` on a diff touching
      `bin/gates` and a prompt file report the `shim` and `prompts` surfaces hot with
      their rule-ids — the exact selection issue #1 observed returning empty
- [x] 3.2 Release note: previously-dead brace patterns now select (err-hot direction);
      supported subset and rejection rules stated
