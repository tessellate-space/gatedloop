# gatedloop setup — the integration contract

gatedloop ships the **process** (the loop, agents, skills, session brief, the `gates` shim). Your project provides the **bindings**. This document is the contract between them, and it covers both things gatedloop owns: **getting a project onto the loop** (`/gatedloop:gates-init` and this document) and **running it** (everything after). Onboarding is not a smaller version of the real product — setup friction is the main reason a project never reaches a working spec-driven loop at all, so it gets the same weight here as enforcement does.

gatedloop does not author artifacts — OpenSpec does, through its own `/opsx:` commands, and keeps them current. gatedloop runs the gated loop over what they produce. That split is why the first prerequisite below is two things rather than one.

## Prerequisites

1. **OpenSpec, initialized *with its Claude Code integration*:**

   ```bash
   openspec init --tools claude     # creates openspec/ AND .claude/commands/opsx/*
   ```

   Supported: OpenSpec `1.14.3` to `1.14.3`, on macOS or Linux (Windows is not supported; the hooks are bash). [`docs/stability.md`](./docs/stability.md) declares the range, and `gates doctor` warns outside it.

   Non-negotiable — the workflow is built around it. `openspec list --json` working proves the first half; `.claude/commands/opsx/` existing proves the second. Without the `--tools claude` half you get the CLI but no way to author a change, and the loop has nothing to consume. `/gatedloop:gates-init` checks both and offers to fix the second.
2. **A task runner** — any of `just` / `npm` / `make` / `cargo` / … You write the recipe bodies; gatedloop only calls their names.
3. **Python 3.9+** on PATH for the `gates` shim. No required third-party dependencies; PyYAML is optional and enables full schema inspection. Every gate, hook and the loop's dispatch decision (`gates schema dispatch`) work without it — the shim falls back to a built-in minimal parser for the manifest (a `.gates.json` manifest needs nothing either way) and to a scoped reader for the two schema keys dispatch needs. Only `gates schema inspect`, which parses a whole third-party `schema.yaml`, requires it. `gates doctor` reports whether it is importable. To install: `python3 -m pip install --user pyyaml`, or `pipx`/`uv` if your Python is externally managed (PEP 668), where a plain `pip install` is refused.

The `gates` command itself needs no setup: the plugin's `bin/` directory is added to the Bash tool's PATH automatically while gatedloop is enabled, so `gates …` just works once the plugin is installed. Where that injection is missing, gatedloop's SessionStart hook adds a fallback PATH entry (see "Troubleshooting: the plugin is active but `gates` is not found" below).

### Troubleshooting: nothing from gatedloop appears at all

`/gatedloop:gates-init` opens with a `gates doctor` preflight that diagnoses the *partially*-wired states — OpenSpec CLI missing or drifted, a stale `gatesVersion`, `gates` not resolving on PATH (its `gates-on-path` row), hooks that need a fresh session. Its `shim-location` row says where the running shim lives: the installed plugin copy (with its version), a checkout, or another path. But there is one failure it structurally cannot reach: if **no** gatedloop command, skill, or session-brief output appears in a session at all, then no command bundled in the plugin — `gates doctor` included — is reachable to report its own absence.

The usual cause is a **config-profile mismatch**. Claude Code supports multiple configuration profiles via the `CLAUDE_CONFIG_DIR` environment variable, and a plugin installed under one profile is entirely invisible under another — no commands, no skills, no session brief, no error. Check it from a **plain shell**, independent of any gatedloop surface:

```bash
echo "$CLAUDE_CONFIG_DIR"          # which profile is active (empty = the default, ~/.claude)
```

