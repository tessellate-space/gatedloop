## ADDED Requirements

### Requirement: A stalled halt says whether a fresh restart remains

A `stalled` halt row SHALL carry `restart_available`, computed by the shim from the
task's `restart` rows and `loop.fresh-restarts`, never supplied by the caller. `gates
stats --outcomes` SHALL report, per change, the number of restarts and how many of
them were followed by the task reaching a green `ci` and being committed. A restart
SHALL NOT be counted as an intervention.

#### Scenario: Halting with a restart left

- **WHEN** an implementer records `gates halt record stalled --task 1.2` and task 1.2
  has not been restarted under `loop.fresh-restarts: 1`
- **THEN** the halt row carries `restart_available: true`

#### Scenario: A restart that recovered

- **WHEN** task 1.2 was restarted and then reached a green `ci` and its task commit
- **THEN** `gates stats --outcomes` counts one restart and one recovered restart for
  the change, and no intervention
