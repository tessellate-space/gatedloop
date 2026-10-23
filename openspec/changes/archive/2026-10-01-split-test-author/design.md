# Design: split-test-author

## Context

This change implements #34 item 6 and #35 B, drawing on the pilot results quoted in the
proposal. Four facts decide the shape.

- **A subagent cannot dispatch a subagent.** A per-task author would need someone
  above the implementer to dispatch it between tasks. That breaks for `tdd-implementer`
  running as a subagent, and for an orchestrator's lanes (#37).
- **The per-task gate is `ci` on the staged tree.** A red test cannot be committed,
  and a red test sitting where the runner discovers it turns every `ci` run red.
- **Done ⟺ committed.** Anything a later task depends on must survive a halt and a
  resume, so it has to be committed.
- **Review decision: the author writes all of a change's tests in one go.** The
  review asked whether that is feasible and what it implies (PR specloop PR 86). It is feasible
  (D1, D3), and it is also what resolves the first point.

## Decisions

### D1. The author writes the whole change, before implementation begins

The loop gains an authoring phase between plan approval and the first task:

```
plan approved
  └─ authoring phase (once per change)
       dispatch test-author(change)
         gates tests brief <change>              ← conventions, per-task paths (D9)
         writes every task's tests into the holding area (D3)
         marks behaviour-free tasks (D8)
         gates tests handoff <change>            ← records the whole set
       authored-set review (D7)                  ← test-quality + project test rules
       commit: "author tests: <change>"          ← holding area + ledger row
  └─ per task N.M
       gates task start N.M
       gates tests place N.M                     ← moves N.M's tests into place
       gates run unit --task N.M → must be RED   ← enforced (D4)
       implement → green → ci + review + gates tests check → commit
```

**Why this is better than per task:**
- **One dispatch and one load of context.** The specs, the design and the project's
  conventions are loaded once per change, not once per task.
- **A view of the whole change.** The author sees every scenario together, so it can
  put each behaviour at one layer across tasks rather than re-proving it task by task.
- **Every design question arrives before any code exists.** The pilot's blind author
  raised 7 unanswered questions. Asked up front, they send the plan back while
  changing it is still cheap.
- **It fits any orchestration without nesting (D6).** Whoever dispatches the
  implementer dispatches the author first, as a sibling.
- **The lock holds from the first commit.** The tests are committed and hashed before
  the implementer exists.

**What it costs, and how the design answers:**
- **Later tasks' tests are written against interfaces that earlier tasks will
  build.** The design has to state those interfaces. Where it doesn't, the author asks
  (D2 item 6). A gap discovered mid-change is a test defect (D5), exactly as per task.
  Defects will probably run somewhat higher than the pilot's 2 in 5 tasks. The
  outcomes view reports them, so the cost is measured rather than guessed.
- **A later task's red run proves "red", not "red for the right reason".** Before
  its task, a test also fails because nothing it imports exists yet. The reason is
  checked at placement time (D4), when the implementer reads the failure output
  before writing code.
- **Large changes mean a large author context.** The author works one task group at
  a time within the single dispatch, and hands off once. A change too large for that
  is a planning problem, not an authoring one.

### D2. The test-author agent

`agents/test-author.md`:

- **Model:** `sonnet` (maintainer decision). Sonnet is good enough for writing tests,
  provided its guardrails are tight and its instructions match the project's own
  conventions (D9).
- **Tools:** `Read`, `Grep`, `Glob`, `Write`, `Edit`, `Bash`. Bash is for `gates` only.

The body carries, in order:

1. **Inputs, from the brief first.** Its first call is `gates tests brief <change>`.
   It then reads exactly what the brief names:
   - `tasks.md`, the spec scenarios and `design.md`;
   - every rule listed;
   - the shared fixture and helper files listed;
   - the public interfaces of the code the tasks name: signatures, types, exported
     names and doc comments.

   It has a tool budget, and it explores nothing beyond these.
2. **The boundary.** It never reads function bodies of the code under change, and
   never the *contents* of existing test files. It knows where existing tests live
   and what they are called from the brief's paths (D9), and it builds on the
   project's shared fixtures and helpers. It never copies an existing test's
   assertions, so the audit's waste patterns can't propagate into new tests. The pilot
   author read no existing tests, and scored 94% keep.
