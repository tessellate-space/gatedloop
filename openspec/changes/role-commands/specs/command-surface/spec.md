## ADDED Requirements

### Requirement: Planner and orchestrator roles ship as commands over shipped primitives

The plugin SHALL ship `/gatedloop:planner` and `/gatedloop:orchestrator` as prompt
commands that add no shim code. The planner command SHALL forbid dispatching,
implementing, merging and archiving, and SHALL send a handoff only after `gates
handoff` exits 0. The orchestrator command SHALL require running a handoff's `verify`
command before queueing and SHALL rebuild its queue from git, not messages, when
unsure. Each SHALL tell the agent to re-run it after compaction.

#### Scenario: A refused handoff

- **WHEN** a planner runs `gates handoff <change>` and it exits 1
- **THEN** the planner command directs reporting the reason to the user and sending
  nothing

#### Scenario: A handoff that no longer verifies

- **WHEN** the orchestrator receives a payload whose `verify` command fails
- **THEN** the orchestrator command directs dropping it and reporting why
