# fix-marker-mechanics — Design

## Context

See proposal.md — Why. The mechanics live in three places: `bin/gates` (marker
write/check under `.git/<worktree>/specloop/markers/`, ledger append under
`.specloop/runs/<change>.jsonl`, the live-check selection in `cmd_run`, the
commit rungs in `cmd_discipline`), `hooks/gate-merge.sh` (PreToolUse compare of the
live-check marker), and the shipped prompts (`skills/tdd-apply/SKILL.md`,
`agents/tdd-implementer.md`). Constraints that shape everything below:

- **The hook compare must stay O(1)** — a hook runs under a timeout and must never
  re-run a gate (harden-unattended-loop D1).
- **The marker and the ledger deliberately have opposite lifetimes** (harden D7/D8):
  the marker is an ephemeral per-worktree lock; the ledger is durable and committed.
  The defect is that the durable record's *write* invalidates the ephemeral lock.
- **zero-dep-shim / fail-loud-gates / stack-agnostic-prompts** bind every edit here.
- The merged-but-unimplemented `scale-gate-cost` change adds a `scope` field to the
  same marker payload and ledger row (its D2). This design must compose with it.

## Goals / Non-Goals

**Goals:**

- A gate's own bookkeeping can never stale the evidence it just produced.
- Every legitimate outcome of `gates run live-check` — pass, skip — is recordable
  and merge-satisfiable; only "never ran" and "ran red" block.
- One resolved recipe runs once per invocation.
- The merge gate checks the tree that is actually being merged in.
- The shipped prompts describe only executable steps.

**Non-Goals:**

- Marker keying across worktrees or concurrent agents (sibling
  `worktree-native-loop` — this change keeps the single-slot-per-worktree model).
- Which commands trigger `gate-merge` (sibling `harden-hook-matching` owns
  matching; this change only decides what a *fired* hook validates).