3. **The RED questions** from `test-quality-rule` D4 and D4a, the
   `specloop.test-quality` items, and every project test rule in the brief, all
   applied before handoff. A project rule wins over a built-in item, and the author
   says so in its report.
4. **Only tests, and only into the holding area** (D3). It writes no implementation,
   configuration, task list, or file outside `.specloop/authored/<change>/`.
5. **Order and interfaces.** It authors tasks in `tasks.md` order. A test for a later
   task targets the interface the design states for it. Where the design leaves a
   name or shape open and the choice is low-stakes, the author picks one and reports
   it as a decision. The tests then fix that interface. Where two tasks' tests share
   a test file, the later task's copy holds the full file, including the earlier
   task's additions.
6. **Blocking questions.** A question the specs and design don't settle, and that
   isn't low-stakes, is not guessed. If any such question exists, the author hands
   off nothing and returns `blocked: weak-spec` with every question listed. Plan
   gaps come back all together, before code.
7. **Report.** For each task:
   - one line per test: `<test id> — fails if <regression>`;
   - or `no behaviour change — <reason>` for a task without behaviour (D8).

   Then the decisions it took (item 5) and any non-blocking questions.
8. **Re-dispatch with a defect.** The author reads the defect detail and revises or
   defends only that task's tests. It then runs `gates tests handoff <change> --task
   N.M`. A defended test is re-handed-off unchanged, with the defence in the report.

### D3. The holding area

The authored tests live in the committed change branch at:

```
.specloop/authored/<change>/<N.M>/<real path>.authored
.specloop/authored/<change>/<N.M>/NO-TESTS          ← reason text, behaviour-free task
```

- **The `.authored` suffix** means no test runner discovers these files, whatever
  the stack. So `ci` stays green while they sit in the tree, and they can be committed
  with the authoring phase (done ⟺ committed).
- **Each holding file is the full intended content** of its real path after that
  task. It is not a patch.
- **Placement is a move.** When a task's tests are placed, the task commit removes
  that task's holding directory. At the end, `.specloop/authored/<change>/` is empty
  and gone.
- **The ledger row keeps the blobs,** so nothing is lost when the files move.

### D4. The shim commands

- **`gates tests brief <change>`**: see D9.
- **`gates tests handoff <change> [--task N.M] [--inline]`** reads the holding area
  and records event `tests-handoff`:
  - `author`: `separate` or `inline`;
  - `tests`: `{task: {path: blob}}`;
  - `base`: `{path: blob|null}`, the real path's content at authoring time, for paths
    that already existed;
  - `no_behaviour`: `{task: reason}`.

  With `--task`, it re-records one task, and that task's entry supersedes the earlier
  one. It refuses when the holding area is empty or a task directory holds both tests
  and `NO-TESTS`.
- **`gates tests place <N.M>`** moves N.M's holding files onto their real paths.
  - It refuses when a real path's current content matches neither its recorded `base`
    nor the blob an earlier task placed there. In that case something changed the file
    since authoring, which is a defect for the author, not an overwrite.
  - For a behaviour-free task it places nothing and says so.
  - It records event `tests-placed` for N.M.
- **`gates tests check [--task N.M]`** fails unless all of these hold for the task:
  1. every placed path is staged with exactly its recorded blob;
  2. no other task's holding files differ from the latest handoff;
  3. for a task with tests, a `unit` run was recorded *after* `tests-placed` and
     failed with an exit other than 75.

  Condition 3 is new: it turns red-before-green from a prompt instruction into a
  checked fact. The check passes on `main`, with no change resolvable, or with no
  handoff for the change.
- **`gates tests defect <N.M> --detail "…"`** records event `test-defect`. It refuses
  a third defect for one task and names the `oracle-conflict` halt instead.
- **`gates tests show [<change>]`** prints the author, the tasks with their paths or
  their no-behaviour reason, placement state, and defect counts.

**The ledger row shape** gains optional `tests`, `base` and `no_behaviour` fields,
added backward-compatibly as `escalation-outcomes` did. Older rows read them as
`null`.

**Where the check runs.** `hooks/gate-commit.sh` and `templates/git-hooks/pre-commit`
run `gates tests check` right after their `ci` marker check, so every commit-creating
path the marker check covers is covered here too.

**Why the check runs at commit, not on Write/Edit.** A tool hook can't reliably tell
the author from the implementer, and the author legitimately rewrites holding files on
a defect. The commit is where the roles' outputs join.

**The authoring commit itself.** It holds only holding-area files and the ledger. At
that commit no task has been placed and no `tests-placed` row exists, so check
condition 2 applies against the handoff just recorded, and conditions 1 and 3 have
nothing to check. That makes the check vacuous, not skipped.

### D5. Defects

- **The implementer never edits a placed or held test.** It records
  `gates tests defect N.M --detail "…"` and stops at the task boundary with a clean
  tree.
- **Who re-dispatches the author:**
  - interactive or headless top level: the session running the loop does it;
  - `tdd-implementer`, or a lane under an orchestrator: it halts with cause
    `oracle-conflict`, detail `test-defect N.M: …`. Whoever dispatched it
    re-dispatches the author, then resumes the implementer at N.M.
- **Two defects per task, then a human.** A third is refused by the shim, and the loop
  halts with `oracle-conflict`, carrying both the defect text and the author's
  defence.
- **Tests that pass before implementation.** If the placed tests pass on the first
  `unit` run, they don't exercise this task's behaviour, or the task is already done.
  The implementer records a defect saying so, and doesn't implement against a green
  oracle.

### D6. Who orchestrates, and how it fits an orchestrator

This answers the review question on PR specloop PR 86. The authoring phase is dispatched by
whoever dispatches implementation. Because it runs once per change, before
implementation, it is always a sibling of the implementer, never a child:

| Entry | Authoring phase dispatched by | Implementer |
|---|---|---|
| Interactive `/specloop:tdd-apply` | the session, at the start | the session itself |
| Headless `claude -p "/specloop:tdd-apply …"` | the same top-level session | itself |
| A session spawning `tdd-implementer` | that session, before the spawn | the subagent |
| An orchestrator over lanes (#37) | the orchestrator, per change, before the lane | the lane |

- **A missing handoff blocks the implementer.** When `loop.test-author` is `separate`
  and a change has no handoff, `tdd-apply` and `tdd-implementer` don't write tests
  themselves. The halt cause is `missing-oracle`, detail "tests not authored — dispatch
  test-author for <change> first". Falling back silently to inline would quietly undo
  the default the maintainer chose.
- **The session brief says so.** Its "approved and ready" line now offers
  "dispatch test-author, then the implementer", or just the implementer when a
  handoff exists.
- **Orchestrator lifecycle (#37):**
  - `approved → authored → dispatched → ready | halted`;
  - a `test-defect` halt routes to the author, not to a human, until the two-defect
    limit is reached.

  #37's dispatch state and `gates dispatch next` can read "authored" straight from the
  ledger. This change adds nothing to #37's scope, but it leaves the state readable
  when #37 lands.

**Inline** (`loop.test-author: inline`) uses the same mechanism: the implementer runs
the authoring phase itself, into the holding area, before its first task. It hands off
with `--inline` and is then bound by the same lock. Only the author's independence is
lost, and the outcomes view shows it.

### D7. The authored set is reviewed before implementation begins

After handoff and before the authoring commit, `convention-review` runs once over the
holding area, scoped to `specloop.test-quality` plus the project's `tests` rules. Each
finding goes back to the author in the same authoring phase, at most twice. After
that, the phase halts with `oracle-conflict`.

The verdict is recorded with `gates review record <clean|findings> --scope authored`.
The per-task review at the task gate still runs, and it now also flags a test file the
implementer added outside the handoff.

### D8. Behaviour-free tasks

A task that changes no behaviour gets a `NO-TESTS` file from the author, containing
the reason. Examples are a docs edit, a configuration rename, or a dependency bump
with no behavioural contract.

- The reason is recorded in the handoff's `no_behaviour` field.
- `place` does nothing for it, and `check` requires no red run.
- The authored-set review (D7) judges each claim. "No behaviour change" on a task
  that plainly changes behaviour is a `specloop.test-quality #13` finding.

