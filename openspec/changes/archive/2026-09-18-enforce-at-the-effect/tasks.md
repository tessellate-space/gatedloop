## 0. Preconditions

- [x] 0.1 Confirm `harden-unattended-loop` (PR specloop PR 8) has merged — this change builds
      directly on its markers (`gates gate-marker`), its durable per-change ledger
      (`.specloop/runs/<change>.jsonl`, harden D7/D8), and its `Stop` hook
      (`hooks/continue-loop.sh`). It does NOT depend on harden's own open closure
      tasks (e.g. task 1d.7) and must not reopen them.
- [x] 0.2 Confirm `CLAUDECODE` is set in an agent session and inherited by a spawned
      subprocess (design D2's premise). A scripted check — launch a shell from the
      session and read the variable — is sufficient; if the marker is named
      differently in the running Claude Code, adjust D2's env name before building on
      it. The git hook must fail toward the human-commit no-op, never toward blocking
      humans, if the variable is absent.

## 1. The effect-layer commit gate (design D1, D2)

- [x] 1.1 Add a git `pre-commit` hook template under `templates/` that runs
      `gates gate-marker check ci "$(git write-tree)"`, referencing the shim via
      `${CLAUDE_PLUGIN_ROOT}` per `plugin-relative-paths`, and exits non-zero on
      mismatch (`fail-loud-gates`).
- [x] 1.2 Scope the template to `CLAUDECODE`: enforce only when the variable is
      present, no-op (exit 0) otherwise (design D2). The no-op path must be a clean
      pass, not a silent skip of a due check.
- [x] 1.3 Verify the template denies an indirectly-created ungated commit (a Python
      subprocess creating the commit — the #2 reproduction) and allows a gated one on
      the same staged tree — the effect-layer guarantee the invocation matcher cannot
      make.

## 2. `gates hook install` — deterministic, composing, never clobbering (design D4)

- [x] 2.1 Add `gates hook install` to `bin/gates` (stdlib-only, `zero-dep-shim`) that
      detects the hook-path owner: husky, lefthook, the `pre-commit` framework, a
      `core.hooksPath` redirect, or a bare existing `.git/hooks/pre-commit`.
- [x] 2.2 Compose the `gates` check into an existing hook/manager where a safe
      composition is determinable; refuse-and-instruct where it is not. Never
      overwrite an existing hook or manager config.
- [x] 2.3 Install the shipped template directly when no hook and no manager are
      present.
- [x] 2.4 Decide whether `gates hook status` earns a top-level verb or ships as a
      `gates doctor` sub-check (design D4 / Open Questions) — resolve against its only
      consumer (`gates doctor`, streamline D3/D4) and implement the chosen form.
- [x] 2.5 Tests (stdlib `unittest`, house style, PyYAML-absent path covered): one case
      per detected topology (bare hook present → composes/refuses without clobber;
      manager present → composes; unknown → refuses-and-instructs; nothing present →
      installs). Assert no existing file is ever overwritten.

## 3. Onboarding offers the install, opt-in with consent (design D5)

- [x] 3.1 Add a hook-install step to `commands/gates-init.md`, sited near the
      permission-scaffolding step (streamline's step 6), offered as a **default-yes**
      AskUserQuestion — never installed silently.
- [x] 3.2 On accept, run `gates hook install` and report the result; on decline,
      install nothing and let onboarding complete normally.
- [x] 3.3 Verify both paths in a throwaway project (live conversational run): accept →
      hook installed via the composing installer; decline → nothing written,
      onboarding still reaches a valid, `ci`-checked manifest.

## 4. Post-hoc reflog audit + ledger taint (design D6, D7)

- [x] 4.1 Add the audit to the shim (testable, not in the hook shell): walk commits
      new since the last audited point, and for each compute its tree and look for a
      green-`ci` ledger row (`gate: ci, exit: 0, tree: <that tree>`) for the change.
- [x] 4.2 Track the last-audited cursor per-worktree under `.git/` (ephemeral, like
      the `Stop` hook's continue-counter) so the audit walks only genuinely-new
      commits and never re-reports.
- [x] 4.3 On an unmatched commit, report loudly (name the SHA and tree) and append a
      taint row to the change's durable ledger. Fix the taint row shape up front
      (harden's "fix the row shape before writing rows" rule); resolve the encoding
      question in design's Open Questions here.
- [x] 4.4 Wire the audit into `hooks/continue-loop.sh` (the `Stop` hook) as an audit
      pass that composes with the existing continue logic — it must run whether or not
      the loop continues, and must not spin.
- [x] 4.5 Tests: a branch of gated commits produces no taint; a commit whose tree has
      no green-`ci` row produces exactly one taint row and a loud report; a second
      audit pass does not re-report an already-audited commit.

## 5. Taint blocks the merge, cheap to clear (design D7)

- [x] 5.1 Add a taint check to the merge gate (`hooks/gate-merge.sh` via `gates`),
      alongside its existing green-`live-check`-on-head check: refuse a change carrying
      an unresolved taint.
- [x] 5.2 Make a green `gates run ci` on the current branch head resolve the taint by
      appending a resolution row (append-only; the incident row stays in history), so
      the merge is no longer blocked on that basis.
- [x] 5.3 Tests: a tainted change is denied at merge; after a green `ci` on the head,
      the same change is allowed; the ledger retains both the incident and the
      resolution rows.

## 6. The forge merge path — documented branch protection (design D10)

- [x] 6.1 Add a `SETUP.md` requirement: for `integration.mode: pull-request` (with or
      without `requireApproval`), the adopter must configure forge branch protection on
      the default branch, naming which checks/reviews to protect, because `gh pr merge`
      and the forge UI have no local git-hook equivalent (the caveat open since PR specloop PR 8).
- [x] 6.2 State plainly in the same place that the local `git merge` path is covered by
      the merge gate while the forge merge path is covered only by branch protection
      (design D8's precise "which guarantee, where").

## 7. The prompt norm sentence (design D9)

- [x] 7.1 Add one sentence to `skills/tdd-apply/SKILL.md` and one to
      `agents/tdd-implementer.md`: a denied gate call means the gate is unsatisfied,
      and rephrasing the invocation is a loop violation, not a solution. Keep it a
      single sentence each — layers 2–4 carry the enforcement, so this is a nudge, not
      the load-bearing rule.

## 8. AUTOMATION.md — the four-layer table (design, four-layer model)

- [x] 8.1 Replace `AUTOMATION.md`'s "raises the floor against accidents, not a jail"
      admission with the four-layer table (layer / mechanism / catches / defeated by),
      matching design's model, and cite issue #2 as the field evidence that motivated
      moving enforcement to the effect layer.

## 9. Close out

- [x] 9.1 Re-read every changed prompt and doc against the rejection test (design D11):
      confirm no step authors an artifact, the git hook and shim name no
      project-specific stack command (`stack-agnostic-prompts`), and hook-manager names
      are used to compose-with, never to invoke.
- [x] 9.2 Confirm `git diff --name-only` touches only the intended surfaces: a new
      `templates/` git-hook template, `bin/gates`, `hooks/continue-loop.sh`,
      `hooks/gate-merge.sh` (or the shim path it calls), `commands/gates-init.md`,
      `SETUP.md`, `AUTOMATION.md`, `skills/tdd-apply/SKILL.md`,
      `agents/tdd-implementer.md`, and `tests/` — nothing else.
- [x] 9.3 Run `python3 -m unittest discover -s tests` and `./bin/gates run ci` — both
      green — before completion, per this repo's own manifest.
- [x] 9.4 Live end-to-end check (conversational run): in an agent session, attempt an
      ungated commit via an indirect path; confirm layer 2 denies it, and that a commit
      forced past layer 2 with `--no-verify` is caught by the layer-3 audit and blocks
      the merge until re-verified — the closing verification of this change's premise.
