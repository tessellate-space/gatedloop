# Proposal

## Why

The repository goes public as gatedloop. Going public is not launching: the plan is to stay 0.x, promise no support, and invest in readiness only once a second person has run one loop end to end. The docs don't say that yet.

- **README.** It opens on ladder, oracle and rung vocabulary before any quickstart, and it says nothing about status, support or who it's for.
- **The field guide.** `docs/field-guide.md` and the `field-trial` capability describe a private, invite-only trial: collaborator access as step zero, journeys for testers, a time-scope to the trial. The trial opened on 2026-08-21, and no tester filed an issue or feedback in two months. As a public page it misleads.
- **The feedback skill** addresses "the tester" throughout.
- **The real topology.** The setup the maintainer actually runs is written down nowhere: a local planner session, plan PRs attested from GitHub, implementers in Claude Code on the web, and a merge lane in local or pull-request mode with `gatedloop/*` statuses and `record-merged`. So a reader can't see how the pieces fit in practice.

## What Changes

- **A status paragraph** at the top of README, before any concept:
  - built for the author's own projects;
  - 0.x, so it changes without notice;
  - tested against OpenSpec 1.14.3;
  - no support promised;
  - issues welcome, through the feedback skill or a GitHub issue;
  - who it's for: people already running unattended coding agents who have been burned by "the agent said it ran the tests".
- **A quickstart near the top.** Install, `/gatedloop:gates-init`, then one change through `/gatedloop:propose` and `/gatedloop:tdd-apply`. The ladder and boundary sections move below it.
- **`docs/status.md` replaces `docs/field-guide.md`.** It keeps the field guide's honest parts:
  - the sharp edges, each with its status;
  - which surfaces have been exercised, and by how many people (one);
  - the upstream coupling: OpenSpec's JSON output and generated commands, at one tested version.

  The trial framing, the tester journeys and the access step are dropped. `field-guide.md` becomes a one-line redirect for one release.
- **`docs/topology.md`**, dated: the hybrid setup actually in use, as an example to adapt, built only from shipped commands:
  - a planner session, on the merge-as-approval path;
  - implementers in Claude Code on the web;
  - the merge lane;
  - the session handoff.
- **The feedback skill** says "you" and "the reporter", not "the tester", with no trial wording. Its whitelist and approval rules are unchanged.
- **`AGENT_INSTALL.md`** is checked for private-repository assumptions. Its URL is fixed by `rename-to-gatedloop`.

## Capabilities

### New Capabilities

- `public-status`: the README status paragraph and quickstart, the status page, and the topology page.

### Modified Capabilities

- `field-trial`: all six requirements are removed.

## Impact

- `README.md`, `docs/status.md` (new), `docs/field-guide.md` (now a redirect), `docs/topology.md` (new).
- `skills/feedback/SKILL.md`.
- The `field-trial` spec.

No code changes. This lands after `rename-to-gatedloop`, so it is written in the new name.
