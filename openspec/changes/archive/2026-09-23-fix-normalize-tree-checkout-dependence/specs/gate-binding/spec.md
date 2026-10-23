## MODIFIED Requirements

### Requirement: Marker freshness is blind to the durable ledger

The tree hash a gate marker records, and the tree hash a marker check compares
against, SHALL exclude every path under `.specloop/runs/**` (the durable ledger).
The normalization SHALL be applied identically when the marker is written and when
it is checked, so the compare remains a single hash equality. Any delta outside
`.specloop/runs/**` SHALL still invalidate the marker exactly as today.

The normalization SHALL be a pure function of the tree it is given: the same tree
SHALL normalize to the same hash regardless of which branch is checked out, what the
working tree contains, or what the real index holds — in particular, regardless of
whether any change's ledger under `.specloop/runs/**` differs between the tree being
normalized and the current checkout. A marker written on a change branch's head
SHALL therefore match a check of that same head run from the merge target.

If the normalization cannot be performed, the check SHALL fall back to the
unnormalized tree (which can only deny, never pass an unnormalized ledger delta)
AND SHALL report the failure on stderr naming the failing step, so a denial it
causes is attributable — it SHALL NOT be swallowed silently.

#### Scenario: Staging the gate's own ledger row keeps the marker fresh

- **WHEN** a green `gates run ci` writes a marker and appends its ledger row, and the
  row is then staged alongside the task's files
- **THEN** the commit gate's marker check still matches — the ledger row is the only
  delta and it is outside the compared hash

#### Scenario: Committing the merge ledger row does not restart the chase

- **WHEN** a green `gates run live-check` has written its marker and the run's ledger
  row is subsequently committed
- **THEN** the live-check marker still matches the resulting head tree

#### Scenario: A real edit still stales the marker

- **WHEN** any tracked path outside `.specloop/runs/**` changes after the marker was
  written
- **THEN** the marker check fails as stale, exactly as before

#### Scenario: The same tree normalizes identically from the branch and from main

- **WHEN** a change branch's head tree carries a ledger file under `.specloop/runs/`
  whose content differs from the same file on the merge target, and that head tree
  is normalized once with the branch checked out and once with the merge target
  checked out
- **THEN** both normalizations yield the same hash, equal to the head tree with every
  `.specloop/runs/**` entry removed

#### Scenario: A live-check marker written on the head satisfies the merge gate from main

- **WHEN** `gates run live-check` passes green on a change branch's head whose
  ledger diverges from the merge target's, and the squash-merge of that branch is
  then attempted from the merge target
- **THEN** the merge gate's marker check matches on the first attempt, without
  re-running the gate

#### Scenario: A normalization failure is reported, not swallowed

- **WHEN** the ledger-stripping step fails for any reason during a marker write or
  check
- **THEN** the unnormalized tree is used (denying rather than passing) and a one-line
  stderr message names the failed step, so the resulting denial can be traced to it
