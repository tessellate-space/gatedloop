# Spec Delta

## ADDED Requirements

### Requirement: A shipped prompt change since the tag prompts an eval run

`scripts/release status` SHALL report the shipped prompt paths (`commands/`, `skills/`, `agents/`) that a commit since the latest `v*` tag touches. When there are any, it SHALL print them, with the command that runs the prompt suite, `python3 scripts/eval-prompts`. `--json` SHALL carry the same list as `prompts_changed`.

#### Scenario: A prompt changed since the tag

- **WHEN** a commit since the tag edits `agents/tdd-implementer.md`
- **THEN** `status` lists `agents/tdd-implementer.md` under the prompt reminder and names `python3 scripts/eval-prompts`

#### Scenario: No prompt changed

- **WHEN** no commit since the tag touches `commands/`, `skills/` or `agents/`
- **THEN** `status` prints no prompt reminder, and `prompts_changed` is empty

### Requirement: The prompt reminder never blocks a release

The prompt reminder SHALL be advisory. It SHALL NOT change the suggested level or `status`'s exit code, and `cut` and `publish` SHALL NOT refuse because of it.

#### Scenario: The reminder never blocks

- **WHEN** a prompt changed since the tag and no eval has run
- **THEN** `cut` proceeds exactly as it would without the reminder
