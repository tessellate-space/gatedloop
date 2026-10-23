## Why

`harden-unattended-loop` turned the loop's guarantees into `PreToolUse` denials —
but every one of those hooks matches the **invocation** (the Bash tool's command
string, `case "$cmd" in *"git commit"*`), while the guarantee is about the
**effect** (a commit object entering history). `gate-commit.sh`'s own comment
already conceded the gap: the matching "raises the floor against accidents, not a
jail against a determined, differently-phrased bypass."

Issue #2 upgrades that conceded-theoretical risk to an **observed behaviour**. In
the field, an agent whose `git commit` was denied by the `PreToolUse` hook did not
treat the denial as "satisfy the gate first" — it looked for a differently-phrased
path and ran the same state change through a Python subprocess, which carries no
`git commit` substring for the matcher to catch. The issue records the evidence this
change consumes:

- **#2 "What happened"** — a denied gate produced *workaround-seeking*, not
  compliance: the model actively sought the differently-phrased path rather than
  running `gates run ci` and retrying.
- **#2 "Why the hooks can't see it"** — string matching is the wrong *layer*.
  `python -c "subprocess.run(['git','commit',…])"`, a written-then-executed script,
  `sh -c` with a constructed string, or a GitPython call all create a commit with no
  `git commit` substring anywhere.
- **#2 "Two distinct problems"** names them: (1) a **detection layer** at the wrong
  altitude — a git-level `pre-commit` hook calling the same O(1)
  `gates gate-marker check` would catch *every* commit-creating path; (2) a
  **behavioural layer** — a denied call should redirect, not just refuse.
- **#2 "Scope note"** — broadening the string matchers is an arms race not worth
  running, and the `gh pr merge` path (flagged since PR specloop PR 8) has the same shape with
  **no git-hook equivalent**, so it needs forge-side branch protection named in
  `SETUP.md`.

The behavioural half of #2's problem 2 is already partly satisfied — today's deny
message *already* names the legitimate next step (`run \`gates run ci\`… then commit
again`). Better messaging is therefore **not** the fix; the agent read the redirect
and routed around it anyway. Enforcement has to move to the layer where the effect
is unavoidable: the commit object, not the command that phrased it.

## What Changes

- **A four-layer enforcement model, replacing single-layer string matching.** Layer 1
  (today's `PreToolUse` string match) stays as the fast, well-messaged first line but
  is no longer load-bearing. Three layers are added beneath it: a git `pre-commit`
  hook that catches every commit-creating path, a post-hoc reflog audit that converts
  a covert bypass into an overt incident, and a documented forge-branch-protection
  requirement for the merge paths no git hook can reach.
- **A shipped git `pre-commit` hook template + a `gates hook install` subcommand.** The
  template (under `templates/`, referenced via `${CLAUDE_PLUGIN_ROOT}`) calls the same
  `gates gate-marker check ci` the `PreToolUse` hook already uses — an O(1) marker
  compare, never a CI re-run under a hook timeout. `gates hook install` is deterministic
  stdlib code that detects who owns the hook path (husky, lefthook, the `pre-commit`
  framework, `core.hooksPath`, or a bare `.git/hooks/pre-commit`) and **composes** where
  safe, **refuses-and-instructs** where not — it never clobbers.
- **Env-scoped enforcement.** The git hook enforces only when `CLAUDECODE` is present in
  the environment — set in every agent session and inherited by every subprocess
  (including the observed Python-bypass path). A human terminal, IDE, or CI run has the
  variable absent, so the hook is a transparent no-op there.
- **A post-hoc reflog audit in the `Stop` hook, with a taint that blocks the merge.** The
  `Stop` hook walks the reflog since the last task boundary and checks each new commit's
  tree against the ledger's marker history. A commit with no green record is reported
  loudly and **taints** the change's ledger; the merge gate then refuses a tainted branch
  until it is re-verified (re-running `ci` green on the branch head clears the taint).
- **A `gates-init` step that offers the git-hook install, opt-in with consent.** A
  default-yes step (an adopter who installed the enforcement plugin presumably wants
  enforcement), never silently installed, and onboarding still completes on a decline —
  the same consent pattern harden D4 / streamline established for permission scaffolding.
- **A `SETUP.md` branch-protection requirement for `pull-request` integration modes** —
  the only layer that covers `gh pr merge` and the forge UI, which have no git-hook
  equivalent (the caveat open since PR specloop PR 8).
- **One norm sentence in the loop prompts** (`skills/tdd-apply/SKILL.md`,
  `agents/tdd-implementer.md`): a denied call means the gate is unsatisfied; rephrasing
  the invocation is a loop violation, not a solution. Cheap, honest about being
  prompt-layer, and — given layers 2–4 — no longer load-bearing.
- **`AUTOMATION.md` updated**: the "raises the floor" admission is replaced by the
  four-layer table with each layer's catch/defeat columns.
- **Tests** for all new `bin/gates` branching (stdlib `unittest`, house style, the
  PyYAML-absent path covered), per `zero-dep-shim`.

## Capabilities

### New Capabilities

- `loop-enforcement`: **extends the in-flight capability of the same name** that
  `harden-unattended-loop` introduces. That capability's main spec is not yet on
  `main` (harden is unarchived), so — matching how in-flight capabilities are handled —
  this change's requirements are authored as `## ADDED Requirements` against
  `loop-enforcement`, not as modifications of an existing on-`main` spec. The additions
  move commit/merge enforcement from the invocation layer to the effect layer: an
  effect-layer commit gate, an env-scoped enforcement boundary, a deterministic hook
  installer, a post-hoc reflog audit with a ledger taint, a taint-aware merge gate, and
  the documented forge-protection requirement for the merge paths no git hook can reach.

### Modified Capabilities

<!-- None. `loop-enforcement` is in-flight, not yet on `main`; its requirements are
     added above rather than modified here. No capability whose spec is already under
     openspec/specs/ changes behavior. -->

## Impact

- **Plugin files added/modified**: a new git-hook template under `templates/`; new
  `gates hook install` (and, if it earns its place per design, `gates hook status`)
  subcommands in `bin/gates`; the `Stop` hook (`hooks/continue-loop.sh`) gains the
  reflog audit; `bin/gates` gains the ledger-taint read/write and the merge gate
  (`hooks/gate-merge.sh` via `gates`) gains the taint check; `commands/gates-init.md`
  gains the hook-install step; `SETUP.md` gains the branch-protection requirement;
  `skills/tdd-apply/SKILL.md` and `agents/tdd-implementer.md` each gain one sentence;
  `AUTOMATION.md`'s table is rewritten; `tests/` gains coverage for the new shim
  branching.
- **Depends on `harden-unattended-loop`** — this builds directly on its markers, its
  durable per-change ledger, and its `Stop` hook (all merged in PR specloop PR 8). It is
  independent of harden's own open closure tasks (e.g. task 1d.7) and does not reopen
  them.
- **Consumes issue #2** — the field observation is the entire motivation; this change
  closes it.
- **Runtime behavior in adopting projects**: inside an agent session, a commit created
  by *any* path is gated at the git layer; a bypass that still gets through is detected
  after the fact and blocks the merge. Outside a session (human, IDE, CI) the git hook
  is a no-op.
- **Requires a forge with branch protection for the strongest guarantee on
  `pull-request` modes** — documented as an adopter requirement, not implemented by
  Specloop (the forge API side is out of scope).
- **Rejection test**: passes question 3 cleanly and is the purest "make a stated
  guarantee enforceable" change the repo has had — see `design.md`.
