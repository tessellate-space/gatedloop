## Context

Specloop shipped (PR specloop PR 1, squash-merged as `6d15996`) describing itself as a spec-driven, closed-loop workflow — implicitly owning the whole lifecycle. Investigation since then established three facts that narrow it:

1. **An OpenSpec schema is a workflow definition**, not a template folder: an artifact DAG where each artifact declares `id`, `generates`, `template`, `instruction` and `requires`, plus an `apply` block naming what must exist before implementation and which file tracks progress.
2. **Five schemas are maintained upstream** in a community catalog at <https://github.com/intent-driven-dev/openspec-schemas> — `minimalist`, `event-driven`, `behaviour-driven`, `intent-driven`, `spec-driven-with-adr` — distributed as standalone repositories and installed by copying into `openspec/schemas/<name>/`. A sixth, `spec-driven`, ships with the CLI itself, so `openspec schemas` in a fresh project lists one and the catalog supplies the rest.
3. **Per-change workflow selection already exists.** Resolution order is `--schema` flag → change metadata (`.openspec.yaml`) → project config → default. Every change already carries `schema:`.

The corpus behind those schemas is almost entirely *upstream* of code — articulation quality, spec review, decision records. Its own tool survey notes it offers "no technical depth on testing harnesses, verification frameworks, or quality assurance mechanisms." That is the space Specloop occupies.

A fourth fact emerged while writing this change and is severe enough to have become its own prerequisite: **three of Specloop's five commands are renamed copies of OpenSpec's own**, already stale against their originals. `unfork-commands` removes them. It lands first, because a change that states a boundary in prose while `commands/` contradicts it in code has described a boundary rather than drawn one.

A fifth arrived from outside this repository. An existing OpenSpec adoption model — a talk, a cheat sheet, and a coverage audit applying its scale to a real project — already frames adoption as a ladder with a measuring stick, and it was written without reference to Specloop. Its vocabulary is better than the one this design had been inventing, and it has already been taught to the audience these docs are written for. D3 adopts it.

## Goals / Non-Goals

**Goals:** state the boundary where readers meet it (manifests, README, SETUP); establish **onboarding as an owned surface**, not a side effect; record a scope test that outlives this conversation; fix the conventions defect found while deriving the boundary.

**Non-Goals:** authoring or forking schemas; building authoring gates; deleting the forked commands (that is `unfork-commands`); executing the `harness` → `gates` rename (that is `rename-to-gates`); any change to enforcement, hooks, the ledger, or loop behaviour.

## Decisions

### D1: Delegate two axes, own the loop between them
The system varies along two independent axes. Axis A — *what varies by project* (commands, probes, conventions) — is answered by the gate manifest. Axis B — *what varies by kind of work* (which artifacts, in what order) — is answered by an OpenSpec schema, selected per change. Specloop owns neither axis; it owns the loop that runs from `tasks.md` to a verified merge. Both delegations are stated in the docs so the boundary is a reader-facing fact rather than an internal understanding.

### D2: The rejection test, not a mission statement
A positioning statement that only says what we *do* cannot settle an argument. The four-question test is recorded instead, because each question has a determinate answer and a destination for the rejected work:

| Question | Answer | Where it goes instead |
|---|---|---|
| Authors an artifact? | not ours | upstream schema, or schema selection |
| Knows a stack command? | not ours | a gate in the manifest |
| Makes a stated guarantee enforceable? | **ours** | — |
| Gets a team running faster? | **ours** | — |

The test's value is that it has already caught a live violation *in this repository*: applied to the shipped command set, it rejects `commands/explore.md`, `commands/propose.md` and `commands/archive.md` on the first question — they author artifacts, and upstream maintains equivalents that our copies have fallen behind. That is the worked example, and it is a better one than any hypothetical because the answer was unwelcome and the test produced it anyway.

Applied forward it splits the bugfix pack cleanly — artifacts contributable upstream, gates retained here.

**The four questions are instances of one.** D3's ladder makes the underlying test measurable: *does it move a phase from `act` to `close`, or move a team up a rung faster?* Authoring an artifact is a 0→3 move — real work, and OpenSpec's. Naming a stack command is a binding, and the adopter's. The four questions stay because they are faster to apply at a code review; the single question stays because it can be scored, and a scored test survives an argument that a checklist does not.

