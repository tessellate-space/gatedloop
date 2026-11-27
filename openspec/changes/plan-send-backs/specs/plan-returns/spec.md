# plan-returns Specification

## Purpose

Every time a plan goes back to its author before approval, the change's durable ledger can say who sent it back, why, in a class from a closed set, and in the sender's own words, so plan-stage rework is counted by category and the recurring kinds become the next lens check or convention.

## ADDED Requirements

### Requirement: Send-back classes are a closed set held in one place

The shim SHALL define exactly one closed set of send-back classes: `scope` (what the change covers), `approach` (the design is wrong), `spec-gap` (a missing requirement or scenario), `decision` (an open question answered), `collision` (an ADR, number or file clash with another change), `drift` (conflicts with the target), `safety` (a risk to data, security or a project's work), `nit` (wording or presentation only, no change in behaviour), and `other` (none of these), which MUST carry detail saying what it is. Every writer and reader SHALL resolve a class against it; extending it SHALL be a spec change to this capability.

#### Scenario: A class outside the set is refused

- **WHEN** `gates plan returned <change> --by human --class typo --words "fix the title"` runs
- **THEN** it exits 1 naming `typo` and listing the accepted classes, and nothing is written to the ledger

#### Scenario: `other` without detail is refused

- **WHEN** a send-back is recorded with class `other` and no `--detail`
- **THEN** it exits 1 saying that `other` requires detail, and nothing is written

### Requirement: Send-back senders are a closed set held in one place

The shim SHALL define exactly one closed set of senders: `human` (a person) and `reviewer` (a session that is not one of the plan loop's checkers). Every writer and reader SHALL resolve a sender against it, and extending it SHALL be a spec change to this capability.

#### Scenario: A sender outside the set is refused

- **WHEN** `gates plan returned <change> --by checker --class scope --words "..."` runs
- **THEN** it exits 1 naming `checker` and listing `human` and `reviewer`, and nothing is written

### Requirement: A send-back carries the sender's words

A send-back SHALL carry the sender's words, given as `--words <text>` or read from `--words-file <path>`, and stored exactly, line breaks and trailing newlines included. Exactly one of the two SHALL be given. Empty or whitespace-only words, both flags, or an unreadable file SHALL be refused, and nothing written.

#### Scenario: Words from a file are kept verbatim

- **WHEN** a send-back is recorded with `--words-file` naming a file whose text holds a double quote, a `$`, two lines and a trailing newline
- **THEN** the row's `words` equals the file's text byte for byte

#### Scenario: Empty words are refused

- **WHEN** a send-back is recorded with `--words ""` or words that are only whitespace
- **THEN** it exits 1 saying the sender's words are required, and nothing is written

### Requirement: A send-back is a ledger row written by the shim

`gates plan returned <change> --by <sender> --class <class> --words <text> [--ref <ref>] [--detail <text>]` SHALL append one row to `.gatedloop/runs/<change>.jsonl` with the event name `plan-returned`, the sender, the class, the words, the ref and detail (or none), the plan's approval digest (`plan_sha`), the digest of its task lines (`tasks_sha`) and the plan loop's current loop number. It SHALL refuse a change with no directory under `openspec/changes/`.

#### Scenario: A human's requested changes are recorded

- **WHEN** `gates plan returned plan-x --by human --class scope --words "Drop the CSV export; that is another change." --ref https://example.test/pr/12#review-3` runs on `plan/plan-x`
- **THEN** one row is appended with `gate: "plan-returned"`, `by: "human"`, the class `scope`, the words byte for byte, the ref, and the plan's current `plan_sha` and `tasks_sha`, and the command exits 0

### Requirement: A send-back can be recorded wherever the plan is

`gates plan returned` SHALL write on any branch, under either `loop.plan-preflight` mode, and whether or not a plan round is open. The ledger row fields SHALL gain `by`, `words` and `ref`, appended as an additive union, so rows of every other kind carry them as absent and the row version is unchanged.

#### Scenario: Recording with the plan loop off

- **WHEN** the manifest leaves `loop.plan-preflight` unset and a reviewer's send-back is recorded
- **THEN** the row is written, and no `plan-round` or `plan-review` row is written

#### Scenario: Other row kinds carry the new fields as absent

- **WHEN** `gates run ci` appends a row after this change
- **THEN** the row carries `by`, `words` and `ref` as null and the same row version as before

### Requirement: Send-back rows decide nothing

No approval, handoff, merge, implementation, attempt-counting or plan-round check SHALL read `plan-returned` rows. The plan loop's round count, its budget and the state `gates plan status` computes SHALL be the same with or without them.

#### Scenario: A send-back during an open round

- **WHEN** round 1 of a full-tier loop is open and a send-back is recorded
- **THEN** round 1 is still open, `gates plan record` still records into it, and `gates plan status` reports the same state as before the send-back

#### Scenario: The handoff ignores send-backs

- **WHEN** an approved plan's ledger holds `plan-returned` rows
- **THEN** `gates handoff`, `gates merge` and `gates discipline check-implement` give the verdicts they give without them

### Requirement: A resume can record the send-back it answers

`gates plan resume <change> --reason <text>` SHALL accept `gates plan returned`'s send-back flags. When any is given, `--by`, `--class` and one words source SHALL be required and validated as `gates plan returned` does, before any write; a refusal writes neither row. Valid flags SHALL append the `plan-returned` row, then the `resume` row. Without them, resume SHALL behave exactly as before.

#### Scenario: Resuming with the human's answer recorded

- **WHEN** the loop stopped on a question and, before amending, a person runs `gates plan resume plan-x --reason "retention: 30 days" --by human --class decision --words "Take option (a), 30 days."`
- **THEN** a `plan-returned` row with class `decision` and those words is appended, followed by a `plan-round` row with outcome `resume` and the reason, and the next round opens round 1 of the new loop

#### Scenario: A partial send-back on resume is refused

- **WHEN** `gates plan resume plan-x --reason "go on" --class scope` runs without `--by` or `--words`
- **THEN** it exits 1 naming the missing flags, and neither row is written

#### Scenario: A ref alone on resume is refused

- **WHEN** `gates plan resume plan-x --reason "go on" --ref https://example.test/pr/12` runs
- **THEN** it exits 1 naming `--by`, `--class` and `--words`, and no row is written

#### Scenario: A plain resume is unchanged

- **WHEN** `gates plan resume plan-x --reason "continue past the stall"` runs
- **THEN** only the `resume` row is appended, as before this change

### Requirement: The plan status lists the send-backs

`gates plan status <change>` SHALL list every `plan-returned` row in ledger order, with its sender, class, ref, words and short plan digest, in the text, `--markdown` and `--json` forms (under `returns` in JSON). Words keep their line breaks: in `--markdown` each of their lines is prefixed with `> `, and in the text form each is indented by six spaces. With no such rows it SHALL print what it printed before this change, and the JSON SHALL carry `returns` as an empty list.

#### Scenario: The approver sees why the plan came back

- **WHEN** a plan was sent back once by a reviewer with class `collision`
- **THEN** `gates plan status <change> --markdown` lists that send-back with `reviewer`, `collision`, its ref and its words

#### Scenario: Multi-line words in the text form

- **WHEN** a send-back's words are two lines
- **THEN** `gates plan status <change>` prints them as two lines, each indented by six spaces

### Requirement: The send-back key is validated and reported

The manifest key `loop.plan-returns` SHALL take `record` or `skip`, and SHALL default to `skip` when absent. Any other value SHALL fail `gates validate` naming the key and the accepted values. `gates plan check <change> --json` SHALL report the effective value as `returns`.

#### Scenario: A misspelt value

- **WHEN** the manifest declares `loop.plan-returns: on`
- **THEN** `gates validate` exits 1 naming `loop.plan-returns` and the values `record` and `skip`

#### Scenario: The default

- **WHEN** the manifest does not declare `loop.plan-returns`
- **THEN** `gates plan check <change> --json` reports `returns: "skip"`

### Requirement: Recording send-backs from the shipped prompts is opt-in

Under `loop.plan-returns: record`, `/gatedloop:propose` and `/gatedloop:planner` SHALL record each human or non-checker send-back with the sender's exact words, with `gates plan returned`, before amending the plan against it (so the row carries the digests of the content sent back), and SHALL commit the change's ledger with the amendment whenever the ledger exists; under `skip` they SHALL record none. `gates plan returned` and `gates stats --plans` SHALL work under either value.

#### Scenario: The command works under skip

- **WHEN** the manifest leaves `loop.plan-returns` unset and a person runs `gates plan returned` by hand
- **THEN** the row is written
