---
name: tdd-apply
description: "TDD implementation of an OpenSpec change — tests first, implement to pass, atomic commit per task, gated by `gates run` and a convention review. Stack-agnostic: all gates/live-checks come from the project's .gates.yaml."
---

TDD implementation of OpenSpec change tasks — has the change's failing tests authored first (by a separate test author, unless the project declares `loop.test-author: inline`), places each task's tests and runs them red, implements to make them pass, commits atomically per task, and gates every commit through the project's `.gates.yaml`.

**Stack independence**: this skill never names a project's test/build/probe commands. It calls **abstract gates** through the `gates` shim (`gates run ci`, `gates run unit`, `gates run live-check`, `gates run verify`, `gates run eval`). Which real command runs is decided by the project's `.gates.yaml`. Convention rules and live-checks are selected per **surface** — `gates rules` / `gates surfaces` / `gates run live-check` compute the hot set from the changed files.

**Input**: Optionally a change name (e.g. `tdd-apply add-auth`). If omitted, infer from context or prompt.

---

## Steps

### 1. Select the change
If a name is provided, use it. Otherwise infer or prompt via `openspec list --json` + **AskUserQuestion**.

### 2. Read change context
```bash
openspec status --change "<name>" --json
openspec instructions apply --change "<name>" --json
gates validate            # fail fast if .gates.yaml is missing/invalid
```
Read all `contextFiles` and the project's `conventions.rules-doc` (from `.gates.yaml`). Handle `blocked` / `all_done` states.

### 2b. Dispatch on the change's schema
Every route below shares the same enforcement — gates, convention review, commit discipline, stop-before-merge (design D1: only the *front half*, the artifact DAG and the entry condition, varies by pack). What varies is decided here, once, before branching:

