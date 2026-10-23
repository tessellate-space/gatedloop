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
