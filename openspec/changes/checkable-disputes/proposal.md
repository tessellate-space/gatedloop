# Proposal

## Why

When the implementer and the test author disagree about a test, both sides argue in prose that nothing checks. `gates tests defect --detail` accepts any non-empty text. A `green` defect claims "the placed tests passed before I implemented anything" without the shim checking that a passing run was recorded. The author's defence never reaches the ledger at all: it lives in the author's report (`agents/test-author.md`), so when a third disagreement halts for a human, the human gets the implementer's side from the ledger and has to dig for the author's.

Google's elephant-goldfish-model handles the same moment in `egm-resolve`. A contest must be checkable: it must cite a file, symbol or recorded decision the other side can read, and "a wish to contest is not evidence". gatedloop can enforce this more strictly than a prompt can, because the shim can resolve a citation and read the ledger.

This passes the rejection test as "makes a stated guarantee enforceable". The guarantee is the existing one that a wrong test goes back to its author and a persistent disagreement reaches a human with both positions (`test-discipline`).

## What Changes

- **A defect must cite something checkable.** `gates tests defect --kind setup|assertion` requires at least one `--cite`. A citation is a repository path, optionally with a line (`path:line`), or a spec scenario (`spec:<capability>#<scenario name>`). The shim resolves each one and refuses the defect, naming the bad citation, if it does not resolve. Citations are stored on the row.
- **A `green` defect needs its evidence in the ledger.** It is refused unless the ledger holds a passing run of the task's oracle gate recorded after the task's latest placement. That is the run the claim is about, so no citation is asked for.
- **A defence is recorded.** `gates tests handoff <change> --task N.M --defend "<why>" --cite <ref>` records a `test-defence` row answering the task's latest defect. The handoff is refused as a defence if the task's held tests changed since the previous handoff, because changed tests are a revision, not a defence. A defence needs at least one citation, resolved the same way.
- **The human gets both sides.** `gates tests show` lists each defect with its citations and the defence that answered it. The refusal past the `assertion` cap prints both positions with their citations, ready for the `halt` detail.
- **The prompts** (`agents/test-author.md`, `agents/tdd-implementer.md`, `skills/tdd-apply/SKILL.md`) say what to cite and when to defend versus revise.
- **This is default-on.** The checks apply to every change whose handoff is recorded after the upgrade. A change already in flight keeps the old rules, keyed on its handoff row (see design D5). The plan PR asks the maintainer to approve the default.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `test-discipline`: adds requirements for the evidence a defect carries, the evidence behind a `green` defect, the recorded defence, and both positions reaching the human. The existing requirement "A wrong test goes back to its author, and a persistent disagreement halts" is unchanged; the new requirements sit beside it.

## Impact

- `bin/gates`: `tests defect` (`--cite`, the green-run check), `tests handoff` (`--defend`, `--cite`), `tests show`, the assertion-cap refusal text, and a citation resolver.
- `agents/test-author.md`, `agents/tdd-implementer.md`, `skills/tdd-apply/SKILL.md`.
- `tests/contract.json` (new flags), README.md and SETUP.md (the commands' new flags), tests for each check.
- No manifest key.
