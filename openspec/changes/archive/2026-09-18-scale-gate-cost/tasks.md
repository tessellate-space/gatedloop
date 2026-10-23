# Tasks: scale-gate-cost

## 1. Scoped-oracle selection (design D1)

- [x] 1.1 Red: selection tests — single hot surface with override → scoped; plus
      catch-all surface still → scoped (catch-all ignored); two non-catch-all hot
      surfaces → global; hot surface without override → global; unmatched changed
      file → global; no staged diff → global
- [x] 1.2 Schema + validate: optional `surfaces[].gates` (`ci`/`unit` string
      commands); validate rejects overrides naming undeclared gates and notes the
      catch-all exclusion rule
- [x] 1.3 Implement selection in `gates run ci|unit`, reusing the existing hot-set
      computation; announce which oracle was chosen and why in the run's summary line

## 2. Scope recording and the full-ci merge requirement (design D2)

- [x] 2.1 Red: marker payload and ledger row carry `scope` (`full` | surface name);
      `discipline check-commit` accepts a fresh scoped marker for the staged tree
- [x] 2.2 Red: completion path refuses a head whose only green `ci` is scoped; passes
      with `scope: full`
- [x] 2.3 Implement scope in marker write/read and ledger append; wire the completion
      check; update `AUTOMATION.md`'s guarantee table (scoped = per-commit locality,
      full = pre-merge truth)

## 3. Quiet-on-green output (design D3)

- [x] 3.1 Red: green run prints exactly one summary line (gate, scope, duration,
      output path) and saves full output under `.specloop/out/`; red run dumps full
      output to stderr and preserves the exit code; `--verbose` streams
- [x] 3.2 Implement capture + rotation (keep last N per gate); exit-code contract
      untouched
- [x] 3.3 Remove any `| tail` guidance workarounds from shipped prompts; the summary
      line is now the default surface

## 4. Review delegation mandate (design D4)

- [x] 4.1 `skills/tdd-apply/SKILL.md`: convention review MUST run as the
      `convention-review` subagent, verdict recorded via `gates review record`; inline
      review named as the anti-pattern with #13's cost as the reason
- [x] 4.2 `agents/tdd-implementer.md`: same mandate in the agent's own loop
      description

## 5. Docs and deferrals

- [x] 5.1 `SETUP.md`: the scoped-oracle contract — manifest shape, the err-full
      selection rule, catch-all exclusion, and "the merge always needs full ci"
- [x] 5.2 `docs/candidates.md`: task batching (#13 suggestion 3) with the reasons to
      wait (done ⟺ committed; axis B; shrinking benefit)
- [x] 5.3 Release note: opt-in; no-override manifests behave exactly as before
