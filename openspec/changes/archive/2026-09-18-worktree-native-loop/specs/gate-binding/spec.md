# gate-binding Delta Specification

## ADDED Requirements

### Requirement: The manifest may declare machine-level gate serialization

The manifest MAY declare a set of gates to serialize machine-wide across all
worktrees of the repository. When a declared gate runs, the shim SHALL hold an
exclusive lock shared by every worktree of the repository for the duration of the
gate's command — and only the command: recording evidence and ledger rows SHALL
happen outside the lock. A run waiting on the lock SHALL be visibly waiting, printing
a periodic notice naming the holder, never appearing hung. The lock SHALL be
implemented with standard-library facilities only, and where the platform offers no
such facility the shim SHALL degrade loudly to running unlocked, never fail the gate
for want of a lock. Absent the declaration, no locking occurs — behavior is exactly
today's.

#### Scenario: Two lanes contend for a serialized gate

- **WHEN** the manifest declares a gate as serialized and two worktree lanes invoke
  it concurrently
- **THEN** one runs while the other blocks, printing a periodic waiting notice naming
  the holder, and runs as soon as the lock frees

#### Scenario: An undeclared gate never locks

- **WHEN** the manifest declares no serialization, or a gate outside the declared set
  runs
- **THEN** the gate runs immediately with no lock taken, identical to today

#### Scenario: The declaration is validated

- **WHEN** the manifest's serialization block names a gate that is not declared in
  the manifest, or is malformed
- **THEN** `gates validate` exits non-zero naming the defect

#### Scenario: A crashed holder does not wedge the machine

- **WHEN** a process holding the lock dies without releasing it
- **THEN** a subsequent run acquires the lock without manual cleanup
