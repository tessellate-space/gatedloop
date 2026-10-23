# Design: acceptance-gate

## Context

See proposal.md — Why. What this design builds on, all in `bin/gates`, `hooks/` and
the specs:

- **Plan approval's shape** (`approval-policy`, `loop-enforcement` "Approval is attested
  from the forge"): a policy in the manifest selects which *writers* are legitimate;
  the writers compute the pin themselves (`_approval_sha_worktree`), record identity
  from the forge review (`--pr`) or git config (`--local`), and fail closed when the
  forge is unreachable. `cmd_approval_attest_local` already appends an
  `approval-local` ledger row — attestation writing to the ledger has a precedent.
- **Trees, not content.** The merge gate compares ledger-normalized trees
  (`_normalize_tree`, fix-marker-mechanics D1, made checkout-independent in
  fix-normalize-tree-checkout-dependence). Everything under `.specloop/runs/**` is
  stripped before hashing, so a ledger row can never stale a marker.
- **`hooks/gate-merge.sh`** runs three O(1) checks on the incoming tree: live-check
  marker, unscoped `ci` marker, taint. It resolves the incoming ref's tree first, HEAD's
  as fallback (design D4 of that change), and every check speaks about the one tree that
  matched.
- **`escalation-outcomes`** (issue #23) adds `cause`/`detail` row fields, the closed
  cause set `HALT_CAUSES`, and `outcomes_from_rows` with `merged` as the terminal
  event. This change assumes it has landed.
- **The verify skill's Layer 1** is prose: find `#### Scenario:` titles, confirm each
  appears (case-insensitively) in the project's acceptance directory. The rule is
  deterministic; only its home is a prompt.
- **`.openspec.yaml`** carries `approved_by`/`approved_at`/`approved_sha`, written by
  `_write_approval_keys`. It is a file inside the tree.
- Constraints: `zero-dep-shim`, `fail-loud-gates`, `stack-agnostic-prompts` (the brief
  may name no test runner or artifact format), the O(1) hook budget, and the documented
  report shape for headless callers.

## Goals / Non-Goals

**Goals:**

- Acceptance is attested from a human act, content-pinned to the tree, never
  self-reported — the same standard as plan approval.
- The human sees behaviour, in scenario language, generated from data the shim owns.
- Merge requires acceptance exactly where a project says so, and nowhere else.
- The north-star metric can end at *accepted*.

**Non-Goals:**

- Any change to plan approval.
- Judging whether an acceptance artifact actually asserts a scenario's outcome —
  issue #26. The brief says what `covered` does and does not mean.
- Linking screenshots, traces or recordings into the brief. That needs a stack-blind
  gate-output contract (issue #28's territory); the brief leaves a documented seam.
- A new LLM agent, or an LLM-authored brief.
- Acting on a rejection (re-planning, re-running) — the reject row is an escalation
  for `--outcomes` and the human; issues #27/#69 own what happens next.

## Decisions

### D1: Acceptance is opt-in, declared next to plan approval

`approval.acceptance: review | self`, optional, in the existing `approval` block.
Absent means nothing is required and nothing changes. `gates validate` rejects other
values, and rejects `review` when the integration mode is `local-squash-merge` (or
`integration` is absent) — there is no pull request whose review could be read, so
the configuration is unsatisfiable and must fail at validate time, not at the first
merge.

One deliberate asymmetry with plan approval: the *plan* gate never reads the policy
(only the writers do), because plan approval is always required. The *acceptance*
gate must read the policy to know whether to require anything at all, because
acceptance is opt-in. `_acceptance_policy(m)` returns `None | "review" | "self"` and
`gates acceptance check` consults it. Once declared, the check itself is
policy-blind again: it reads rows, never the policy's value.

**Alternative — always required:** rejected. Half the field-trial repos are solo and
already attest plans with `--local`; forcing a second ceremony on every merge before
the brief has proven itself would make the boundary a tax. Opt-in, like the
permission scaffolding and the git-layer hook.

**Alternative — a separate top-level `acceptance.policy`:** rejected; the manifest
already has a block for "who approves what", and `acceptance` (top level) is kept for
the one thing that is not a policy — where the artifacts live (D5).

### D2: The record is a ledger row, because the pin is a tree

Plan approval pins a hash of *content* (`proposal.md`, `design.md`, `specs/**`) and
writes its keys into `.openspec.yaml`, which is excluded from that hash. Acceptance
must pin the *tree* — what will be merged — and every file inside the tree is part of
it. Writing `accepted_tree` into `.openspec.yaml` would change the tree the value
pins: a circular dependency with no fixed point short of stripping `.openspec.yaml`
from the normalization too, which would widen a rule that exists for exactly one
directory.

The ledger is already stripped from every normalized tree and already survives the
squash-merge. It is the one place an acceptance can be recorded without invalidating
itself. Row shape: `gate: "acceptance"`, `exit: None`, `verdict: "accept" | "reject"`,
`tree: _normalize_tree(root, _head_tree(root))`, `accepted_by`, and on reject
`cause` ∈ {`weak-spec`, `missing-oracle`} plus required `detail`. `accepted_by` is
appended to `LEDGER_ROW_FIELDS` (union rule); `acceptance` joins `NON_GATE_EVENTS`.

Why only two causes on reject: at acceptance the code has already passed every
declared oracle. If the human says no, either the spec asked for the wrong thing
(`weak-spec`) or the spec was right and nothing checked it (`missing-oracle`). The
other four causes describe the loop's own stopping, which is over by now.

**Alternative — `.openspec.yaml` keys plus a wider normalization:** rejected as above.

**Alternative — a git note or tag on the accepted commit:** rejected. Notes and tags do
not survive a squash-merge as ledger rows do, and they would be a second store to
keep honest (the same objection that put review verdicts in the ledger).

### D3: Writers mirror plan approval's, one code path per concern

- `gates acceptance attest <change> --local`: legitimate only under `self`; `tree`
  computed by the shim; `accepted_by` from `_local_git_identity` (an optional `--as`
  display override, never touching the tree, as today); refuses under `review` naming
  `--pr`; refuses under no policy naming the key.
- `gates acceptance attest <change> --pr <n>`: reads `gh pr view <n> --json reviews`,
  takes the first `APPROVED` review's author and `submittedAt`, fails closed on a
  missing/unauthenticated/offline `gh` or no approving review, rejects `--as`. Legitimate
  under both `review` and `self` — a real review is always acceptable evidence.
- `gates acceptance reject <change> --cause <c> --detail <t>`: legitimate under either
  policy; refuses other causes and empty detail. Identity recorded as for `--local`.

The forge-reading code is shared with `cmd_approval_attest` (one helper that returns
the first approving review or a reason), so the two attestations cannot drift in what
they accept as a review.

**Alternative — accept via a PR label or a slash comment:** rejected for now. A label
is a click anyone with triage rights can make; a review is the forge's own record of
who read what. Labels can be a later writer if a team needs one.

### D4: The merge gate gains one policy-aware, O(1) check

`gates acceptance check <tree>`: exit 0 with "acceptance not required" when the policy
is undeclared; otherwise read the ledger, take the *latest* `acceptance` row whose
`tree` equals `_normalize_tree(<tree>)`, exit 0 on `accept`, exit 1 naming the cause
on `reject`, exit 1 naming the remedy when none matches. `hooks/gate-merge.sh` calls it
after the taint check on `${matched_tree}` — the same tree the live-check marker and
the unscoped-`ci` marker matched, so all four pieces of merge evidence speak about one
tree. It is a file read; no gate runs.

The `ask` permission rule on `git merge` stays. The ask proves a human is present when
the merge happens; the accept row proves a human read the behaviour and said yes,
possibly hours earlier and possibly a different human. They answer different
questions.

The forge path (`gh pr merge`, forge UI) is not covered by any local hook; the existing
requirement says branch protection covers it. This change extends that documentation:
under `acceptance: review` the required review *is* the acceptance review, and
`gates acceptance attest --pr` is how it reaches the ledger.

**Alternative — check acceptance in the commit hook too:** rejected. Acceptance is
about the increment, not a task; per-task commits continue to be gated by `ci` alone.

### D5: The brief is a deterministic view the shim generates from what it owns

`gates acceptance brief <change> [--out <path>]`:

1. **Scenarios** — walk `openspec/changes/<change>/specs/**/spec.md`, collect `####
   Scenario:` titles per capability. Deterministic ordering (path, then file order).
2. **Coverage** — if the manifest declares `acceptance.match` (a glob), read every
   matched file and extract scenario titles from lines that begin with a documented
   marker set (`Scenario:`, `Scenario Outline:`, `#### Scenario:`, `- Scenario:`)
   followed by the title; compare case-insensitively with surrounding whitespace
   trimmed. This is the verify skill's Layer 1 rule moved from prose into code. A
   match is `covered`; otherwise `check by hand`. No `acceptance.match` → everything
   `check by hand`, with the reason stated.
3. **Verdicts for this tree** — from the ledger, the latest `verify`, `live-check`,
   `integration`, `ci` rows whose `tree` equals the current head's normalized tree
   (gate, exit, ts) and the latest `review` row on that tree; each `absent` when none.
4. **Check these by hand** — every uncovered scenario, listed once.
5. **Footer** — what `covered` does and does not mean (an artifact of that name exists
   and the declared gate ran green on this tree; it does not mean the artifact asserts
   the scenario's outcome — issue #26), and that no artifact links are included yet.

Byte-identical for the same specs, ledger and head tree: no clock, no locale, sorted
keys. `--out` defaults to stdout; the documented file location is
`.specloop/runs/<change>.acceptance.md` — inside the ledger-blind prefix, so committing
the brief cannot change the accepted tree (the `stats` reader globs `*.jsonl` only, so
the file is inert to it). The brief is *not* hashed into the acceptance; the tree is
what is accepted, and the brief can always be regenerated from it.

Stack-agnostic by construction: the shim knows a glob and a marker set, never a
format or a runner.

**Alternative — the implementer writes the brief:** rejected; self-reported evidence
is what this change removes. **Alternative — join per-scenario results from gate
output:** deferred; needs an optional results contract (issue #28) and would put a
format assumption into the shim.

### D6: The loop generates the brief and stops where the policy says so

`skills/tdd-apply/SKILL.md` §7.5, between step 2 (live-check) and step 4 (read the
declared process): run `gates acceptance brief <change>` and show it; then, if
`gates acceptance policy` prints a declared policy, **stop before integration** until
`gates acceptance check` passes — the same boundary as `requireApproval: true`, and
the same wording. `agents/tdd-implementer.md` §4: generate the brief as the last act
before the final report; the report gains `"acceptance": "required" | "not-required"`
read from the policy. Both edits are a few sentences and name only `gates` commands.

`skills/verify/SKILL.md` Layer 1 stops restating the match rule and points at
`gates acceptance brief` for the coverage list, keeping its verdict format.

### D7: The outcomes view ends at acceptance where declared

`outcomes_from_rows` takes the acceptance policy as an argument (pure function; the
caller reads the manifest). Under a declared policy: `accepted` when an `accept` row's
tree equals the `merge` row's tree; `merged` otherwise when a `merge` row exists;
hands-off requires `accepted`; the share is accepted ÷ (merged + accepted); `reject`
rows count under halts by their cause. Undeclared: unchanged, and the human report
states the metric ends at `merged` for that reason.

The join on the merge row's tree rather than "any accept row" is what makes *accepted*
mean *this is what shipped*: an acceptance of an earlier tree followed by an edit and
an unaccepted merge is `merged`, not `accepted`.

### D8: Deliberately left out

Plan approval untouched; the brief not hashed or required to be committed; no artifact
links (seam: a per-gate `artifacts:` glob, later); no adequacy judgement (#26); no new
agent; no label/comment writers; no change to per-task commit gating.

## Risks / Trade-offs

- [A `local-squash-merge` project attests with `--local` and the human never reads the
  brief] → The brief is printed by the loop before it stops; `--local` is the solo
  policy, where the same person is the approver — `self` is the honest declaration of
  that, exactly as for plans.
- [The tree pin is too strict: committing the brief or a ledger row after acceptance
  breaks it] → Both live under `.specloop/runs/**`, which the normalization strips.
  Anything else changing the tree *should* break it — that is the content pin.
- [`gates acceptance check` reads the whole ledger under the hook budget] → One file,
  small; the taint check already does the same read in the same hook.
- [Coverage by title match is weak] → It is the existing rule, now in code and
  labelled honestly in the footer. Weak-but-stated beats absent; adequacy is #26.
- [Two in-flight changes touch `outcomes_from_rows` and the final report] → Ordered:
  this change's specs include `escalation-outcomes`' text and add to it. Land #23
  first; this one's tasks say so.
- [The marker set for acceptance titles misses a team's format] → It is documented
  and small; a miss reads as `check by hand`, never as a false `covered`.

## Migration Plan

Ship after `escalation-outcomes`. Additive: a new manifest key pair, a new subcommand
family, one new row field, one new hook check that passes when undeclared. Nothing
changes for a project that does not declare `approval.acceptance`. Rollback is
reverting the release; acceptance rows already written are ignored by old readers via
the fixed-shape lookup.
