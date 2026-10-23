# Proposal: lock-and-ledger-hygiene

## Why

#33 items 5–7 come from three lanes sharing one machine-wide `ci` lock. Each was
checked against the code.

- **The waiting notice floods and kills the gate** (item 5). `_gate_lock` prints
  "still waiting…" on every 0.2 s poll. A five-minute wait overflowed the agent's
  tool-output cap and killed the gate run. The notice doesn't say how long the lock
  has been held, so a hung holder (an orphaned suite blocked on a wedged socket,
  holding for 6.5 h) looks exactly like a busy one.
- **A long wait counts against the caller's tool timeout** (item 6). The Bash tool's
  600 s cap backgrounds the gate, and the implementer then ends its turn "waiting for
  the gate". This happened six times across lanes.
- **Ledger-only commits pay a full `ci` at the git layer** (item 7). The tool-level
  hook runs `gates discipline check-commit`, which already allows ledger-grade and
  planning-grade commits. The git-layer pre-commit hook runs only `gate-marker check
  ci`, so the same commit made by any other path is denied and costs a 129 s full run.
  The two layers are meant to enforce one rule, and they don't.

## What Changes

- **The waiting notice is rate-limited and says more.** At most one line every 30 s,
  giving the holder's pid, how long it has held the lock, whether that pid is alive,
  and how long this run has waited.
- **The wait is bounded below the host's tool timeout.**
  `concurrency.max-wait-seconds` defaults to 480. When it is exceeded, `gates run`
  exits 75 with a stable `specloop: lock busy` message, and writes a ledger row with
  `precondition: lock-busy`. The implementer re-runs the same command on a lock-busy
  exit, up to three times, and halts with `environment` after that. Any other exit 75
  keeps today's meaning: halt, environment.
- **`gates lock status`** shows, for each serialized gate, whether the lock is held,
  by which pid, since when, and whether that pid is alive. A holder that has been
  alive for over an hour is flagged "possibly hung", along with the command a human
  can use to inspect it. Specloop never kills a holder.
- **The git-layer pre-commit hook runs `gates discipline check-commit`,** the same
  check as the tool-level hook. So ledger-grade and planning-grade commits are allowed
  on every path, and the git layer gains every other check the tool layer has. That
  includes `hook-correctness`'s worktree check and self-explaining stale denials.

## Capabilities

### Modified Capabilities

- `gate-binding`: the serialization wait is bounded and rate-limited, and lock state
  is inspectable. The ledger-grade allowance holds at both commit layers.

## Impact

- `bin/gates`: `_gate_lock`, a new `lock status` subcommand, the lock-busy row, and
  `concurrency.max-wait-seconds` in the schema and validation.
- `templates/git-hooks/pre-commit` calls `discipline check-commit`. Adopters with the
  hook installed get the new body on their next `gates-init` hook install. The
  `adoption-prompts` catalogue gains an item to reinstall it.
- `agents/tdd-implementer.md` and `skills/tdd-apply/SKILL.md`: the lock-busy retry
  rule.
- `tests/`: the lock wait, the bound, status, and git-layer parity.
- Ships in 0.5.0.
