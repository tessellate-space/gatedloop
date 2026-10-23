# Proposal: solo-approval-mode

## Why

Three field-trial issues describe one gap from three sides: the approval machinery
assumes a forge PR and a second human. #3 — in a remoteless solo repo the only
legitimate writer of `approved_by`/`approved_at`/`approved_sha` is `gates approval
attest --pr`, which hard-requires a GitHub PR with an `APPROVED` review, so the solo
workflow forces exactly the hand-edit the D12 guarantee assumes nobody does. #6 — a
solo developer who has issued standing consent gets no way to declare it, so the
policy lives in an orchestrating session's memory, "exactly the kind of undeclared
convention specloop otherwise refuses to tolerate". #4 — once a plan *is* approved,
nothing surfaces "spawn the lower-tier implementer" as the next action, so top-tier
sessions hand-run a loop the plugin purpose-built a Sonnet agent for. #3 gives the
writer, #6 the policy, #4 the routing; together they make solo mode a declared,
first-class configuration instead of three workarounds.

## What Changes

- **A declarable plan-approval policy.** `.gates.yaml` gains an `approval:` block —
  `plan: review` (today's behavior, the default when absent) or `plan: self` (solo:
  standing self-approval). `gates validate` checks the shape; nothing else in the
  manifest changes.
- **A local attestation writer.** `gates approval attest <change> --local` computes
  `approved_sha` over the change's artifacts (the existing D12 computation), records
  the configured git identity and timestamp, and writes the keys machine-side — valid
  only when the declared policy is `self`; under `review` it refuses and names the PR
  path. Content-pinning is unchanged: a post-approval artifact edit still invalidates.
- **Onboarding asks who approves plans.** `/specloop:gates-init` asks the approval
  question alongside the existing integration-mode question and writes the block; the
  answer is declared once, not re-litigated per change.
- **The session brief routes approved work to the implementer.** When a change is
  approved and unimplemented (approval keys valid, tasks unchecked), the brief and
  `/specloop:start` present spawning `tdd-implementer` as the default action for it —
  making the cheap path the discoverable path. (Per-task model tiering from #4 is
  explicitly deferred to `docs/candidates.md`.)

## Capabilities

### New Capabilities

- `approval-policy`: plan approval is a declared policy read from the manifest — who
  approves, which attestation writers are legitimate under each policy, and how the
  keys stay content-pinned — rather than a convention held in a session's memory.

### Modified Capabilities

- `onboarding`: the bootstrapper asks how plans are approved (beside the existing
  "how does a change reach main" question) and writes the declared policy; the session
  brief surfaces "approved + unimplemented → spawn the implementer" as a default menu
  entry.

## Impact

- `bin/gates`: `approval attest --local`, policy read + validation; `tests/` covers
  policy resolution, the refusal under `review`, and sha-pinning under `self`.
- `commands/gates-init.md` (question + written block), `commands/start.md` +
  `hooks/_session_brief.py` (routing entry), `agents/tdd-implementer.md` untouched.
- `SETUP.md`: the solo procedure becomes documented and sanctioned (closes #3's
  fallback ask); `schema/gates.schema.json` gains the optional `approval` block.
- `docs/candidates.md`: per-task tiering recorded with reasons to wait.
- D10's gate itself is unchanged — it still requires valid, content-pinned approval
  keys on the merge target; only the set of legitimate writers becomes
  policy-dependent.
