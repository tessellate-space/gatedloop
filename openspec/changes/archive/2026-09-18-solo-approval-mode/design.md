# Design: solo-approval-mode

## Context

See `proposal.md` — Why. Constraints that shape the approach: the D12 attestation
machinery (sha computation over the change's artifacts in a stated order, keys in the
change's `.openspec.yaml`, the D10 gate refusing on mismatch) already exists and is
merged; `gates approval attest --pr` reads the approving review from `gh`; the shim is
stdlib-only; the shim's own docstring currently concedes that a hand-edit with a
correctly computed sha passes — the "illegitimate writer" is a social claim, not a
mechanical one.

## Goals / Non-Goals

**Goals:** make the solo path a declared policy with a machine writer, keeping every
existing guarantee except the pause (content pin, merge-target requirement, audit
trail); make the delegation to the Sonnet implementer the discoverable default for
approved work; one new manifest block, validated.

**Non-Goals:** per-task model tiering and escalation (recorded in
`docs/candidates.md`); multi-policy per change kind; weakening `review` mode in any
way; authenticating *who* ran the local attestation beyond the configured git
identity — a solo repo has no second party to defend against, and `review` mode
remains the answer where one exists.

## Decisions

### D1: The policy lives in `.gates.yaml`, not `openspec/config.yaml`

The block is read by the shim at gate time and validated by `gates validate`; the
manifest is the file the shim already owns and validates. `openspec/config.yaml`
belongs to the authoring side and is consumed by OpenSpec, which never reads approval.
Shape:

```yaml
approval:
  plan: self   # or: review (default when the block is absent)
```

**Rejected — `.openspec.yaml` per change:** policy is a standing property of the
project, not of one change; per-change declaration reintroduces the per-change human
turn the policy exists to remove.

### D2: `--local` is a writer, not a bypass — the gate stays identical

`gates approval attest <change> --local` computes `approved_sha` with the existing
D12 computation, sets `approved_by` from `git config user.name`/`user.email` (or an
explicit `--as <name>`, which never affects the sha), and `approved_at` from the
clock. The D10 gate does not learn about policies: it keeps checking key presence and
sha match. Only the *writer* consults the policy — `--local` refuses under `review`,
`--pr` works under both (a solo dev may still use PRs). This keeps the enforcement
surface unchanged and the policy surface small.

**Rejected — the gate reading the policy and skipping the check under `self`:** that
deletes the content pin, which is the half of D12 worth keeping when no reviewer
exists (post-approval edits must still invalidate).

### D3: The honesty note moves from docstring to docs

With a sanctioned writer, the shim's concession ("a hand-edit with a correctly
computed sha passes") becomes the documented boundary: Specloop attests *content*,
and under `self` it attests identity only as strongly as the local git config —
stated plainly in `SETUP.md` next to the policy block, per the repo's habit of
documenting what a guarantee does not cover (AUTOMATION.md precedent).

### D4: Brief routing reads data that already exists

The session brief (`hooks/_session_brief.py`) and `commands/start.md` already parse
change state. "Approved + unimplemented" is: approval keys present, `gates approval
sha` matches, zero `[x]` in `tasks.md`. The brief entry names the change and offers
the spawn as default with the interactive loop as alternative — wording mirrors the
existing apply-ready menu entry, and nothing auto-starts (the existing "never start
either path unprompted" rule holds).

**Rejected — auto-spawning the implementer from a hook:** turns a routing hint into
an unattended actor the user never dispatched.

## Risks / Trade-offs

- **[Self-approval weakens the second-party guarantee]** By declaration, that is the
  point — but only where declared: `review` stays the default, the block is visible
  in the manifest diff, and `--local` refuses under `review`. A team that wants the
  stronger guarantee sees any attempt to weaken it as a reviewed manifest change.
- **[Identity is only as strong as git config]** Under `self`, `approved_by` is
  self-asserted. → D3 documents it; the sha pin is the load-bearing half in solo use.
- **[Brief grows another detection]** More states to compute at SessionStart. → The
  inputs are files already read by the brief; the sha check is the existing O(1)
  computation.

## Open Questions

- Whether `--local` should also append a ledger row (`.specloop/runs/<change>.jsonl`)
  mirroring what PR attestation records — likely yes, decidable at implementation
  without touching the specs.