### D3: Positioned on the adoption ladder — Specloop is the third rung, prefabricated
The narrower boundary invites describing Specloop as a convenience wrapper over OpenSpec. Rejected — but the rejection has to survive `unfork-commands` deleting a third of the command surface, so it needs to name things that remain true afterwards. The adoption model named in the Context supplies both the frame and the evidence.

Its ladder has three levels and one measuring stick. The stick scores each SDLC phase 0–4: `none` → `advise` → `observe` → `act` → **`close`**, where *close* means a tool changes real state, reads back the result, and self-corrects with no human turn.

| Level | What the team adds | What moves |
|---|---|---|
| **Rookie** | `openspec init`, run the default loop | System design, Implementation → `act` |
| **Intermediate** | fork a schema, write the constitution, add skills | Testing → `act`, Code review → `observe` |
| **Advanced** | subagents running unattended, hook-enforced gates, oracles | Implementation, Testing, Code review, Release → **`close`** |

The talk's own answer to *"how do I get a gate?"* is the product statement, in its speaker notes: vanilla `apply` walks a task list and checks it off, **nothing enforces a gate — the gate only exists because a team builds one.** And the accompanying coverage audit diagnoses every phase stuck at rung 3 the same way: *held there by missing oracles, not missing tools.*

**Specloop is that third rung, prefabricated.** The mapping is close to one-to-one, which is why the frame is adopted rather than invented:

| Advanced level needs | Specloop ships |
|---|---|
| a subagent that runs the recipe unattended | `agents/tdd-implementer.md` |
| a gate — a required checkpoint | `.gates.yaml`, abstract gate names |
| an oracle — the machine-readable verdict | the exit code, and only the exit code |
| a hook — what makes the gate non-optional | `harden-unattended-loop`'s `PreToolUse` / `Stop` hooks |
| Code review → close | `convention-review`, surfaces, rule-ids |
| Release → close | `live-check`, blocking |

**The two owned jobs, restated on the ladder:**

- **Climb** — get a team from rookie to advanced without building the machinery themselves: onboarding, `gates-init`, workflow packs, pack inspection.
- **Close** — supply the gate, oracle and hook that turn `act` into `close`: the loop, the subagents, the enforcement.

These are the same two surfaces this design already owned — enforcement and onboarding — in language a reader has already been taught. The ladder also states the limit honestly, which a positioning statement rarely does: Requirements never moves, System design reaches `act` and stops, because neither has a machine-readable verdict. Specloop should claim four closed phases, not six.

This relates to but does not replace the six-stage organisational ladder in `docs/specloop-map.html`: rung 4 on a phase is *how* a team reaches Stage 5, and the deck's final checkpoint says so directly.

Stated in one line for the manifests, where a ladder does not fit: **Specloop is the enforcement and onboarding layer for OpenSpec.** Three things it provides are not expressible upstream today:

- **stack binding** — `behaviour-driven` hard-codes Cucumber.js, `gherkin-lint` and an `acceptance-tests/` directory into instruction prose precisely because no schema can name a gate abstractly;
- **enforcement** — upstream gates are prose a model can skip silently, versus marker-backed `PreToolUse` denial;
- **the closed loop itself** — nothing upstream carries `tasks.md` to verified-on-main unattended, resumably, with a parseable report.

Plus the fourth that D9 promotes: **onboarding**, getting a project from zero to a first green loop.

A "wrapper" framing would argue against the enforcement hooks, the ledger, and the gates — the only parts that are genuinely ours. Note that `/opsx:apply` and `/specloop:tdd-apply` are not the same thing and their name collision is misleading: upstream's walks a task list; ours runs red → green → `ci` → convention-review → atomic commit per task under hook enforcement. The overlap is the task cursor.

### D4: One conventions source, generated into `config.yaml`
The current `rules: conventions: |` block is **verified broken** — `openspec new change` prints *"Rules for 'conventions' must be an array of strings, ignoring this artifact's rules"*. The upstream documented shape is a mapping keyed by artifact id whose values are arrays of strings:

```yaml
rules:
  proposal:
    - Maximum of 250 words
  specs:
    - Use Given/When/Then format
```

The block has two defects — a key that is not an artifact id, and a shape (multi-line prose with `### id` headers) that is not an array of strings — and a third that caused them. **One file is serving two consumers with incompatible needs:**

