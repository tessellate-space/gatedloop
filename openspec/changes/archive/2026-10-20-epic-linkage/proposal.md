# Proposal

## Why

Issue #22: Specloop's unit is one change. The implementer, the Stop hook, `check-implement`, `check-archive` and `gates stats` each see one change. A story of five or six changes that only make sense together exists nowhere as a first-class object, so there is:
- no roll-up;
- no ordering guarantee;
- no view of what is done, running or stuck.

In the field report, that state lived in an orchestrating session's memory file and was re-derived every few hours.

The issue proposes five things. The rejection test splits them:

| Item | Verdict | Why |
|---|---|---|
| 1. Epic linkage the shim validates | **ours** | makes a guarantee enforceable |
| 2. An epic can't archive before its children | **ours** | `check-archive`'s "merge before archive", one level up |
| 3. `gates stats --epic` roll-up | **ours** | a join over the ledger the shim already owns |
| 4. Epics in the session brief | **ours** | a generated view |
| 5. `drain <epic>`: pick, dispatch, merge, loop | **not shipped** | the orchestrator Specloop declined in #37/#95 |

Item 5 is declined for the same reason as #37: it ships as a worked example in `docs/running-at-scale.md`, built only from the commands this change and 0.5.0 provide. The epic's own prose artifacts (charter, features, decisions) belong to an upstream schema, as the issue itself says.

## What Changes

- **An epic is a change.** No new artifact type and no new directory: an epic is an ordinary OpenSpec change, typically on a schema with no `apply` block (the bundled `architecture` pack is one), holding the story's charter. A child declares `x-specloop-epic: <epic-change>` in its own `.openspec.yaml`. The `x-` prefix is OpenSpec 1.14's reserved tool-metadata form, so the key passes `openspec validate --strict` (`openspec-1-14-compat` moves the approval keys to the same form).
- **Linkage is validated.** `gates validate` fails, naming the change, when a child names:
  - an epic that is neither an active nor an archived change;
  - itself;
  - an epic that itself names an epic (one level only).
- **An epic is never implemented.** `check-implement` refuses to cut an implementation branch for a change that any other change names as its epic.
- **Ordering.** `check-archive <epic>` refuses while any child is not archived, listing each one and its state. Archiving goes through the hook already in place.
- **Roll-up.** Two new commands:
  - `gates epics [--json]` lists each epic with its children's states, derived in code: proposed, approved, implementing, halted, ready, merged, archived;
  - `gates stats --epic <name>` reports per-child economics and totals, plus tasks done of total.
- **The brief** lists active epics, each with its children's states, above the flat change list. It is generated from `gates epics --json`.
- **Docs:** a "Draining an epic" example in `docs/running-at-scale.md`.

## Capabilities

### New Capabilities

- `epics`: linkage, validation, the implement and archive guarantees, the roll-up and the brief.

### Modified Capabilities

None. `check-implement` and `check-archive` gain epic cases under the new capability.

## Impact

- `bin/gates`:
  - reading `x-specloop-epic` from `.openspec.yaml`;
  - the epic checks in `validate`;
  - `discipline check-implement` and `check-archive`;
  - `gates epics`;
  - `stats --epic`.
- `hooks/_session_brief.py`.
- `docs/running-at-scale.md`, SETUP, README.
- Tests.
