# Spec Delta

## MODIFIED Requirements

### Requirement: Planner and orchestrator roles ship as commands over shipped primitives

The plugin SHALL ship `/gatedloop:planner` and `/gatedloop:orchestrator` as prompt
commands that add no shim code. The planner command SHALL forbid dispatching,
implementing, merging and archiving, and SHALL send a handoff only after `gates
handoff` exits 0. There is one exception to the dispatch ban. Under `loop.plan-preflight:
run`, the planner command SHALL permit dispatching the test author in preflight mode and
the convention review in authored-set mode, for the plan preflight only, within these
limits: they run against the planner's own plan branch in its own worktree; no real
`gates tests handoff`, review verdict, halt or any other ledger row is recorded; the
test author writes only to the preflight holding area, `.gatedloop/out/preflight/<change>/`;
and that area is deleted before the plan is committed. Before running
`gates handoff`, the planner command SHALL run `gates plan check <change> --against
<target>`, and on a finding SHALL read what moved against the plan. It SHALL send the
handoff only when the plan still holds, and otherwise report the finding and send
nothing. The orchestrator command SHALL require running a handoff's `verify` command
before queueing and SHALL rebuild its queue from git, not messages, when unsure. Each
SHALL tell the agent to re-run it after compaction.

#### Scenario: A refused handoff

- **WHEN** a planner runs `gates handoff <change>` and it exits 1
- **THEN** the planner command directs reporting the reason to the user and sending
  nothing

#### Scenario: A handoff that no longer verifies

- **WHEN** the orchestrator receives a payload whose `verify` command fails
- **THEN** the orchestrator command directs dropping it and reporting why

#### Scenario: The planner's preflight dispatch

- **WHEN** the project declares `loop.plan-preflight: run` and the planner proposes a
  change
- **THEN** the planner command permits dispatching the test author in preflight mode
  and the convention review in authored-set mode against its own plan branch, directs
  that no handoff or other ledger row is recorded, and directs deleting the holding area
  before the commit

#### Scenario: Any other dispatch stays forbidden

- **WHEN** a planner considers dispatching an implementer, a merge runner, or a test
  author outside the preflight
- **THEN** the planner command forbids it

#### Scenario: A plan that drifted while queued

- **WHEN** `gates plan check <change> --against <target>` reports a file the plan names
  that has changed since the plan's base, and the plan no longer holds against it
- **THEN** the planner command directs reporting the finding and sending no handoff
