# gate-preconditions — design

## Context

See proposal.md — Why. The relevant current state in `bin/gates`:

- Gate values and surface `live-check` values are scalar strings everywhere:
  `_errors` enforces "gate '<name>' must be a non-empty command string";
  `cmd_run` does `gates.get(gate)` and `s["live-check"]` and hands the string to
  `_exec`.
- `cmd_run` writes a marker on green (`ci` on the staged-index tree,
  `live-check` on the head tree) and appends one ledger row per run with fields
  `ts, gate, exit, duration_ms, change, task, tree, attempt, approved_by, sha`.
  Taint resolution (`_maybe_resolve_taint`) joins on green `ci` rows.
- YAML parsing is two paths that must agree: PyYAML when importable, else
  `_mini_yaml`. `_mini_yaml`'s `_scalar` parses inline flow **lists** (`[...]`)
  but not flow **mappings** (`{...}`) — today `integration: {run: x, requires: y}`
  on a PyYAML-less machine parses to the literal string `{run: x, requires: y}`
  and would be executed as a shell command. Block mappings nest fine through
  `parse_map`.
- Binding conventions: `zero-dep-shim` (stdlib only), `fail-loud-gates`,
  `stack-agnostic-prompts` (shipped prompts say only `gates run <gate>`).

## Goals / Non-Goals

**Goals:**

- One normalizer through which every consumer of a gate/live-check value goes,
  so scalar vs mapping is decided in exactly one place.
- A precondition failure that is machine-distinguishable at every layer the
  loop reads: exit code, stderr message, marker absence, ledger row shape.
- Parse-path agreement guaranteed by tests, since `_mini_yaml` is the
  conditional code path this repo exists to test.

**Non-Goals:**

- No retry/backoff, no "boot the environment" automation — the shim reports;
  the adopter's `requires` command owns remediation text.
- No per-gate timeout, no multiple `requires` entries (a list can come later if
  ever needed; one command can already chain with `&&`).
- No changes to hooks, commit gates, or the enforcement layer — a precondition
  failure writes no marker, so existing enforcement is correct by construction.
- No new CLI surface: `gates run <gate>` is unchanged in invocation.

## Decisions

### D1 — Both mapping forms are supported; `_mini_yaml` learns the flow-mapping subset

The issue's own example uses the inline flow form
(`integration: { run: ..., requires: ... }`), and PyYAML users will naturally
write it. Restricting the documented shape to block form only would still leave
the flow form *valid YAML* that PyYAML parses into a mapping while `_mini_yaml`
returns a string — the exact "parses differently depending on which machine you
run on" corruption class `tests/` exists to prevent. So `_scalar` is extended to
parse a **single-level flow mapping with scalar values**: split on top-level
commas (quote-aware, reusing the same discipline `_strip_comment`/`_has_bare_colon`
already implement), then split each entry on the first colon outside quotes.
Nested flow mappings and flow lists inside a flow mapping are out of the subset
and fail loudly.

Fail-loud backstop, both paths: whatever the parser returns, `_errors` rejects a
gate/live-check value that is a *string beginning with `{`* — a mapping the
fallback (or a typo) failed to parse must never validate as a command. This
makes "silently degrade to a string and execute it" impossible even if a manifest
sneaks past an exotic YAML edge.

*Alternative considered*: block form only, with the flow form rejected at
validate. Rejected because PyYAML-equipped machines would parse the flow form
fine, so validate would have to detect "this dict came from flow syntax", which
it cannot — the restriction would be unenforceable on half the installs.

### D2 — One normalizer, used by every consumer

