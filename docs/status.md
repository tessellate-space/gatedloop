# gatedloop status

**Tested by one maintainer, on their own projects, against OpenSpec 1.14.3, on macOS and Linux with Python 3.9 and 3.13.** Nobody
else has reported running the loop end to end. This page says what has been
exercised, where the plugin is fragile, and what depends on OpenSpec staying the way
it is. It is kept current with each release; [`README.md`](../README.md) has the
status paragraph and the quickstart, and [`SETUP.md`](../SETUP.md) the `.gates.yaml`
contract.

## Tested by

One maintainer. Two people were invited to try it from 2026-08-21, and neither filed
anything. So every claim below comes from one person's projects, one stack at a time, and
mostly one host: Claude Code, locally and on the web.

## What has been exercised

| Surface | Exercised | How |
|---|---|---|
| The `gates` shim and the hook scripts | yes | the `unittest` suite in `tests/`, run by this repository's own `ci`, against real git repositories and worktrees |
| Onboarding (`/gatedloop:gates-init`, `gates doctor`) | yes, by one person | on the maintainer's projects; never on a stack the maintainer didn't pick |
| The gated loop (`/gatedloop:tdd-apply`, the `tdd-implementer` and `test-author` agents) | yes, by one person | every change in this repository since it began gating itself, plus the maintainer's other projects |
| Plan PRs, attestation and `gates handoff` | yes, by one person | the setup in [`topology.md`](./topology.md) |
| The merge lane (`gates merge` in both modes, `gates record-merged`, `gatedloop/*` statuses) | yes, by one person | this repository runs in pull-request mode with branch protection |
| The SessionStart brief and `/gatedloop:start` | yes, by one person | in the maintainer's repositories only |
| Workflow packs (`bugfix`, `architecture`) and `workflow-select` | lightly | installed and dispatched; few real changes run through them |
| Token usage rows, `gates stats --cost` and `loop.token-budget` | lightly | usage recorded on this repository's own changes since `token-ledger` merged; the budget has not halted a real change |
| `/gatedloop:planner` and `/gatedloop:orchestrator` | not yet | new in 0.10.0; the planner/orchestrator split they encode has run by hand, as in [`topology.md`](./topology.md) |
| The stability contract (row `v`, `tests/contract.json`, the ci matrix) | yes, in ci | every pull request runs Ubuntu and macOS with Python 3.9 and 3.13; the snapshot fails ci on any drift in the public surface; a weekly job runs OpenSpec's latest release |
| The READY report's gate block (`gates ledger record-ready`) | lightly | this repository's own changes since `loop-hardening` |
| `/gatedloop:feedback` | barely | built for reports that never came |

The prompts (commands, skills, agents) have no automated oracle. `ci` here says the
shim still parses, the version fields agree and the plugin still loads. It says
nothing about whether a prompt is right; running it is the only test the prompt
surface has. `prompt-evals` (planned) adds an on-demand `claude plugin eval` suite for the
implementer and the convention review.

## Sharp edges

Each one is labeled. **Shipped** means it is how the current release behaves.
**Shipped limitation** means it is known and accepted, with no fix planned.
**Planned** means a change exists to fix it and hasn't landed. Hitting one of these
is not a new bug; hitting something not listed here may be.

### A gate longer than the host's tool-call cap — *shipped limitation*

The shipped skill and the `tdd-implementer` agent run every gate in the foreground
and read its exit code in the same turn. The host caps a tool call at 600 seconds,
so a `ci` that takes longer than that can't finish in one call. Where it does, the
pattern in use is to start the gate in the background with its exit code appended to
a file, end the turn, and read the file when the completion notice arrives;
[`topology.md`](./topology.md), "Implementing", has it. Nothing in the plugin does
this for you.

### The invisible install — *shipped limitation*

Claude Code supports several config profiles through `CLAUDE_CONFIG_DIR`. A plugin
installed under one profile is invisible under another: no commands, no skills, no
session brief, and no error. Nothing inside a session can diagnose its own absence,
so check from a plain shell:

```bash
echo $CLAUDE_CONFIG_DIR
```

Then confirm the plugin is registered under that profile. `gates doctor` reports the
partly visible states, such as `gates` not on PATH, but by construction it can't see
a fully invisible install.

