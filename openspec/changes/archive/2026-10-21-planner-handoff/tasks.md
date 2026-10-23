## 1. Attest from a merge

- [x] 1.1 `gates approval attest <change> --merged <pr>` per design D1, D2 and D4. Tests use the fake-`gh` fixture and a bare remote, and cover:
  - the keys written, with the sha computed over the merge commit's plan;
  - `check-implement` accepting the result;
  - every D2 refusal;
  - `review` naming `--pr`.

## 2. The record job

- [x] 2.1 The `plan/<change>` branch in `cmd_record_merged` per design D3. Tests cover:
  - a self-policy plan PR, giving one commit with the keys and no push;
  - an already-approved change;
  - the `review` policy;
  - a `plan/` head naming no active change;
  - the existing change-PR path unchanged.

## 3. Handoff

- [x] 3.1 `gates handoff <change> [--json]` per design D5. Tests cover:
  - an approved plan on the target, with the full payload;
  - a plan only on a branch;
  - a stale approval sha;
  - the plain-text form;
  - that nothing is written.

## 4. Docs

- [x] 4.1 Docs:
  - SETUP's approval section: the merge path, when it applies (`self`, pull-request mode), and that `--local` is unchanged;
  - SETUP and README: `gates handoff`;
  - `docs/running-at-scale.md`: "Planners and one orchestrator" per design D6, including the plan-check job example.

  `python3 scripts/release docs` exits 0.

## 5. Close

- [x] 5.1 `gates run ci` green on the final tree; `openspec validate planner-handoff --strict` passes
