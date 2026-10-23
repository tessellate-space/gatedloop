# Design

## Context

`rename-to-gatedloop` keeps every earlier-name literal in `bin/gates` in one delimited region, `the earlier name`. The rest of the file is held to the new name by the allow-list test (its D6). So this change is mostly a deletion inside that region and of what calls into it.

## Decisions

### D1. What goes, what stays

| Goes in 0.8.0 | Stays until a later change |
|---|---|
| `_state_dir`'s fallback to `.specloop/`, `_meta_value`'s fallback key, the earlier status context in `check-remote`, `_canonical_rule_id`, the earlier hook markers in the detectors, the earlier schema block | `gates migrate-name`, `_migrate_name_text`, `_earlier_name_remnants` |
| `marker publish`'s second context | the doctor `name` row and the `rename` catalogue item, which still find what `migrate-name` would move |
| `forwarder/specloop/`, its marketplace entry, `FORWARDER_NAME` and `STATE_DIRS` in `scripts/release` | the migration notes |
| `_warn_earlier_name` and its once-per-command flag | |

### D2. An unmigrated project is refused, never silently ignored

Once the fallback goes, a project with only `.specloop/` would otherwise look like a fresh project. It would gain an empty `.gatedloop/`, and its ledger would split. So every command except `gates doctor` and `gates migrate-name` refuses while `.specloop/` exists, naming the command. That keeps `fail-loud-gates`.

### D3. The allow-list shrinks with the code

Each allow-list entry that names a removed thing is deleted with that thing: the forwarder, the read-both tests and the `scripts/release` constant. An entry left behind would allow a hit nothing should produce.

### D4. Precondition

This repository runs `gates migrate-name` on itself, and commits the result, before this change is implemented. Otherwise D2 refuses its own loop.

### D5. The spec delta

The delta is written as an ADDED requirement, because `rename-to-gatedloop` isn't archived yet: its requirement "The earlier name is read loudly for one release" isn't in `openspec/specs/plugin-positioning` to modify. Once it's archived, before this change is implemented, the delta should become a REMOVED of that requirement plus this ADDED one. Without that, the living spec keeps both, and they contradict each other.

## Risks

- **An adopter who never updated during 0.7.x.** They meet D2's refusal, which names the command. `gates migrate-name` still exists to run.
- **Branch protection still requiring `specloop/ci`.** It stops passing once only `gatedloop/ci` is posted. The 0.7.x notes and `gates migrate-name`'s printed edits gave the replacement for a full release. This change's release notes repeat it.
