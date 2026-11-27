# Spec Delta

## MODIFIED Requirements

### Requirement: Planner and orchestrator roles ship as commands over shipped primitives

The plugin SHALL ship `/gatedloop:planner` and `/gatedloop:orchestrator` as prompt
commands that add no shim code. The planner command SHALL forbid dispatching an
implementer, a merge runner or a test author outside preflight mode, and SHALL forbid
implementing, merging and archiving. Running the plan loop SHALL be part of the
planner's job: on its own `plan/<change>` branch, in its own worktree, the planner
command SHALL direct running the loop at the tier `gates plan tier` computes, and
dispatching the plan-review agent, the test author in preflight mode and the
convention review in authored-set mode for it. It SHALL direct recording each verdict
with `gates plan record`, and never a real `gates tests handoff`, a review verdict or a
halt. Before running `gates handoff`, the planner command SHALL run `gates plan check
<change> --against <target>`, and on a finding SHALL read what moved against the plan.
It SHALL send a handoff only after `gates handoff` exits 0 and the plan still holds,
and otherwise report and send nothing. The orchestrator command SHALL require running
a handoff's `verify` command before queueing and SHALL rebuild its queue from git, not
messages, when unsure. Each SHALL tell the agent to re-run it after compaction.

#### Scenario: A refused handoff

- **WHEN** a planner runs `gates handoff <change>` and it exits 1
- **THEN** the planner command directs reporting the reason to the user and sending
  nothing

#### Scenario: A handoff that no longer verifies

- **WHEN** the orchestrator receives a payload whose `verify` command fails
- **THEN** the orchestrator command directs dropping it and reporting why

#### Scenario: The planner runs the plan loop

- **WHEN** the project declares `loop.plan-preflight: run` and the planner proposes a
  change
- **THEN** the planner command directs running the loop at the computed tier on its
  own plan branch, dispatching plan review, the preflight test author and the
  authored-set review, and recording each verdict with `gates plan record`

#### Scenario: Any other dispatch stays forbidden

- **WHEN** a planner considers dispatching an implementer, a merge runner, or a test
  author outside preflight mode
- **THEN** the planner command forbids it

#### Scenario: The loop stops on a question

- **WHEN** the plan loop stops on a recorded question
- **THEN** the planner command directs putting the question and its options at the top
  of the plan PR's body, opening it as a draft, and resuming the loop with
  `gates plan resume` only after the question is answered

#### Scenario: A plan that drifted while queued

- **WHEN** `gates plan check <change> --against <target>` reports a file the plan names
  that has changed since the plan's base, and the plan no longer holds against it
- **THEN** the planner command directs reporting the finding and sending no handoff
