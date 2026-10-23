## 1. Characterization tasks

- [x] 1.1 Accept the `CHARACTERIZATION` file in the holding area per design D1: recorded in the handoff row, refused alongside `NO-TESTS`, and locked. Tests
- [x] 1.2 `tests check` requires a green post-placement run for a characterization task per design D2, and the missing-run message names which run it needs. Tests cover a green run allowed, a red run refused, and a mixed change of normal and characterization tasks

## 2. Defect kinds

- [x] 2.1 `tests defect --kind` per design D3: `kind` required, separate caps, the halt causes, and kind-less legacy rows counting as `assertion`. Tests
- [x] 2.2 `tests show` and `stats` report defects by kind (design D3); tests

## 3. Prompts and docs

- [x] 3.1 Update the prompts:
  - `agents/test-author.md`: when to declare `characterization`, and that a mixed task needs nothing;
  - `agents/tdd-implementer.md` and `skills/tdd-apply/SKILL.md`: the green run for characterization tasks, and choosing the defect kind (design D4).
- [x] 3.2 Update the docs:
  - SETUP: characterization tasks, defect kinds, and warm-up as `requires` (design D5);
  - `commands/gates-init.md`: the `confirm` offer mentions the warm-up.

  `python3 scripts/release docs` exits 0.

## 4. Close

- [x] 4.1 `gates run ci` green on the final tree; `openspec validate authored-test-kinds --strict` passes
