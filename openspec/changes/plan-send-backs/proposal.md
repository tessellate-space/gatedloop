# Proposal

## Why

The ledger says why a lane stops (`halt` rows carry a cause from a closed set) and what the plan loop's checkers found (`plan-review` rows), but nothing structured about why a human or a reviewing session sends a plan back before approval. A resume's reason is the planner's paraphrase in free text, with no sender and no class, and requested changes on a plan PR, an answer that changes direction, or a defect a non-checker reviewer found leave no row at all. So `gates stats` cannot say why plans come back, who sends them back, or which kinds recur. Each send-back costs human attention, and a recurring kind points at the lens check, convention or template that would prevent it (issue #218). This is the planning-stage counterpart of the escalation record.

It passes the rejection test as "makes a stated guarantee enforceable": the guarantee that plan-stage rework is counted by category, never narrated. It authors no artifact and names no stack command.

## What Changes

- **A `plan-returned` ledger row**, a new record-only row kind written by the shim. It carries `by` (`human` or `reviewer`), the send-back's class from a closed set (`scope`, `approach`, `spec-gap`, `decision`, `collision`, `drift`, `safety`, `nit`, `other`), the sender's exact `words`, an optional `ref` (a PR or comment URL), `detail` (required for `other`), and the plan's `plan_sha` and `tasks_sha` at the time. A class or sender outside its set, empty words, or `other` without detail is refused, and nothing is written.
- **`gates plan returned <change> --by <who> --class <class> (--words <text> | --words-file <path>) [--ref <ref>] [--detail <text>]`** writes the row, on any branch and whether or not the plan loop runs. `--words-file` carries text a shell argument would alter, and is what the prompts use.
- **`gates plan resume` can record the send-back it answers.** Given `--by`, `--class` and the words (with the optional `--ref` and `--detail`), it validates them first and then writes the `plan-returned` row before its `resume` row. Without them it behaves exactly as today.
- **`gates plan status` lists the send-backs** beside the loops: sender, class, ref, the words and the plan digest they were said about. The loop's state is computed as before.
- **`gates stats --plans`**: per change, send-backs by sender and by class (every class listed, zeros included), the plan loop's own returns by checker (its `findings` and `question` verdicts), and resumes; with `--all`, the aggregate and a per-month trend. One JSON document under `--json`; malformed rows are disclosed, never zeroed.
- **The existing views are unchanged.** `gates stats`, `gates stats --outcomes`, the plan loop's round counting and every approval, handoff and merge check ignore `plan-returned` rows.
- **Opt-in for the prompts.** A new manifest key, `loop.plan-returns` (`record` or `skip`, default `skip`), decides whether `/gatedloop:propose` and `/gatedloop:planner` record send-backs. `gates plan check --json` reports it as `returns`, and `/gatedloop:upgrade` offers it. The command and the stats view work under either value.

## Capabilities

### New Capabilities

- `plan-returns`: the record of why a plan goes back to its author before approval: the row, its closed sets and their validation, the writer, the resume feed, its place in the plan status, and the opt-in key that has the shipped prompts record it.

### Modified Capabilities

- `gate-economics`: adds the `gates stats --plans` view, and states that the existing views ignore send-back rows.
- `upgrade-adoption`: the catalogue gains a `plan-returns` item.

## Impact

- `bin/gates`: the row kind, the closed sets and their validation, `plan returned`, the new `plan resume` flags, the status section, `stats --plans`, the `loop.plan-returns` key and its validation, and three new ledger fields (`by`, `words`, `ref`).
- `schema/gates.schema.json`, `adoption/catalog.json`, `tests/contract.json`, `tests/parser-structure.json`.
- `commands/propose.md` and `commands/planner.md`: record a send-back under `loop.plan-returns: record`.
- README.md, SETUP.md, `docs/status.md` and `docs/candidates.md`.
- Overlaps with in-flight changes: `approved-tests` and `review-provenance` also append ledger fields (to `LEDGER_ROW_FIELDS` and the exact field sets pinned in `tests/test_ledger.py`, `tests/test_task_baseline.py`, `tests/test_review_record.py` and `tests/test_audit.py`), `review-provenance` also adds a catalogue item and a `loop` key, and `approved-tests` also edits `commands/propose.md` and `commands/planner.md`. Whichever merges second appends after the other, under the union rule.