```
openspec/config.yaml
  rules:  proposal: [...]  specs: [...]  ← consumer 1: OpenSpec artifact steps  (broken)
  <rule-id prose>                        ← consumer 2: rule resolution → convention-review
```

An earlier revision proposed re-keying in place and leaving both blocks in the same file. **Superseded: the conventions get their own source file, and `config.yaml` is generated from it.**

```
conventions/rules.md          ← the source. `### <rule-id>` + prose. One artifact, one format.
      │
      ├──► rule resolution ──► convention-review        (reads the prose, cites the id)
      └──► gates conventions sync ──► openspec/config.yaml  rules: keyed by artifact id
```

Each `### <rule-id>` section carries an **`Applies to:`** line naming the artifact steps it constrains (`proposal`, `specs`, `design`, `tasks`) or `code` for review-only rules, plus a one-line imperative statement of the rule. The generator collects those statements into arrays under each artifact id; `code`-only rules are never emitted, because OpenSpec has no step to deliver them to.

Four reasons this beats re-keying in place:

1. **Two hand-maintained copies drift, silently.** The defect being fixed here was itself silent for the whole life of the repository. Fixing it by creating a second place to keep the same content in sync would be a strange conclusion to draw from that.
2. **The consumers need different *shapes* of one content, not different content.** The review gate wants addressable prose with stable ids and an argument in it; the artifact step wants a short imperative string. That is a rendering difference, and rendering is what a generator is for.
3. **`config.yaml` is not ours to squat in.** It is OpenSpec's project config and — as the adoption talk teaches it — the project's *constitution*. Writing a second, differently-shaped document into it makes the file harder to read for the audience upstream intends.
4. **It turns conventions into an onboarding deliverable.** A new project gets a rules file with the shipped rules already in it and a command that installs them into their config, rather than being told to hand-write YAML. That is the *climb* job from D3.

Generation must be **checkable or it will not be run**: `gates validate` fails loudly when `config.yaml`'s `rules:` do not match what the source would generate, per `fail-loud-gates`. And the same command works on an adopter's project, not only this repo — the source file is the input, their `config.yaml` is the target.

Deleting the block outright to satisfy the CLI remains the one unacceptable option: it would silently disable the convention-review gate, the more damaging of the two failures.

### D4a: Document why rule-ids exist at all
Rule-ids are not self-explaining, and the reason for them has lived only in the heads of the people who chose them. Written down, because the alternative — inline rule prose at each call site — looks simpler and will be proposed again:

- **A finding becomes checkable.** "Violates `zero-dep-shim`" sends a reader to one paragraph with a stable name. "This adds a dependency" sends them to an argument.
- **A surface can select a subset.** `surfaces[].rules` names ids, so a diff touching one area pulls only that area's rules. This is what keeps `convention-review` under ~10 tool calls; without ids the agent reads every rule on every diff.
- **A dangling reference is detectable.** `gates validate` fails loudly when a surface names an id the rules-doc does not define. Inline prose has no referent to dangle, and therefore no way to catch a rule that was deleted while still being relied on.
- **One source can be rendered for two consumers.** Ids give the generator in D4 something to key on, so the review gate and the artifact steps are fed from one document instead of two copies in two formats.

This goes in the rules-doc itself, so the mechanism explains itself at the point of use.

### D5: Ship the memo as a repository document
`docs/specloop-map.html` records the two-axis model, the two gate families, the ladder scoring, and an errata list. It is the reasoning behind the boundary; the README states the boundary, the memo explains why it is there.

### D6: Authoring gates are ours — but the mechanism, not the judgement
There are two gate families. Execution gates run on code (`ci`, convention-review, `verify`, `live-check`); authoring gates run on artifacts before code exists (is the intent clear, is it too large to review, does it contradict an existing capability, has a human approved it). Specloop has only the second family. **Decision: the authoring family is ours.**

**For:**

- **Symmetry with no new machinery.** An authoring gate is a gate whose subject is an artifact instead of a binary. `run <gate>` already reads nothing but an exit code, so it does not care which.
- **The failure lands where we operate.** Upstream names the risk — *"vibe specifying"*, auto-approving generated specs without real review, on the heuristic *"if you cannot reasonably review it, it's too large"*. Unattended, nobody is reviewing the proposal either. This is our operating condition, not theirs.
- **We are already in this business as of this change.** The approval requirement (D7) *is* an authoring gate. The question is no longer whether to have one, only whether to admit it.
- **Enforcement is the differentiator, again.** Upstream's authoring gates are skills and prose a model can skip silently. Ours would be hook-enforced, exactly as with commit and merge.
- **Packs multiply artifacts.** Every pack adds unreviewed surface; with no authoring gate, breadth makes the problem worse.
- **One measurement story.** Authoring-gate outcomes land in the same ledger, making intent quality and execution quality comparable.

