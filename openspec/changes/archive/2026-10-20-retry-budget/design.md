# Design

## Context

Today a task runs like this (`skills/tdd-apply/SKILL.md` §5, and `agents/tdd-implementer.md`, which follows it):
1. **RED:** `gates run unit --task <N.M> --attempt 1` must fail.
2. **GREEN:** implement, then `gates run unit --task <N.M> --attempt <n>`, incrementing `n` on each retry.
3. **Gate:** `gates run ci`, then convention review.
4. "If a gate stays red after 2 focused fix attempts, HALT" with cause `stalled`.

Every ledger row already carries `task` (inferred from the latest `task-start` when not passed) and `attempt`. Nothing reads them back to decide anything.

## Decisions

### D1. What counts as a failed attempt

For task `T`, a **failed attempt** is a red (`exit != 0` and `!= 75`) `unit` or `ci` row whose task is `T`, recorded:
- after `T`'s **first** red `unit` row since its latest `task-start`, which is the RED phase and is required, not a failure;
- after `T`'s latest `restart` row, if any.

Exit 75 (a down environment or a busy lock) is never an attempt, because the code under test wasn't judged. A green row doesn't reset the count: a task that goes green and then red again at `ci` is still the same task trying.

The count comes from the ledger alone. The caller's `--attempt` stays a label on the row, and a wrong value can't buy extra attempts.

### D2. The refusal

Before running `unit` or `ci` for task `T`, `gates run` computes the failed-attempt count. When it is `>= loop.attempts`, it:
- refuses without running the gate, so no ledger gate row is written;
- prints a single message:

  ```
  specloop: task 1.2 has used its attempt budget (2 failed attempts since its RED run).
    A fresh restart remains (1 of 1): `gates attempt restart 1.2` from a clean tree, in a new context that reads only `gates attempt notes 1.2`.
    Otherwise: halt with cause `stalled` (`gates halt record stalled --task 1.2 ...`).
  ```
- exits 1.

When no restart remains, the message names only the halt. The refusal is the stopping rule; `fail-loud-gates` holds because the run says exactly why it refused.

A run with no task (no `--task`, and no `task-start` to infer one) is never budgeted. That covers this repo's own `gates run ci` before a non-task commit, and every adopter not running the loop.

### D3. Attempt notes

```
gates attempt note <task> --hypothesis TEXT --changed TEXT --oracle TEXT --next TEXT
```

The command appends `{"gate": "attempt-note", "task": T, "attempt": <failed-attempt count>, "note": {...}}`. Each field is required, single-line and at most 200 characters; anything longer is refused rather than truncated. Notes are lessons, not transcripts: the four fields are the issue's own structure.

`gates attempt notes <task> [--json]` prints the task's notes oldest first, numbered by attempt, across restarts.

The loop writes a note after **every** failed attempt, before the next one. A resuming agent reads `gates attempt notes` before touching the task, so a crash-resume gets the same memory a restart does.

### D4. The fresh restart

```
gates attempt restart <task>
```

The command:
1. refuses unless the tree is clean and HEAD is the task's last commit, meaning the halt discipline already holds;
2. refuses when the task's `restart` rows already number `loop.fresh-restarts`;
3. otherwise appends `{"gate": "restart", "task": T}`, which resets D1's count.

**Who restarts.** The implementer never restarts itself: it can't spawn an agent, and restarting in the same context defeats the point. When the budget refuses, an implementer halts with cause `stalled`. The halt row gains `restart_available: true|false`, computed by the shim, not supplied by the agent.

The **dispatcher** then decides:
- `tdd-apply` (interactive), or an adopter's orchestrator, reading `restart_available`;
- it dispatches one fresh implementer whose brief holds the spec, the task and `gates attempt notes`, and nothing from the halted run;
- the fresh agent's first act is `gates attempt restart <T>`.

A restarted attempt that exhausts its budget has no restart left, so it halts `stalled` with `restart_available: false`, and a human gets it.

### D5. The budget

| Key | Default | Meaning |
|---|---|---|
| `loop.attempts` | `2` | failed attempts allowed per task, per context |
| `loop.fresh-restarts` | `1` | restarts allowed per task; `0` disables them |

Both are integers `>= 0`, validated by `gates validate`. `loop.attempts: 0` means the first failed attempt after RED refuses. That's legal but odd, and `gates validate` warns.

The defaults keep today's documented behaviour (2 attempts) and add exactly one restart.

### D6. Outcomes

`gates stats --outcomes` gains, per change:
- `restarts`: the number of `restart` rows;
- `restart-recovered`: restarts after which the task reached a green `ci` and was committed.

These answer #27's own question: does a fresh restart avoid an escalation often enough to be worth its cost? A restart is not an `intervention`, because no human acted.

### D7. Adoption

A catalogue item `retry-budget`, `since: 0.6.0`:

| Field | Value |
|---|---|
| detector | `manifest-key loop.attempts` |
| question | the attempt budget and fresh restarts |
| options | keep the defaults, 2 + 1 restart (Recommended); set my own; no restarts (`fresh-restarts: 0`) |

## Risks

- **Over-refusal while debugging a flaky gate.** Exit 75 is excluded, but a genuinely flaky red counts. That's deliberate: a flaky blocking gate is the adopter's to fix, and the refusal names the task and count so it's visible.
- **Notes that are useless or long.** The four required fields and the 200-character cap keep notes short. Their quality stays the agent's, the same as a commit message's.