1. Read the change's schema name — `openspec status --change "<name>" --json`'s `schemaName` field (already fetched in step 2).
2. `gates schema dispatch <schema-name> --json` — the one call this step makes. It decides the route in code from the resolved schema's own structure, never from `openspec instructions apply`'s response (design D4: a complete apply-less change returns a plausible-looking `"state": "ready"`, `"Proceed with implementation."` with `tasks: []` — indistinguishable from a real "go" without checking the schema first, so this step never trusts it). It prints `{"schema", "route", "reason", "has_apply", "implementable", "flow"}`. Branch on **`route` only** — never on the schema's name, and never re-derive the route from the other fields.
3. **`route` is `refuse`** → **refuse cleanly.** The schema is decision-terminal: it has no `apply` block, or an `apply` block that tracks nothing (e.g. gatedloop's `architecture` pack: `explore → design → adr`). There is nothing to implement. Report this plainly with the printed `reason`, name the completed planning artifacts, and suggest `/gatedloop:archive` once they're all present. Do **not** create or resume a change branch, do not invent a `tasks.md`, and do not proceed past this step.
4. **`route` is `regression-first`** → the schema declares `gatedloop: { flow: regression-first }` (gatedloop's `bugfix` pack does, and so does any fork of it, under any name) → go to **5-regression-first** below instead of the default loop.
5. **`route` is `per-task`** → the default per-task loop (step 5), unchanged. This covers `spec-driven`, every community feature schema, and any project-local fork of one that declares no flow.
6. **`gates schema dispatch` exits non-zero** → it could not decide: the schema did not resolve, it declares a flow gatedloop does not know, or the dependency-free reader refused a shape it does not recognise. This is a HALT, never a fallback to the default loop — stop and report the command's message verbatim (unattended, record the halt with cause `environment` when the schema could not be resolved or read, `other` with the message as `--detail` otherwise).

### 3. Create or resume the change branch
Branch **once per change**, resume-safe: if `<change-name>` exists, `git checkout <change-name>` and **RESUME** (read `openspec status`, continue from the first unchecked task, never redo committed ones, and read `gates attempt notes <N.M>` for that task before touching it, so a resume gets the same memory a restart does); else `git checkout -b <change-name>`. All task commits land here; squash-merge at Step 7.5.

Cutting a NEW change branch is hook-gated (design D10): `git checkout -b <change-name>` is refused unless the change's plan is present on `main` (reviewed and merged, not just written) and its `.openspec.yaml` carries a populated, still-matching `approved_by`/`approved_sha`. A refusal means the plan needs review and merge first — this is not a bug to work around.

### 4. Show progress
Display progress and "Starting TDD loop — tests first, then implementation, then commit."

### 4b. Authoring phase — once per change, before the first task
The change's failing tests are written before any of it is implemented, by an agent that does not implement it (design D1 of `split-test-author`). Run `gates tests show <change-name> --json`:
- **`handoff` is `true`** — the tests are already authored (a resume). Skip to step 5.
- **`handoff` is `false`, `mode` is `separate`** (the default):
  1. **Dispatch the author**: the `test-author` subagent (`subagent_type: test-author`), given the change name. It reads `gates tests brief <change-name>`, writes every task's tests into `.gatedloop/authored/<change-name>/`, and hands off with `gates tests handoff <change-name>`. If it returns `blocked: weak-spec`, nothing was handed off: record `gates halt record weak-spec --detail "<every question it returned>"`, commit that row alone, and stop — the plan goes back for those answers before any code exists.
  2. **Review the authored set** (design D7): dispatch the `convention-review` subagent in its authored-set mode, over the holding area. A finding goes back to the author for that task (it revises and re-runs `gates tests handoff <change-name> --task <N.M>`), then the review runs again — at most two rounds. Findings still open after the second: `gates halt record oracle-conflict --detail "<the findings and the author's position>"` and stop. Record every verdict with `gates review record <clean|findings> --scope authored`.
  3. **The authoring commit**: stage the holding area and the ledger, run `gates run ci` on that staged tree, and commit — `git add .gatedloop/authored/<change-name> .gatedloop/runs/<change-name>.jsonl`, then `git commit -m 'author tests: <change-name>'`. The `.authored` suffix keeps every runner from discovering the held tests, so `ci` is unaffected by them.
  4. **No author, no tests.** If the `test-author` subagent cannot be dispatched, do not write the tests yourself — falling back to inline silently would undo the default the project chose. Record `gates halt record missing-oracle --detail "tests not authored — dispatch test-author for <change-name> first"`, commit that row alone, and stop.
- **`handoff` is `false`, `mode` is `inline`** — see 5-inline.

Show the author's report (per task: each test with the regression that makes it fail, or the reason a task changes no behaviour; its interface decisions) before starting step 5.

### 5. TDD + Atomic Commit loop (unit tests)
For each pending task:

**5a. Announce** — mark `in_progress` in TodoWrite, then record the tree this task starts from: `gates task start <N.M>`. From here on `gates task changed` answers "did I change this file?" from data — every path differing from that tree, untracked files included — instead of from memory (baseline finding 0.4: a run disowned three of its own correct edits as a non-existent "background watcher", then reasoned about what was safe to revert on that basis). If a path you did not write shows up, report it as an observation and check it; never infer a third party.

**5b. Determine test scope** — unit only for this phase. Ask if unclear.

**5c. Place the authored tests, then run them RED** — the task's tests were written in the authoring phase (4b); this loop never writes them. The red step runs on the **task's oracle gate**: the gate the plan's tag declares, as `gates tests show <change-name>` reports it in its `oracle` column (`unit` when the plan declares none). The tag is the contract, fixed by the approved plan; never choose another gate for the red step, and never pick one yourself for an untagged task. Below, `<oracle-gate>` is that gate.
1. `gates tests place <N.M>` moves the task's held tests onto their real paths. For a task its author marked behaviour-free (the plan's `[oracle: none]`, or an untagged task its author judged so), it places nothing and says so — no red run is needed; go to 5d, and name the task's covering test or say that no behaviour changes in its commit (5h). For a task declared `characterization` (its tests pin behaviour the tree already has, such as a refactor's guard; the plan tags it `[oracle: <gate> characterization]`, or its author declared it for an untagged task), it places the tests and says so: in step 2 the run must **pass** instead, and a red run there is a defect (5-defects). Only the plan or the author makes that declaration.
2. `gates run <oracle-gate> --task <N.M> --attempt 1` — it MUST fail (or, for a `characterization` task, pass). Passing `--task`/`--attempt` records the red run in the durable ledger, and `gates tests check` (5f) refuses the commit without a failing run of the task's oracle gate recorded after placement; a red run on any other gate does not count. A precondition failure (exit 75) is not a red run.
3. **Read why it fails** before writing any code. A test for a later task may fail because nothing it uses exists yet; confirm the failure is the one the author's report names for it, not something the test gets wrong.
4. **Never edit a placed or held test** — not to make it compile, not to fix a typo. The commit hooks refuse a staged test that differs from the handoff. A test you judge wrong is a defect (5-defects).