**Against:**

- **It brushes against the rejection test.** A gate does not *author* an artifact, but it does opine on artifact content, and that drifts toward owning the workflow.
- **Upstream already has the judgements** — grill-me, adversarial multi-model review, glossary, cross-feature analysis. Rebuilding them repeats the mistake this change exists to correct.
- **Subjective blocking is riskier than an exit code.** A false "your spec is too vague" halts an unattended run with no mechanical remedy, unlike a failing test.
- **Adversarial review costs a second model call per artifact** — real money, and unattended it cannot be waved through by a human.
- **Quality of intent is domain-specific.** A generic largeness check risks being noise in one repo and useless in another.
- **It doubles the product surface** at the moment we deliberately narrowed it.

**Resolution — own the mechanism, delegate the judgement.** This is exactly the gates/surfaces split applied one level up: Specloop defines the authoring-gate *class*, the point at which it blocks, and its enforcement; the adopter binds it to a command, which may well be an upstream skill. `run <artifact-gate>` where the binding is someone else's reviewer keeps every "for" and neutralises the first four "against" — we do not rebuild grill-me, we make it blocking. Building it is a **later change**; this one only records that the door is open and on what terms.

### D7: Approval lives in `.openspec.yaml`, not in artifact prose
Every change must record who approved its plan and when, so authorship and approval are traceable without reading PR history.

The obvious implementation — edit the templates to add an `Approved by:` section — would mean forking upstream schemas and carrying them, which D2 forbids. An earlier revision of this design therefore proposed delivering the requirement as an artifact **rule**, producing a prose section in each generated file. That is superseded: the record belongs in the change's metadata file.

```yaml
# openspec/changes/<name>/.openspec.yaml
schema: spec-driven
created: 2026-08-04
approved_by: <github-login>
approved_at: <date>
approved_sha: <tree hash of the artifacts at approval>
```

**Verified**: OpenSpec tolerates unknown keys in `.openspec.yaml`. A change carrying `approved_by`, `approved_at` and `approved_sha` passes `openspec validate --strict`, and `openspec status --json` / `openspec instructions --json` are unaffected. They are not echoed back in that JSON, so a consumer reads the file directly — trivial, and the shim already has a minimal YAML parser for exactly this class of file.

Three reasons this beats a per-artifact prose section:

1. **Machine-readable.** A hook parses YAML rather than regexing markdown for a heading whose formatting the generating model controls.
2. **One place.** "Every artifact except `tasks.md`" needs no per-artifact rule — and `tasks.md` genuinely is the exception, since it is derived from proposal, design and specs rather than independently agreed.
3. **It can carry a tree hash.** This closes a hole the prose form cannot: approve a proposal, then edit it, and an `Approved by:` line sits there still looking true. `approved_sha` pins the approval to the exact content that was approved, so a post-approval edit is detectable.

Metadata travels with the *change*, not the schema — so this works with any upstream schema, present or future, without a fork. The matching **enforcement** (implementation may not begin until the plan is on `main` and carries a valid approval) is specified in `harden-unattended-loop`, which also decides how the fields get populated — attested from the merging pull request rather than typed by the model.

### D8: The gate-binding seam is renamed to `gates` (resolving the open question)
The previous revision recorded the three-way "harness" collision as an open question, leaning toward `bin/specloop` + `.specloop.yaml`. **Resolved: `bin/gates` + `.gates.yaml`.**

`.specloop.yaml` would have reproduced the original error in a new word — naming a configuration file after the project rather than after what it configures. The file *is* a gate table, `gates` is already the core noun in every shipped prompt and in the manifest schema, and it has no collision anywhere in the OpenSpec ecosystem. The objection — losing the product-name link — is answered by the `/specloop:*` command namespace and `.specloop/runs/`, which already carry the brand.

The rename is executed by `rename-to-gates`, sequenced **before** `harden-unattended-loop` so the enforcement change is not written against a name that is about to move. This change records the decision and writes the docs in the resulting vocabulary.

