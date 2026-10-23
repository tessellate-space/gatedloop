## ADDED Requirements

### Requirement: A serialized gate's wait is rate-limited, informative and bounded

While a serialized gate waits for its lock, the shim SHALL print a waiting notice at
most once every 30 seconds. The notice SHALL name the holder's pid, how long the
holder has held the lock, whether the holder is alive, and how long this run has
waited. The wait SHALL end after `concurrency.max-wait-seconds`, which defaults to
480. The run SHALL then exit 75 with a message beginning `specloop: lock busy`, and
SHALL record a ledger row marking the precondition as `lock-busy`.

#### Scenario: A five-minute wait

- **WHEN** a serialized gate waits five minutes for its lock
- **THEN** it prints at most eleven waiting lines, each naming the holder and the
  elapsed times

#### Scenario: The bound is reached

- **WHEN** the wait exceeds `concurrency.max-wait-seconds`
- **THEN** the run exits 75 with a `specloop: lock busy` message and a `lock-busy`
  ledger row, and the gate command never ran

#### Scenario: An invalid bound

- **WHEN** `concurrency.max-wait-seconds` is not a positive integer
- **THEN** `gates validate` fails naming the key

### Requirement: The implementer retries a busy lock and halts on any other precondition

On an exit of 75 whose message begins `specloop: lock busy`, the implementer SHALL
re-run the same command, at most three times, before halting with cause
`environment`. Any other exit of 75 SHALL keep its meaning: the environment is absent,
so halt. The implementer SHALL run every gate in the foreground.

#### Scenario: A lane meets a busy lock

- **WHEN** a gate exits with `specloop: lock busy`
- **THEN** the implementer re-runs the identical command rather than halting or
  editing code

### Requirement: Lock state is inspectable, and the shim never kills a holder

`gates lock status` SHALL report, for each serialized gate, whether its lock is held,
and if so the holder's pid, how long it has been held, and whether the holder is
alive. It SHALL flag a holder alive for more than an hour as possibly hung and show a
command a human can use to inspect it. No `gates` command SHALL terminate a holder.

#### Scenario: A hung holder

- **WHEN** a live process has held the `ci` lock for six hours
- **THEN** `gates lock status` reports it as possibly hung, with its pid and age

#### Scenario: A free lock with stale metadata

- **WHEN** the lock is free but its metadata names a pid that has exited
- **THEN** `gates lock status` reports the lock as free

### Requirement: Both commit layers apply the same commit check

The git-layer commit hook SHALL run the same commit check as the tool-level commit
hook, including the ledger-grade and planning-grade allowances.

#### Scenario: A ledger-only commit through the git layer

- **WHEN** only `.specloop/runs/<change>.jsonl` is staged and the commit is created by
  a path the tool-level hook does not see
- **THEN** the git-layer hook allows it with the ledger-grade verdict, and no `ci` run
  is required
