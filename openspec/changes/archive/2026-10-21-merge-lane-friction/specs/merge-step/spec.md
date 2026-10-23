## ADDED Requirements

### Requirement: A merge step whose gate did not run is reported as not run

When the `ci` gate at step 3 or the `confirm` gate at step 5 of `gates merge` exits 75,
the merge SHALL restore the checkout, commit nothing, exit 75, and report that the
gate did not run, naming the lock holder and wait or the failed precondition. It SHALL
NOT report the merged tree as failed.

#### Scenario: The ci lock is busy past its bound

- **WHEN** step 3's `ci` cannot take the serialized lock within its bound
- **THEN** `gates merge` exits 75, names the holder, says nothing about the merged tree
  is known yet, and leaves the target and checkout unchanged

#### Scenario: The merged tree is red

- **WHEN** step 3's `ci` runs and exits 1
- **THEN** the merge reports the merged tree as failed, as before

### Requirement: A waiting merge takes a serialized lock before other waiters

While `gates merge` waits on a serialized gate's lock it SHALL hold a priority claim,
and any other waiter SHALL NOT acquire that lock while the claim's process is alive.
The current holder SHALL never be pre-empted, and a claim whose process is dead SHALL
be ignored. The merge's own wait SHALL be bounded by `concurrency.merge-wait-seconds`,
defaulting to `concurrency.max-wait-seconds`.

#### Scenario: A lane and a merge wait on the same lock

- **WHEN** a lane holds the `ci` lock, and a merge and a second lane are both waiting
- **THEN** when the lock is released the merge acquires it, and the second lane
  acquires it only after the merge releases it

#### Scenario: A stale claim

- **WHEN** a priority claim names a process that no longer exists
- **THEN** waiters ignore it and the lock is taken in the usual order

### Requirement: The permission scaffolding's checkpoint is the integrating command

`gates-init`'s permission scaffolding SHALL write its `ask` rule for
`Bash(gates merge *)`, not for every `git merge`. `gates doctor` SHALL warn when the
project's local settings still ask on `Bash(git merge *)`, naming the replacement.

#### Scenario: Scaffolding written fresh

- **WHEN** the adopter accepts permission scaffolding in `gates-init`
- **THEN** the written `ask` list is `["Bash(gates merge *)"]`

#### Scenario: An older scaffolding

- **WHEN** `.claude/settings.local.json` asks on `Bash(git merge *)`
- **THEN** the doctor's `merge-checkpoint` row warns and names `Bash(gates merge *)`
