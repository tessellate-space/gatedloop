# Spec Delta

## Purpose

Makes a convention review's isolation checkable: the host, not the reviewer or its caller, records that a review ran as the isolated `convention-review` subagent, every review row says whether it did, and a project can refuse to merge on a review that ran inline.

## ADDED Requirements

### Requirement: Review provenance is recorded by the host, never by the caller

When the `convention-review` subagent stops, a plugin hook SHALL append a `review-provenance` row to the change's ledger with the subagent's id, its transcript path and the tree it stopped on. No prompt SHALL instruct an agent to record provenance itself.

#### Scenario: A subagent review leaves provenance
- **WHEN** the `convention-review` subagent stops on a change branch
- **THEN** the change's ledger gains a `review-provenance` row naming the agent id, the transcript path and the current tree

#### Scenario: Another subagent leaves none
- **WHEN** any other subagent (for example `test-author` or `merge-runner`) stops
- **THEN** no `review-provenance` row is written

#### Scenario: Off a change branch
- **WHEN** the `convention-review` subagent stops on the merge target or a `plan/*` branch
- **THEN** no row is written and the hook exits 0

### Requirement: Provenance input must come from the host

`gates review provenance` SHALL refuse input that does not carry an `agent_type` naming the `convention-review` agent and an `agent_transcript_path` that exists as a file, and SHALL exit non-zero naming what was missing.

#### Scenario: Hand-written provenance is refused
- **WHEN** `gates review provenance` is given input whose transcript path does not exist
- **THEN** it exits 1, writes no row, and names the missing transcript

### Requirement: Every review row states how the review ran

`gates review record` SHALL stamp each row it writes with `via: subagent` when the change's ledger holds a `review-provenance` row for the same tree, and `via: inline` otherwise, and SHALL print which. Rows recorded before this change carry no `via` and SHALL read as `inline`.

#### Scenario: A review after a subagent run
- **WHEN** a `review-provenance` row exists for tree T and `gates review record clean --task 1.2` runs on tree T
- **THEN** the review row carries `via: subagent`, and the output says the review ran as the isolated subagent

#### Scenario: A review with no subagent run
- **WHEN** no `review-provenance` row exists for the current tree and `gates review record clean --task 1.2` runs
- **THEN** the review row carries `via: inline`, and the output says the review ran inline

#### Scenario: The authored-set review is stamped too
- **WHEN** `gates review record clean --scope authored` runs on a tree with provenance
- **THEN** the row carries `via: subagent`

### Requirement: The reviewer cannot run commands outside a read-only set

A `PreToolUse` hook SHALL deny any `Bash` call made from inside the `convention-review` agent unless the command is one of `git diff`, `git show`, `git log`, `git status`, `gates rules` or `gates tests show`, and SHALL name the allowed set when it denies. Calls from any other agent or the main session SHALL be unaffected.

#### Scenario: A read command is allowed
- **WHEN** the `convention-review` agent runs `git diff --staged`
- **THEN** the call proceeds

#### Scenario: A write is denied
- **WHEN** the `convention-review` agent runs `git commit -m x` or `gates review record clean`
- **THEN** the call is denied, and the reason lists the allowed commands

#### Scenario: Other agents are untouched
- **WHEN** the `tdd-implementer` agent runs `gates review record clean --task 1.2`
- **THEN** this hook does not deny it

### Requirement: The reviewer does not load the project's memory files

The shipped `convention-review` agent SHALL declare that it starts without the project's `CLAUDE.md`, so it judges the diff against the rules `gates rules` names and not against project lore.

#### Scenario: The agent definition opts out
- **WHEN** the shipped `agents/convention-review.md` is read
- **THEN** its frontmatter sets `omitClaudeMd: true`

### Requirement: An adopter can refuse to merge on an inline review

The manifest SHALL accept `loop.review` with values `recorded` (default) and `isolated`. Under `isolated`, `gates merge` step 1 SHALL refuse a change whose latest clean review row, for any task or for the authored set, is `via: inline`, naming each. Under `recorded`, step 1 SHALL report the count of inline reviews and SHALL NOT refuse on them.

#### Scenario: Isolated policy refuses an inline review
- **WHEN** `loop.review: isolated` is declared and task 2.1's latest clean review row is `via: inline`
- **THEN** `gates merge` stops at step 1, exits 1, and names task 2.1

#### Scenario: A later isolated review supersedes an inline one
- **WHEN** `loop.review: isolated` is declared and task 2.1 has an inline clean review followed by a `via: subagent` clean review
- **THEN** step 1 does not refuse on task 2.1

#### Scenario: The default only reports
- **WHEN** `loop.review` is absent and two tasks' latest clean reviews are `via: inline`
- **THEN** step 1 proceeds and prints that 2 reviews ran inline

#### Scenario: An unknown value fails validation
- **WHEN** `loop.review: strict` is declared
- **THEN** `gates validate` exits 1 naming the allowed values