- Taint/audit scoping (sibling `scope-audit-to-branch-commits`).
- A merge-queue/merge-train primitive (#16 item 5's first ask) — the ledger
  exclusion removes the pain that motivated it; a primitive stays a candidate.
- Origin-reachability of the discipline checks (#17 item 6) and hook cwd
  resolution (#17 item 7).

## Decisions

### D1: Normalize the tree hash at both ends, don't special-case the diff

The marker compare stays a hash equality, but both sides are **ledger-normalized
trees**: strip every entry under `.specloop/runs/` from the tree object and hash
what remains. `_write_marker` normalizes the tree it is given before recording;
`gate-marker check` normalizes the tree the hook passes before comparing. Hooks
keep passing raw trees (`git write-tree` of the index, `<ref>^{tree}`) — the
normalization is shim-internal, so the hook scripts' interface does not change and
the two callers cannot disagree about what "fresh" means (the same
single-implementation argument as `_check_marker_and_report`).

Mechanically: a temporary index (`GIT_INDEX_FILE`) populated with `git read-tree
<tree>`, `git rm --cached -r --ignore-unmatch .specloop/runs`, `git write-tree`.
Pure plumbing, stdlib subprocess, no working-tree effect, a few milliseconds — the
O(1) hook budget survives.

**Alternative — accept a marker when `git diff-tree` between recorded and current
trees touches only `.specloop/runs/**`:** rejected. It turns one equality into a
diff walk plus a path-classification loop at *check* time, puts the leniency
decision in the checker (two code paths could classify differently), and makes the
marker's recorded tree ambiguous evidence ("fresh for which of the equivalent
trees?"). Normalized-at-write means the recorded hash *is* the class
representative.

**Alternative — write the ledger row before computing the marker tree and
auto-stage it (issue #10's direction 1):** rejected. It fixes only the commit-time
chase, not the merge-time one (live-check's marker records the HEAD *commit* tree,
which no amount of staging reorders), forces `gates run` to mutate the git index
(a gate that edits your staging area is a new kind of surprise), and still breaks
whenever a *later* run appends a row.

**Alternative — declare the ledger commit-exempt and gitignore it (issue #10's
direction 2):** rejected. Harden D7/D8's durability argument stands: the ledger
must survive the clone, and the squash-SHA row is what joins it back to `main`'s
history. The design intent is right; the mechanics were wrong.

The exclusion is exactly `.specloop/runs/**` — not `.specloop/**` — so any future
non-ledger state under `.specloop/` still invalidates markers by default.

### D2: The skip is a recorded verdict, answering the no-marker comment honestly

The empty-check-set path in `cmd_run` currently ends with a design comment: *"No
ledger row and no marker: nothing ran (design's own requirement that a
skipped-because-empty run can never satisfy the marker)."* The concern behind it is
real — a selection defect (globs that silently match nothing) must not green-light
merges — but the implemented answer makes the merge gate *unsatisfiable*, which is
worse than the risk it guards: #9 shows every fresh adoption and every
docs-only diff permanently denied, and the observed escapes (`--all` for a
markdown file, `--changed <some-hot-file>`) either waste a full suite run or
fabricate a hot set — strictly worse evidence than an honest recorded skip.

So the skip becomes a **verdict**, not an absence. The marker payload gains
`verdict: "pass" | "skip"` (absent = pass, so pre-existing markers stay valid) and,
for skips, an `evidence` object carrying what the message already prints: baseline
kind, resolved merge target, files considered. A ledger row is appended with the
same verdict. `gate-marker check` treats a tree-matching skip marker as satisfied
and *says so* — its success line names the verdict and evidence, so a merge
allowed by a skip is visibly allowed by a skip.

Why this answers the comment's concern rather than deleting it:

1. **Nothing is satisfied by default.** The operator (or loop) still has to run
   `gates run live-check`; a missing marker still denies. "Skip" ≠ "never ran".
2. **The decision is bound to a tree.** A skip verdict satisfies only the exact
   head tree it examined (ledger-normalized, per D1). Any real change re-opens
   the question.
3. **The decision is auditable.** The evidence rides in the marker and the durable
   ledger — a reviewer can see *why* gates decided no probe applied, which the
   current unsatisfiable denial never records anywhere.
4. **The residual risk is symmetric with the pass path.** Syntactically valid
   globs that miss real surfaces are a manifest-authoring defect no runtime can
   detect — and the same defect on the pass side (a probe bound to the wrong
   command) also produces a green today. Malformed globs are already caught loudly
   at load (`expand-brace-globs`). The comment's guard was paying an infinite cost
   (unmergeable states) against a risk the pass path accepts everywhere else.

One code path covers #9 (gate undeclared anywhere) and #14/#40 (hot set empty or
live-check-less): both resolve to an empty check set, both record the same shape
of skip. A *declared* probe that runs red keeps writing nothing — the invariant
#9 itself asked to preserve.

**Alternative — `gate-merge` asks the shim whether live-check is declared before
requiring a marker (issue #9's other direction):** rejected. It splits the
decision across two moments (declaredness at merge time vs. hot set at run time),
answers only the undeclared case (docs-only diffs in a declaring repo still
deadlock), and gives the merge a satisfied state with no record behind it —
exactly what the recorded-verdict model exists to avoid.

### D3: Dedupe by exact resolved command string

Within one `cmd_run` live-check invocation, the `(surface, command)` pairs are
deduped by the command string, first-declaration order preserved; the log line
attributes each execution to every surface binding it (`live-check [frontend,
e2e]`). The aggregate exit code is unchanged by construction — running an
identical command once cannot report less than running it twice, and the
non-idempotent-suite flake (#14) is precisely the case where the second run
reports *more* than the truth.

**Alternative — dedupe by a semantic recipe identity (hash of an expanded
command, env, cwd):** rejected as scope creep; the manifest binds plain command
strings, so string equality *is* recipe identity in this system. Two surfaces
that want the same suite spelled differently have declared two recipes, and
running both is the declared meaning (documented in SETUP.md's live-check
section as part of this change).

### D4: The merge gate resolves the incoming ref; branch-head markers are the point

`gates run live-check` records the branch head's tree — correct, since that is
where the probes ran. The squash-merge flow then switches to the merge target,
where HEAD's tree is the *target's*, so the compare could never match (#17 item
5): the gate was validating "live-check passed on what I currently have" when the
question is "live-check passed on what I am about to take".

`hooks/gate-merge.sh` therefore extracts the merge source ref from the `git
merge` invocation (the trailing non-flag argument), resolves `<ref>^{tree}`, and
checks the marker against that. If no source ref can be resolved (e.g. `git merge
--continue`, an octopus, an expression git can't verify), it falls back to the
current HEAD tree — the old behavior, which remains correct for the
run-after-fast-forward case — and a denial names *both* trees it tried. The
guidance line becomes accurate: "run `gates run live-check` on the change
branch's head".

Boundary with `harden-hook-matching`: that sibling decides *whether* the hook
fires (token vs. substring matching, #17 item 4). This change decides *which
tree* a fired hook validates. Both edit `gate-merge.sh`; the overlap is textual,
not semantic, and neither depends on the other having landed.

Accepted approximation: with a diverged merge target, the squash *result* tree
differs from the branch head tree, so branch-head evidence is evidence about the
inputs, not the merged output. That is today's intended semantics too (the marker
has always recorded the branch head); predicting the merge-result tree pre-merge
is out of scope, and the post-merge `ci` on the target plus the next change's
gates cover the composition.

### D5: Ledger-grade commits, scoped to exactly the exclusion set

With D1, a staged diff consisting solely of `.specloop/runs/**` paths normalizes
to the same tree as HEAD — demanding a fresh `ci` marker over it demands proof
about a delta the proof cannot even see. `discipline check-commit` gets a third
rung beside planning-grade: a non-empty, ledger-only staged diff is allowed with
an explicit printed verdict (fail-loud-gates: the verdict is printed, never
silent). An empty diff still falls through to the full requirement (the existing
"zero evidence is never a free pass" stance), and one non-ledger path in the diff
removes the discount entirely. The bypass surface this opens is precisely "you
may commit audit-trail rows without a green" — acceptable, because the ledger is
the *record* of gate outcomes, not an input to any gate, and the git-layer hook
applies the same rung.

### D6: Prompt updates say why, in one line each

`skills/tdd-apply/SKILL.md` §5h keeps its instruction — stage the task's files,
the `[x]` flip, and the ledger row together — which D1 makes executable, and gains
one clause noting the ledger is excluded from the marker's hash (so a reader
understands why this doesn't self-invalidate). §7.5 step 5's merge-row commit
drops any chase language; the ledger-grade rung covers it. `agents/tdd-
implementer.md` needs no mechanical change beyond the same alignment pass — its
"commit the row with the task" guidance becomes true rather than aspirational.
Neither file may name a real command (stack-agnostic-prompts) — nothing here
does.

### D7: Compatibility with `scale-gate-cost`

Both changes grow the same marker payload and ledger row: `scale-gate-cost` adds
`scope` ("full" or a surface name); this change adds `verdict` (and `evidence` on
skip markers, a `verdict` key on ledger rows). The fields are orthogonal —
`scope` says *which oracle ran*, `verdict` says *whether anything needed to run* —
and both stores are dicts read by key with absent-means-default semantics, so
neither change's reader breaks on the other's writer. Tree normalization (D1)
applies identically to scoped markers: a scoped `ci` marker records a normalized
tree like any other. Whichever change is implemented second simply constructs
payloads carrying both fields. The ledger row shape doctrine ("every row carries
all keys") means the implemented-second change extends `LEDGER_ROW_FIELDS` with
the union; rows written in the gap read as `None`/default for the missing key,
which both designs already treat as the safe value.

## Risks / Trade-offs

- **[A skip verdict green-lights a tree a defective manifest never examined]** →
  Mitigated per D2: loud glob validation at load, evidence recorded in marker and
  ledger, tree-bound acceptance, and explicit skip-labelled output at merge time.
  Residual risk is the same class as a wrong probe command passing, and is a
  manifest-review concern, not a runtime one.
- **[Ledger exclusion hides a malicious or corrupted ledger edit from the commit
  gate]** → Accepted narrowly: the exclusion and the ledger-grade rung cover only
  `.specloop/runs/**`; the ledger is an audit record whose integrity is checked by
  readers (taint audit, `gates ledger`), not by the commit gate; and the git
  history of the file remains ordinary reviewable history.
- **[Normalization cost on every marker write/check]** → A temp-index read-tree/
  rm/write-tree round-trip is milliseconds on repos of this class; still no gate
  re-run under a hook. If it ever measures hot, the normalized hash can be cached
  in the marker alongside the raw tree without changing the contract.
- **[Ref extraction from the merge command mis-parses an exotic invocation]** →
  The fallback is the previous behavior (HEAD tree), never a false allow: a parse
  failure can only make the gate as strict as it is today, and the denial names
  both trees tried so the operator sees what was compared.
- **[Two changes racing on the same payload shape (`scale-gate-cost`)]** →
  Orthogonal keys with absent-means-default reads (D7); the second implementation
  carries the union. Stated in both proposals' ordering notes.
- **[Back-to-back identical recipes were load-bearing for someone]** → No known
  case, and the declared meaning of two surfaces binding one command is "this
  command covers both", not "run twice". Anyone needing a double run can declare
  it as a distinct command string.
