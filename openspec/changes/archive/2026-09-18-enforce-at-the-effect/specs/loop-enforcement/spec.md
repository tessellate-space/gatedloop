## ADDED Requirements

### Requirement: Commit enforcement operates at the git layer, catching every commit-creating path

Commit enforcement SHALL act on the commit object being created, not on the phrasing
of the invocation. A git `pre-commit` hook SHALL deny any commit — created by any path
(`git commit`, a subprocess spawned from another program, a wrapper script, or a
library that talks to git directly) — unless a fresh `ci` marker exists whose recorded
tree matches the tree that would be committed (`git write-tree` of the staged index).
The check SHALL be the same O(1) marker/hash comparison the tool-invocation hook uses
and SHALL NOT re-run CI.

#### Scenario: An indirectly-created commit is gated

- **WHEN** a commit is created inside an agent session through a path that carries no
  `git commit` command string (for example a Python subprocess), and no green `ci`
  marker matches the staged tree
- **THEN** the git `pre-commit` hook denies the commit, so the invocation-string
  matcher's blind spot no longer lets an ungated commit through

#### Scenario: A gated commit through any path is allowed

- **WHEN** `gates run ci` passed and recorded the staged index tree, and a commit is
  then created by any path against that same tree
- **THEN** the git `pre-commit` hook allows it, because the marker matches the tree
  being committed

#### Scenario: The hook never re-runs CI

- **WHEN** the git `pre-commit` hook fires
- **THEN** it performs only a marker/tree comparison and never invokes the `ci` gate
  itself, so it cannot exceed a hook timeout

### Requirement: Git-layer commit enforcement is scoped to agent sessions

The git `pre-commit` hook SHALL enforce only when a Claude Code session is present in
the environment (`CLAUDECODE` set), and SHALL be a transparent no-op otherwise. This
scoping is deliberate and SHALL NOT be treated as a silent skip: the gate exists to
hold an autonomous loop to its invariant, and outside a session no such loop is
running the commit.

#### Scenario: A commit inside a session is enforced

- **WHEN** a commit is attempted and `CLAUDECODE` is present in the environment
- **THEN** the git `pre-commit` hook applies the marker check

#### Scenario: A human or CI commit is not gated

- **WHEN** a commit is made from a plain terminal, an IDE, or a CI runner, with
  `CLAUDECODE` absent from the environment
- **THEN** the git `pre-commit` hook is a no-op and the commit proceeds unhindered

### Requirement: The git-layer commit hook installs without clobbering an existing hook

Installation of the git `pre-commit` hook SHALL be performed by deterministic shim
code (`gates hook install`), not by prompt prose. It SHALL detect who owns the hook
path — a hook manager (husky, lefthook, the `pre-commit` framework), a `core.hooksPath`
redirect, or a bare existing `.git/hooks/pre-commit` — and SHALL compose with it where
a safe composition is determinable, and refuse-and-instruct where it is not. It SHALL
NEVER overwrite an existing hook or hook-manager configuration.

#### Scenario: An existing hook is present

- **WHEN** `gates hook install` runs in a repository that already has a `pre-commit`
  hook or a recognized hook manager
- **THEN** it composes the `gates` check into the existing flow without overwriting
  what is there

#### Scenario: The hook topology cannot be classified safely

- **WHEN** `gates hook install` cannot determine a safe way to compose with the
  existing hook setup
- **THEN** it refuses to modify anything and reports how to wire the check by hand,
  rather than clobbering

#### Scenario: No hook is present

- **WHEN** `gates hook install` runs in a repository with no existing `pre-commit`
  hook and no hook manager
- **THEN** it installs the shipped hook template directly

### Requirement: Onboarding offers git-layer enforcement with the adopter's consent

`/specloop:gates-init` SHALL offer to install the git `pre-commit` hook as a
default-yes step, SHALL NOT install it silently, and SHALL complete onboarding
normally if the adopter declines.

#### Scenario: The adopter accepts the offer

- **WHEN** onboarding reaches the hook-install step and the adopter confirms
- **THEN** it runs `gates hook install` and reports the result

#### Scenario: The adopter declines the offer

- **WHEN** onboarding reaches the hook-install step and the adopter declines
- **THEN** no git hook is installed or modified, and onboarding completes normally

### Requirement: An ungated commit is detected after the fact and taints the change

The `Stop` hook SHALL audit commits created since the last audited point by joining
each commit's tree to the durable ledger's green-`ci` rows for the change. A commit
whose tree has no matching green-`ci` row SHALL be reported loudly, naming the
offending commit, and SHALL record a taint on the change's durable ledger. This is
detection after the effect, not prevention, and SHALL NOT be presented as prevention.

#### Scenario: All commits are gated

- **WHEN** the audit runs and every new commit's tree matches a green-`ci` ledger row
  for the change
- **THEN** no taint is recorded and nothing is reported as an incident

#### Scenario: A commit has no green-CI record

- **WHEN** the audit finds a new commit whose tree matches no green-`ci` ledger row
  (it slipped the invocation and git-layer hooks)
- **THEN** the audit reports the offending commit loudly and records a taint on the
  change's ledger

#### Scenario: The audit does not re-report the same commit

- **WHEN** the audit runs again after a commit was already audited
- **THEN** it only considers commits new since the last audited point and does not
  re-report an already-audited commit

### Requirement: A tainted change cannot be merged until it is re-verified

The merge gate SHALL refuse a change carrying an unresolved taint, in addition to its
existing green-`live-check`-on-head requirement. A taint SHALL be resolvable by
re-running `ci` green on the current branch head, which SHALL append a resolution to
the durable, append-only ledger rather than deleting the incident record.

#### Scenario: A tainted change is blocked at the merge

- **WHEN** a merge is attempted for a change whose ledger carries an unresolved taint
- **THEN** the merge gate denies it and reports that the change must be re-verified

#### Scenario: Re-verifying the head clears the taint

- **WHEN** `gates run ci` passes green on the current branch head of a tainted change
- **THEN** the taint is resolved (a resolution row is appended, and the incident row
  remains in history) and the merge is no longer blocked on that basis

### Requirement: The forge merge path is covered by documented branch protection for pull-request modes

For `pull-request` integration modes, project documentation SHALL state that forge
branch protection is required, because the forge merge path (`gh pr merge` or a
forge-UI merge) has no local git-hook equivalent and is not covered by the commit or
merge hooks. Specloop SHALL NOT implement a forge-side merge gate itself.

#### Scenario: A pull-request mode is documented

- **WHEN** an adopter configures `integration.mode: pull-request`
- **THEN** the documentation names branch protection on the default branch as a
  requirement and states which checks/reviews to protect

#### Scenario: The local merge path is distinguished from the forge path

- **WHEN** the documentation describes enforcement coverage
- **THEN** it states plainly that the local `git merge` path is covered by the merge
  gate while the forge merge path is covered only by branch protection

### Requirement: A denied gate call is a loop violation, not an invitation to rephrase

The loop prompts (`skills/tdd-apply/SKILL.md`, `agents/tdd-implementer.md`) SHALL state
that a denied gate call means the gate is unsatisfied, and that rephrasing the
invocation to get past the denial is a loop violation rather than a solution.

#### Scenario: The norm is stated in the loop prompts

- **WHEN** a reader consults the loop's skill or agent prompt
- **THEN** it finds the explicit norm that a denial is to be satisfied, not rephrased
  around
