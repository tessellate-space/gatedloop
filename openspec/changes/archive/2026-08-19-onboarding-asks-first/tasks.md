## 0. Preconditions

- [x] 0.1 Confirm `reposition-specloop` is merged (PR specloop PR 3) — it creates `docs/conventions.md`, which §2 edits, and rewrites `commands/gates-init.md`, which §1 edits

## 1. The bootstrapper offers; the adopter picks

- [x] 1.1 Write the curated detector list as data, not prose scattered through the prompt: each entry is a marker file, the tool it implies, and the gate body it would suggest. Four to six ubiquitous entries — the four already named (`npm run`, `make`, `just`, `cargo test`) are the starting set, chosen because they are near-universal, not because they are complete
- [x] 1.2 Rewrite `commands/gates-init.md` to **present** what it detected and bind only what the adopter confirms — no automatic selection, even when exactly one candidate is found
- [x] 1.3 Make "none of these" a first-class outcome: the adopter writes the gate body by hand and onboarding completes normally
- [x] 1.4 Make the detector list's *presence* honest: say in the prompt that it is a convenience list, not a supported-stack list, and that an unlisted stack is expected rather than unsupported
- [ ] 1.5 Verify against a project whose stack is **not** on the list — onboarding must reach a valid manifest without the adopter fighting a wrong suggestion

## 2. Say what the rule actually protects

- [x] 2.1 Add the carve-out to `stack-agnostic-prompts` in `docs/conventions.md`: a shipped prompt may name a tool **to offer it**; it may never name one **to invoke it**. Invocation goes through `gates run <gate>`, without exception
- [x] 2.2 State the test a reviewer applies: would this prompt still be correct in a project that uses none of the named tools? If yes it is offering; if no it is binding, and it is a violation
- [x] 2.3 Record why the rule needed the carve-out — it was written as an absolute and read as one, while `gates-init` and `templates/gates.yaml.template` had contradicted it since both were written, undetected because convention review was silently disabled (the defect PR specloop PR 3 fixes)
- [x] 2.4 Re-run `gates conventions sync` and confirm `gates validate` passes with no drift
- [x] 2.5 Confirm `templates/gates.yaml.template`'s example tool names now sit inside the carve-out rather than outside the rule

## 3. The session brief's missing third branch

- [x] 3.1 Reproduce first: in a project with OpenSpec initialised and no `.gates.yaml`, run `bash hooks/session-brief.sh` and capture the current output — it offers the full loop menu, every entry of which reads a manifest that does not exist
- [x] 3.2 Add the third state to `hooks/_session_brief.py` / `hooks/session-brief.sh`: OpenSpec present + no manifest → offer exactly one step, `/specloop:gates-init`, and suppress the loop menu
- [x] 3.3 Keep the two existing branches byte-identical in behaviour — this adds a state, it does not re-tune the others
- [x] 3.4 Verify all three states end to end against the installed plugin, not just the script standalone: no OpenSpec; OpenSpec without manifest; fully onboarded
- [x] 3.5 Check the same gap does not exist in `commands/start.md`, which is the manual equivalent of the brief and defers to the same injected directive

## 4. Report the gate you just bound (from `reposition-specloop` 1.13)

- [x] 4.1 After writing the manifest, `gates-init` runs `ci` once and reports its exit code
- [x] 4.2 Do **not** treat red as an onboarding failure — say plainly that the gate is bound and currently failing, and that `tdd-apply` will refuse to commit until it passes
- [x] 4.3 Name the consequence explicitly, because the observed failure was silence rather than error: an adopter who does not know the gate is red experiences the loop as an unexplained no-op
- [x] 4.4 Verify both paths in a throwaway project: a green gate at bind time, and a deliberately red one

## 5. Ask how a change reaches main (from the 2026-08-18 field review)

- [x] 5.1 Decide the manifest shape for the declared integration process (e.g. an `integration:` mapping with the mode and whether approvals are required), add it to `schema/gates.schema.json`, and accept it in `gates validate` — optional, absence meaning current behaviour
- [x] 5.2 Add the question to `gates-init` with the three presets (local squash-merge / PR / PR + required approvals) via **AskUserQuestion** — presented options, never a free-form prompt, never auto-bound
- [x] 5.3 Detect the likely answer where possible — a remote exists, `gh` reports branch protection or a PR-based history — and offer it as the *default* option; detection is an offer, the same rule as §1
- [x] 5.4 Record the confirmed choice in `.gates.yaml` and confirm `gates validate` passes with and without the declaration
- [x] 5.5 Cross-reference the declaration from `harden-unattended-loop` (D10–D12 consume it; §7.5 of `tdd-apply` reconciles against it there) — a note in that change's design, not a behaviour change here

## 6. Close out

- [x] 6.1 Confirm no task in this change touched `skills/` or `agents/` — `git diff --name-only` is the check
- [x] 6.2 Re-read the rewritten `gates-init` against the rejection test: it must not author an artifact, and every tool name it contains must be there to offer, never to invoke
