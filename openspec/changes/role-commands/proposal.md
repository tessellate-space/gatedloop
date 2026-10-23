# Proposal

## Why

The maintainer runs a cross-session setup:
- any number of **planner** sessions;
- one **orchestrator** session that dispatches implementers, runs merges and archives;
- messages between them sent with Claude Code's `SendMessage`.

The protocol lives only in each session's memory. A session that is compacted, or started fresh, has to be told its role again, and the rules come from memory each time:
- a planner never dispatches;
- the orchestrator re-checks every handoff before queueing;
- a message is a doorbell, never evidence.

`planner-handoff` (0.6.0) shipped the primitive, `gates handoff <change>`, and the contract as docs in `docs/running-at-scale.md`. Two role commands make that contract something a session loads, rather than something a human re-types.

**Scope and the rejection test.** #37's orchestrator was declined because it put dispatch policy in Specloop. These commands add **no** shim code and decide nothing in code. Each one states a role, its rules, and the shipped commands it uses. Judgement (what to dispatch next, when to merge) stays the agent's, under the same gates. The maintainer chose to ship them on 2026-10-22, knowing that boundary.

## What Changes

- **`/gatedloop:planner`**:
  - you author and propose only, in your own worktree, and never dispatch, implement, merge or archive;
  - after a plan merges, run `gates handoff <change> --json` and send the payload to the orchestrator with your messaging tool;
  - a refused handoff is reported, never sent.
- **`/gatedloop:orchestrator`**:
  - you are the only session that dispatches implementers, merges and archives;
  - on a handoff payload, run its `verify` command (`gates approval check`) before queueing, and drop a payload that fails it;
  - rebuild the queue from git (approved, unimplemented changes; READY rows) whenever unsure, never from messages;
  - dispatch implementers and merges with the shipped agents and commands, running long gates in the background.
- **Surviving compaction.** Each command begins with a short role block meant to be restated. It tells the agent to re-run the command after compaction, or whenever it's unsure of its role.
- **Docs.** `docs/topology.md` (from `public-status`) and `running-at-scale.md` §8 point to the two commands.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `command-surface`: two role commands, each a prompt over shipped primitives.

## Impact

`commands/planner.md`, `commands/orchestrator.md`, README's command list, SETUP, `docs/running-at-scale.md` and `docs/topology.md`. No code changes.
