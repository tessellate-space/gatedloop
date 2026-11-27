## ADDED Requirements

### Requirement: The merge removes the change's preflight branch

After its push publishes the change, `gates merge` SHALL delete the change's
`gatedloop/preflight/<change>` branch locally and, when the target's remote has it, on
that remote. A failed deletion SHALL be printed with the command to run and SHALL NOT
fail the merge.

#### Scenario: A direct merge

- **WHEN** `gates merge` publishes a change whose preflight branch exists locally and on
  the target's remote
- **THEN** both are deleted and the merge exits 0

#### Scenario: The deletion fails

- **WHEN** the remote refuses the branch deletion
- **THEN** the merge still exits 0 and prints the `git push --delete` command to run

#### Scenario: No preflight branch

- **WHEN** the change has no preflight branch
- **THEN** `gates merge` deletes nothing and prints nothing about it

#### Scenario: A local target

- **WHEN** the merge target has no remote and the preflight branch exists locally
- **THEN** `gates merge` deletes the local branch and attempts no remote deletion
