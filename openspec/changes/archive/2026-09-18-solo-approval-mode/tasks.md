# Tasks: solo-approval-mode

## 1. The declared policy (design D1)

- [x] 1.1 Red: policy resolution tests — absent block → `review`; `plan: self` →
      `self`; invalid value → validate error naming accepted values
- [x] 1.2 Implement policy read in `bin/gates` + the validate rule; add the optional
      `approval` block to `schema/gates.schema.json`

## 2. The local writer (design D2)

- [x] 2.1 Red: `approval attest --local` under `self` writes keys with the D12 sha and
      the configured git identity; under `review` (or absent block) refuses naming
      `--pr`; `--as <name>` changes `approved_by` but never the sha
- [x] 2.2 Implement `--local`; reuse the existing sha computation verbatim (one code
      path for both writers)
- [x] 2.3 Red→green: post-attestation artifact edit → D10 gate refuses (same test
      shape as the existing `--pr` pinning test)
- [x] 2.4 Decide + implement the ledger row for local attestation (design Open
      Question); if written, mirror the `--pr` row shape

## 3. Onboarding asks (design D1, onboarding delta)

- [x] 3.1 `commands/gates-init.md`: the approval question beside the integration-mode
      question — one line of consequence per answer; declining writes nothing
      (`review` default)
- [x] 3.2 The written manifest carries the block only when answered; summary names the
      approval step for the chosen mode

## 4. Brief routing (design D4)

- [x] 4.1 `hooks/_session_brief.py`: detect approved + unimplemented (keys present,
      sha matches, no `[x]`); menu entry offers spawning `tdd-implementer` as default,
      interactive loop as alternative; missing/stale approval names the missing step
      instead
- [x] 4.2 `commands/start.md`: the same entry in the manual brief
- [x] 4.3 Nothing auto-starts: entry is a menu line, not an action (existing rule
      restated in both files)

## 5. Docs and deferrals

- [x] 5.1 `SETUP.md`: the `approval` block, the solo procedure via `--local`, and the
      D3 honesty note (content attested; identity as strong as git config)
- [x] 5.2 `docs/candidates.md`: per-task tiering + escalation (#4's second half) with
      reasons to wait
- [x] 5.3 `AUTOMATION.md`: update the approval-gate description — writers are
      policy-dependent, the gate is not