Then confirm the plugin is registered under *that* profile (`/plugin` inside Claude Code, or inspect the profile's plugin config). If gatedloop was installed under a different profile than the one the session is using, install or enable it under the active one — no in-session diagnostic can do this for you, because reaching it is exactly what fails.

### Troubleshooting: the plugin is active but `gates` is not found

The other case: gatedloop's commands, skills and session brief all appear, and its hooks fire, but every `gates …` step fails with `gates: command not found` (`which gates` finds nothing). The binary is in the plugin's install directory; it just isn't on the Bash tool's PATH. This has been seen with a non-default `CLAUDE_CONFIG_DIR` (issue #40).

- **The fallback.** When Claude Code gives the SessionStart hook a `CLAUDE_ENV_FILE`, gatedloop's brief appends one line to it that puts the plugin's `bin/` at the *end* of PATH, so a `gates` already on PATH still wins. It takes effect in a **new session**; start one first.
- **By hand.** If a new session doesn't fix it, add the line yourself: `export PATH="$PATH:<plugin root>/bin"`. `CLAUDE_PLUGIN_ROOT` names the plugin root in hook scripts, but it is not set in the Bash tool's environment, so take the directory from `gates doctor` (below). A hard-coded versioned cache path breaks on the next plugin update, so redo it after updating.
- **Diagnosing.** Run the shim by its full path: `gates doctor`'s `gates-on-path` row warns when `gates` doesn't resolve and prints the exact `export` line for the copy you ran. It also says when the `gates` on PATH is a different copy from the one you ran.

## Brownfield: from an unconfigured project to a first green gate

Adding gatedloop to an existing project with none of this yet — no OpenSpec, no `.gates.yaml`. One command per step, in order:

1. `openspec init --tools claude` — creates `openspec/` and the `/opsx:` authoring commands. Prerequisite; nothing below works without it.
2. `/gatedloop:gates-init` — detects your task runner from the repo layout, proposes gates + surfaces, offers to write a starter conventions doc, and asks you to confirm anything it can't infer. Writes `.gates.yaml`.
3. `gates validate` — confirms the manifest itself is well-formed (`gates-init` already runs this before finishing, but it's yours to re-run any time you hand-edit).
4. `gates run ci` — confirms whether the gate you just bound currently passes on this project's actual code. `gates-init` runs this once automatically and reports the result either way: **red here is not a setup failure** — a brownfield project commonly binds a gate it doesn't pass yet, and that gap is often exactly why you're adopting gatedloop. The point of this step is that you find out *now*, from onboarding, rather than from a confusing refusal the first time `/gatedloop:tdd-apply` tries to commit.
5. `/opsx:propose <change>` — author your first change (OpenSpec's job: proposal, specs, design, tasks).
6. `/gatedloop:tdd-apply` — run the gated loop over it.

Steps 2–4 are what `/gatedloop:gates-init` does end to end; running it once takes you from step 1 to step 5's starting line.

## The two things you configure, in order

1. **Select a workflow schema** — decides *which artifacts* a change produces and in what order (proposal → specs → design → tasks, or a different shape entirely). Defaults to `spec-driven`, set in `openspec/config.yaml`'s `schema:` key; fork or install a different one when the default doesn't fit ("Changing how artifacts are authored" below). Do this first: it decides what a change's `tasks.md` even looks like, and the gate manifest has no say over that.
2. **Write `.gates.yaml`** — your gate commands and surfaces, detailed below. This is the only file gatedloop itself reads.

## The manifest: `.gates.yaml`

The single file you own. Three ways to create it, most-assisted first:

1. **Guided (recommended) — `/gatedloop:gates-init` inside Claude Code.** Detects your task runner, proposes gates + surfaces from your layout, and **asks you** (via question prompts) for anything it can't confidently infer — always pinning down the required `ci` gate before it finishes. Writes real commands, validates, and hands you a working manifest.
2. **Starter file — `gates init`.** Drops `templates/gates.yaml.template` at your repo root as `.gates.yaml` for you to fill in by hand. No agent needed.
3. **Manual.** Copy `templates/gates.yaml.template` yourself.

Whichever you use, finish with:

```bash
gates validate       # fails loud on a missing required gate or a dangling rule-id
```

### `gates` — abstract name → command
The workflow runs `gates run <gate>` and reads its **oracle**. Three terms, used deliberately from here on:

- **Gate** — a required checkpoint a change must pass (`ci`, `live-check`, …).
- **Oracle** — the machine-readable verdict a gate reads back. Concretely, an exit code — never a human's memory of having checked, and never a summary a model could talk itself out of. This is why `gates run <gate>` never inspects the command's body or its output, only whether it exited 0: an exit code is the one verdict shape that can't be argued with.
- **Hook** — what runs the gate automatically, so passing it isn't optional. (Today that's a documented step in a skill/agent's own instructions; hook-*enforced* gates — where the harness itself denies the next action on a red oracle — are `harden-unattended-loop`'s job.)

`gates run <gate>` never inspects the command's body, so any runner works.

| Gate | Required? | Called at | Meaning |
|---|---|---|---|
| `ci` | **yes** | per-task, before every commit | Aggregate build/test oracle — one exit code = "safe to commit". |
| `unit` | no | inner red→green loop | Fast unit tests. |
| `integration` | no | after tasks | Integration/API suite derived from specs. |
| `verify` | no | change completion | Spec → behavior/acceptance check. |
| `live-check` | no (per surface) | change completion (BLOCKING) | Runtime probe; runs every hot surface's `live-check`. |
| `eval` | no | change completion (ADVISORY) | Scored pipeline; `{dataset}`/`{score}` filled from `gates run eval <dataset> <score>`. Never blocks. |
| `confirm` | no | the merge step's step 5, on the merged tree (BLOCKING) | Your "bring the merged tree up and smoke it" recipe. A red or exit-75 `confirm` stops the merge before anything is pushed; undeclared, step 5 is skipped with a note. |

Optional gates that are absent are **skipped cleanly** — not an error. A missing **required** gate (`ci`) fails loud at `gates validate`.

**A blocking gate's runner must:**
- fail on an undefined test, or one skipped for a missing implementation — a skipped scenario that exits 0 reads as a pass;
- not retry a failure to green — a retry that passes hides a flaky test on a blocking path;
- keep model-dependent checks under `eval`, never under `ci`, `verify` or `live-check`.

Only your runner's configuration can honour this. gatedloop documents it and does not enforce it: `gates validate` can't inspect a command string for runner flags without naming a stack.

**The exit codes `gates run` owns.** A gate exits with its command's own code — 0 is
green, anything else is red — except for one reserved code the shim itself uses when the
gate body **never ran**: **75**. It has two causes, told apart by the first line the
shim prints and by the ledger row's `precondition` field:

| First line begins | Cause | Ledger row | What the loop does |
|---|---|---|---|
| `gatedloop: precondition '<cmd>' failed` | a declared `requires` failed (below) | `precondition: "<cmd>"` | halts: the environment is absent, never the code |
| `gatedloop: lock busy` | a serialized gate's lock stayed held past `concurrency.max-wait-seconds` (below) | `precondition: "lock-busy"` | re-runs the identical command, at most three times, then halts with cause `environment` |

Both prefixes are stable. `gates lock status` shows who holds a serialized gate's lock.

### Preconditions: a gate/live-check value can declare `requires`

A gate value and a surface's `live-check` value both accept a mapping form
alongside the plain command string:

```yaml
gates:
  integration: { run: "just it", requires: "just stack-check" }
```

`run` is the command that used to be the whole value; a scalar string is
still fully equivalent to `{run: <that string>}` and behaves byte-for-byte
as before — this is purely additive. `requires` is optional and is itself
just a command whose body the shim never inspects, same as `run`.

When `requires` is declared, `gates run <gate>` executes it **first**. If it
exits 0, the gate body runs exactly as it always has. If it exits non-zero,
the shim reports `gatedloop: precondition '<cmd>' failed (exit N) — gate
'<gate>' was not run`, **never runs the gate body**, writes no marker, and
exits with the **reserved code 75** — distinct from both a green run (0) and
an ordinary gate failure (whatever the gate body itself returns). A
precondition failure is not a verdict on your code; it means the environment
the gate needs isn't up. The loop (`tdd-apply`, `tdd-implementer`) treats
this exit 75 as "fix or boot the environment, never the code" — it does not retry
the gate unchanged and does not investigate the report as a test failure.

The same `requires` field is supported on a surface's `live-check`; when
`gates run live-check` selects a hot surface whose `requires` fails, no probe
body runs **for any hot surface** (a partial "some probes ran" state on a
down environment would be its own source of ambiguity), no marker is
written, and the run exits 75.

**Exit code 75 is reserved once you declare `requires`** (or serialize a gate:
a lock wait that reaches its bound exits 75 too, see `concurrency` below). If your own gate
or probe body also happens to exit 75 on its own failure, that's an accepted
collision (the two are still distinguishable: the stderr line and the ledger
row's `outcome` field name which one happened) — but avoid relying on 75 as
your gate body's own meaningful exit code.

**Write `requires` as a fast probe, not a suite.** It runs before every
invocation of the gate it guards, so a slow or hanging precondition delays
every run. A cheap connectivity/health check is the intent; re-running your
test suite as a "precondition" defeats the point.

**A warm-up belongs in `requires` too.** A `requires` command may *prepare* the
environment as well as probe it, provided it is idempotent and exits 0 once the
environment is ready: a first-request warm-up of a freshly started stack, for
example, so a cold lane's first end-to-end scenario doesn't fail on start-up. It
runs **before** the gate's verdict, so it is not a retry: nothing is re-run after a
failure, and a red gate body stays red. A cold-lane warm-up for `confirm` or a
`live-check` goes here, never in a loop that re-runs the gate until it passes.

### `concurrency` — serialized gates, and the bound on their wait

`concurrency.serialize` names gates (or `live-check`) that `gates run` serializes
machine-wide across every worktree of the repo, with a lock held only around the gate
command ([`docs/worktree-lanes.md`](docs/worktree-lanes.md)). A run that finds the
lock held prints one waiting line at once and then at most one every 30 s, each naming
the holder's pid, whether it is alive, how long it has held the lock, and how long
this run has waited.

```yaml
concurrency:
  serialize: [ci]
  max-wait-seconds: 480   # optional; a positive integer, default 480
  merge-wait-seconds: 900 # optional; gates merge's own waits, default max-wait-seconds
```

The wait is bounded by `concurrency.max-wait-seconds`. 480 keeps a wait below the
host's 600 s tool-call cap, which would otherwise background the gate. When the bound
is reached, the gate command never runs: the shim prints a line beginning with the
stable prefix **`gatedloop: lock busy`**, writes a ledger row with `outcome:
"precondition-failed"` and `precondition: "lock-busy"`, and exits **75**. That is the
same "try again" exit as a failed `requires`, and the prefix is what tells them apart:
the loop re-runs the identical command on `gatedloop: lock busy` (at most three times,
then halts with cause `environment`), and halts at once on any other exit 75.

`gates lock status` shows, for each serialized gate, whether its lock is free or held,
and if held, by which pid, for how long, and whether that pid is alive (`--json` for
the same data as one document). It probes the lock itself, so a lock whose metadata
names an exited pid but that nobody holds reads as free. A live holder past an hour is
flagged "possibly hung", with a `ps` command to inspect it. gatedloop never terminates
a holder: a crashed one frees the lock with its file descriptors, and a hung one is a
human's call.

One more lock exists that you never declare: **`merge`**. The merge step holds it for
its whole run, because two local merges into one target from one machine can't both
be right, so it is always serialized and bounded by the same
`concurrency.max-wait-seconds`. A busy one is the same `gatedloop: lock busy` exit 75.
`gates lock status` lists it once it has ever been taken.

**A waiting merge goes first.** When `gates merge` waits on a serialized gate's lock —
`ci` at its step 3, `confirm` at step 5 — it holds a **priority claim** beside the lock
file (`<gate>.lock.priority`, naming its pid). Every other waiter that sees a live claim
keeps waiting, even once the lock comes free, so the merge takes it next; the run in
progress is never interrupted, so the merge waits at most for that one run. A claim whose
pid is dead is ignored and removed by the next waiter that sees it. Merges are themselves
serialized by the `merge` lock, so at most one claim exists per gate. `gates lock status`
shows it on the gate's line (`ci: held by pid N (alive) for 3m12s; merge pid M waiting
with priority`, and a `priority_pid` field under `--json`).

The merge's own wait on those locks is bounded by **`concurrency.merge-wait-seconds`**, a
positive integer that defaults to `max-wait-seconds`. Since the merge waits for one
holder's run, raise it alone when your full `ci` outlasts the general bound. The `merge`
lock itself keeps `max-wait-seconds`.

### `surfaces` — glob → rules + live-check
A change's touched files decide which surfaces are **hot**. The hot set drives two things at once:
- **convention review scope** — the union of the hot surfaces' `rules`.
- **live self-check** — every hot surface's `live-check` command.

```yaml
surfaces:
  - name: backend
    match: "backend/app/**"        # a glob, or a list of globs
    rules: [layering, routers-never-query-db]
    live-check: "just smoke"
```

No distinct areas? One catch-all surface: `match: "**"`.

**Identically-spelled `live-check` commands run once per invocation.** If two
hot surfaces bind the exact same command string, that is one recipe, not two —
string equality *is* recipe identity, since the manifest binds plain commands
rather than some richer identity (a hash of an expanded command, env, cwd).
The one execution is attributed to every surface that binds it in the log
(`live-check [frontend, e2e]`), and running it twice could never report *less*
than the truth — only more, which is exactly how a non-idempotent suite's
flake would get double-counted as two independent failures instead of one. If
two surfaces want the same suite spelled differently, that is two declared
recipes, and running both is the declared meaning — spell it once and share it
across surfaces if that isn't what you want.

**Glob matching is fail-hot, by design.** Matching is `fnmatch`, and `fnmatch`'s
`*` crosses path separators — so `match: "*.md"` also matches `docs/deep/x.md`,
not only a top-level `x.md`. This is the documented contract, not a bug to
route around: the one direction of error the shim permits is a surface running
**hotter** than its glob's literal, path-separator-exact reading — more rules
apply, more live-checks run — never colder. A narrower matcher would risk the
opposite (a real change silently missing its surface), which is the failure
this design refuses to introduce for the sake of glob precision. Write globs
assuming this reach (`"backend/app/**"` also matches nested paths you didn't
expect) and rely on file review, not the glob's specificity, for anything
that must not be treated as hot.

**Brace alternation (`{a,b}`) is expanded, not treated as a literal.**
`match: "{bin,tests}/**"` selects the union of `bin/**` and `tests/**` —
multiple groups and a group nested inside another both expand to the full
cross product of their alternatives. Before this, a brace pattern silently
matched nothing (`fnmatch` treats `{` as a literal character), a bug this
release fixes; if you already wrote a brace glob expecting it to select,
it now genuinely does — the same **err-hot** direction as the paragraph
above, so this can only *enlarge* a hot set (more rules, more live-checks),
never shrink one. The supported subset is one or more `{comma,separated}`
groups, with nesting; there is no numeric range (`{1..9}`) and no escaping.
An unbalanced `{`, an empty group (`{}`), or an empty alternative
(`{a,,b}`) is rejected — fails `gates validate` loud, naming the surface
and the offending pattern, rather than silently matching nothing.

### `rules` — id or inline prose
Each `rules:` entry is either:
- a **rule-id** resolved against `conventions.rules-doc` (recommended — single source of prose, stable handle to cite in findings), or
- **inline prose** (an escape hatch for projects with no addressable rules-doc).

A rule-id that doesn't resolve in the rules-doc fails loud at `gates validate`.

### `conventions.rules-doc`
Path to your canonical conventions document — a standalone file with `### <rule-id>` sections. Start from `templates/rules-doc.template.md`. **Never point this at `openspec/config.yaml`**: its own `rules:` key is a different, incompatible shape (a mapping of artifact id → array of strings, consumed by OpenSpec's artifact steps) — using it as a hand-written rules-doc is exactly what silently disabled convention review on gatedloop's own repo before `reposition-gatedloop` fixed it. If your project uses OpenSpec, give a rule an `Applies to: <artifact-id>` line and run `gates conventions sync` to *generate* `openspec/config.yaml`'s `rules:` from your rules-doc instead of writing it by hand.

Layering rules (what counts as domain and I/O, where interfaces and their fakes live) are the ones the loop consults before writing code: its red step reads your rules for the paths a task touches before it classifies code or chooses a seam, and halts rather than invent a seam no rule or design defines.

**One rule is built in.** `gatedloop.test-quality` ships inside the plugin (`rules/loop-rules.md`), and `gates rules` lists it for every diff, so convention review always holds the tests a change adds or changes to it. You don't declare it. Where one of your own rules contradicts one of its items, yours wins.

**Test conventions are `Applies to: tests` rules.** Tag a rule `Applies to: tests` for how your project writes tests — where they live and how they are named, the shared fixtures to build on, what may be faked. Like `code`, it is review-only (`gates conventions sync` never emits it), and `gates rules` lists it for every diff whatever surfaces are hot. The test author reads the same rules through `gates tests brief`. `/gatedloop:gates-init` step 6 drafts them from your existing material.

### `loop.test-author` — who writes a change's tests
```yaml
loop:
  test-author: separate   # default; or `inline`
```
A change's failing tests are written **once per change, before its first task**, by an agent that does not implement it (`split-test-author`). Under `separate` (the default, also when the block is absent) that is the `test-author` agent (Sonnet), dispatched by whoever dispatches the implementer: the interactive or headless `/gatedloop:tdd-apply` session does it itself; a session spawning `tdd-implementer` dispatches it first; an orchestrator dispatches it per change, before the lane. It is always a sibling of the implementer, never a child, and an implementer started under `separate` with no authored tests halts with `missing-oracle` rather than writing its own. Under `inline` the implementer runs the same authoring phase itself, bound by the same lock — only the author's independence is lost, and `gates stats --outcomes` reports it. Any other value fails `gates validate`.

The authoring phase:
1. The author reads `gates tests brief <change>` — the change's artifacts and task lines, each task's declared oracle (or that the author decides, for an untagged task), your `tests` rules, each task's surface rules, the built-in rule, the command `unit` is bound to (printed, never run), existing test *paths* near each task's code, and your shared fixtures. It reads public interfaces, never function bodies and never the contents of existing tests.
2. It writes every task's tests into the **holding area**, `.gatedloop/authored/<change>/<N.M>/<real path>.authored` (the full intended file after that task), or `<N.M>/NO-TESTS` with a reason for a task that changes no behaviour. A task whose tests **all** pin behaviour the tree already has (characterization tests before a refactor, a guard for output the task must not change) also gets `<N.M>/CHARACTERIZATION` with its reason, beside its tests; a task with both `CHARACTERIZATION` and `NO-TESTS` is refused at handoff. A task mixing new red tests with such guards needs no declaration. The `.authored` suffix means no test runner discovers them, so `ci` stays green while they are committed.
3. `gates tests handoff <change>` records every blob in the ledger; convention review checks the whole set once (`gates review record … --scope authored`); the holding area and the ledger are committed as `author tests: <change>`. Once a task is placed, its holding directory is empty, so a later full handoff would drop it: `gates tests handoff` without `--task` then refuses, naming the placed task, and the tasks being re-authored are handed off with `--task <N.M>`.

Per task, `gates tests place <N.M>` moves that task's tests onto their real paths (over the file as it was before the change, as main last delivered it at `git merge-base HEAD <target>`, or as an earlier placement left it — any other content is a test defect), `gates run unit --task <N.M>` must fail, and the commit hooks run `gates tests check`, which refuses a placed or held test that differs from the handoff and a placement with no failing `unit` run after it (exit 75, a precondition failure, does not count). For a `characterization` task the check is reversed: the first `unit` run after placement must be **green**, and a red one there is a defect, because a characterization test never seen to pass on the tree as it was pins nothing. Only the author declares it, the declaration is locked like the tests, and authored-set review judges it.

A test the implementer judges wrong, or placed tests that pass before anything is implemented, go back to the author with `gates tests defect <N.M> --kind setup|assertion|green --detail …`. The kind is required, and each has its own cap per task:

| Kind | Means | Cap | Past the cap |
|---|---|---|---|
| `setup` | the test cannot run as written: a path, import, fixture or environment it assumes is wrong | 3 | halt `weak-spec`: the author's brief is missing something |
| `assertion` | the test runs, and asserts behaviour the spec doesn't require or contradicts | 2 | halt `oracle-conflict`: a human decides |
| `green` | the placed tests passed before any implementation, on a task not declared `characterization`: an observation, not a claim the tests are wrong. The author re-declares the task (`CHARACTERIZATION` with a reason, or `NO-TESTS`) or rewrites the tests to fail against the tree | 1 | halt `oracle-conflict`: a human decides |

So fixture mistakes no longer spend the behaviour cap, and a test that is right but green on its first run has a truthful record. A defect row recorded before kinds existed counts as `assertion`.

A defect at a task already committed **reopens** it: the author re-hands it off and it is placed again as usual, and the red run its first placement recorded stays the record, so no second red run is demanded against committed code. A **halt** at a completed task leaves its placement in force (a halt in flight still voids it). Completion is read from history: a task is completed at a ledger row when the commit that checks it in `tasks.md` comes before the first commit carrying the row, so ticking a task in the same commit as a halt does not count. A ledger-only commit (a halt or defect row on its own) skips the lock in both commit hooks, since it cannot change a test. `gates tests show` lists each task's declared oracle (`oracle:` in its text, an `oracle` field in `--json`) and each defect with its kind and detail, and `gates stats --outcomes` counts them by kind, so a mislabelled defect is visible.

**A task's oracle, declared in the plan** (`task-oracle`). A task line in `tasks.md` may end with its oracle tag, so the plan a human approves fixes each task's kind before any test exists, instead of the author guessing it from prose:
```markdown
- [ ] 3.1 Parse the header [oracle: unit]                          # red first on `unit`
- [ ] 3.2 Verify the rows 3.1 wrote [oracle: unit characterization] # green first on `unit`
- [ ] 5.1 Wire the end-to-end step [oracle: integration]           # red first on `integration`
- [ ] 6.1 Describe the flag in the README [oracle: none]            # no tests
```
The tag is the line's last bracketed span; anything mid-line is prose. `<gate>` is any gate your `.gates.yaml` declares except `ci` (green at every commit), `live-check` (it probes a surface, not a task), `eval` (an advisory score) and `confirm` (it runs only on the merged tree), none of which can judge one task. `characterization` means the task's tests must pass on their first run under that gate rather than fail; `none` means the task adds no tests. A task with no tag behaves exactly as before. `gates validate` checks every tag in the active changes and fails on an unknown gate, an excluded gate or a malformed tag, naming the change, the task and the tag. A task id is two or more dot-separated numbers, optionally ending in one lowercase letter (`1.2`, `1.2.3`, `1.2a` for a task a plan amendment inserts), and every reader of `tasks.md` reads a lettered id as it reads `1.2`; listings order tasks naturally (`1.2`, `1.2a`, `1.9`, `1.10`). A tag on a line whose id is outside that form (an unnumbered task) is reported as a warning, since the tag would otherwise be ignored silently. A gate you name as an oracle should accept the same `-- <args>` scoping `unit` does, or each red step runs it whole.

A tag changes only through the approved plan. The approval sha covers the tags ("The declared approval policy" below), so a retag on the merge target fails `check-implement` until it is re-attested; and on the change branch, `gates tests handoff`, the commit lock and `gates tests check --ref` refuse a task whose tag differs from its tag in the merge target's `tasks.md`, naming the task, both tags and the route: amend the plan on the target and re-attest. A task the target does not have (a change proposed on its own branch) is not compared.

The brief prints each tag to the author, and `gates tests handoff` refuses a holding area that contradicts one, naming the task, the tag and what the plan requires:
- tests, or a `CHARACTERIZATION` marker, for a task tagged `none`;
- `NO-TESTS` for a task tagged with a gate;
- a task tagged `characterization` without its `CHARACTERIZATION` marker;
- a `CHARACTERIZATION` marker on a task the plan says goes red first.

The handoff does not check that the tests exercise the declared gate (the shim cannot know which files a gate runs); the red run on that gate does, since a test the gate never runs cannot go red under it. An author who holds a tag is wrong stops and reports it as `weak-spec`: the plan is amended and re-approved, never worked around.

```yaml
loop:
  task-oracle: optional   # default; or `required`
```
Under `required`, the handoff also refuses a change with any untagged task, naming each one and the tag syntax. The check runs at handoff, so a change already handed off before you set the key is unaffected. Any other value fails `gates validate`.

### `loop.attempts` and `loop.fresh-restarts` — the retry budget
```yaml
loop:
  attempts: 2         # default: failed attempts per task, per context
  fresh-restarts: 1   # default: restarts per task; 0 disables them
```
The loop's stopping rule is enforced from the ledger, not by the prompt (`retry-budget`). For a task, a **failed attempt** is a red run of its oracle gate or of `ci`, recorded after the task's RED run (its first red oracle-gate run since the later of `gates task start` and its latest `gates tests place`) and after its latest restart. The oracle gate is the one the plan's tag declares, or `unit` for an untagged task, so an `[oracle: integration]` task's budget starts at its first red `integration` run. Counting from the placement means the red runs of a test-defect cycle, against tests the author has since replaced, spend nothing. Exit 75 never counts, because nothing judged the code. A green run doesn't reset the count, and the caller's `--attempt` is only a label, so a wrong value buys nothing. A `gates run ci` or `unit` with no `--task` belongs to the task the loop is in (the latest `task-start` after the handoff). A run with no task at all is never budgeted, so a project not running the loop is unaffected.

**What refuses, and why.** Once a task's count reaches `loop.attempts`, `gates run unit` and `gates run ci` for it exit 1 without running the gate and without writing a ledger row. The message names the count, the budget and the way forward. That's `gates attempt restart <N.M>` while a restart remains; otherwise it's a halt with cause `stalled`. The merge's unscoped `ci` is never a task's attempt.

```bash
gates attempt note 1.2 --hypothesis "..." --changed "..." --oracle "..." --next "..."   # after every failed attempt
gates attempt notes 1.2 [--json]   # the task's notes, oldest first, across restarts
gates attempt restart 1.2          # the dispatcher's fresh restart: resets the count
```
- **`gates attempt note`** appends an `attempt-note` row numbered with the task's current failed-attempt count. Its four fields are required, single-line and at most 200 characters each. An over-long, multi-line or empty field is refused, naming it, and nothing is written. A resuming or restarted agent reads `gates attempt notes`, not a transcript.
- **`gates attempt restart`** refuses on a dirty working tree (staged, unstaged or untracked) — the task's placed tests at exactly their placed content, and the removal of their holding files, count as clean, while a placed test edited after placement is named in the refusal — and once the task's `restart` rows number `loop.fresh-restarts`. Otherwise it records a `restart` row, and the count starts again from zero. The implementer never restarts itself. It halts `stalled`, and the halt row carries `restart_available`, computed by the shim. `/gatedloop:tdd-apply`, or your orchestrator, then dispatches one fresh implementer whose brief holds only the spec, the task and the notes. That agent's first act is the restart.

Either key must be a non-negative integer, or `gates validate` fails naming it. `attempts: 0` is legal but warns: the first failed attempt after RED refuses. `gates stats --outcomes` reports `restarts` and `restart_recovered` (restarts after which the task reached a green `ci`) per change. A restart is never an intervention, because no human acted.

**Cost:** one author dispatch and one authored-set review per change, plus one author dispatch per defect.

### Token usage: `usage` rows, `economics` and `loop.token-budget`
```yaml
economics:                 # optional: only `gates stats --cost` reads it
  currency: USD
  prices:                  # per million tokens, per model name as the usage rows record it
    "<model-name>": { input: 3, output: 15, cache-read: 0.3, cache-write: 3.75 }
loop:
  token-budget: 5000000    # optional, no default: tokens a change may spend
```
The ledger records what the host session spent on each task (`token-ledger`). Two hooks write a `usage` row through `gates usage record`, and nothing else does:

- **At a gated commit.** Once `hooks/gate-commit.sh` has allowed a commit, it passes the hook input's `transcript_path` to `gates usage record --stage`. The row covers the task's window, and the ledger is staged so the row lands in the commit it costs.
- **At every session stop.** `hooks/continue-loop.sh` records the task in flight before it decides whether to continue, so a task that halts or is abandoned is costed up to the stop. With no task in flight (the authoring phase), the row is `task: null`, the unattributed bucket.

A row holds `task`, `window` (`from`, `to`), `messages` (assistant messages counted, subagents' included), `source`, and `tokens`, which maps each model name to its `input`, `output`, `cache_read` and `cache_write` counts. It holds counts only, never a line of transcript text. A window starts at the later of the task's latest `gates task start` and the end of its latest counted usage row, so two flushes never count a message twice: the second writes zero. `source` says where the counts came from:

| `source` | Counts | When |
|---|---|---|
| `claude-code-transcript` | yes | the hook input named a transcript that parsed. Sibling subagent transcripts under the session's directory are counted with it. |
| `no-transcript` | null | no transcript path: a human's session, another host, or the git-layer `pre-commit` hook, which has no hook input |
| `unreadable-transcript` | null | the file exists but nothing in it parsed; `detail` says why |

A null-count row never moves the window, so the next readable flush still covers that span. A missing source is never a failure: `gates usage record` exits 0 and the commit or stop goes ahead. It writes nothing off a change branch or before the change has a ledger. Only a ledger that can't be written exits 1, and the hooks ignore even that. A tree whose only change is appended usage rows still counts as a clean task boundary for the `Stop` hook's continue decision and for `gates attempt restart`.

```bash
gates usage record [--task N.M] [--transcript <path>] [--change <name>] [--stage]   # what the hooks run; the task defaults to the one in flight
gates usage show [--change <name>] [--json]                      # the change's usage rows and tokens per task
gates stats --cost                                               # price the recorded tokens with economics.prices
```

**Prices are your binding.** `economics.prices` maps a model name to its prices per million tokens for `input`, `output`, `cache-read` and `cache-write`, in the one `currency` you declare. `gates validate` checks the shape: a currency string when prices are declared, all four prices, each a non-negative number. It checks nothing about the model names. `gates stats --cost` multiplies each model's counts by its prices, prints a cost per task and per change, and names every recorded model it found no price for, with its tokens, beside the priced subtotal. Without the block, `--cost` prints tokens only and says no prices are declared. Prices affect `--cost` and nothing else; the tokens are what the ledger stores.

**The budget is enforced in code.** With `loop.token-budget` declared (a positive integer, or `gates validate` fails), task-bearing `gates run unit` and `gates run ci` sum every usage row of the change, counting input, output, cache-read and cache-write across every model. At or above the budget they exit 1 without running the gate, naming the budget, the recorded spend and `gates halt record budget --task <N.M>`. The loop halts with cause `budget`. It never retries and never restarts, because the spend belongs to the change. The merge's unscoped `ci` and a run with no task are never budgeted. Without the key, no budget applies. **The lag:** only recorded rows count, and the task in flight is recorded at its commit or the session stop, so a change can overshoot by up to one task's spend in one session. The refusal says so.

### Scoped `ci`/`unit` — per-task gate cost proportional to what a task touched

A surface MAY declare its own `ci`/`unit` command, cheaper than the aggregate one:

```yaml
surfaces:
  - name: frontend
    match: "frontend/**"
    gates:            # optional, per-surface overrides
      ci: "just ci-frontend"
      unit: "just unit-frontend"
```

**Selection is err-full, in code, exactly like `rules`/`live-check` selection.**
`gates run ci` computes the relevant diff's hot set with the same deterministic
selection and runs the scoped command **only** when that hot set is exactly **one**
surface and that surface declares the override. Every other case — no hot surface, an
unmatched changed file, more than one hot surface, or a hot surface with no override —
runs the globally declared `ci` unchanged. This can only ever *narrow* to a declared
scoped command; it can never skip the gate outright. `ci` scopes off the **staged
diff** (what will actually be committed); `unit` scopes off the **working tree**
(tests are written before staging, per the loop's own red step).

**Catch-all surfaces are excluded from the one-surface count.** A surface whose
pattern matches every path (`match: "**"`) is ignored when deciding whether the diff
is single-surface — most manifests declare one, and counting it would make every
diff look "multi-surface" and silently disable scoping forever. `gates validate`
notes this exclusion, and rejects a `gates:` override naming a gate that isn't
`ci`/`unit`, or that has no matching global declaration to narrow from.

**An unmatched path errs full, catch-all or not.** A changed path that no
non-catch-all surface matches counts as unmatched even when a catch-all surface
matches it, so a diff holding one scoped surface's file and, say, a top-level script
runs the global gate, and the announcement names the path (`ci[full] — scripts/build.sh
matches no surface`). Add the path to a surface to scope it again. The loop's own
state under `.gatedloop/` (the ledger rows every task commit stages, the held tests)
is never counted, and neither is the current change's own
`openspec/changes/<change>/tasks.md` (the change the branch resolves to): every task
commit stages its `[x]`, so counting it would end scoping for every task commit, as
unmatched or as a second hot surface. Another change's `tasks.md` is an ordinary path.
`gates surfaces` and `gates rules` still see the tick, so review scope is unchanged.

**A multi-surface `unit` runs every hot surface's oracle.** When the working tree
spans two or more non-catch-all surfaces and every path is matched, `gates run unit`
runs each hot surface's `unit` override in surface order, plus the global `unit` once
if any hot surface declares none. Identical commands run once, arguments after `--`
reach each command, every precondition is checked before any command runs, and all
run under one lock. Every command runs even after a red, so each surface's verdict is
printed, and the run's exit is the first non-zero one. It is one run: one ledger row,
whose scope names the components in run order joined with `+`, `full` for the global
(`unit[frontend+e2e]`, `unit[frontend+full]`). The global `unit` alone could miss a
surface's own tests and read a task's required red as green.

**A multi-surface `ci` still runs the global `ci`.** The global `ci` is the oracle
the merge requires, so a union of scoped `ci` commands would only be a narrower
oracle under another name.

**The oracle chosen, and why, is announced** in the run's own output (`ci[frontend]
— hot surface 'frontend' declares an override`, or `ci[full] — nothing scoped
narrower`), and the marker/ledger row it writes records the same `scope` value — an
audit trail can always tell which evidence backed which commit.

**Full `ci` is always the last word.** A scoped green satisfies a per-task commit,
never the merge: `hooks/gate-merge.sh` additionally requires `gates gate-marker check
ci <tree> --require-scope full` on the branch head, alongside the existing `live-check`
requirement. Since selection reads the *staged* diff and every task is already
committed by change completion, nothing is staged — selection falls back to `"full"`
on its own, so satisfying this is just re-running `gates run ci` with a clean index
before merging. The trade this makes explicit: a scoped green moves *when* the full
suite runs (once per change instead of once per task) — never *whether* it runs
before integration.

**Release note: opt-in, and byte-for-byte compatible with no overrides declared.** A
manifest that never declares a surface `gates:` block behaves exactly as before —
every hot-set computation still runs, but with no override to find, selection always
falls back to the one command it always ran. Declaring an override on even one
surface changes only that surface's per-task cost; every other surface, and the
merge requirement, are unaffected.

## `gates` command reference

```bash
gates validate                 # check the manifest; exit 1 on any error (a file that does not parse: one line naming its position, and any conflict markers)
gates run ci                   # run the ci gate; exit with its code
gates run unit                 # run the unit gate (skips cleanly if undeclared)
gates run live-check           # run every hot surface's live-check
gates run eval sales 0.86      # fills {dataset}=sales {score}=0.86
gates surfaces                 # which surfaces are hot for the current diff
gates rules                    # which rule-ids apply to the current diff (feed to review)
gates stats                    # gate economics from the durable ledger (active time, per-gate share, failed attempts, tokens per task and model)
gates stats --outcomes --all   # autonomy: terminal state, hands-off share of merged changes, halts by cause, interventions by kind
gates epics [--json]           # every epic (named by children in x-gatedloop-epic) with each child's state and tasks done/total
gates stats --epic <name>      # an epic's per-child economics and totals: state, tasks, gate runs, gate time, red runs, tokens, halts
gates stats --cost             # tokens priced with economics.prices; unpriced models named; tokens alone without prices
gates usage record [--task N.M] [--transcript <path>] [--change <name>] [--stage]   # append a `usage` row (the commit and Stop hooks run it); exit 0 whatever the source
gates usage show [--change <name>] [--json]                      # a change's usage rows and tokens per task
gates halt record stalled --task 2.3 --detail "attempt budget used"   # record why the loop stopped (closed cause set)
gates intervention record ask --task 2.3 --detail "which port?"          # record a human turn the question-tool hook did not see
gates attempt note 2.3 --hypothesis … --changed … --oracle … --next …   # the lesson of a failed attempt (four one-line fields)
gates attempt notes 2.3 [--json]                                       # a task's attempt notes, oldest first
gates attempt restart 2.3                                              # one fresh restart: clean tree, at most loop.fresh-restarts
gates acceptance brief <change> [--out <path>]   # the deterministic acceptance brief: scenarios covered / check by hand, verdicts for this tree
gates acceptance policy                          # acceptance=review|self|none, from approval.acceptance
gates acceptance attest <change> --local         # record an `accept` for the branch head's tree (only under acceptance: self)
gates acceptance attest <change> --pr <n>        # record an `accept` from the PR's APPROVED review
gates acceptance attest <change> --merged <pr>   # under acceptance: self, the merged PR is the acceptance (merger, merge time, merge commit's tree)
gates acceptance reject <change> --cause weak-spec --detail "..."   # record a rejection (weak-spec | missing-oracle)
gates acceptance check <tree>                    # the merge gate's acceptance check (exit 0 when not required or accepted)
gates integration                                # print the declared integration process: mode=… requireApproval=…
gates merge <change>                             # local-squash-merge in six gated steps, or (pull-request mode) prove, push, publish statuses, open/update the PR; exits with the number of the step that refused
gates marker publish <gate> [--sha <sha>]        # post a `gatedloop/<gate>` success status carrying the tree, from a green local marker (needs `gh`); `tests` is computed from the lock at the commit
gates marker check-remote <gate> <sha>           # exit 0 only if the latest `gatedloop/<gate>` status on <sha> is a success naming that sha's tree
gates record-merged <sha>                        # for a forge squash commit: record the change's merge row (under acceptance: self, its accept row first), archive it, one local commit; never pushes (a plan/<change> PR under self: attest it from the merge)
gates approval attest <change> --merged <pr>     # under approval.plan: self, the plan PR's merge is the approval (merger, merge time; sha over the merge commit)
gates handoff <change> [--json]                  # the planner-to-orchestrator payload, printed only when the plan is approved on the merge target; reads only
gates ledger record-ready <change>               # append the `ready` row the implementer commits before READY TO MERGE; prints the report's `gatedloop: gates {...}` block (ci, review: clean|findings|partial|none, live_check) from the ledger
gates taint check [--change <name>] [--ref <ref>]  # exit 1 on an unresolved taint, naming each tainted commit (a merge commit marked with the sync route); --ref reads the change a merge's incoming ref names
gates lock status [--json]                       # each serialized gate's lock: free, or held by pid N (alive|dead?) for how long; flags "possibly hung"; names a merge waiting with priority
gates tests brief <change>                       # the test author's inputs: artifacts, test and surface rules, runner, nearby test paths, fixtures
gates tests handoff <change> [--task N.M] [--inline]   # record the holding area's tests in the ledger
gates tests place <N.M>                          # move one task's held tests onto their real paths
gates tests check [--task N.M]                   # the authored-test lock the commit hooks run
gates tests check --ref <commit> [--change <name>]   # the same lock at a commit's tree and ledger, every task; no handoff passes
gates tests defect <N.M> --kind setup|assertion|green --detail "..."   # an authored test is wrong, or green before implementation: back to its author (3 setup, 2 assertion, 1 green per task)
gates tests show [<change>] [--json]             # author, each task's tests or reason, characterization, placement, defects by kind
gates adoption status [--json]                   # the settings this plugin version asks the project to decide, still undecided
gates adoption record <id> adopted|declined|later   # record the project's decision on an adoption item in .gatedloop/adoption.json
```

`gates adoption status` reads the catalogue that ships with the plugin and lists
each item that applies to this project, that the project hasn't already acted on
(a manifest key already set counts as the decision), and that has no recorded
decision. An item introduced after the installed version is never listed.
`later` holds only until the plugin version changes. `--json` prints
`{"version", "undecided": [{"id", "since", "what"}]}`. It exits 0 whether or not
anything is listed, and non-zero only when it cannot decide (a bad catalogue, an
unreadable record or manifest). The session brief runs it at every session start
and adds one line when anything waits (or one line saying the check could not
run); it never asks a question, headless or not. `/gatedloop:upgrade` is the
interactive walk over the same list: one question per item, the recommended answer
first plus "Decide later", each answer recorded with `gates adoption record` as soon
as it is given. It commits nothing. `/gatedloop:gates-init` records the answers its
own steps cover (the test-conventions pass records `test-conventions`) and ends
with the same walk, so a freshly onboarded project has nothing left waiting.

`gates adoption record` is the only writer of `.gatedloop/adoption.json`: what the
project decided about each setting a gatedloop release asked it to consider, with
who decided (your git identity), when, and at which plugin version. It refuses an
unknown item id or decision without writing. Commit the file, so the whole team
shares the decisions.

Changed-file set defaults to `git diff HEAD` + staged + untracked. Override with `--changed a.py b.ts` or `--all`.

**When gates feel slow:** run `gates stats` (add `--change <name>` for a change other
than the current branch, or `--all` for every recorded change) to see where active
loop time actually goes — time and share per gate, failed-attempt counts, and a
per-task breakdown, read straight back out of the durable ledger. Beside time it
prints the tokens each task and model spent, from `usage` rows, and names the tasks
with none; a ledger from before usage rows existed says token spend was not
recorded. Then read
[`docs/gate-economics.md`](docs/gate-economics.md) for what to do about what it shows.

**When you want to know what stopped the runs:** `gates stats --outcomes` reads the same
ledger for autonomy instead of cost — per change, a terminal state (`merged` / `halted` /
`in-progress`) and a verdict (`hands-off` when merged with no halt, intervention or
taint, else `assisted`, naming which); with `--all`, the hands-off share of merged
changes, halts by cause, interventions by kind and a per-month trend. Under a declared
`approval.acceptance` the terminal event is `accepted` (an `accept` of the merged tree)
and hands-off requires it; undeclared, the report says the metric ends at `merged`.
`--json` emits one
document. "Reading the outcomes view" in `docs/gate-economics.md` explains what it cannot
see.

`gates run` is quiet on green by default: one summary line naming the gate, its
scope, duration, and where the full output landed (`.gatedloop/out/<gate>-<ts>.log`,
gitignored and rotated — the last 5 per gate); a red exit prints the full captured
output before that same summary, and the exit code is untouched either way. Pass
`--verbose` to stream unfiltered instead, exactly like before this existed.

## Approval: `.openspec.yaml`

Every change carries three additional keys in its `.openspec.yaml`, alongside OpenSpec's own `schema:`/`created:`. They start with `x-`, the prefix OpenSpec reserves for tool metadata:

```yaml
# openspec/changes/<name>/.openspec.yaml
schema: spec-driven
created: 2026-08-04
x-gatedloop-approved-by: <github-login>
x-gatedloop-approved-at: <date>
x-gatedloop-approved-sha: <tree hash of the plan artifacts at approval>
```

The rest of this document calls them `approved_by`, `approved_at` and `approved_sha`, their names before 0.6.0.

`approved_sha` is the tree hash of the change's **plan** artifacts — `proposal.md`, `design.md`, `specs/**`: everything the active schema's `apply.requires` names, which is what a human actually reviewed before implementation could begin. **`tasks.md` is excluded and is not separately approved** — it is *derived* from the already-approved plan (design, specs, proposal), not independently agreed, so requiring its own approval would be approving the same decision twice under two names. The one exception is its oracle tags (`task-oracle` D9): when `tasks.md` carries at least one `[oracle: …]` tag, the hash also covers a digest of its `(task id, tag)` pairs, leaving out checkbox state and task text, so ticking or rewording a task never voids the approval and retagging one does. A plan with no tag hashes exactly as before, so upgrading voids no untagged plan's approval; a plan already attested with tags needs one re-attestation under the new shim. Because the hash is pinned to content, editing an approved proposal after the fact is detectable: the file on disk no longer matches `approved_sha`, where a prose `Approved by:` line would sit there looking true regardless.

This is definition only. OpenSpec ignores the keys: a change carrying them passes `openspec validate --strict`, and neither `openspec status --json` nor `openspec instructions --json` echoes them back, so a consumer reads `.openspec.yaml` directly.

**The earlier spelling.** gatedloop 0.5.0 wrote the keys without the prefix. From OpenSpec 1.14, `status`, `validate` and `archive` warn about them as unrecognized keys, and `validate --strict` fails on them.
- **Reading.** Every gatedloop reader accepts either spelling, field by field, and prefers the new one. That includes `check-implement`'s read of the merge target, so a plan approved under 0.5.0 still opens implementation.
- **Writing.** `gates approval attest` writes the new keys and removes the old ones, so a re-attest migrates the file.
- **Migrating.** `gates approval migrate [<change>]` renames the keys in place in every active change, or in the one you name, and prints each file it changed. Values and order are kept, and the approval sha covers no `.openspec.yaml`, so every approval still checks. It doesn't commit; commit the files at planning grade. Archived changes are left alone.
- **Diagnosing.** `gates doctor`'s `approval-keys` row warns while an active change still carries the earlier spelling, and `/gatedloop:upgrade` offers the migration (see "Upgrading").

| Was (0.5.0) | Now (0.6.0) |
|---|---|
| `approved_by`, `approved_at`, `approved_sha` | `x-gatedloop-approved-by`, `x-gatedloop-approved-at`, `x-gatedloop-approved-sha`; run `gates approval migrate` |

**Populating and enforcing the keys** — `/gatedloop:propose` ends the authoring flow by opening a pull request for the plan (never leaving it on a branch for someone to notice). Once that PR carries an `APPROVED` review, `gates approval attest <change> --pr <n>` reads it — via `gh pr view <n> --json reviews`, taking the first `APPROVED` review — and writes the three approval keys from it; the model never supplies the value directly, and the gate fails closed (no write) if `gh` is missing, unauthenticated, offline, or the PR has no approving review. `gates discipline check-implement <change>` — hook-enforced at `git checkout -b <change-name>` — then refuses to let implementation start unless the plan is present on the resolved merge target AND its `approved_sha` still matches the plan's current content (`gates approval sha <change>` computes that hash, over `proposal.md`/`design.md`/`specs/**`, in that lexical order, plus the `tasks.md` tag digest when the plan carries a tag — never the rest of `tasks.md`, which is derived from the plan rather than independently approved, and never `.openspec.yaml` itself).

### The declared approval policy — `review` or `self`

`.gates.yaml` accepts an optional `approval:` block naming who approves plans:

```yaml
approval:
  plan: self   # or: review (the default when the block is absent)
```

`review` is everything above, unchanged — a second party's `APPROVED` review is the
only legitimate source, and `gates approval attest --pr <n>` is the only legitimate
writer. `self` is standing self-approval for a solo, remoteless repo: a real
constraint, not a hypothetical one — GitHub refuses a self-approval, so a solo
developer working entirely through PRs has no way to satisfy `review` at all.
`gates validate` rejects any `approval.plan` value other than these two, naming both
in the error.

**The D10 gate itself (`gates discipline check-implement`, `gates approval check`)
never reads this block.** It only ever checks the two things it
always checked: the plan is present on the merge target, and `approved_sha` still
matches the plan's current content. The policy is consulted by the *writers* only —
which command is a legitimate way to populate the keys — never by the gate that
reads them back. Declaring `self` does not weaken what the gate enforces; it only
adds a second, machine-computed way to satisfy it.

**The same check runs again at the merge and at acceptance.** `gates merge` step 1
checks the plan approval before any evidence, in both modes, and every `gates
acceptance attest` writer checks it before writing: the approval recorded on the merge
target must still match the plan there, and the plan at the head being merged or
accepted must hash to that recorded `approved_sha`. A plan amended on the target
without a re-attest, or edited on the change branch after approval, stops there with
the re-approval route. Under `approval.acceptance: self`, `gates record-merged` still
records the merge row of such a change, because the forge merge happened, but no
acceptance, and exits non-zero. An untagged `tasks.md` is outside the sha, so ticking
or adding a task never needs re-approval.

**"Present on the merge target" accepts a local counterpart, under `self` only.**
Under `review`, "the merge target" is unconditionally the origin ref — a PR's
approving review can't be evidenced by a purely local branch. Under `self`, a local
counterpart of the target that carries the change (local `main` when the target
resolves to `origin/main`) is accepted too, with a loud advisory that it isn't on
origin yet — see [`docs/worktree-lanes.md`](./docs/worktree-lanes.md) for the full
acceptance map, including `check-archive`'s parallel (and policy-independent)
local-counterpart acceptance.

**The solo procedure — `gates approval attest <change> --local`.** Under a declared
`self` policy, this writer computes `approved_sha` with the exact same content-hash
computation `--pr` uses (`gates approval sha <change>` — over `proposal.md`,
`design.md`, and every `specs/**` file, in that lexical order), records the
configured git identity (`git config user.name`/`user.email`, formatted as `Name
<email>`) as `approved_by`, and `approved_at` from the clock. Run it after the plan
is merged to the resolved integration target, exactly like `--pr`:

```bash
gates approval attest <change> --local
```

`--as <name>` overrides the recorded `approved_by` display name (useful if your git
identity isn't the name you want on record) — it **never** touches the computed sha;
the content pin is identical either way. Under a declared `review` policy (or when
the `approval:` block is absent), `--local` refuses outright and names the `--pr`
path instead — it is never a silent fallback when a PR isn't available.

**The merge path — `gates approval attest <change> --merged <pr>`.** For a solo
maintainer working through plan PRs, the real act of approval is merging the plan
PR, and the forge already records who merged it and when. Under a declared `self`
policy, `--merged` reads that record through `gh pr view <pr>` and writes:

| Key | Value |
|---|---|
| `x-gatedloop-approved-by` | `<merger's login> (merged #<pr>)` |
| `x-gatedloop-approved-at` | the PR's merge time |
| `x-gatedloop-approved-sha` | `gates approval sha` over the plan as it stands in the PR's merge commit — never the working tree |

It refuses, writing nothing and naming the unmet condition, when the policy is
`review` (it names `--pr`), the PR is not `MERGED`, its base is not the resolved merge
target, its merge commit is not on the target, the change's `proposal.md` is absent
from that merge commit, or `gh` is missing or unauthenticated. It appends the same
ledger row `--local` does; the `(merged #<pr>)` marker is what tells the sources apart.

**When it applies.** In pull-request mode (`integration.mode: pull-request`) you never
run it by hand: the record job's `gates record-merged <sha>` sees a merged PR whose
head is `plan/<change>`, and, under `self`, for an active change with no approval yet
or whose `approved_sha` no longer matches the plan in the merge commit (a merged plan
amendment), attests it from the merge and commits the keys as its one local commit
(`attest approval: <change> (merged #<pr>)`), never pushing. Under `review`, or when the
change's recorded approval still matches the merged plan, it skips and says why. In local-squash mode there
is no forge merge to read, so `--local` stays the path — unchanged, as it is for a
project without a forge or a plan not merged through a PR.

All three writers write each value double-quoted, so a YAML reader gets it back as
written (unquoted, the ` #` in `(merged #42)` would open a comment). Every reader
accepts quoted and unquoted values alike, and `gates approval migrate` keeps values as
they are.

**Handing a plan to an orchestrator — `gates handoff <change> [--json]`.** It runs
the same check `check-implement` runs, against the merge target, and exits 1 with that
check's reason unless the plan is there, approved, and unchanged since. On success it
prints a fixed payload — the change, its schema, the target and its head, the approval,
the epic (or `null`), task counts, and `"verify": "gates approval check <change>"`, the
command a receiver re-runs before acting. Without `--json`, the same fields print as
`key: value` lines. It sends, writes and commits nothing: the message is a doorbell,
git stays the source of truth. See
[`docs/running-at-scale.md`](./docs/running-at-scale.md) §8 for the planner/orchestrator
contract. `/gatedloop:planner` and `/gatedloop:orchestrator` load each side of it into a
session as a role: the planner sends a payload only when `gates handoff` exits 0, and
the orchestrator runs its `verify` before queueing. Re-run either after a compaction.

**The honesty note (design D3).** Content is attested mechanically: `approved_sha`
is computed by the shim itself, never supplied by a caller, and a post-approval edit
to any plan artifact invalidates it exactly the same way under either writer.
*Identity* is a different claim. Under `--pr`, `approved_by` is a GitHub login read
from an actual `APPROVED` review — a real second party left it. Under `--local`,
`approved_by` is only as strong as the local git config (or an unauthenticated `--as`
string) — there is no second party to defend against in a genuinely solo repo, and
`self` is the honest declaration of that fact, not a workaround for it. This mirrors
the general shape this repo has stated plainly before it was fixed: **a hand-edit of
`.openspec.yaml` with a correctly recomputed sha still passes the gate** — the sha pin
is the load-bearing half of the guarantee, and it is unconditional; who is recorded as
having approved is exactly as strong as whichever writer (or, absent a declared `self`
policy, whoever holds write access to the repo) actually ran it. This repo hit the gap
`solo-approval-mode` closes directly: three plan PRs (`unblock-parallel-planning`,
`solo-approval-mode`, `expand-brace-globs`) were merged without an `APPROVED` review —
GitHub refuses to let an author approve their own PR — so `gates approval attest --pr`
correctly refused, and the human explicitly authorized a one-time, hand-written
`approved_by`/`approved_at`/`approved_sha` as a bootstrap (the sha itself still
computed by `gates approval sha`, never invented). `--local` under a declared `self`
policy is what makes that hand-edit unnecessary from here on — the same content pin,
recorded by a command instead of a human's editor.

### Acceptance: the human gate after the loop — `acceptance: review` or `self`

Plan approval is the human gate *before* the loop. The same block can declare the one
*after* it: a human accepts the working increment's **behaviour**, recorded against the
exact tree that will be merged. It is opt-in — with no `acceptance` key nothing is
required anywhere and every hook behaves exactly as before.

```yaml
approval:
  plan: self
  acceptance: self   # or: review (needs integration.mode: pull-request)
acceptance:
  match: "features/**/*.feature"   # optional: where your acceptance scenarios live
```

`gates validate` rejects any other `acceptance` value, and rejects `acceptance: review`
when the integration mode is `local-squash-merge` (or `integration:` is absent): there
is no pull request whose review could be read, so it names `acceptance: self` and
`integration.mode: pull-request` as the two ways out. The top-level `acceptance` block
takes exactly one key, `match`.

**The brief — what the human reads.** `gates acceptance brief <change>` prints, in
scenario language, every `#### Scenario:` in the change's specs, each marked `covered`
when a same-titled acceptance scenario exists in a file `acceptance.match` names, else
`check by hand`; the latest `verify`, `live-check`, `integration` and `ci` verdicts and
review verdict recorded for **this exact tree** (`absent` otherwise); a "check these by
hand" list; and what it cannot claim. A title counts when a line starts with one of the
markers `Scenario:`, `Scenario Outline:`, `#### Scenario:` or `- Scenario:` followed by
the title, compared case-insensitively. It is generated by the shim, byte-identical for
the same specs, ledger and tree, and never written by a model. `--out
.gatedloop/runs/<change>.acceptance.md` is the documented place to keep it; that path is
outside the accepted tree, so committing it disturbs nothing. The loop prints it at
completion (`tdd-apply` §7.5, `tdd-implementer` §4) whether or not a policy is declared.

**Recording the verdict — the writers mirror plan approval's.** An acceptance is one
`acceptance` ledger row, pinned to the ledger-normalized tree of the change branch's
head (or, from a merged PR, of its merge commit), with `accepted_by` recording who. It is a row, not an `.openspec.yaml` key,
because it pins a *tree*: writing it into any file inside that tree would change the
tree it pins, and the ledger is the one place excluded from it. Run the writer on the
change branch and commit the row with the change.

- `gates acceptance attest <change> --local` — legitimate only under `acceptance:
  self`; `accepted_by` is the configured git identity (`--as <name>` overrides the
  display name, never the tree). Under `review` it refuses and names `--pr`.
- `gates acceptance attest <change> --pr <n>` — reads the pull request's first
  `APPROVED` review through `gh`, exactly as plan approval does; fails closed when `gh`
  is missing, unauthenticated or offline, or when no review approves; refuses `--as`.
  Legitimate under either policy.
- `gates acceptance attest <change> --merged <pr>` — legitimate only under
  `acceptance: self`, for a solo owner in pull-request mode: the forge refuses a review
  of one's own PR, so the owner's merge of the implementation PR is the acceptance.
  `accepted_by` is the merger's login marked `(merged #<pr>)`, the time is the merge
  time, and the row pins the ledger-normalized tree of the PR's merge commit, the same
  tree the change's merge row records. It refuses, writing nothing and naming the unmet
  condition, when the PR is not `MERGED`, its base is not the merge target, its head
  branch is not `<change>`, its merge commit is not on the target, or `gh` is missing
  or unauthenticated; under `review` it names `--pr`; it refuses `--as`. When an accept
  for that tree is already recorded it writes nothing. You rarely run it by hand:
  `gates record-merged` runs it for you.
- `gates acceptance reject <change> --cause weak-spec|missing-oracle --detail "..."` —
  a rejection is an escalation: the spec asked for the wrong thing (`weak-spec`), or
  it was right and nothing checked it (`missing-oracle`). `gates stats --outcomes`
  counts it under halts by cause.

With no `approval.acceptance` declared, every writer refuses and names the key.

**The merge requires it.** Under a declared policy the merge hook adds a fourth check
after taint: `gates acceptance check <tree>` passes only when the latest acceptance row
for the incoming tree is an `accept`. Any edit after acceptance changes the tree and
denies the merge; a later `reject` for the same tree denies it; a later `accept`
restores it. The `ask` rule on `git merge` stays: it proves a human is present at the
merge, the accept row proves a human judged the behaviour.

**The honesty note's acceptance counterpart.** The tree is computed by the shim and is
unconditional: nothing but an edit can move it. *Who* accepted is as strong as the
writer: a GitHub login from a real review under `--pr`, the local git config (or an
unauthenticated `--as`) under `--local`. `self` is the honest declaration of a solo
repo, where the approver and the implementer's operator are the same person.

## Epics: `x-gatedloop-epic`

A story of several changes that only make sense together is an **epic**: an ordinary
change, proposed and approved like any plan, that its children name. Usually it sits
on a schema with no `apply` block (the bundled `architecture` pack is one), because an
epic ends at its children, not at code. Its charter and decisions are its artifacts,
and those are OpenSpec's. gatedloop only links the changes and enforces the order.

A child names its epic with one top-level key in its own `.openspec.yaml`:

```yaml
# openspec/changes/lane-permissions/.openspec.yaml
schema: spec-driven
created: 2026-10-19
x-gatedloop-epic: autonomous-dev
```

The `x-` prefix is the form OpenSpec 1.14 reserves for tool metadata, so the key
passes `openspec validate --strict`. A bare `epic:` would fail it, and gatedloop does
not read one. The shim reads the key without PyYAML.

**Validation.** `gates validate` fails, naming the child, when an active change names:
- an epic that is neither an active nor an archived change;
- itself;
- an epic that itself names an epic (epics are one level deep);
- an archived epic (the epic was archived while this child was open).

**Two guarantees, hook-enforced:**
- **An epic is never implemented.** `gates discipline check-implement`, run by the
  hook at `git checkout -b <change>`, refuses a branch for any change an active change
  names as its epic, whatever the epic's schema. It names the children to implement
  instead.
- **An epic archives after its children.** `gates discipline check-archive`, run by
  the hook at `openspec archive <change>`, keeps its merge check and also refuses
  while any child is not archived. It lists each open child with its state. That
  covers `/opsx:archive` and `/gatedloop:archive`. `gates merge` and `gates
  record-merged` run `openspec archive` themselves, outside the hook, but only for a
  change integrated from a branch named after it, and an epic never gets one.

**The roll-up.** `gates epics [--json]` lists every epic, active or archived, with
each child's tasks done of total and a state derived in code:

| State | When |
|---|---|
| `archived` | the child's directory is under `openspec/changes/archive/` |
| `merged` | `gates stats --outcomes` says `merged` or `accepted` |
| `halted` | `gates stats --outcomes` says `halted`; the cause is shown |
| `ready` | in progress, and its latest `ready` or `halt` row is `ready` |
| `implementing` | in progress, with a `task-start` row |
| `approved` | none of those, and its plan carries an approval |
| `proposed` | none of the above |

The ledger states come from the outcomes classifier, so the two views never
disagree. An epic whose children are all archived is `drained`.
`gates stats --epic <name> [--json]` reports the per-child economics and totals:
state, tasks, gate runs, gate time, red runs and halts by cause. The session brief
prints one line per active epic above the change list and leaves that epic's children
out of the list. A repository with no epics gets the same brief as before.
`docs/running-at-scale.md`, "Draining an epic", is an example orchestrator loop built
from these commands.

## The merge step: `gates merge <change>`

Under `integration.mode: local-squash-merge` (or no `integration:` block), a finished
change is integrated by **`gates merge <change>`** — from `/gatedloop:merge` when a person
merges, from the `merge-runner` agent when an orchestrator does, and from
`/gatedloop:tdd-apply` §7.5 (under `mode: pull-request` the same command hands the change
to the forge instead; see "Pull-request mode" below). It runs six steps in code and stops at the first that
refuses. **Nothing reaches the remote until every step has passed**: there is one push,
at the very end.

| Step | What it does | Exit on refusal |
|---|---|---|
| 0. Preconditions | Takes the machine-wide `merge` lock; requires branch `<change>` with `openspec/changes/<change>/` on it and a primary checkout clean apart from untracked files; records where HEAD is (`.git/gatedloop/merge-state`) | 1 (75 on `gatedloop: lock busy`) |
| 1. Prove the head | Commits the branch's trailing ledger rows (in the worktree that has it checked out). Then the merge hook's own checks, against `<change>^{tree}` and **that change's** ledger: the `live-check` marker, an unscoped `ci` marker, a green `verify` where declared, no unresolved taint, and an acceptance where `approval.acceptance` is declared. Prints every spec scenario, `covered` or `check by hand` | 1 |
| 2. Integrate | Fetches, detaches onto the target's tip, `git merge --squash <change>`. A conflict aborts and names the conflicting paths | 2 |
| 3. Prove the merged tree | An unscoped `gates run ci` on the staged squash, then commits it as `<change>: <proposal title>` with the change's commit subjects as its body | 3 |
| 4. Record | `gates ledger record-merge <change> --sha <squash sha>`, committed at ledger grade on top | 4 |
| 5. Confirm | `gates run confirm` on the merged tree, if declared; its green row joins step 4's commit | 5 |
| 6. Archive and publish | `openspec archive <change> --yes`, the archive commit (all three paths of the move), then one push of the three commits. A push rejected because the target moved retries once from step 2 | 6 |

Every exit code names its step, so an orchestrator routes on the code; the step's own
message is always printed. On any refusal after step 1 the primary checkout is put back
exactly where it was and the target is untouched. A red or exit-75 `confirm` also
discards the local commits and records its failure row on the change's branch, so it
survives them.

One exit is not a step number: **75** means a gate **did not run**, so nothing about the
merged tree is known yet. At step 3 (`ci`) or step 5 (`confirm`) it is either a
serialized lock still held past its bound — the message names the holder and the wait,
and the gate's own `gatedloop: lock busy` line is printed above it — or a failed
`requires`, which the message names. The merge restores the checkout, commits nothing
it would keep, and exits 75, never 3 or 5, so the same retry-on-busy rule applies as for
any gate. A red `ci` at step 3 still exits 3 ("the merged tree is what failed"). A busy
`merge` lock before step 0 is the same exit 75.

**The `confirm` gate** is your "bring the merged tree up and smoke it" recipe, bound in
`gates:` like any other gate (`gates-init` offers it once a `live-check` is bound):

```yaml
gates:
  confirm:
    run: "<your smoke of the merged tree>"
    requires: "<your check that its environment is up>"
```

The plugin never reads its body. Undeclared, step 5 is skipped with a note — not a
failure.

**What stays yours.** The environment `confirm` and `live-check` run on, and whatever
brings it up and down, are the project's: put those steps in the command body or its
`requires`. A fresh stack that flakes on its first scenario wants an idempotent
warm-up in `requires` (see "Preconditions" above), which runs before the verdict;
the runner-strictness rules still refuse a retry after a failure.

**Who may merge is unchanged.** `gates merge` enforces a declared acceptance policy in
code (step 1 locally; in pull-request mode it withholds auto-merge), `tdd-implementer`
never runs it, and `merge-runner` resolves only
mechanical conflicts, re-runs the head's gates after a resolution, and halts on anything
that needs a choice between two behaviours.

**After a crash** between the local commits and the push, the primary is left detached
on commits nobody published. Run `gates merge <change>` again: it finds the recorded
position, restores it, and starts over.

### Pull-request mode: `gates merge` hands the merge to the forge

Under `integration.mode: pull-request`, `gates merge <change>` proves the head locally
and then hands integration to the forge. It takes the same `merge` lock, never touches
the checkout or the target, and exits 0 once it has handed the change off:

| Step | What it does | Exit on refusal |
|---|---|---|
| 0. Preconditions | Branch `<change>` with `openspec/changes/<change>/` on it, and a remote integration target | 1 (75 on `gatedloop: lock busy`) |
| 1. Prove the head | As in local mode: commits trailing ledger rows, then the `live-check` marker, an unscoped `ci` marker, `verify` where declared and no unresolved taint. A declared acceptance does not refuse here; it decides step 4 | 1 |
| 2. Push | `git push -u <remote> <change>` | 2 |
| 3. Publish statuses | `gates marker publish live-check`, then `ci`, on the pushed head | 3 |
| 4. Pull request | Opens the PR (`<change>: <proposal title>`, base = the target branch) or updates the open one, with the acceptance brief as its body. Then squash auto-merge **only** when `requireApproval` is false and any declared acceptance is satisfied; otherwise it prints the PR's URL and stops: waiting for review | 4 |

An unproven head stops at step 1: nothing is pushed and no PR is opened. Under
`approval.acceptance: review` the acceptance can only come from the PR's approving
review, so the first run opens the PR and waits; after `gates acceptance attest <change>
--pr <n>`, run `gates merge <change>` again to refresh the brief and, where nothing else
stands in the way, enable auto-merge. Under `approval.acceptance: self` with no
acceptance recorded, step 4 leaves auto-merge off and says so: the owner's merge in the
forge is the acceptance, and `gates record-merged` records it.

**After the forge merges it**, `gates record-merged <squash sha>` writes the ledger
facts the forge cannot. It resolves the pull request that produced the commit (`gh api
.../commits/<sha>/pulls`), and when its head branch names an active change it records
that change's merge row against `<sha>`, runs `openspec archive <change> --yes`, and
makes **one** local commit, `archive change: <change>`, holding the row, the archive
move and `openspec/specs`. Under `approval.acceptance: self` it first records the PR's
merge as the change's acceptance, as `gates acceptance attest <change> --merged <pr>`
does, so the same commit holds an `accept` row pinned to the merge commit's tree and
`gates stats --outcomes` reads the change as `accepted`; when an accept for that tree is
already recorded it adds none, and when the writer refuses (the forge unreachable, say)
nothing is committed. Under `review`, or with no policy, it writes no acceptance. That commit is ledger- plus planning-grade, so it needs no
`ci` marker. It never pushes. A commit from no pull request, an ordinary PR, a branch
like `gatedloop/record-merged-*` that names no change, or a change already archived is
skipped with a note, exit 0, so it is safe to run on every push to the target. It
refuses (exit 1) a sha the checkout's HEAD does not contain, and a checkout with
uncommitted changes to tracked files.

### Markers as commit statuses: `gates marker publish` / `check-remote`

A marker lives under `.git/` on the machine that ran the gate. `gates marker publish
<gate> [--sha <sha>]` (default HEAD) turns one into a commit status the forge and CI can
read: it requires a green local marker for the commit's ledger-normalized tree (for
`ci`, from an unscoped run), then posts `gatedloop/<gate>`, `state=success`, description
`tree <hash>` — `tree <hash> (skip: no hot surface)` for a skip verdict — with
`target_url` set to the Actions run when `GITHUB_RUN_ID` is present. With no such
marker it refuses and posts nothing. `gates marker check-remote <gate> <sha>` exits 0
only when the latest `gatedloop/<gate>` status on `<sha>` is a success naming `<sha>`'s
own normalized tree, and names both trees when they differ.

**`tests` is computed, not a marker.** `gates marker publish tests [--sha <sha>]` needs
no gate run: it evaluates the authored-test lock at the commit (`gates tests check
--ref`, below) for every active change the commit's tree carries, and posts
`gatedloop/tests` as `success` with `tree <hash>` when it holds — `tree <hash> (no
authored tests)` when no change there has a handoff, so a planning or docs pull request
gets the status too — or as `failure` naming the first offending path, then exits 1.
`check-remote tests <sha>` verifies it like any other.

`gates tests check --ref <commit> [--change <name>]` is the lock at a commit rather than
the staged index: each placed path must hold exactly its placed content (its base content
where a defect, or a halt at a task not yet completed, voided the placement; its earlier
placed content where a defect reopened a completed task), the holding area must match the
latest handoff, and every placed task with tests must have a red `unit` run recorded after
its placement (after its first placement, for a reopened task), all read from the commit's tree and the ledger it carries. It checks every
task and names the path, the task and the commit on a failure. The change comes from
`--change`, else from the branch the ref names. `gates merge` step 1 runs it on the
branch head in both modes, so a placed test edited past the commit hooks refuses the
merge.

Both reach the forge through `gh`, an optional dependency: missing or unauthenticated,
they exit 1 naming it. `gates doctor` adds a `gh` row only where `integration.mode:
pull-request` is declared, a warning when `gh` is missing or unauthenticated.

**A status posted from a laptop is self-reported.** What makes it evidence is branch
protection that requires `gatedloop/ci` with **your CI provider as its expected source**,
so only the CI job's own `gates run ci && gates marker publish ci` can satisfy it (next
section). [`docs/running-at-scale.md`](docs/running-at-scale.md) has a sample workflow
to adapt.

## Changing how artifacts are authored

Fork the schema, not the generated commands:

```bash
openspec schema fork <source> <name>     # copies it to openspec/schemas/<name>/
```

Then point `openspec/config.yaml` at the fork. A forked schema is your file, so it survives an upstream update by construction — and "I want different artifacts" or "I want different authoring prompts" is a schema concern, which is where the lever actually is.

**Schema selection is per-change, not just per-project.** `openspec/config.yaml`'s `schema:` is the project default, but any single change can override it in its own `.openspec.yaml` — resolution order is `--schema` flag → that change's `.openspec.yaml` → the project default. Two changes in the same project can legitimately run different schemas (e.g. one `spec-driven`, one an `event-driven` fork for an eventing feature). Set it at change creation with `openspec instructions proposal --change <name> --schema <name>`, before writing the proposal.

### Choosing a schema

The bundled default, `spec-driven` (`proposal → specs → design → tasks`), covers most feature work. Beyond it:

**Community catalog** — five more workflows maintained at <https://github.com/intent-driven-dev/openspec-schemas>, installed by copying into `openspec/schemas/<name>/` (its `AGENT_INSTALL.md` is the install procedure; gatedloop does not vendor a copy — see "Installed schemas have no upstream update path" below). For feature work with meaningful behaviour, technical design, and durable decisions, **`intent-driven`** (`proposal → specs → design → adr → tasks`) is the most complete general-purpose schema in the catalog and the recommended non-default choice. Named alternatives: `minimalist` (`specs → tasks`, for small well-scoped changes) and `spec-driven-with-adr` (`spec-driven` plus durable ADRs, a narrower subset of what `intent-driven` covers). `behaviour-driven` and `event-driven` round out the catalog for Gherkin-style and event-centric work respectively. gatedloop recommends and installs from this catalog; it does not fork or maintain a competing copy of any feature workflow.

**gatedloop's own packs** cover the two gaps the catalog leaves, and are not schema forks of anything above:

| Pack | Artifact flow | Choose when |
|---|---|---|
| `bugfix` | `report → spec-delta → tasks` | The starting point is a failing reproduction, not a proposal — the repro is required RED before the fix and GREEN after; every fix records a spec delta. It declares `gatedloop: { flow: regression-first }` (below). |
| `architecture` | `explore → design → adr`, no `apply` block | The work ends at an accepted decision, not code — `/gatedloop:tdd-apply` refuses to run an implementation loop against a change on this schema, deliberately, rather than improvise a task list. |

#### How `/gatedloop:tdd-apply` routes a schema

The route is decided from the schema's structure and what it declares — never from its name — by `gates schema dispatch <name> --json`:

| Schema shape | Route |
|---|---|
| no `apply:` block | refuse — the workflow ends at its final artifact |
| `apply:` with no `tracks` | refuse, exactly as above — there is nothing to tick off |
| `apply:` with `tracks`, no declared flow | `per-task` — the default gated loop |
| `apply:` with `tracks` and `gatedloop: { flow: regression-first }` | `regression-first` — the repro runs red before any fix |

A schema opts into a flow with a namespaced top-level key, which OpenSpec accepts alongside its own fields:

```yaml
gatedloop:
  flow: regression-first
```

The known flows are `per-task` (the default when nothing is declared) and `regression-first`. Any other value makes dispatch fail loud, naming the known flows, rather than fall back to the default loop. The `bugfix` pack declares `regression-first`, so a fork of it keeps the flow under any name as long as it keeps the declaration; a schema *named* `bugfix` that drops it is routed by its structure alone.

**For a decision-terminal schema, omit `apply:` entirely.** That is the correct spelling. An `apply:` block without `tracks` is refused the same way, but `gates schema inspect` warns about it, because it reads as if an implementation phase were intended.

Both ship in this plugin at `packs/bugfix/` and `packs/architecture/` (kept out of this repo's own `openspec/schemas/` so the two don't collide: that directory is gatedloop's own active project, this is what gets distributed). Install either the same way as a community schema — copy the pack directory into `openspec/schemas/<name>/` in the target project, activate `schema:` in the change's `.openspec.yaml`, then `openspec schema validate`. `AGENT_INSTALL.md` at this plugin's root is the copyable procedure, following the same convention as the community catalog's.

**Installed schemas have no upstream update path.** Whether bundled (`spec-driven`) or copied from the community catalog into `openspec/schemas/<name>/`, a schema is a snapshot at install time — there is no registry, no version pin, and no `openspec schema update` today. A later improvement to the schema you installed reaches you only by re-copying it (and re-applying any local fork changes by hand). This is an ecosystem-wide limitation, not a gatedloop gap.

Editing `.claude/commands/opsx/*.md` is **not** supported. Those files are generated: `openspec update` regenerates them in place — no backup, no prompt — whenever the recorded version differs *or* the tool/workflow profile has drifted, and `openspec update --force` does so unconditionally. `/gatedloop:gates-init` warns once if it spots local edits there, but it cannot protect them.

## What gatedloop never touches

Your task runner, application code, existing rules prose, secrets, and any project config outside `.gates.yaml`. Adoption is additive: one manifest, optionally a rules-doc. Removing the plugin leaves your project intact.

It also holds no copy of OpenSpec's commands. `/opsx:*` is installed and maintained by OpenSpec; the one place gatedloop delegates to it — `/gatedloop:archive`, which adds the archive commit — adds a step and reproduces nothing.

## Running headless

`/gatedloop:tdd-apply` (and the `tdd-implementer` agent it's built on) can run with
nobody watching once a change's plan is merged and approved (`gates approval attest`,
`gates discipline check-implement` — "Approval" below):

```bash
claude -p "/gatedloop:tdd-apply <change>" \
  --permission-mode acceptEdits \
  --output-format json
```

`--json-schema` is also accepted with `--print`/`--output-format json` for structured
output validation, if you want to constrain the shape further than the report already
guarantees.

**Who dispatches the test author.** A headless `/gatedloop:tdd-apply` run is a top-level
session, so it dispatches the `test-author` agent itself in its authoring phase, and
re-dispatches it for a task when a test defect is recorded. A caller that spawns
`tdd-implementer` directly must dispatch `test-author` for the change first (under
`loop.test-author: separate`): the implementer cannot dispatch a sibling, halts with
`missing-oracle` when there is no handoff, and halts with `oracle-conflict` (detail
`test-defect <N.M>: …`) when it records a defect — its caller then re-dispatches the author
for that task and resumes the implementer.

**What still stops it, on purpose.** `tdd-implementer` always halts before the merge
(`agents/tdd-implementer.md` §4) and its final report ends in one line of literal JSON —
`{change, tasks_done, tasks_total, branch, gates, outcome, cause, acceptance}` — so a headless caller
reads the outcome without parsing prose. `cause` is `null` on `READY TO MERGE`; on a halt
it is one of `missing-oracle`, `weak-spec`, `oracle-conflict`, `stalled`, `environment`,
`other`, and it echoes the `halt` row the implementer recorded with `gates halt record`
*before* reporting — a halt that was never recorded does not take (the `Stop` hook
re-enters it). `acceptance` is `"required"` when `approval.acceptance` is declared (a
human must still accept the behaviour before any merge) and `"not-required"` otherwise;
the acceptance brief is printed immediately before the report either way. The earlier
fields are unchanged, so existing parsers keep working. If `gates-init`'s opt-in permission scaffolding
(`.claude/settings.local.json`, see "Enforcement" below) is in place, `gates merge *` stays
an `ask` rule even under `acceptEdits` — in a true headless run there is nobody to answer
an `ask` prompt, which is the **intended** outcome: the run cleanly stops before the
merge and reports, exactly matching "stop before the merge." A human (or a separate,
supervised step) runs the merge afterward.

The `ask` rule sits on `gates merge`, the command that integrates, and not on every
`git merge`: integration goes through `gates merge` locally or through the forge under
pull-request mode, and the merge hook still gates a raw integration `git merge` into the
target. Scaffolding written before 0.6.0 asked on `Bash(git merge *)`, which also prompts
on a lane's routine sync of the target into its own change branch, so an unattended lane
stalled there (issue #44). `gates doctor`'s `merge-checkpoint` row warns while
`.claude/settings.local.json` still asks on `Bash(git merge *)`, naming
`Bash(gates merge *)` as the replacement, and `/gatedloop:upgrade` offers the one-line edit
(the recurring `merge-checkpoint` item); gatedloop never edits a permission file without
your yes.

**Archiving is out of scope for a headless run.** `/gatedloop:archive` delegates to
`/opsx:archive`, which blocks on an interactive confirmation upstream owns — a wrapper
can only be as unattended as the thing it wraps. If an automated pipeline genuinely
needs to archive, call the OpenSpec CLI directly (`openspec archive <name> -y --json`,
observed to complete in seconds) rather than routing through `/gatedloop:archive`.

## Enforcement: gates are hooks, not just prompt rules

Every guarantee above used to live only as a sentence in a skill or agent prompt —
"never commit on red `ci`", "`live-check` blocks the merge", "stop before the merge".
Interactively that's fine; unattended, nothing stopped a model from skipping a gate and
producing a green-looking branch nobody gated. The plugin now backs the load-bearing
guarantees with real Claude Code hooks (`PreToolUse`, `Stop`), installed automatically
once the plugin is enabled — nothing in your project needs to opt in for these:

| Guarantee | Hook | Mechanism |
|---|---|---|
| Never commit on red `ci` | `PreToolUse` on `Bash(git commit *)` | Denies unless the staged diff is planning-grade (below) or a fresh `ci` marker's tree matches `git write-tree` of the staged index |
| The implementer never edits an authored test, and runs it red first | `PreToolUse` on `Bash(git commit *)`, and the git `pre-commit` hook | After the `ci` marker check, `gates tests check` denies a placed or held test that differs from the handoff, and a placement with no failing `unit` run recorded after it. Past the hooks, `gates merge` step 1 runs `gates tests check --ref` on the branch head, and CI's `gates marker publish tests` posts the result as `gatedloop/tests` for branch protection to require |
| `live-check` blocks the merge | `PreToolUse` on `Bash(git merge *)` | Denies unless a fresh `live-check` marker matches the branch-head tree |
| A sync never commits past the gate | `PreToolUse` on `Bash(git merge *)` | Into a change branch, passes only a merge that creates no commit of its own (`--no-commit`, `--squash`, `--ff-only`, `--abort`, a fast-forward or an already-up-to-date merge). Git runs no commit hook for a merge commit, so any other is denied with the route: `git merge --no-commit <ref>`, then `gates run ci`, then `git commit` |
| A human accepted the behaviour (only under a declared `approval.acceptance`) | `PreToolUse` on `Bash(git merge *)` | Denies unless the latest `acceptance` ledger row for the same tree is an `accept` |
| Proposals run on the merge target or a `plan/*` branch based on it | `PreToolUse` on `Write` | Denies authoring a plan artifact (`proposal.md`/`design.md`/`specs/**`) on any other branch |
| The scaffold obeys the same discipline | `PreToolUse` on `Bash(openspec new change *)` | Denies the scaffold step itself, before any change directory exists, on the same terms as authoring |
| Merge precedes archive | `PreToolUse` on `Bash(openspec archive *)` | Denies archiving a change not yet present on the resolved merge target |
| Implementation starts only on a merged, approved plan | `PreToolUse` on `Bash(git checkout -b *)` / `git switch -c *` | Denies unless the named change's plan is present on the merge target AND its `.openspec.yaml` carries a populated `approved_by` whose `approved_sha` still matches |
| An epic is never implemented | `PreToolUse` on `Bash(git checkout -b *)` / `git switch -c *` | Denies, before the approval check, a branch for any change an active change names in `x-gatedloop-epic`, naming the children to implement instead |
| An epic archives after its children | `PreToolUse` on `Bash(openspec archive *)` | Denies archiving an epic while any child is not archived, listing each open child with its state |
| The loop keeps moving unattended | `Stop` | Blocks the stop and directs continuation from the next unchecked task, when a change branch has unchecked tasks and a clean tree |

Every `PreToolUse` denial is an **O(1) hash compare against a marker** `gates run
<gate>` writes on success — never a gate re-run under a hook timeout. The marker lives
under `.git/` (ephemeral, per-worktree, never committed); a durable, committed ledger
of every gate outcome lives separately at `.gatedloop/runs/<change>.jsonl` and survives
a squash-merge (keyed on `(change, task)`, never a commit SHA).

### Every gate resolves the repo the guarded command runs in, not the session root

Each hook above resolves the repository from the guarded command **itself** — an
explicit `git -C <dir>`, a `GIT_DIR`/`GIT_WORK_TREE` assignment or git's own
`--git-dir`/`--work-tree` options, or the last `cd <dir>` before the command — before ever consulting the hook input's own `cwd`, which is only
the next fallback, with the session's project directory last of all. This matters the
moment a second git worktree is in play — a planning worktree authoring alongside an
implementer's checkout, or a background agent whose shell resets its working directory
between calls and issues `cd <worktree> && git commit …` — because markers live under
the per-worktree `.git/worktrees/<name>/` directory: a hook that measured the wrong
directory would check a commit against the *wrong* worktree's index and an *empty*
marker store, denying a genuinely green commit. A denial always names the repository
it evaluated, so a mis-resolution is diagnosable from the message alone. There is
nothing to configure here; it is how every hook above already resolves its repo.

A `cd` target may be absolute, relative, `~`, `~/…`, `$HOME/…` or `${HOME}/…`, and a
`cd` inside a leading `( … )` subshell governs only that subshell's commands. A target
the hook cannot evaluate — another variable such as `cd "$LANE"`, `~user`, or a command
substitution — is **denied** rather than judged against the session's checkout: the
message names the `cd` and says to use an absolute path or `git -C <dir>`. (`gates hook
git-cwd` exits 3 for it; every guarding hook turns that into the denial.)

**A merge counts the lane's evidence.** Markers stay per worktree, so a lane's green
`live-check` and unscoped `ci` are recorded in the lane's own store. When a merge brings
in a branch that another worktree has checked out, the merge hook (and `gates merge`)
also reads that worktree's store, so a squash run from the primary checkout sees what
the lane proved. A marker still counts only for the exact tree the incoming branch
points at, and a denial names every store it read. The commit gate never borrows
another worktree's marker. See
[`docs/worktree-lanes.md`](./docs/worktree-lanes.md) for the full supported
multi-worktree pattern this resolution makes possible.

**Release note:** this fix lives in the hook scripts themselves, which run from the
*installed* plugin copy — updating this repo does not change a hook mid-session. A
running Claude Code session keeps its old, session-root-only hook behavior until the
plugin is reinstalled (or updated) **and a new session is started**, exactly like any
other hook change; `gates doctor`'s `shim-location` row already carries this
reminder.

### A planning-only commit is gated at planning grade, not against `ci`

When every file in a staged commit is a planning file — under OpenSpec's `openspec/`
directory, or the manifest's declared `conventions.rules-doc` path — the commit gate is
satisfied by `.gates.yaml` validating and `openspec validate <change> --type change
--json` passing for each staged change directory, instead of a green `ci` marker. A
docs-only proposal commit can't break your running stack, so it is gated on what it
*can* break: the manifest and the OpenSpec artifacts it touches. Ledger rows
(`.gatedloop/runs/**`) may ride along: no marker can see them (they are stripped from
the tree every marker hashes), so a planning commit that also carries ledger rows — an
archive commit with the change's merge row, as `gates record-merged` makes — is still
planning-grade. The moment a single staged file falls outside those two sets, the full
`ci` marker requirement applies to the **whole** commit — there is no partial credit. An empty staged diff is never treated as
vacuously planning-only; it still needs a fresh `ci` marker, same as before this existed.

**Convention review is recorded, not hook-enforced** — deliberately. `gates review
record <clean|findings> --task <N.M>` appends a `review` row to that same ledger,
carrying the verdict as an exit code and the exact tree reviewed, so "this task was
reviewed clean" has a backing artifact you can audit against the commit it claims to
cover. It is not a denial, because the verdict is an LLM's judgement rather than an
executable oracle: blocking a commit on a self-recorded verdict would enforce only
that the command was typed. Every row in the table above has a real oracle behind it;
this one has an artifact, which is the honest ceiling for a judgement gate.

**The loop records what each task started from**, for the same reason. `gates task
start <N.M>` writes the current tree to that ledger as a `task-start` row, and `gates
task changed` prints every path that differs from it now — untracked files included.
It exists because an unattended run once disowned three of its own uncommitted edits
as a non-existent "background watcher" and then reasoned about what was safe to revert
from there. An agent that cannot tell its own writes from someone else's will
mis-handle exactly the decisions that matter, and the fix is data it can consult rather
than a rule it must remember. With no baseline recorded the command refuses instead of
printing an empty answer — "I have no record" must never read as "nothing changed".

### Four layers, because the `PreToolUse` matcher is not airtight

`PreToolUse` matching is on the command *string*, not the effect — a differently-phrased
commit (a Python subprocess, a written-then-run script, a git library) carries no
`git commit` substring, so it slips past layer 1. That was an accepted trade-off until
it was observed in the field (issue #2): a denied agent routed around the matcher
rather than satisfying the gate. Enforcement now sits at four layers, described in full
in `AUTOMATION.md`:

| Layer | Mechanism | Catches | Defeated by |
|---|---|---|---|
| 1. `PreToolUse` string match | the hooks in the table above | the honest direct `git commit` | any indirection (observed, #2) |
| 2. Git `pre-commit` and `pre-push` hooks | `gates discipline check-commit` at the git layer (the same check as layer 1), and `gates discipline check-push` for a push of the merge target, **inside a declared agent session only** | **every** commit-creating path, on any host; a raw merge of the target pushed by hand | `--no-verify`; unsetting the `discipline.agent-env` variables |
| 3. Post-hoc reflog audit | the `Stop` hook joins each new commit's tree to the ledger's green-`ci` rows | anything that slipped layers 1–2 | nothing hides it — it taints and blocks the merge, but cannot un-create the commit |
| 4. Forge branch protection | adopter-configured required checks/reviews | `gh pr merge` and forge-UI merges | a repo with no branch protection configured |

Layer 2 is **opt-in** — `gates hook install` (offered by `/gatedloop:gates-init`, default-yes)
wires a git `pre-commit` hook that runs the same `gates discipline check-commit` as layer
1 at the layer where the commit object is created, regardless of how it was phrased, so a
ledger-only or planning-only commit is allowed at its grade on every path and anything
else needs the `ci` marker. With `--verdict-file <path>`, `check-commit` also writes one
token to that path on success, naming the grade that allowed the commit (`ledger`,
`planning` or `marker`); its exit status and printed text are unchanged, so a caller
branches on the token rather than on the wording. The same install adds a git `pre-push` hook: a push that
updates the merge target is denied unless `gates discipline check-push <sha>
--remote-ref <ref>` finds the pushed commit proven — a `merge` ledger row records it
(what `gates merge` writes before its one push), or the merge gate's incoming-tree
checks hold for its tree (`live-check` and full `ci` markers, `verify` where declared,
and for each change it carries in, no unresolved taint, the authored-test lock and
acceptance where declared). A denial names each unmet check and `gates merge <change>`
as the remedy; other branches and deletions pass silently, and neither hook runs a
gate. Under `integration.mode: pull-request` the forge pushes the target, so the hook
never sees that push; branch protection covers it.

The push hook is **opt-in**. `gates hook install --commit-only` installs or refreshes
the commit hook alone and records the `git-push-hook` adoption item as `declined` in
`.gatedloop/adoption.json` (commit it, so the team shares the choice), the same record
`/gatedloop:upgrade` writes when that item is answered `declined`. While it is
declined, a plain `gates hook install` refreshes the commit hook only and prints that
the push hook was skipped; `gates doctor` reports the `git-push-hook` row as ok,
naming the decline. Opt back in with `gates hook install --push` (it records
`adopted`) or by answering the item `adopted`.

Both hooks enforce **only inside a declared agent session**. `discipline.agent-env` in
`.gates.yaml` lists the environment variables whose presence marks one; the default is
`[CLAUDECODE]`, and declaring the list replaces it:

```yaml
discipline:
  agent-env:
    - CLAUDECODE
    - OTHER_HOST_VAR   # the variable your other agent host sets
```

`gates discipline agent-session` exits 0 when any is set and 1 otherwise, and both hooks
are a transparent no-op on 1 — a human terminal, an IDE, or a CI runner is unaffected.
`gates validate` fails naming the key when it is not a non-empty list of variable names;
the hooks then decide by the default rather than blocking anyone.

The hooks resolve the shim through `${CLAUDE_PLUGIN_ROOT}`, then `gates` on PATH, then
the absolute path of the shim that ran `gates hook install`, which it records in the
copy it writes (the one line it changes), so the hooks work on a host with no plugin
environment. If none resolves, the hook lets the commit or push through with a stderr
note, and `gates doctor` reports the copy stale. `gates hook install` composes with an existing hook manager
(husky, lefthook, the pre-commit framework, a `core.hooksPath` redirect, or a bare hook)
where it safely can and refuses-and-instructs where it cannot — it never clobbers.
It finds the hook where git itself runs hooks from (`git rev-parse --git-path hooks`:
the repository's shared `.git/hooks`, or `core.hooksPath`), so `gates hook install` and
`gates doctor` give the same answer from the primary checkout and from any linked
worktree. A linked worktree's private `.git/worktrees/<name>/` is never used.
A direct install writes a **copy** of the shipped template, and a copy does not change
when the plugin does: a hook installed before 0.5.0 still runs the older marker-only
check (it denies a ledger-only or planning-only commit made outside the tool layer).
Run `gates hook install` again to refresh it. It recognizes its own copy by the
template's header line, and when the copy's bytes differ from the shipped template
(an older template, or a local edit) it saves the old body to
`pre-commit.gatedloop-prev` (or `pre-push.gatedloop-prev`) beside the hook, writes the shipped template, keeps it
executable, and prints both paths. A second refresh overwrites that backup. A copy
that already matches is left alone ("nothing to do"), and a foreign hook or a hook
manager's config is still never touched. The comparison ignores the recorded shim-path line, and a copy whose
recorded path is gone while nothing else resolves the shim is stale too. `gates doctor`
reports both hooks (`git-commit-hook`, `git-push-hook`) and warns on a stale copy, and
`/gatedloop:upgrade` offers the refresh as the `git-hook-refresh` item (either hook)
and, where the commit hook is wired and the push hook absent, the `git-push-hook` item. A composed
block delegates to the shipped template at run time, so it picks up a new check on
its own and is never stale.

Layer 3 needs nothing configured: the `Stop` hook already audits and records a **taint**
on the change's ledger for any commit with no green-`ci` record, and the merge gate
refuses a tainted change until a green `gates run ci` on the branch head re-verifies it.

### Branch protection is required for `pull-request` integration modes

Layers 1–3 cover the **local** commit and `git merge` paths. They do **not** cover the
**forge** merge path: `gh pr merge`, or a click in the forge UI, is not a local `git
merge`, so neither the `PreToolUse` matcher nor the merge gate fires on it — there is no
local git-hook equivalent. For any project on `integration.mode: pull-request` (with or
without `requireApproval`), the adopter **must configure forge branch protection** on the
default branch — gatedloop documents this requirement and names what to protect, but does
not implement anything forge-API-side (that is the adopter's forge binding, not
gatedloop's):

- **Required status checks** on the default branch — at minimum `gatedloop/ci`, with
  **your CI provider as its expected source** (on GitHub: the GitHub Actions app), so
  the only status that satisfies it is the one your CI job posts with `gates run ci &&
  gates marker publish ci` on the PR's head. A status `gates merge` posts from a laptop
  is self-reported and must not count. Require `gatedloop/tests` (the authored-test lock
  at the head, `gates marker publish tests`) the same way, in two steps: first add the
  publish step to your workflow, then require the status, or every open pull request
  waits on a status nothing posts. Require `gatedloop/live-check` the same way where
  CI also runs and publishes it. The sample workflow in
  [`docs/running-at-scale.md`](docs/running-at-scale.md) does the `ci` and `tests` half
  and records forge merges with `gates record-merged`.
- **Required review** — for `requireApproval: true`, require at least one approving review
  before merge, which is the forge-side counterpart of the loop's stop-before-the-merge.
- **Under `approval.acceptance: review`, that required review *is* the acceptance
  review.** The reviewer approves the behaviour the brief describes, not only the diff;
  `gates acceptance attest <change> --pr <n>` then records it into the ledger, so the
  forge path and the local path require the same human act and `gates stats --outcomes`
  can see the acceptance.

Branch protection is also what makes **plan approval** mean anything. `approved_sha` pins
an approval to exact plan content, so editing an artifact after approval invalidates it —
but a hash cannot tell a real approver from an invented one, and an
`approved_by` hand-written together with a recomputed `approved_sha` is self-consistent
(verified end to end; see `AUTOMATION.md` task 1d.7). What rules that out is that the
approval only counts when it is on the **default branch**: protect that branch and the
only way to get one there is through a reviewed pull request, which is where the forge —
the one party that knows who actually approved — has the final word.

State it plainly, since the two paths differ: **the local `git merge` path is covered by
the merge gate; the forge merge path is covered only by branch protection.** A
`pull-request`-mode project that skips branch protection keeps layers 1–3 (local paths)
but leaves the forge merge ungated — the `Stop`-hook audit still reports a taint loudly,
but nothing local can block a forge-side merge.

## Upgrading

Update the plugin with `/plugin marketplace update`. Claude Code installs a new
version only when its version number changes. A version can also add settings your
project should decide deliberately rather than run on defaults it never chose. The
plugin ships a catalogue of them, and three pieces handle them:

- **The session brief says when settings are waiting.** At every session start it
  runs `gates adoption status`. When items are undecided it adds one line naming the
  installed version, how many items there are, and `/gatedloop:upgrade`. Otherwise it
  adds nothing. It never asks, interactive or headless.
- **`/gatedloop:upgrade` walks them.** It asks one question per undecided item, with
  the recommended answer first and "Decide later" last. Where an item corresponds to
  an onboarding step, such as capturing test conventions, it runs that
  `/gatedloop:gates-init` step. Each answer is recorded as soon as it is given, so
  an interrupted walk resumes where it stopped.
- **`.gatedloop/adoption.json` holds the decisions.** Only `gates adoption record`
  writes it. Commit it, along with `.gates.yaml` when a setting changed the
  manifest, so the whole team shares the answers.

An item is no longer asked about once:
- the project has acted on it, for example the manifest already sets the key;
- it was answered `adopted` or `declined`;
- it was answered `later`, until the next plugin version.

Some items are **recurring**: an act a release can need again rather than a setting
chosen once. For those, only the project's state counts. An `adopted` answer does not
hide the item, and `declined` holds only for the plugin version it was recorded at,
the way `later` does. The walk says so when it asks about one.

`git-hook-refresh` and `approval-keys` are the recurring ones today. It applies only when
`.git/hooks/pre-commit` (or wherever the hook path points) holds a direct copy of a
gatedloop hook template that differs from the one this version ships. Adopting it runs
onboarding's hook-install step, `gates hook install`, which replaces the copy and keeps
the old body in `pre-commit.gatedloop-prev` beside it (see "Four layers" above). A
composed hook, or no hook at all, never brings it up. `approval-keys` (since 0.5.1)
applies while an active change's `.openspec.yaml` still carries approval keys in the
earlier spelling; adopting it means running `gates approval migrate` and committing the
result. It recurs because a change attested by an older gatedloop can reappear. `confirm-gate` asks a project
that binds a `live-check` whether to add the optional `confirm` gate, through
onboarding's confirm offer.

An item that doesn't apply to the project is never asked about, for example the
schema-flow question in a project with no local schemas. The `gates` command
reference above describes `adoption status` and `adoption record`.

## Migrating from Specloop

The plugin was called Specloop until 0.7.0. Every name it owned changed with it. `gates`, `.gates.yaml` and the gate names didn't change: they are the contract, and they never carried the product name.

| Was | Now |
|---|---|
| `specloop@specloop`, `/specloop:*` | `gatedloop@gatedloop`, `/gatedloop:*` |
| `.specloop/` | `.gatedloop/` |
| `x-specloop-approved-*`, `x-specloop-epic` | `x-gatedloop-approved-*`, `x-gatedloop-epic` |
| `specloop/<gate>` statuses | `gatedloop/<gate>` |
| `specloop.test-quality` | `gatedloop.test-quality` |
| a schema's `specloop: { flow: … }` | `gatedloop: { flow: … }` |
| `# >>> specloop pre-commit …` hook markers | `# >>> gatedloop pre-commit …` |
| `pre-commit.specloop-prev` | `pre-commit.gatedloop-prev` |

**From 0.9.0 the earlier names are not read.** Through 0.8.x the shim read each earlier spelling where the new one was absent, printing a one-line warning, and `gates marker publish` posted both contexts. From 0.9.0 it reads only the new spellings, and writes only them:
- A project that still holds `.specloop/`, alone or beside `.gatedloop/`, is refused by every command except `gates doctor` and `gates migrate-name`, and the refusal names `gates migrate-name`. Running on would start an empty `.gatedloop/` beside it and split the ledger.
- `x-specloop-*` keys are not read, so an approval recorded under them reads as unapproved until the change is migrated.
- A git hook carrying the earlier markers isn't recognised as gatedloop's, so `gates hook install` would add a second block beside it. Migrate first.
- `gates marker publish` posts only `gatedloop/<gate>`. Branch protection still requiring `specloop/<gate>` never passes again.

**`gates migrate-name`** runs from the repository root and makes local edits only. It never commits and never pushes:
1. It moves `.specloop/` to `.gatedloop/` with `git mv`, or with a plain rename when git doesn't track the directory.
2. It renames the `x-specloop-*` keys in every active change's `.openspec.yaml`. Values and order are kept, and the approval sha covers no `.openspec.yaml`, so every approval still checks. Archived changes are left alone.
3. It renames the markers in a composed git hook. A direct copy of the template is refreshed by `gates hook install`, and the command says so.
4. It prints each edit it doesn't make, with the replacement:
   - branch protection requiring `specloop/ci` or `specloop/live-check`;
   - the Claude Code plugin install;
   - any `enabledPlugins`, `extraKnownMarketplaces` or permission rule in `.claude/settings.json` or `.claude/settings.local.json` that names the earlier plugin.

It exits 0 when nothing is left to migrate. Commit what it changed; the commit is planning- and ledger-grade. `gates doctor`'s `name` row warns while anything earlier remains. The adoption catalogue's recurring `rename` item offers the migration through `/gatedloop:upgrade` from 0.7.0.

**The Claude Code side.** An existing `specloop@specloop` install keeps resolving the `specloop` entry of the marketplace it was added from, even after that marketplace's own name changed. Through 0.8.x that entry was a forwarder, which showed a notice at session start and answered each former `/specloop:*` command with the same notice. From 0.9.0 the entry and the forwarder are gone. Run `/plugin marketplace add tessellate-space/gatedloop`, then `/plugin install gatedloop@gatedloop`, then `/plugin uninstall specloop@specloop` and `/plugin marketplace remove specloop`. `gatedloop@gatedloop` resolves only once the new marketplace is added. The earlier repository, `tessellate-space/specloop`, is a private archive with no redirect.

## Migrating from `harness`

gatedloop's shim and manifest were renamed `harness` → `gates` (the name collided with both the *agentic harness* — Claude Code itself — and upstream OpenSpec's *intent harness*). Rename at your convenience:

| Was | Now |
|---|---|
| `bin/harness` (or `harness` on PATH) | `gates` |
| `.harness.yaml`, `harnessVersion` | `.gates.yaml`, `gatesVersion` |
| `/gatedloop:harness-init` | `/gatedloop:gates-init` |

Neither old name works anymore — `harness` is gone from `bin/`, and a `.harness.yaml`/`harnessVersion` manifest fails validation like any other malformed one. Rename before you next run `gates`.