**The RED questions.** The test author answers these for every test it writes (`agents/test-author.md` §3), and so does this loop for any test it writes itself (5-inline, step 6). Answer them in order. The review holds every test to the built-in `gatedloop.test-quality` rule, so a test these questions would have stopped is a finding later.

0. **Read the project's architecture first.** Run `gates rules --changed <paths the task touches>` (take the paths from the task line and the design), read those rules from the rules-doc, and read the change's `design.md`. Questions 3 and 4 are architecture decisions, and they are answered the way this project already makes them, never by a general theory of the loop's own:
   - **Classification.** "Domain" and "I/O" mean what the project's rules say they mean. Where the rules name the layers (ports, adapters, services, stores), use those names.
   - **Seams.** An extraction follows the seam pattern the rules or the design define: where the interface lives, what it is called, and what implements it.
   - **No seam defined.** When neither the rules nor the design define where a seam belongs, don't design one. Halt with `weak-spec`, detail "needs a domain seam for <thing>; neither the project's conventions nor the design define where it belongs". A seam is an architecture decision, and those are made in the plan.
   - **Precedence.** A project rule outranks any `gatedloop.test-quality` item it contradicts. The project knows its stack; the built-in rule doesn't.
   - **No rules-doc, or no layering rule.** Questions 1–3 still apply, using the plain meaning of domain and I/O. Question 4's extraction halts as above, because with nothing written there is no sanctioned seam.
1. **Which real regression makes this test fail?** Name it in one line. If none can be named, don't write the test.
2. **Is it already tested one layer down?** Look with `gates task changed` and a search of the test tree. If a test already fails for that regression, name it, add none, and record it as the task's oracle (5h).
3. **Domain or I/O?** Domain logic gets a pure test at its public seam, with no fakes. An adapter gets one contract test against the real system at the integration gate, and nothing in between.
4. **Would this need a fake of a type the project doesn't own?** Stop. Extract the domain logic behind an interface the project owns and test that. If the extraction is outside this task's stated scope, halt with `weak-spec`: `gates halt record weak-spec --task <N.M> --detail "needs a domain seam for <thing>"`. The plan didn't provide a seam, so the spec is what's weak.

