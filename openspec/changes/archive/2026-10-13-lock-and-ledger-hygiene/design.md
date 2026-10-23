# Design: lock-and-ledger-hygiene

## Decisions

### D1. The wait loop

Polling stays at 0.2 s, since acquiring the lock quickly matters. Printing is
decoupled from polling:

- **First line:** printed immediately:
  `specloop: waiting for gate 'ci' — held by pid 4312 (alive) for 3m12s`.
- **Later lines:** at most one every 30 s, with the same fields plus "waited 1m30s".
- **Liveness:** checked with `os.kill(pid, 0)`. `ProcessLookupError` means dead;
  `PermissionError` means alive but owned by another user.

A five-minute wait prints 11 lines at most, against today's roughly 1,500.

### D2. The bound, and why it's 480

The host's Bash tool call is capped at 600 s. When a gate's wait and run together
exceed that cap, the host backgrounds the gate. That's #33 item 6's root cause. A
480 s wait leaves 120 s of margin to report and exit.

The wait bound doesn't cover the gate's own runtime. A 250 s suite that starts after a
470 s wait can still exceed the cap. So `tdd-apply` and the implementer also carry the
foreground rule, which `hook-correctness` D8 adds. It's documented here too: pass the
Bash tool's longest timeout when invoking a gate.

On timeout the shim exits 75, which is EX_TEMPFAIL, "try again". The exit contract
already uses 75 for "the precondition failed, the environment isn't there". The two
are told apart by:

- **the message prefix,** `specloop: lock busy`, which is stable, is documented in
  SETUP.md's gate contract, and is tested verbatim;
- **the ledger row,** where `precondition` is `"lock-busy"`, so `gates stats` counts
  lock waits separately from environment failures.

A distinct exit code was considered and rejected. Adopters' wrappers and CI already
treat 75 as "not a code failure", and a new code would be a contract change for every
consumer.

`concurrency.max-wait-seconds` is added to `schema/gates.schema.json` as a positive
integer, validated by both parsers.

### D3. `gates lock status`

For each gate in `concurrency.serialize`, the command probes the lock with
`LOCK_EX | LOCK_NB` on a separate file handle, releasing it at once if it gets it:

- acquired → `free`, whatever the metadata says;
- not acquired → `held by pid N (alive|dead?) for 6h12m`.

A holder alive for more than an hour gets "possibly hung — inspect with `ps -o
pid,etime,command -p N`". It's the one place a command name appears, in output text
rather than a prompt, and `ps` is POSIX, not a stack tool.

Nothing breaks or kills the lock. An `flock` dies with its holder, so a crashed holder
never needs breaking, which the existing scenario "a crashed holder does not wedge the
machine" already relies on. A hung holder is a process a human decides about.
`--json` gives the same data for #37's dispatch state.

### D4. Git-layer parity

`templates/git-hooks/pre-commit` runs the same check the tool-level hook runs:

```sh
"${GATES}" discipline check-commit "${tree}"
```

It prints the verdict on success, and prints the denial followed by the existing
"rephrasing won't help" lines on failure.

`discipline check-commit` already covers the planning-grade and ledger-grade
allowances, plus the full marker check. With `hook-correctness`, it also covers the
worktree check and the stale diagnosis. The two layers share one implementation from
now on.

An adopter whose repo already has the old hook installed keeps it until the hook is
reinstalled. So `adoption-prompts` gains a catalogue item, `git-hook-refresh`, since
0.5.0. Its detector compares the installed hook's body against the template, and its
action runs `gates-init`'s hook-install step.

## Out of scope

- Hook matcher, stale diagnosis and worktree checks: `hook-correctness`.
- The merge recipe's detach refusal: `merge-step`.
