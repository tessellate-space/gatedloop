# Design

## Context

See proposal.md for the motivation. The relevant current state in `bin/gates`:

- `_tests_defect` validates `--kind` and a non-empty `--detail`, applies the per-kind caps (`MAX_TEST_DEFECTS_BY_KIND`) and appends a `test-defect` row. Past the `assertion` cap, its refusal quotes the earlier defects' details only.
- A handoff row (`TESTS_HANDOFF_EVENT`) records each task's held tests as `{path: blob}`; `_authoring_state` folds them, a `--task` handoff replacing that task's entry. So "did the held tests change since the previous handoff" is a blob comparison the shim can already make.
- `gates tests check` already locates a task's latest placement and the first run of its oracle gate after it (the red-after-placement check). The `green` evidence check reuses that lookup, asking for a passing run instead.
- The author's defence exists only in its report to the dispatcher (`agents/test-author.md`, re-dispatch paragraph).

## Goals / Non-Goals

**Goals:**

- Neither side of a dispute can make a claim the shim cannot resolve.
- The ledger holds the whole exchange, so a human reading a halt sees both positions.

**Non-Goals:**

- Judging whether a citation supports the claim. The shim checks that the cited evidence exists, not that it proves the point. That judgement stays with the other agent and, past the cap, the human.
- Changing the caps or the halt causes.
- Citations on authored-set review findings (the convention review's findings already cite a rule-id).

## Decisions

**D1. Three citation forms, resolved against the change branch's worktree.** `path` and `path:line` (`path:a-b` for a range) resolve when the file exists in the worktree, including the holding area `.gatedloop/authored/<change>/`, and the line or range is within it. `spec:<capability>#<scenario>` resolves when a `#### Scenario: <scenario>` exists under that capability in the change's delta specs or in `openspec/specs/`, matched case-insensitively with whitespace collapsed. Alternatives considered: free-form URLs (unresolvable offline, rejected) and symbol names (would need a language-aware index, against `zero-dep-shim` and `stack-agnostic-prompts`, rejected; `path:line` covers a symbol).

**D2. `--cite` is repeatable and required for `setup` and `assertion`, not for `green`.** A `green` defect's claim is a fact about a run, and the run is in the ledger, so the shim checks the run instead of asking the agent to point at it. That is stronger evidence than any citation.

**D3. The defence is a flag on `tests handoff`, not a new subcommand.** A defence already is a handoff of unchanged tests (`agents/test-author.md`), so `--defend` makes that existing act carry its reason. The shim refuses `--defend` when the task's held blobs differ from its entry in the previous handoff state, or when no `test-defect` row for the task follows its previous handoff. The `test-defence` row is written next to the handoff row, in the same call.

**D4. Show and the cap refusal read the exchange from the ledger in order.** Defects and defences for a task are interleaved by ledger order, so a reader sees "defect, defence, defect" as it happened.

**D5. Default-on, keyed on the handoff row.** New handoff rows carry `"disputes": "cited"`. The checks in D1–D3 apply when the task's governing handoff row has it, so a change handed off before the upgrade keeps the old rules until its next full handoff. Alternative considered: a manifest key. Rejected because the checks only constrain the plugin's own agents, adopters configure nothing, and a key would offer a way to switch off a guarantee the loop already claims. This needs the maintainer's approval, because the standing rule is that new adopter-facing behaviour is opt-in unless the plan says otherwise. The plan PR asks for it.

**D6. The names the tests pin.** Every task's tests are written before any of it is implemented, so these are fixed here:

- The resolver is `unresolved_citations(root: Path, change: str, citations: list[str]) -> list[str]`, module-level in `bin/gates`. It returns the citations that do not resolve, in input order, and an empty list when all do. `root` is the worktree root; the holding area it searches is `.gatedloop/authored/<change>/`.
- Two ledger fields are appended to `LEDGER_ROW_FIELDS` after `v`, in this order, per the union rule: `disputes` (`"cited"` on a `tests-handoff` row written by this shim; `None` on every other row) and `cites` (the list of citations, as given, on `test-defect` and `test-defence` rows; `None` on every other row, and on a `green` defect). The row version stays 1.
- The defence row has `gate: "test-defence"` (a constant beside `TEST_DEFECT_EVENT`, and in `NON_GATE_EVENTS`), the task in `task`, the `--defend` reason in `detail` and its citations in `cites`. It is appended directly after the handoff row of the same call.
- `--defend` requires `--task`, at least one `--cite`, and no `--dry-run` (a dry run records nothing, so it cannot record a defence); `--cite` without `--defend` on `tests handoff` is refused. Each refusal exits 1 and writes nothing.
- `gates tests show --json` keeps every existing key and each `defect_log` entry's shape. It adds one top-level key, `exchanges`: `{task: [entry, ...]}` in ledger order, each entry `{"event": "test-defect" | "test-defence", "kind": <defect kind, or None for a defence>, "detail": ..., "cites": [...]}` (`[]` when the row has none). The text form prints each defect's citations on the line after it, and each defence as `defence: <detail>` with its citations, in the same order.
- The refusal past the `assertion` cap keeps its current wording (the halt command, `oracle-conflict`) and replaces the `; `-joined details with one line per `test-defect` and `test-defence` row for the task, in ledger order: `  defect <n> (<kind>): <detail>` or `  defence: <detail>`, each followed by `    cites: <c1>, <c2>` when the row has citations. Each `detail` appears verbatim.
- The passing-run check of D2 is keyed on the governing handoff like the citation checks (D5): under a handoff without `disputes`, a `green` defect is recorded as before.

**D7. Each task regenerates the contract it changes.** `tests/test_contract.py` fails `ci` on any difference between the code and `tests/contract.json`, and `ci` runs before every commit. So the task that changes the public surface rewrites the snapshot (`python3 tests/test_contract.py --write`) in its own commit: 1.2 (`--cite` on `tests defect`, the `disputes` and `cites` fields) and 3.1 (`--defend` and `--cite` on `tests handoff`). 1.1, 2.1 and 3.2 add no flag, field or document key the snapshot records. The same holds for existing tests that pin what a task changes: the task declares each under `rewrites:` on its oracle tag, so its author can read and rewrite it. Stamping `disputes` on every new handoff makes every existing test that records a `setup` or `assertion` defect after a real handoff need a `--cite`, and the passing-run check makes every existing test that records a `green` defect need a passing run first. Each such file is rewritten by the first task whose code breaks it, and that rewrite already holds under the later tasks' rules, so no file is rewritten twice.

## Risks / Trade-offs

- [Agents cite something trivially resolvable, such as the test file itself, to get past the check] → Accepted. The check only removes the evidence-free claim. Whether a citation is to the point is still judged by the other side, and the cap still brings in a human. The prompts say what a useful citation is.
- [A spec scenario renamed mid-change breaks a recorded citation] → Citations are resolved once, when recorded. A later rename does not invalidate a row.
- [More refusals mean more halts in unattended runs] → A refusal is immediate and names the fix (add `--cite`). It costs a retry, not a halt.

## Migration Plan

None beyond D5: in-flight changes keep the old rules. Rollback is reverting the change; the new row kind and fields are extra data in the ledger.
