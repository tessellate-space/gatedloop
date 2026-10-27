# Spec Delta

## MODIFIED Requirements

### Requirement: Git-layer commit enforcement is scoped to agent sessions

The git `pre-commit` hook SHALL enforce only when an agent session is present in the
environment, and SHALL be a transparent no-op otherwise. An agent session is present
when any variable named in `discipline.agent-env` is set; the default list is
`[CLAUDECODE]`. This scoping is deliberate and SHALL NOT be treated as a silent skip:
the gate exists to hold an autonomous loop to its invariant, and outside a session no
such loop is running the commit.

#### Scenario: A commit inside a session is enforced

- **WHEN** a commit is attempted and `CLAUDECODE` is present in the environment
- **THEN** the git `pre-commit` hook applies the marker check

#### Scenario: A human or CI commit is not gated

- **WHEN** a commit is made from a plain terminal, an IDE, or a CI runner, with
  `CLAUDECODE` absent from the environment
- **THEN** the git `pre-commit` hook is a no-op and the commit proceeds unhindered

#### Scenario: Another host's agent is declared

- **WHEN** `.gates.yaml` declares `discipline.agent-env: [CLAUDECODE, OTHER_HOST_VAR]`
  and a commit is attempted with only `OTHER_HOST_VAR` set
- **THEN** the git `pre-commit` hook applies the marker check

#### Scenario: An invalid declaration

- **WHEN** `discipline.agent-env` is not a list of non-empty variable names
- **THEN** `gates validate` fails naming the key

## ADDED Requirements

### Requirement: A push to the merge target is gated at the git layer

Inside an agent session, a git `pre-push` hook SHALL deny a push that updates the merge target's branch unless the pushed commit is proven: a `merge` ledger row records that commit, or the merge gate's incoming-tree checks hold for the pushed commit's tree. Pushes of any other branch, deletions, and pushes outside an agent session SHALL pass untouched. The hook SHALL NOT run any gate.

#### Scenario: The shim's own merge push

- **WHEN** `gates merge` completed its steps and pushes the target
- **THEN** the hook finds the merge row for the pushed commit and allows the push

#### Scenario: A raw merge pushed without proof

- **WHEN** an agent merges a branch into the target by hand and pushes, with no merge row and no live-check marker for the pushed tree
- **THEN** the hook denies the push naming the unmet check and `gates merge` as the remedy

#### Scenario: A feature branch push

- **WHEN** an agent pushes a change branch in pull-request mode
- **THEN** the hook does nothing and the push proceeds

#### Scenario: A human push

- **WHEN** the target is pushed with no agent-env variable set
- **THEN** the hook is a no-op

### Requirement: Both git-layer hooks install and are diagnosed through one path

`gates hook install` SHALL install the `pre-push` hook beside `pre-commit` under the same owner detection, composition and refuse-and-instruct rules, and SHALL write the installing shim's path into each hook as the last fallback for resolving the shim. `gates doctor` SHALL report a `git-push-hook` row with the same states as the commit hook's row.

#### Scenario: A fresh install

- **WHEN** `gates hook install` runs in a repository with no hooks and no manager
- **THEN** both templates are installed, executable, and `gates doctor` reports both wired

#### Scenario: Only the commit hook is present

- **WHEN** a repository has the current `pre-commit` template and no `pre-push`
- **THEN** `gates doctor` reports the push hook absent, and the adoption catalogue offers to install it

#### Scenario: The recorded shim path is gone

- **WHEN** the shim path written into a hook no longer exists and neither the plugin root nor PATH resolves the shim
- **THEN** `gates doctor` reports the hook as stale and the refresh item offers to reinstall it

### Requirement: Enforcement coverage is documented per layer and host

Project documentation SHALL state, for each guarantee the loop makes, which layer enforces it: the tool-hook layer (Claude Code sessions), the git layer (any host, inside a declared agent session), or the forge (branch protection and published statuses). It SHALL say plainly which guarantees hold on a host other than Claude Code.

#### Scenario: An adopter on another host reads the docs

- **WHEN** an adopter runs the loop from a host that is not Claude Code
- **THEN** the documentation tells them the shim, the ledger, the commit and push gates and the forge statuses hold, and that the tool-hook denials (implement, scaffold, propose, archive, the Stop audit) do not

### Requirement: The push hook is opt-in and a decline sticks

The `pre-push` hook SHALL be installed only with the adopter's consent. `gates hook install --commit-only` SHALL install or refresh the `pre-commit` hook alone and record the `git-push-hook` adoption item as `declined`. While that item is recorded `declined`, a plain `gates hook install` SHALL skip `pre-push` and say how to add it; `gates hook install --push` SHALL install it and record `adopted`.

#### Scenario: Installing the commit hook only

- **WHEN** an adopter runs `gates hook install --commit-only`
- **THEN** only the `pre-commit` hook is installed or refreshed, and the `git-push-hook` item is recorded `declined`

#### Scenario: A re-install after a decline

- **WHEN** the `git-push-hook` item is recorded `declined` and an adopter runs `gates hook install`
- **THEN** only the `pre-commit` hook is installed or refreshed, the output says the push hook was skipped and names `gates hook install --push`, and no `pre-push` hook is written

#### Scenario: Opting back in

- **WHEN** an adopter who declined runs `gates hook install --push`
- **THEN** the `pre-push` hook is installed and the `git-push-hook` item is recorded `adopted`

#### Scenario: The doctor respects a decline

- **WHEN** the `git-push-hook` item is recorded `declined` and no `pre-push` hook is installed
- **THEN** `gates doctor` reports the `git-push-hook` row as ok, naming the decline, and does not warn

### Requirement: The git-layer hooks act only inside a declared agent session

The `pre-commit` and `pre-push` hooks SHALL check anything only when a variable named in `discipline.agent-env` (default `[CLAUDECODE]`) is set. Otherwise each SHALL exit 0 without checking, so commits and pushes made by a human in a terminal, from an IDE, or by a CI runner are untouched, whether or not the hooks are installed.

#### Scenario: A human commits and pushes the target

- **WHEN** no `discipline.agent-env` variable is set and a human commits code and pushes the merge target with both hooks installed
- **THEN** neither hook checks anything, and the commit and the push proceed

#### Scenario: A CI runner pushes

- **WHEN** a CI job without any `discipline.agent-env` variable set pushes any branch, the merge target included
- **THEN** the `pre-push` hook exits 0 without checking

### Requirement: Plan approval is unchanged by the git-layer hooks

This change SHALL NOT alter how a plan is approved. `approval.plan: self` local attestation, `review`, and a merge of the plan's pull request as its approval SHALL work exactly as before. The push gate SHALL check only a pushed commit's merge proof (a merge row or the incoming-tree checks), never how the change's plan was approved.

#### Scenario: A self-attested plan

- **WHEN** a project declares `approval.plan: self` and a maintainer runs `gates approval attest <change> --local`
- **THEN** the approval is recorded and checked exactly as before this change

#### Scenario: The push gate does not read the approval

- **WHEN** a change merged by `gates merge` is pushed to the target
- **THEN** the push gate allows it on its merge row alone, whatever approval policy the project declares
