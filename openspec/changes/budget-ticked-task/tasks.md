## 1. An implicit run after a ticked task is unbudgeted

- [x] 1.1 In `cmd_run`, when no `--task` is given and the latest started task is checked in `HEAD`'s `tasks.md` (`_blob_at` + `_checked_task_ids`), resolve the run's task to `None` before the budget check, so it is unbudgeted and its row carries `task: null`. Tests drive a real git repo on a change branch with a real ledger through the issue's sequence: all tasks ticked and committed, the last task's RED run, two red `ci` runs and its restart used, then a plain `gates run ci` runs the gate and records `task: null`; the same run with `--task` still refuses (design D1) [oracle: unit]
- [ ] 1.2 Tests pin the gaming route and the fail-closed paths: a task ticked only in the working tree (or staged, not committed) stays budgeted and refused; a missing `tasks.md` at `HEAD` stays budgeted (design D3) [oracle: unit]

## 2. Docs

- [ ] 2.1 In SETUP.md's "`loop.attempts` and `loop.fresh-restarts`" section, say a run with no `--task` belongs to the latest started task only while it is unchecked at `HEAD`, and that a run with `--task` is always budgeted (design D4) [oracle: none]