The implementer can't declare a task behaviour-free; only the author can. That keeps
the claim on the same side as the tests.

### D9. Project-specific instructions reach the author deterministically

A Sonnet author writing to generic rules would reproduce the audit's problem in a new
form: tests that are technically clean but foreign to the project. So the project's
conventions are given to it by the shim, not left for it to discover.

**`gates tests brief <change>`** prints, and never decides:

- the paths of the change's `tasks.md`, `specs/**` and `design.md`, and each task
  line with its id;
- **project test rules:** the rule-ids whose `Applies to:` includes `tests`, resolved
  against `conventions.rules-doc`;
- **surface rules:** for each task, the hot surfaces' rule-ids for the paths the task
  line and design name. It is the same resolution `gates rules --changed` performs;
- **built-in rules:** `specloop.test-quality` and its plugin path;
- **the runner:** the command the `unit` gate is bound to, printed and never run, so
  the author knows the runner and framework without guessing;
- **where tests live:** up to five existing test *paths* per task, found by shared
  directory or file stem. They are listed as paths only, and the author reads no
  contents (D2 item 2);
- **shared fixtures and helpers:** files the project's `tests` rules name. When no
  rule names them, the brief lists files under the sibling test directories whose
  names mark them as shared, such as `conftest`, `fixtures`, `helpers`, `factories`
  or `support`. The author may read these.