### D9: Onboarding is an owned surface, not a mitigation
The previous revision mentioned onboarding only in Risks, as something that offsets a narrower description. That is backwards, and it understates the thing most likely to determine whether anyone adopts this at all: **setup friction is what stops teams from getting onto a spec-driven workflow**, on both brownfield and greenfield projects.

Onboarding passes the rejection test on the fourth question — *gets a team running faster* — with no ambiguity. It is one of exactly two rows that answer "ours", and D3 names it the **climb** job: moving a team up the ladder without making them build the machinery. So it is stated as an owned surface alongside enforcement, and the docs give it equal billing rather than treating it as an apology for scope.

Concretely, the onboarding command owns the whole distance from an empty project to a first green loop: verifying OpenSpec and its Claude Code integration are installed (`unfork-commands` D3), helping select and install a workflow schema (`workflow-packs`), detecting the task runner, writing the gate manifest, and stubbing the gates and conventions source it references. Each of those is a place a team currently stalls.

### D10: Adopt gate / oracle / hook as the shipped vocabulary
Specloop's docs say "gate" and "exit code" and assert the contract without ever arguing for it. The adoption talk names three things, and the middle one is the word we are missing:

- **Gate** — a required checkpoint a change must pass.
- **Oracle** — the machine-readable verdict the gate reads back. An exit code, not a human's memory of having checked.
- **Hook** — what runs the gate automatically, so it is not optional.

"Oracle" is worth adopting because it names *why* the gate contract is an exit code and nothing else, which is currently an unexplained constraint that reads like fussiness. It also gives the coverage audit's diagnosis — phases *"held at rung 3 by missing oracles, not missing tools"* — a name inside our own docs, and it is already the word `workflow-packs` reaches for when it calls the failing reproduction the bugfix pack's oracle.

The vocabulary is documentation, not a rename: `.gates.yaml` still declares gates, because a gate is what you declare and an oracle is what it returns.

## Risks / Trade-offs

- **A narrower description reads as a smaller product** → mitigated by leading with what it *closes* rather than what it omits, and by D9's promotion of onboarding to a stated owned surface rather than a footnote.
- **Upstream schemas evolve independently** → we adopt selection, not vendoring, so a schema change is an upstream release rather than our breakage. The known cost is that installed schemas have no versioning or update path anywhere in the ecosystem; `workflow-packs` D6 accepts this deliberately, on the grounds that the whole ecosystem accepts it.
- **The rejection test could be applied too bluntly** → it arbitrates *ownership*, not value. "Not ours" means it belongs upstream or in the project, never that it is a bad idea.
- **Moving the conventions could silently disable convention-review** → the spec requires both consumers to keep working, validation must still fail loudly on a dangling rule-id, and the generated block must be checked against its source rather than trusted.
- **A generator nobody runs is worse than no generator** → `gates validate` fails when `config.yaml` has drifted from the conventions source, so staleness is a loud error rather than a quiet divergence.
- **The ladder is a frame an external reader has not met** → the docs state the rungs before using them, exactly as the source model does, and the memo carries the full version. A frame that needs a glossary in the README is still better than a claim with no unit of measure.
- **Three prerequisite changes now sit in front of this one's docs work** (`unfork-commands`, `rename-to-gates`) → accepted, and it is the correct order: writing the reader-facing docs before the command set and the file names settle would mean writing them twice.

## Open Questions

- ~~**What do we call the gate-binding seam?**~~ — **RESOLVED (D8)**: `gates`. Executed by `rename-to-gates`.
- ~~**Does `.openspec.yaml` tolerate extra keys?**~~ — **RESOLVED (D7)**: yes; verified against `openspec validate --strict`, `status --json` and `instructions --json`.
- ~~**Should the rules-doc stay inside `openspec/config.yaml`?**~~ — **RESOLVED (D4)**: no. The conventions move to their own source file; `config.yaml`'s `rules:` block is generated from it and checked for drift by `gates validate`.
- **Where does the conventions source live — `conventions/rules.md`, `docs/conventions.md`, or `.specloop/rules.md`?** The decision that matters (one source, generated output) is settled; the path is not, and it should be chosen alongside the open question in `rename-to-gates` about whether `.gates.yaml` stays at the repo root or moves under `.specloop/`. Both are "where do the plugin's owned files live", and answering them separately is how a layout becomes inconsistent.
