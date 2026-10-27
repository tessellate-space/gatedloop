# Gate economics — what to do once you can see the bottleneck

`gates stats` reads the durable ledger (`.gatedloop/runs/<change>.jsonl`) and reports,
per change, where the loop's active time actually goes: time and share per gate,
failed-attempt counts, and a per-task breakdown. Field report #18 found this by hand
across 15 merged changes and derived one dominant fact — **gate execution is the
loop's biggest cost**, not authoring or review. `gates stats` is the read-back so
nobody has to re-derive that from raw jsonl again. This page is the "now what": five
principles for shaping `.gates.yaml` once the report shows where the time went. Every
recommendation is a gate *shape* — none names a stack tool, because the shape applies
whether the underlying command is a compiled build, an interpreted test runner, or
something not invented yet.

## 1. Run the cheapest suites first

A gate manifest can declare more than one check; order them cheapest-first inside a
single gate body, or split them across `unit` (fast, inner loop) and `ci` (aggregate,
pre-commit). A change that only ever touches one surface pays for the whole suite on
every attempt if the manifest doesn't let it stop early — put the check most likely to
fail, and cheapest to run, first.

## 2. Target a fast per-task `ci`

`ci` runs before every commit, so its cost is paid once per task, not once per change.
If `gates stats` shows most of a change's active time inside `ci` and most of `ci`'s
runs are failed attempts, the fix is a faster `ci` scoped to what a single task
plausibly touches — a narrower default test selection, a build cache keyed on
changed inputs, or a two-tier contract where a fast, scoped oracle runs per task and
the full, unscoped suite runs once at the merge lane (see SETUP.md's `gates` command
reference for how a project declares that split, if it has adopted one). The
unscoped run is still the last word before anything lands — a fast inner loop is a
shape for the common case, not a replacement for the real gate.

## 3. Key expensive builds on their inputs

A build or compile step that re-runs from scratch on every gate invocation pays full
price for every attempt, including attempts that only touched a test file or a
comment. A gate command that keys its cache on the actual changed inputs (source
files, lockfiles, whatever the toolchain already hashes) turns most attempts into a
cache hit instead of a full rebuild — the gate contract doesn't care how the command
gets to its exit code, only that it does.

## 4. Keep the full suite at the merge lane

The fast, per-task path exists to shorten the inner loop, not to replace the
oracle that gates the merge. Whatever runs at change completion (`ci` on the final
head, `verify`, `live-check`) should be the full, unscoped suite — the one whose
green is the actual claim "safe to merge." A manifest that only ever runs the fast
path has traded a real gate for a faster one that proves less.

## 5. Run one heavy gate per machine

A single expensive gate (a full build, a live-check probe) run concurrently by more
than one loop on the same machine competes for the same CPU, memory, or lock a real
oracle needs to be honest — the report can look slower than the work actually was,
and a flaky failure can be contention rather than a real regression. Serializing the
heaviest gate onto one runner per machine keeps its number legible. The lock itself
(coordinating across concurrent worktrees on one host) is a separate, larger
mechanism than a manifest shape — out of scope for this page.

---

Run `gates stats` after a few tasks land, read the per-gate share, and start with
whichever principle above matches what the report actually shows — not the one that
sounds most appealing in the abstract.

---

## Reading the tokens

Since `token-ledger`, the same report prints what each task cost in tokens beside
what it cost in time. The commit hook and the `Stop` hook append a `usage` row for
the task in flight, counted from the session transcript (counts only, never its
text). `gates stats` sums those rows per task and per model, then says what it could
not see: the tasks with no counted usage row, and how much of the ledger's span no
usage window covers. `--json` carries the same figures under each change's `tokens`
key, and `--epic` totals them per child.

**Tokens track gate shape too.** A red gate run is paid for twice: once in wall time,
and again in the tokens the loop spends reading its output and trying a fix. A full
suite where a scoped one would do, or a chatty gate log, shows up in both columns.
The principles above lower both.

**Prices are yours.** `gates stats --cost` multiplies the counts by `economics.prices`
in `.gates.yaml` and names any recorded model you priced nothing for. The plugin ships
no price list, because prices change and differ by contract; the tokens are the
stored truth, and the prices only convert them.

**A budget turns the number into a stopping rule.** `loop.token-budget` caps a
change's recorded tokens. Past it, `gates run unit|ci` refuses and the loop halts
with cause `budget`. Recording works without it, and the recommended first step is
to record for a while and read the per-task spend before picking a number.

What the tokens cannot answer: a session with no readable transcript (another host,
a human's terminal) records null counts, and a task that never reached a commit or a
stop since its last flush is not counted yet.

---

## Reading the outcomes view

`gates stats` measures what the loop *costs*; `gates stats --outcomes` measures how
often it *ran itself*. Same ledger, different question: *what fraction of changes ran
hands-off, and what stopped the rest?*

**Hands-off** means a change is `merged` and its ledger holds zero `halt`, zero
`intervention` and zero `taint` rows. Anything else merged is `assisted`, and the
report names which kind of row made it so. `--all` reports the hands-off share as
*N of M merged changes* — and as *not computable*, never zero, before anything has
merged.

**`accepted` vs `merged`.** Where a project declares `approval.acceptance`, the terminal event is *acceptance*, not merge: a change is `accepted` when an `accept` row pins the same tree its `merge` row records, and hands-off requires that — so the share becomes *N of M merged or accepted changes*, and a merge whose shipped tree no human accepted (none recorded, or an acceptance of an earlier tree followed by an edit) stays `merged` and `assisted`, naming the missing acceptance. A `reject` at acceptance counts under halts by its cause (`weak-spec` or `missing-oracle`). Without the policy the view is unchanged and the report says the metric ends at `merged` — which measures the loop satisfying its own oracles, not the human's intent.

**Why a taint counts against it.** A taint is a commit that bypassed the loop's own
`ci` gate. Whoever made it, that stretch of the run was not the loop running itself.

**Where to invest next.** Read the halts by cause, not the total. Every cause names a
thing to build: `missing-oracle` → a gate that can decide the question; `weak-spec` →
a sharper spec pattern; `oracle-conflict` → a rule for which verdict wins;
`stalled` → a smaller task or a better attempt budget; `environment` → a
`requires` precondition that boots what was missing; `budget` → a cheaper gate shape
(principles 1–5 above: every red run and every re-read of a long gate log is spent
again in tokens) or a smaller change, since `loop.token-budget` caps the change, not
the task. A large `other` share means the cause set itself needs a member.

**Three blind spots.** The ledger cannot see what never reached it:

- a halt that was never recorded (only `gates halt record` makes a halt count — and
  take effect);
- a human turn that went through neither the question tool nor a gated commit (an
  uncommitted hand edit, a conversation outside the session);
- a commit created after the last audit — the audit runs at every `Stop` and before
  every merge, so this closes at merge time, not before.

Rows written before the `session` field existed are disclosed as such:
human-commit classification is unavailable for them, and a commit they gated is
counted as unclassifiable rather than as agent or human.