- **"none" lines:** when there are no project test rules, no siblings, or no shared
  fixtures, the brief says so explicitly. The no-rules line names the capture step
  that adds test rules.

**`Applies to: tests`** is a review-only target, alongside `code`. `gates conventions
sync` never emits it, `gates validate` accepts it, and `gates rules` always includes
`tests`-tagged ids for review. The author and the reviewer therefore read the same
rules.

**Onboarding captures these rules.** `gates-init` step 6 gains a test-conventions
pass. It drafts `Applies to: tests` candidates from the project's existing material,
covering:
- where tests live, and how they are named;
- shared fixtures and factories;
- what may be faked and what must be real;
- which layer owns what;
- the runner's handling of undefined steps and retries.

It confirms each candidate with the adopter. `templates/rules-doc.template.md` gains
one example `tests` section, and `adoption-prompts` asks existing projects the same
question on upgrade.

### D10. The regression-first route

On the regression-first route, the author writes the regression test from
`report.md`'s reproduction, as that task's authored test. `place`, the enforced red
run, and the lock then apply unchanged. The implementer writes only the fix, and can
no longer reshape the repro until it passes.

`schema-declared-flow` renames that route's section of `tdd-apply`, and whichever
change lands second rebases the prose.

### D11. Outcomes

`gates stats --outcomes` derives, per change:
- `authorship`: `separate`, `inline`, `mixed` or `none`;
- `test_defects`: the count of defects.

Both appear in the JSON and as two table columns. A change with no handoff reports
`none` and 0, and is otherwise counted as before.

## Cost

This design costs one author dispatch and one authored-set review per change, plus one
dispatch per defect. That is less than the per-task version this replaces, which
dispatched once per task. Projects that don't want an independent author declare
`inline`.

## Risks

- **Mid-change design discoveries invalidate later tests.** Each is a defect (D5),
  counted in outcomes. If the rate turns out high in practice, the fix is better
  interfaces in the design, which the author's up-front questions already push for.
- **A misconfigured runner passes undefined or skipped tests.** The enforced red run
  (D4 check condition 3) then fails on the first task and surfaces the problem
  immediately.
- **Holding-area files are edited by hand.** `check` compares them to the handoff on
  every commit, so an edit either goes through `handoff --task` or blocks.

## Out of scope

- Hiding implementation files from the author at the tool level. The boundary is a
  prompt rule. The evidence that it held is the report's per-test regression lines and
  the authored-set review.
- #37's dispatch state and `gates dispatch next`. D6 only keeps the authoring state
  readable for them.