A test this loop writes itself is then run the same way — `gates run <oracle-gate> --task <N.M> --attempt 1`, confirming it fails — so every red run is in the ledger (task 0.2's gap: nothing recorded that a red run preceded implementation — now every `gates run` invocation does, pass or fail).

**5d. Implement (Green)** — minimal code scoped to this task, against the placed tests. Add no test of your own beside them: review flags a test file added outside the handoff.

**5e. Run tests (Green)** — `gates run <oracle-gate> --task <N.M> --attempt <n>`, incrementing `--attempt` on each retry. `--attempt` is only a label; the budget is counted from the ledger.
- **The budget.** A task gets `loop.attempts` failed attempts (default 2): red runs of its oracle gate or of `ci` after its RED run (its first red oracle-gate run) and since its last restart. Exit 75 never counts. Once the budget is used, `gates run unit` and `gates run ci` for the task refuse with exit 1, without running, and the message says what remains.
- **A note after every failed attempt**, before the next one: `gates attempt note <N.M> --hypothesis "<what you believed was wrong>" --changed "<what you changed>" --oracle "<what the gate said>" --next "<what to rule out next>"`. Each field is one line of at most 200 characters. A note is a lesson, not a transcript.
- **The token budget.** Where the project declares `loop.token-budget`, `gates run unit` and `gates run ci` refuse once the change's recorded token usage reaches it, and the message names the budget and the spend. This is a halt, never a retry and never a restart (the spend belongs to the change, not the task): discard the task's partial work, record `gates halt record budget --task <N.M> --detail "<what remains>"`, commit that row alone, and stop. A human decides whether to raise the budget, cheapen the gates, or split the change.
- **When the attempt budget refuses**, pause and ask. The question is whether to restart the task fresh, which needs a new context that reads only the spec, the task and `gates attempt notes <N.M>`, or to take it over. The pause is recorded as an `ask` intervention by the question-tool hook; a pause that does not go through the question tool is recorded with `gates intervention record ask --task <N.M>`.

**5f. Task gate** — before committing, ALL must be clean:
- `gates run ci --task <N.M>` green — the aggregate build/test oracle; never commit on red. **Stage first**: the task's files (its placed tests and the removal of its holding directory included: `git add -A .gatedloop/authored/<name>`) and the `tasks.md` `[x]` flip (5g) go into the index *before* this run, because the marker is keyed on the staged tree — anything staged after it stales the marker, and the commit denial names those files. Only the ledger row may be staged afterwards (5h).
- Run every gate in the foreground, with the longest timeout the host's shell tool allows, and read its exit code in the same turn; never background a gate, and never end a turn waiting on one.
- **convention review**: convention review MUST run as the `convention-review` subagent (`subagent_type: convention-review`) — never inline in this loop's own context. It runs `gates rules` to get the hot surfaces' rule-ids for this diff, resolves them against the project's `conventions.rules-doc`, and checks the diff — each finding cites its rule-id. Pass it the draft commit message (5h) along with the diff, so it can see a `Covered-by:` trailer. Resolve all findings before commit. Reviewing inline is the anti-pattern this rule forbids: field issue #13 measured it as one of two dominant token drivers across six unattended runs (300–500k tokens, 60–100 minutes of gate time per change) — rules prose and the diff text both accumulate in the loop's own context for the rest of the run, instead of being scoped to a subagent call that returns only a verdict. Only if nested subagents are genuinely unavailable, fall back to doing the check inline (`gates rules` → read the cited rules → review the diff) — and treat that as a degraded mode, not the default.
- **`gates tests check`** — the placed tests are staged exactly as handed off, the held tests of later tasks are untouched, and a failing run of the task's oracle gate was recorded after placement (a green first one, for a `characterization` task). Both commit hooks run it right after the `ci` marker check and deny the commit on failure; run it yourself first to see what it names.
- **record the verdict**: `gates review record <clean|findings> --task <N.M>` — every time the review returns, including when it returns findings. This is the only artifact backing a "convention-clean" claim (baseline finding 0.3: a run once reported every commit clean and left nothing that could confirm or refute it). Record `findings` first, then fix, then re-review and record `clean` on the fixed tree — a review is only evidence about the tree it saw.

**5g. Mark task complete** — `- [ ]` → `- [x]`

**5h. Atomic commit** — stage, then gate, then commit: the task's files (placed tests and the holding-directory removal included) and the `tasks.md` `[x]` flip are already staged from 5f; add the durable ledger row `gates run` just appended, and commit them together (done ⟺ committed — an uncommitted ledger row does not survive a squash-merge). Staging the row can never stale the `ci` marker you just earned: the ledger is excluded from the tree the marker hashes (design D1 of `fix-marker-mechanics`), so the row you're about to add cannot change what the marker compares against.
```bash
git add <specific files> openspec/changes/<name>/tasks.md .gatedloop/runs/<name>.jsonl
git commit -m '<imperative lowercase description>'
```
Commit convention: imperative lowercase, ≤72 chars, no ticket prefix; tests + implementation together; must not break the build.

Every task names its oracle. A task that adds no test, because an existing test already covers its behaviour (5c question 2), names that test in a commit trailer:
```
Covered-by: <test identifier as the project's runner names it>
```
Coverage is recorded, never assumed. A behaviour change with neither a new test nor this trailer is a `gatedloop.test-quality` finding.

**5i. Continue** to the next task.

### 5-defects. A wrong test goes back to its author
The implementer never corrects an authored test (design D5 of `split-test-author`). When a placed test is wrong — it asserts something the spec and design do not say, or it cannot be satisfied by any implementation of the stated interface — or when the placed tests **pass on their first run** (they do not exercise this task's behaviour, or the task is already done; never implement against a green oracle):
1. Discard the task's partial work, keeping the ledger (`gates task changed` lists what the task touched).
2. `gates tests defect <N.M> --kind setup|assertion|green --detail "<why>"`, then commit that ledger row alone, leaving a clean tree at the task boundary (a ledger-only commit is allowed at ledger grade, and the commit hooks do not run the authored-test lock on it). The kind is what you observed (design D4 of `authored-test-kinds`, D5 of `unblock-authored-lock`): `setup` when the test errored before asserting (a path, import, fixture or environment it assumes is wrong), `assertion` when it ran and asserts the wrong behaviour, `green` when the placed tests passed on their first run and the task is not `characterization`. `green` records that observation without claiming the tests are wrong; never file a `setup` or `assertion` defect for it. The author answers it by re-declaring the task (`CHARACTERIZATION` with a reason, or `NO-TESTS` with no tests) or by rewriting the tests so they fail against the tree; only the author declares a task's kind. The author may answer a `setup` defect with a fix only; to dispute it, it defends the tests, and a further defect is then recorded as `assertion`.
3. **Re-dispatch the author** for that task: the `test-author` subagent, given the change name, the task id and the defect detail. It revises or defends that task's tests and runs `gates tests handoff <change-name> --task <N.M>`. Run the authored-set review over the revised task (4b step 2), commit the re-handed-off holding files with the ledger, then resume at 5a for the same task.
4. **Each kind has its own cap per task.** `gates tests defect` refuses a second `green` defect (the tests are still green after the author's answer): record `gates halt record oracle-conflict --task <N.M> --detail "test-defect <N.M>: still green after re-handoff"`, commit that row alone, and stop — a human decides. It refuses a third `assertion` defect: record `gates halt record oracle-conflict --task <N.M> --detail "test-defect <N.M>: <your position>; author: <its defence>"`, commit that row alone, and stop — a human decides. It refuses a fourth `setup` defect: record `gates halt record weak-spec --task <N.M> --detail "test-defect <N.M>: <what the tests could not run against>"`, commit it alone, and stop — the author's brief is missing something. A defect recorded before kinds existed counts as `assertion`.

**A completed task can be reopened.** A defect found after the task was committed (a late end-to-end mismatch, a review finding) goes through the same steps: the defect voids the placement, the author re-hands the task off, and 5a–5c place it again. The red run recorded after its first placement stays the record, so no new red run is demanded against code that is already committed; the lock still checks the re-placed tests' content in full, and a re-declared `characterization` task still needs a green first run after the new placement. A halt at a completed task (waiting on a source, say) leaves its placement in force and needs no new placement.

This loop re-dispatches the author itself because it runs at the top level. An implementer running under a dispatcher (`tdd-implementer`, or a lane under an orchestrator) cannot dispatch a sibling, so it halts at step 2 instead and its dispatcher does step 3.

### 5-restart. A stalled implementer with a restart left
When this loop has dispatched a `tdd-implementer` and it halts with cause `stalled`, read the latest `halt` row in `.gatedloop/runs/<change-name>.jsonl`. Its `restart_available` is computed by the shim from `loop.fresh-restarts`, never by the agent.
- **`restart_available: true`** — dispatch **one** fresh `tdd-implementer` for the change. Its brief holds only the spec, the task id and the output of `gates attempt notes <N.M>`, and nothing from the halted run: no transcript, no diff, no theory of the bug. A restart in the same context would only keep polishing the same dead end. The fresh agent's first act is `gates attempt restart <N.M>`, which resets the task's count.
- **`restart_available: false`** — the restart is used, or the project declares `loop.fresh-restarts: 0`. Stop and report the halt; a human takes it from there.

A restart is the dispatcher's act. The implementer never restarts itself. An adopter's orchestrator does the same from the same row.

### 5-inline. When the project declares `loop.test-author: inline`
The project has opted out of an independent author (design D6). The mechanism is the same; only the author's independence is lost, and `gates stats --outcomes` shows it:
- In 4b, this loop runs the authoring phase itself, before its first task: `gates tests brief <change-name>`, then every task's tests into `.gatedloop/authored/<change-name>/` exactly as `agents/test-author.md` §1–§6 describe (the RED questions in 5c included), then `gates tests handoff <change-name> --inline`. The authored-set review and the authoring commit follow as in 4b.
- Placement, the red run, the lock and defects apply unchanged. A defect's step 3 is this loop revising that task's tests in the holding area and re-running `gates tests handoff <change-name> --task <N.M> --inline` — never an edit to a placed test.

### 5-regression-first. Regression-first route (schemas declaring `gatedloop.flow: regression-first`)
Reached only via step 2b's dispatch, when `gates schema dispatch` returns `route: regression-first` — whatever the schema is named. Same gates, same convention review, same commit discipline as step 5 (design D1) — what's different is the entry condition and the commit granularity, because "commit fix and repro together" (design D3) means the reproduction cannot be its own green commit the way step 5's per-task loop normally works.

Treat the schema's three task groups (confirm red / fix / confirm green, the shape of gatedloop's `bugfix` pack `tasks` template, which a fork may reword) as **one commit unit**, not three:

1. **Announce** — `gates task start <N.M>` once, at the start of the unit (as 5a).
2. **Place the regression test** — `gates tests place <N.M>`. In the authoring phase (4b) the test author turned `report.md`'s reproduction into this unit's authored test, matching what it documents — this schema's version of "write tests first," sourced from the report artifact instead of derived from a spec (design D10 of `split-test-author`). The lock applies unchanged: you write only the fix, and never reshape the repro until it passes.
3. **Run it RED** — `gates run unit --task <N.M> --attempt 1`. It MUST fail. **A pass here is a HALT condition, not an early done** — it means the reproduction doesn't reproduce the reported bug. Stop before writing any fix: record it as a `green` test defect (5-defects), so the author fixes the reproduction (it may need to go back to the `report` artifact). Do not proceed to the next step on a green first run.
4. **Implement the fix** (as 5d).
5. **Run the same test again — GREEN required** — `gates run unit --task <N.M> --attempt <n>`, incrementing on each retry, under the same budget, notes and refusal as 5e.
6. **Task gate (5f, unchanged)**: `gates run ci --task <N.M>` green, convention review via the `convention-review` subagent, findings resolved, verdict recorded (`gates review record <clean|findings> --task <N.M>`).
7. **Mark every task in the unit complete**, then **one atomic commit** covering the regression test, the fix, the `tasks.md` flips, and the ledger row — never split the failing-test commit from the fix commit. If the spec delta needs a follow-up edit because the fix revealed it was wrong, include that in this same commit and say why.
8. **Continue** to the next task group, if any remain (most bugfix changes are a single unit).

### 6. Integration tests from specs
After all implementation tasks, derive integration tests from `openspec/changes/<name>/specs/*/spec.md`. For each WHEN/THEN scenario, first ask 5c's question 2 at the integration layer: a scenario gets an integration case only when it crosses a layer boundary or no lower-layer test covers it. Otherwise derive none, and name the covering test in the step's report. Run `gates run integration`. On failure, diagnose (implementation bug → fix impl, re-run `gates run unit` then integration; test/spec mismatch → fix test or flag spec). After 2 failed attempts, pause and ask. The pause is recorded as an `ask` intervention by the question-tool hook; a pause that does not go through the question tool is recorded with `gates intervention record ask --task <N.M>`. Commit when green. Skip this step if the change has no specs or no `integration` gate.

### 7. Frontend / acceptance step definitions
If this change produced acceptance features (e.g. `.feature` files) and the project has a `verify`/`live-check` for them, wire the missing step definitions, run `gates run verify`, fix loop (pause after 2 attempts), commit. An undefined step is a failure to fix, never a skip: a scenario with a missing definition is failing until its definition is written, and a skipped scenario never counts as passing. Hold every definition to `gatedloop.test-quality` items 10–12: state why no cheaper layer can observe the behaviour, keep any verdict that depends on a model's reply under `eval` rather than a blocking gate, and use no fixed sleep and no application logic re-derived to aim an action. The pause is recorded as an `ask` intervention by the question-tool hook; a pause that does not go through the question tool is recorded with `gates intervention record ask --task <N.M>`. Skip if not applicable.

### 7.5 Change-completion gate and merge
All tasks done → run change-level gates on the branch, then integrate — **how** depends
on the project's declared integration process (`onboarding-asks-first` §5), never
assumed:
1. **`gates run verify`** — spec → behavior coverage (if declared).
2. **Live self-check (BLOCKING)** — `gates run live-check` runs exactly the hot surfaces' probes. Integration is blocked on failure, in every mode below.
2b. **Acceptance brief, then stop for acceptance where declared** — run `gates acceptance brief <change-name>` and show its output to the human as-is: every spec scenario in scenario language, `covered` or `check by hand`, and the gate verdicts recorded for this exact tree. The shim generates it; never write, summarize or amend it yourself. Then run `gates acceptance policy`:
   - **`acceptance=none`** — nothing more is required; continue to step 3. The brief was information for whoever merges.
   - **`acceptance=self` or `acceptance=review`** — a human must accept the behaviour before it integrates. Report that the change is waiting for that, and how they record it: `gates acceptance attest <change-name> --local` (under `self`) or `gates acceptance attest <change-name> --pr <n>` (from the implementation PR's approving review), or `gates acceptance reject <change-name> --cause weak-spec|missing-oracle --detail "<what was meant>"`. Never run an acceptance writer on the human's behalf: an acceptance recorded by the loop is self-reported, which is exactly what the gate exists to exclude. Then, by mode (`gates integration`):
     - **`local-squash-merge`** — **STOP here**: do not merge. Continue only once `gates acceptance check "$(git rev-parse <change-name>^{tree})"` exits 0 — a human (or a later session, after acceptance) resumes from here. This is the same boundary as `requireApproval: true` below.
     - **`pull-request`** — continue to step 3. `gates merge` (step 4) opens the PR and leaves auto-merge off until this exact tree is accepted — under `review` the acceptance can only come from that PR's approving review — and re-running it after the acceptance is recorded enables auto-merge where nothing else stands in the way.
3. **Declared eval (ADVISORY)** — if the proposal's "Evaluation impact" names a dataset, run `gates run eval <dataset> <score>`; report score vs baseline; do NOT block.
4. **Read the declared process**: `gates integration` prints `mode=<...>` and `requireApproval=<...>` from `.gates.yaml`. Branch on it:
   - **`local-squash-merge`** (or `integration:` absent — today's default): run
     ```bash
     gates merge <change-name>
     ```
     and nothing else — never a hand-run checkout, squash, commit or push. It proves the
     head with the merge gate's own checks (live-check marker, unscoped `ci`, `verify`
     where declared, taint, acceptance where a policy is declared), squashes onto the
     target's tip, runs an unscoped `ci` on the merged tree, records the merge row against
     the squash commit, runs the `confirm` gate where declared, archives the change, and
     pushes all of it once, at the end. It exits with the number of the step that refused
     and prints that step's message; report it as-is. Exit 75 means a gate did not run, so
     nothing about the merged tree is known: with a `gatedloop: lock busy` line (another
     merge holding the merge lock, or a lane's run holding the `ci` or `confirm` lock at
     step 3 or 5), re-run the same command (at most three times); otherwise a declared
     precondition failed, which is the environment, not the code. Recording the merge (step 5 below) and archiving (§8) are inside
     it, so skip both on this branch.
   - **`pull-request`** (either `requireApproval` value): run
     ```bash
     gates merge <change-name>
     ```
     and nothing else — never a hand-run push, PR or forge merge. It proves the head with
     the same checks as above (a declared acceptance does not refuse here; it decides
     auto-merge), pushes the branch, publishes the head's `live-check` and `ci` markers as
     `gatedloop/*` commit statuses, and opens or updates the pull request with the
     acceptance brief as its body. It enables squash auto-merge only when
     `requireApproval=false` and any declared acceptance is satisfied; otherwise it prints
     the PR's URL and stops. Either way it exits 0 once it has handed the change to the
     forge: report the URL, and whether the forge merges it once its required checks pass
     or it is **waiting for review** — a human approves and merges it in the forge; never
     merge it yourself. This is the same "stop before the merge" boundary `tdd-implementer`
     always keeps, generalized to whenever the declared process requires a human review. A
     refusal exits with its step (1 prove the head, 2 push, 3 publish statuses, 4 pull
     request) and prints the step's message; report it as-is. Exit 75 beginning
     `gatedloop: lock busy`: re-run the same command (at most three times).
5. **Recording the merge** happens after integration, never by hand-appending a row:
   inside `gates merge` on the local branch (its steps 4 and 6 record and archive), and
   for a pull request **after the forge merges it**, with `gates record-merged <squash
   sha>`. That one command finds the change through the PR's head branch, records the
   merge row against the squash commit, archives the change and makes one local commit;
   it never pushes. Projects usually run it in CI on every push to the target (an example
   to adapt: `${CLAUDE_PLUGIN_ROOT}/docs/running-at-scale.md`); otherwise run it by hand
   on the target branch at or after the squash, and land its commit the way the project
   lands commits.

### 8. Completion
Show tasks completed, progress, git log of session commits. If all done → suggest `/gatedloop:archive`, unless `gates merge` integrated the change locally (it archived it as its step 6) or handed it to the forge (`gates record-merged` archives it once the forge has merged it).

---

## Guardrails
- **Dispatch (2b) decides the route, never the loop body.** Every route — the default per-task loop, the regression-first route, or refusing a schema whose implementation phase tracks nothing — runs the identical gates, the identical `convention-review` subagent, the identical commit discipline, and the identical stop-before-merge boundary (design D1). If a future pack needs a genuinely different *enforcement* step rather than a different entry condition, that is a sign it doesn't belong in this skill's dispatch — enforcement is pack-invariant by design.
- Every test/build/probe command goes through `gates run <gate>` — never hard-code a project's tooling here.
- Per-task gate (5f): `gates run ci` green + convention review clean before every commit; never commit on red or with unresolved findings.
- Live self-check blocks integration (7.5) in every mode — local squash-merge or a PR: `gates run live-check`; the declared eval is advisory only.
- One branch per change (step 3) — integrated at 7.5 per the declared `integration` process (`gates integration`); never branch per task.
- `requireApproval: true` means STOP before merging, same as `tdd-implementer`'s always-stop rule — `gates merge` opens the PR and leaves auto-merge off; report it, and leave the merge to a human. Never merge a PR or enable auto-merge yourself.
- A declared acceptance policy (`gates acceptance policy` prints `self` or `review`) means STOP before integration the same way (7.5 step 2b) — show the brief `gates acceptance brief` generates, and leave accepting or rejecting the behaviour to a human; the merge hook refuses the merge until an `accept` pins the incoming tree.
- Resumable — done ⟺ committed (task's `[x]` committed with its code); on any halt leave the tree clean at a task boundary so a fresh agent resumes from the first `[ ]` via `git checkout <change-name>` + `openspec status`.
- One task, one commit — never bundle implementation tasks. Stage specific files — never `git add .`.
- Never commit with failing tests.
- A denied gate call means the gate is unsatisfied — satisfy it (`gates run ci`, resolve the finding) and retry the *same* call; rephrasing the invocation to get past a denial (a subprocess, a wrapper script) is a loop violation, not a solution, and the git-layer hook plus the post-hoc audit catch it regardless (issue #2).
- **A failed precondition is not a red gate.** Any `gates run <gate>` (`unit`, `ci`, `live-check`, …) that reports a precondition failure and exits 75 means a declared `requires` command failed *before* the gate body ever ran — the environment was absent, not the code wrong. Do not retry the gate unchanged and do not read its output as a test failure to investigate; surface it to the user as an environment problem, distinct from an ordinary red gate, and wait for the environment to be fixed or booted before running the gate again.
- **A busy lock is the one exit 75 to retry.** When the message begins `gatedloop: lock busy`, another lane held a serialized gate's lock past `concurrency.max-wait-seconds` and the gate never ran. Re-run the identical command (same flags, same `--attempt`) at most three times; never edit code in response. Still busy after that → treat it as an environment problem as above (unattended: halt with cause `environment`). `gates lock status` shows who holds the lock and whether it looks hung; the loop never kills a holder.
- `gates run` is quiet by default — one summary line on a green gate, the full output only on red — so never pipe its output through `| tail` or similar to manage context; that both is unnecessary and truncates the one output (a failure's) that actually matters. Pass `--verbose` only if you genuinely need the unfiltered stream.
