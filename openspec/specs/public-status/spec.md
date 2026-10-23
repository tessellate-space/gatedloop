# public-status Specification

## Purpose
Say honestly what the project is before anything else: the README opens with its status (the author's own tool, 0.x, the tested OpenSpec version, no support, who it is for) and a quickstart, `docs/status.md` states what has been exercised, by how many people, and where it couples to OpenSpec, and a dated `docs/topology.md` shows the setup actually in use as an example to adapt.

## Requirements

### Requirement: The README states the project's status before anything else

The README SHALL open, under its title, with a status paragraph saying the plugin is
built for the author's own projects, is 0.x, names the tested OpenSpec version,
promises no support, says who it is for, and says how to report a problem. A
quickstart SHALL follow before any section that introduces the plugin's vocabulary.

#### Scenario: A first-time reader

- **WHEN** someone opens the README
- **THEN** the first paragraph tells them the status and the audience, and the
  quickstart comes before the ladder and the boundary sections

### Requirement: The status page states what has been exercised and where it is fragile

`docs/status.md` SHALL list each known sharp edge with a status label, state how many
people have run the loop, and name the upstream couplings that break first when
OpenSpec changes. No document SHALL describe an invite-only trial or name an
individual tester.

#### Scenario: Upstream coupling is visible

- **WHEN** a reader checks what depends on OpenSpec
- **THEN** `docs/status.md` names the JSON outputs and generated commands relied on,
  and the tested version

### Requirement: A dated page shows the topology actually in use

`docs/topology.md` SHALL describe, with its date and as an example to adapt, how
planning, implementing and merging sessions fit together using only shipped commands,
and SHALL state that inter-session messages are a doorbell with git as the source of
truth.

#### Scenario: Reading the topology

- **WHEN** a reader follows `docs/topology.md`
- **THEN** each step names the shipped command it uses, and no step relies on a
  message having been delivered
