# Proposal

## Why

The test author is the first agent that reads a plan against the real code, and it runs only after the plan is approved. Every gap it finds then costs a halted lane, a plan amendment and a second approval. #168 reports this from tessellate-space under 0.11.1: of 24 plan PRs merged on 2026-11-05 and 2026-11-06, 20 were amendments made after approval. The causes were handoff refusals and failed test-quality reviews, plans that were wrong about the code, a task order that deadlocked, and plans that drifted while they waited to be handed off. Nothing in the propose path checks a plan before a person approves it. The shim already refuses most of the specific defects, but only at handoff, after approval.

## What Changes

- **A preflight holding area outside the tree.** `.gatedloop/out/preflight/<change>/` has the real holding area's layout and is git-ignored, because `.gatedloop/out/` ignores itself. `gates tests brief <change> --preflight` creates it and prints it as the place to write. A preflight never reads or writes the tracked `.gatedloop/authored/<change>/`.
- **`gates tests handoff <change> --dry-run`.** Runs every refusal a real handoff runs against the preflight holding area, prints the same messages and exits the same way. It writes nothing: no ledger row and no git object. It does not compare tags with the merge target, because a preflight runs on the plan that is being amended. Neither `gates tests brief` nor `gates tests handoff` requires an approval today, so a dry run works on an unapproved plan as it is.
- **`gates tests show <change> --preflight`** (also with `--json` and `--diff`). Reads the preflight holding area instead of the ledger, so the authored-set review can run when there is no handoff. A rewrite's diff is taken against the file at `HEAD`.
- **`gates plan check <change> [--against <ref>] [--json]`.** A new command with static checks the shim can make deterministically. It exits 1 and names every finding. Initial checks:
  - the change's own oracle-tag errors and warnings that `gates validate` reports, scoped to this change;
  - under `loop.task-oracle: required`, every untagged task (the handoff refuses these);
  - a `rewrites:` path that does not exist at the base. When an earlier task of the same change names that path, the finding says that the earlier task creates the file, so the later task holds the full file without the clause;
  - with `--against <ref>`, each file the plan names (in task lines, `rewrites:` clauses and `design.md`) that changed between the plan's base and `<ref>`, with the kind of change (modified, deleted or renamed). This is the drift re-check at handoff. Existence checks then run at `<ref>`.
- **The propose path runs a preflight before a plan PR opens or updates.** `/gatedloop:propose` always runs `gates plan check`. When the project declares `loop.plan-preflight: run`, it also dispatches the test author in preflight mode, runs `gates tests handoff --dry-run`, runs the convention review in authored-set mode over `--preflight`, and then deletes the preflight holding area. Findings go back to the planner, who amends the plan before asking for approval. The PR body carries a one-line preflight summary. Nothing is recorded.
- **`loop.plan-preflight: run | skip`**, defaulting to `skip`. `gates validate` refuses `run` together with `loop.test-author: inline`. The values are not `on`/`off`, because a YAML 1.1 parser reads those as booleans while `_mini_yaml` reads them as strings.
- **Held tests are never committed off a change branch.** `gates tests check` (run by both commit hooks) refuses a staged path under `.gatedloop/authored/` whenever the branch resolves to no active change: a `plan/*` branch, the merge target, or any other such branch. Today it passes there, because it finds no change to check. This is the fail-loud backstop for the preflight area. It needs no change to either hook script.
- **Prompts.** `agents/test-author.md` gains a preflight mode: it writes into the preflight holding area, ends with `--dry-run` instead of a handoff, records nothing, and returns order problems as blocking questions. `agents/convention-review.md` reads `--preflight` in a preflight. `commands/propose.md` gains the preflight step. `commands/planner.md` explicitly permits the planner to dispatch the test author and the authored-set review in preflight mode only. They work against the planner's own plan branch, record no handoff and discard the holding area. The planner also runs `gates plan check --against <target>` before `gates handoff`.
- **One adoption item**, `plan-preflight` (`since: 0.12.0`), asks whether to run the preflight.

**No guarantee moves.** Approval, attestation, `gates handoff`, the real `gates tests handoff`, the lock and `gates merge` are unchanged. The preflight advises the planner and records nothing. After approval the real test author runs again, from scratch.

Against the rejection test: it authors no artifact and names no stack command. It makes a stated guarantee (an approved plan is one the loop can implement) checkable before approval instead of after. It also gets a team running faster by removing the amend-and-re-approve round trip that 20 of 24 field plans paid.

## Capabilities

### New Capabilities

- `plan-preflight`: checking a plan against the code and the shim's own refusals before it is approved. Covers the preflight holding area, the dry-run handoff, the preflight view of the authored set, `gates plan check` and its drift mode, the opt-in key, the propose-path preflight, and the refusal of held tests staged off a change branch.

### Modified Capabilities

- `command-surface`: the planner role may dispatch the test author and the authored-set review in preflight mode only, within stated limits, and runs the drift check before it sends a handoff.
- `upgrade-adoption`: the `plan-preflight` adoption item.

## Impact

- `bin/gates`: `tests brief --preflight`, `tests handoff --dry-run`, `tests show --preflight`, a new `plan` subcommand with `check`, the `loop.plan-preflight` key and its validation, and a refusal in `tests check`.
- `schema/gates.schema.json`: `loop.plan-preflight`.
- `adoption/catalog.json`: the `plan-preflight` item.
- Prompts: `agents/test-author.md`, `agents/convention-review.md`, `commands/propose.md`, `commands/planner.md`.
- Docs: SETUP.md, README.md, AUTOMATION.md, `docs/running-at-scale.md` §8, `docs/candidates.md`.
- `tests/contract.json`: the new subcommand and flags.
- Interactions with in-flight changes: `checkable-disputes` adds `--defend` to `tests handoff`, which composes with `--dry-run` (a dry run records no defence). `review-provenance`'s Bash allowlist for the reviewer admits `gates tests show`, so `--preflight` stays inside it.
- Compatibility: the new behaviour is opt-in. An unset key leaves the propose path as it is apart from `gates plan check`, which only reports what the handoff would refuse anyway.