`_gate_spec(value) -> (run, requires)`: a string normalizes to `(value, None)`;
a dict to `(value["run"], value.get("requires"))`. `cmd_run` (both the named-gate
branch and the live-check branch), `_errors`, and anything that prints a gate's
command (`cmd_surfaces`' live-check display) go through it. `eval`'s
`{dataset}`/`{score}` substitution and extra-arg appending apply to the
normalized `run` string, unchanged.

Validation in `_errors` (all-errors-at-once style, consistent with the file):
mapping form requires `run` non-empty string; `requires`, if present, non-empty
string; any other key is an error naming the gate/surface and the key.

### D3 — Distinct exit path: reserved exit code 75, and a discriminated ledger row **is** written

**Exit code**: 75 (`EX_TEMPFAIL` from BSD sysexits — "temporary failure, retry
later") is reserved and documented in SETUP.md's gate contract. It is the right
semantic (the verdict is "try again once the environment is up", not "the code
is wrong"), and scripts/agents can branch on it. A gate body could itself exit
75; the collision is accepted and documented — the stderr line
`specloop: precondition '<cmd>' failed (exit N) — gate '<gate>' was not run`
plus the ledger row are the authoritative discriminators, the exit code is the
cheap first-class signal. Adopters who declare `requires` are told the shim owns 75.

**Ledger**: the issue requires "no ledger row *claiming the gate was
exercised*". Writing *nothing* would make an unattended halt unreconstructible
from the durable record — the ledger's whole purpose (it is the audit trail of
why a run stopped). So the shim writes a row that claims the opposite, with an
explicit discriminator:

```json
{"ts": ..., "gate": "<name>", "exit": 75, "outcome": "precondition-failed",
 "precondition": "<requires cmd>", "precondition_exit": N,
 "duration_ms": ..., "change": ..., "task": ..., "tree": null, "attempt": ...,
 "approved_by": ..., "sha": null}
```

Safety by construction: `exit` is non-zero so it can never read as green, never
satisfies `_maybe_resolve_taint` (which joins on green `ci` rows), and `tree` is
null so no tree-join can match it; `outcome` makes it unmistakable to a human or
agent reading the ledger. Existing row consumers filter by the fields they know
(`exit == 0`, `gate == "task-start"`, …), so an additive field is compatible.
*Alternative considered*: write no row. Rejected — it trades a durable
explanation of a halt for nothing, and the distinguishability requirement is met
by the field, not by absence.

**No marker** is written on a precondition failure (nor on any non-green run —
unchanged), so no PreToolUse/commit-gate check can be satisfied by one.

### D4 — Live-check runs preconditions per hot surface, before any probe body

In the `live-check` branch, each hot surface's spec is normalized; every
declared `requires` runs first. If any fails, the run reports each failure,
runs **no probe bodies at all**, writes no marker and exits 75 with one
precondition-failure ledger row (`gate: "live-check"`, `precondition` listing
the failed command(s)). Rationale: live-check is a change-completion blocking
gate; a partial "some probes ran" state on a down environment is noise, and the
remedy (boot the stack) is the same for all of them. When every precondition
passes, probe execution is exactly today's (all probes run, `or`-accumulated rc).

*Alternative considered*: run probes for surfaces whose preconditions passed.
Rejected — it mixes "gate failed" and "environment absent" in one run, which is
the ambiguity this change exists to remove.

### D5 — The universal rule is one paragraph in two prompts

`skills/tdd-apply/SKILL.md` and `agents/tdd-implementer.md` each gain the same
rule, stated once: **exit 75 / "precondition failed" means the environment was
absent — fix or boot the environment, never the code; do not retry the gate
unchanged and do not investigate the gate body's output as if it were a test
failure.** The autonomous implementer HALTs at the task boundary with a clean
tree and reports the shim's message verbatim (it cannot ask the user, and
booting an environment is a stack action it must not invent). The interactive
skill surfaces it to the user as an environment problem, distinct from red.
Stack-agnostic: the prompts name the exit path, never any command.

### D6 — Schema mirrors the shim

`schema/gates.schema.json`: gate values and `live-check` become
`oneOf: [non-empty string, {run: string(required), requires: string},
additionalProperties: false]`. The shim's `_errors` remains the runtime
authority (the JSON schema is documentation plus editor tooling, as today).

### D7 — Tests target the branches

New stdlib-only module `tests/test_gate_preconditions.py` (SourceFileLoader
pattern, as the existing suite):

- `_mini_yaml` vs PyYAML agreement on block and flow mapping forms, including
  quoted values containing commas/colons (skip-if-no-PyYAML guard for the
  agreement half, as `test_manifest.py` does).
- `_scalar`/flow-mapping edge: unparseable `{...}` fails loudly, never a string.
- `_errors`: accepts both shapes; rejects missing/empty `run`, empty `requires`,
  unknown keys, and a string value beginning with `{`.
- `cmd_run` named-gate path with a stub manifest and temp repo: requires-pass →
  gate runs, today's semantics; requires-fail → exit 75, no marker file, ledger
  row has `outcome: precondition-failed` and no green claim; scalar gate →
  untouched behavior.
- `cmd_run live-check` path: hot surface with failing `requires` → no probe run,
  exit 75, no marker.

## Risks / Trade-offs

- [Exit-code 75 collision: a gate body that itself exits 75 reads as a
  precondition failure to a script branching only on the code] → the shim's
  stderr line and the ledger row's `outcome` field disambiguate; SETUP.md
  documents 75 as reserved when `requires` is declared. Accepted as the cost of
  a single-integer contract.
- [`_mini_yaml` grows — every line added to the fallback is conditional code
  invisible on PyYAML machines] → this is precisely the class `tests/` covers;
  the agreement tests pin both paths to the same output.
- [A `requires` command that is slow or hangs delays every gate run] → the
  adopter owns the command (stack-blindness); the guidance in SETUP.md and the
  template says a precondition should be a fast probe, not a suite.
- [New ledger field surprises an external ledger reader] → the row shape is
  additive and non-green; the repo's own consumers already filter on known
  fields. Documented in the ledger comment block in `bin/gates`.

## Migration Plan

Purely additive. Every existing `.gates.yaml` validates and behaves
identically (scalar path is untouched). No deprecations, no version bump of
`gatesVersion` (shape is extended, not changed). Rollback = revert the commit;
manifests that adopted the mapping form would then fail validate loudly (never
silently), which is the correct failure direction.

## Open Questions

None — a list-valued `requires` and precondition timeouts are deliberately
deferred, not undecided (Non-Goals).