### Hook changes need a new session — *shipped*

The enforcement hooks load at session start. Install or update the plugin, then start
a new session; until then the old hooks, or none, are in force.

### The git layer enforces only inside a declared agent session — *shipped, by design*

The git hooks (`gates hook install`) act only where the agent host's variable is set:
`discipline.agent-env` in `.gates.yaml`, `CLAUDECODE` by default. A human's own
commits and pushes pass untouched, and an agent on another host is gated only once
its variable is declared. The `pre-push` gate on the merge target is opt-in, and
`--commit-only` declines it until `--push`. A hook installed before 0.8.0 is an old
copy: re-run `gates hook install`, and `gates doctor` reports it as `stale-copy`
until you do.

### The plan declares each task's oracle — *shipped, opt-in*

The authored-test lock is checked at every commit, again at the merge head
(`gates merge` step 1) and at the forge (`gatedloop/tests`). Since 0.8.0 it no longer
blocks ledger-only commits, halts at a finished task, or a finished task reopened by
a defect, which had left finished changes unable to merge (#56, #49). Since 0.9.0
(`task-oracle`) a task line may end with `[oracle: <gate>]`, `[oracle: <gate>
characterization]` or `[oracle: none]`: the brief tells the author, the handoff
refuses a contradiction, and the lock reads the red run on the declared gate, so an
e2e task tagged `[oracle: integration]` goes red under `integration` instead of being
declared `CHARACTERIZATION`. An untagged task is still the author's to decide from the
prose, and a wrong guess there shows only as a `green` defect. `loop.task-oracle:
required` refuses untagged tasks at handoff; it is off by default.

### A scoped `ci` or `unit` errs full on an unmatched path — *shipped*

Before 0.10.0 a diff holding one surface's file and a file no surface matched ran
that surface's narrow command, and a task spanning several surfaces ran only the
global `unit`, which could miss a surface's own tests and read a required red as
green (#61, #45). Now any changed path no non-catch-all surface matches runs the
global gate and the announcement names it; the loop's own `.gatedloop/` state never
counts. A multi-surface `unit` runs each hot surface's override, plus the global
`unit` once for a surface with none. Since 0.11.0 (`scope-own-tasks`) the current
change's own `tasks.md` doesn't count either, so the tick every task commit stages
no longer forces the full `ci`; in 0.10.0 it did, and the `openspec/**` remedy the
0.10.0 docs suggested only added a second hot surface (#122). Another change's
`tasks.md` is an ordinary path.

### The merge rechecks the plan approval, and some commands are now denied — *shipped*

Since 0.11.0 (`loop-hardening`) a few things that used to pass are refused, each
naming its route (#101, #108, #110):

- `gates merge` step 1 and every acceptance writer refuse a change whose plan no
  longer matches its recorded approval. Re-approve the amendment first; a `tasks.md`
  tick never needs it.
- A plain `git merge <target>` into a change branch is denied, because git runs no
  commit hook for a merge commit. Sync with `git merge --no-commit <target>`, then
  `gates run ci`, then `git commit`. A fast-forward or an already up-to-date sync
  passes.
- A guarded command behind a `cd` the hooks can't resolve (a variable other than
  `$HOME`, `~user`, a command substitution) is denied instead of being judged against
  the session's checkout. Use an absolute path or `git -C <dir>`.

[`AUTOMATION.md`](../AUTOMATION.md) has the full list, including the one-line
manifest parse error and the handoff that refuses to drop placed tests.

### Statuses posted from a laptop are self-reported — *shipped, by design*

The merge hook covers `git merge`. A merge made in the forge never passes through it.
Pull-request mode closes that path at the forge instead: `gates merge` publishes the
`ci` and `live-check` markers as `gatedloop/<gate>` commit statuses naming the tree
they proved, and `gates record-merged <sha>` writes the merge row and the archive
afterwards; under `approval.acceptance: self` the same commit records the owner's
merge as the acceptance. A status posted from a laptop proves only that the laptop said so; it is
evidence only where branch protection requires `gatedloop/ci` from your CI provider.
That protection is a repository setting only you can apply;
[`running-at-scale.md`](./running-at-scale.md), §5, lists it.

### Propose on the merge target, one branch per change — *shipped, by design*

Plans are authored on `main`, or on a `plan/*` branch based on it, in its own
worktree. From any other branch OpenSpec loses sight of other in-flight changes, so
the scaffold step is hook-denied there. Implementation uses one branch per change
(branch name = change name), and cutting it is hook-gated on the plan being merged and
its approval attested.

### Re-running onboarding over an existing manifest — *shipped*

`/gatedloop:gates-init` validates an existing `.gates.yaml` and asks before
regenerating it, and stops to confirm before `openspec init` regenerates
locally edited `/opsx:*` command files. Both are prompt rules, not code: back up a
hand-tuned manifest before re-running it.

### Installed workflow packs don't update — *shipped limitation*

A pack installed into a project is a snapshot. There is no registry, no version pin
and no `openspec schema update`; a later improvement reaches the project only by
reinstalling it. [`AGENT_INSTALL.md`](../AGENT_INSTALL.md) says the same.

### The earlier plugin name is refused — *shipped*

The plugin was renamed in 0.7.0, and the earlier names were read with a warning through
0.8.x. From 0.9.0 nothing reads them: a project still holding the earlier state directory is refused
by every command except `gates doctor` and `gates migrate-name`, which does the
migration, and only `gatedloop/<gate>` statuses are posted. README's migration section
has the steps.

## Upstream coupling

gatedloop does not author anything; OpenSpec does, and the shim reads what OpenSpec
prints. Supported: **OpenSpec 1.14.3 to 1.14.3**, the range [`stability.md`](./stability.md)
declares; ci tests both ends, and a weekly job runs OpenSpec's latest release. `gates doctor`
warns, without failing, outside the range.

| gatedloop relies on | Used by | When upstream changes it |
|---|---|---|
| `openspec list --json` | the session brief, the candidate list in [`running-at-scale.md`](./running-at-scale.md) §1 | the brief offers the wrong menu, or none |
| `openspec status --change <name> --json` | `tdd-apply` (where to resume, and the change's `schemaName` for dispatch); the commit hook's check of a proposal-only change | resume and dispatch stop, and planning commits are denied: a halt, not a wrong commit |
| `openspec instructions <artifact> --change <name> --json` | `tdd-apply` step 2 (the context files to read) | the loop reads less context than it should, and nothing refuses |
| `openspec validate` | the commit hook's check of each staged change in a planning commit; the plan-check job; this repository's close-out | planning commits are denied, or a malformed plan passes |
| `openspec archive <change> --yes` | `gates merge` (its archive step), `gates record-merged`, `/gatedloop:archive` | the merge stops at its archive step, after the merge row |
| the generated `/opsx:*` commands | `/gatedloop:propose` delegates to `/opsx:propose`, `/gatedloop:archive` to `/opsx:archive` | propose or archive does whatever the new upstream prompt does; `openspec update --force` regenerates them without asking |
| `.openspec.yaml` accepting `x-` keys | the approval keys (`x-gatedloop-approved-*`) and `x-gatedloop-epic` | `validate --strict` fails on every approved change |

Workflow packs also read `openspec schemas --json` and `openspec schema which`.

What has broken before is the last row: OpenSpec 1.14.0 started reporting unknown
change metadata, and `--strict` failed on every attested change until the keys moved
under `x-`, which 1.14.2 reserves for tools. Expect the next break in the JSON shapes,
and check `gates doctor` first after any upgrade.

## What's next

The planned changes live in `openspec/changes/`, each with its proposal, design and
tasks; ideas that aren't scheduled are in [`candidates.md`](./candidates.md). Open
issues are the rest. [`stability.md`](./stability.md) says what the public contract
covers and how a part of it is retired. A 1.0, and any support promise, waits until a
second person has run one loop end to end; until then the plugin stays 0.x, and a
removal may ship in a minor release with its migration steps.

So a missing feature is likely *coming*, or out of scope by the rejection test. A
gate that commits on red, an agent that merges on its own, or a session brief that
offers a command that does not resolve is *broken*. Report it with
`/gatedloop:feedback` or a GitHub issue.
