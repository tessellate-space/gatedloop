# gatedloop conventions

Convention rules for gatedloop's own code. Each `### <rule-id>` is a stable
rule-id that a surface (in `.gates.yaml`) can reference and a review finding
can cite.

This is the **single source** for rule-id prose. It has two consumers that
need different *shapes* of the same content, not different content: the
`convention-review` agent resolves ids from here directly via the `gates`
shim (`.gates.yaml`'s `conventions.rules-doc` points here); `openspec/config.yaml`'s
`rules:` block is *generated* from here by `gates conventions sync`, keyed by
artifact id, for OpenSpec's own artifact-instruction consumer. Run `gates
conventions sync` after editing this file, and `gates validate` fails loudly
if the generated block drifts from this source.

Each rule section has two required metadata lines right after the heading:
- `Applies to: <artifact-id>[, <artifact-id> ...]` — the active schema's
  artifact ids (e.g. `proposal`, `specs`, `design`, `tasks`) this rule
  constrains at authoring time, or `code` for a review-only rule with no
  artifact-authoring counterpart, or `tests` for a review-only rule about the
  project's tests (`gates rules` lists it for every diff, and `gates tests
  brief` hands it to the test author). Artifact ids are **not a fixed set** — they
  come from whichever schema `openspec/config.yaml`'s `schema:` names, and
  the shipped catalog's sets genuinely differ (`minimalist` has no
  `proposal`; `event-driven` adds `asyncapi`/`event-storming`/
  `event-modeling`; `intent-driven` and `spec-driven-with-adr` add `adr`).
  `gates conventions sync` resolves the active schema's ids at run time
  rather than hard-coding one set.
- `Rule: <one-line imperative statement>` — the exact string `gates
  conventions sync` emits into `config.yaml`'s `rules:` array for each
  artifact id named above. `code` and `tests` targets are never emitted —
  OpenSpec has no artifact step to deliver them to.

The prose paragraph(s) that follow are for the human/agent reader resolving
the id; the generator reads only the two metadata lines.

## Why rule-ids, not inline prose

A rule-id is a stable name a surface, a finding, or a generator can point
at instead of restating an argument. That indirection earns its keep four
ways:

- **A finding becomes checkable.** "Violates `zero-dep-shim`" sends a
  reader to one paragraph with a stable name. "This adds a dependency"
  sends them to an argument they have to re-litigate.
- **A surface can select a subset.** `.gates.yaml`'s `surfaces[].rules`
  names ids, so a diff touching one area pulls only that area's rules —
  this is what keeps `convention-review` under ~10 tool calls. Without ids
  the agent would have to read every rule on every diff.
- **A dangling reference is detectable.** `gates validate` fails loudly
  when a surface names an id this file doesn't define (`fail-loud-gates`).
  Inline prose has no referent to dangle, and therefore no way to catch a
  rule that was deleted while a surface still relied on it.
- **One source renders for two consumers.** Ids give `gates conventions
  sync` something to key on, so `convention-review` and OpenSpec's
  artifact steps are fed from this one file instead of two hand-maintained
  copies in two shapes — which is exactly the defect this file's
  existence fixes (`openspec/config.yaml`'s `rules:` block used to be one
  of those copies, in a shape the OpenSpec CLI rejected at runtime).

Inline prose (a bare string instead of a rule-id in a surface's `rules:`
list) stays a legitimate escape hatch for a project with no addressable
rules-doc. It just cannot do any of the four things above.

### stack-agnostic-prompts
Applies to: code
Rule: Never hard-code a project's test, build, or probe command in a shipped prompt — invoke it through `gates run <gate>`.

Shipped prompts, skills, and agents MUST NOT hard-code any project's test,
build, or probe commands. All such invocation goes through `gates run
<gate>`; convention rules and live-checks are selected per surface from the
adopter's `.gates.yaml`.

**Carve-out: naming a tool to offer it is not the same as naming it to invoke
it.** `commands/gates-init.md` cannot detect a project's build system without
naming one, and its curated detector list (`just`, `npm`, `make`, `cargo`, …)
names tools for exactly one purpose: to present them as candidates the
adopter confirms or declines, never to run them or write them into
`.gates.yaml` unconfirmed. That is compatible with this rule; a prompt that
invoked one of those tools directly, or wrote its name into a gate body
without the adopter's confirmation, would not be — invocation still goes
through `gates run <gate>`, without exception.

**The reviewer's test:** would this prompt still be correct in a project that
uses none of the named tools? If yes — every name is offered, the adopter
chooses, and an unlisted stack falls back to a hand-written gate — the prompt
is offering. If no — the prompt's own behavior depends on one of those tools
being present — it is binding, and it is a violation.

**Why the carve-out was needed, not just written down:** this rule was
authored as an absolute and read as one, while `commands/gates-init.md` and
`templates/gates.yaml.template` had named exactly these tool names since both
were written — a direct contradiction nobody caught, because
`openspec/config.yaml`'s `rules:` block silently failed to validate and
convention review had nothing to check the surface against (the defect
`reposition-gatedloop` fixed). The carve-out writes down what the rule was
actually protecting — no shipped prompt invokes a project-specific command
directly — so the same contradiction cannot recur silently.

No project-specific tool name may appear in a shipped prompt **except to
offer it under this carve-out**; `pytest`, `keycloak`, `shadcn`, `langfuse`,
… remain forbidden outright — nothing offers them as a curated onboarding
candidate.

### zero-dep-shim
Applies to: code
Rule: Keep `bin/gates` stdlib-only — never add a hard third-party runtime dependency.

`bin/gates` uses only the Python standard library. YAML parsing falls back
to the built-in minimal parser when PyYAML is absent; never introduce a hard
third-party runtime dependency.

### plugin-relative-paths
Applies to: code
Rule: Reference plugin-bundled files via `${CLAUDE_PLUGIN_ROOT}`, never a hard-coded absolute path or a `../` escape.

Hooks, commands, and scripts reference plugin-bundled files via
`${CLAUDE_PLUGIN_ROOT}` — never a hard-coded absolute path and never a `../`
escape (the plugin directory is copied to a cache on install, so external
paths won't resolve).

### no-forked-upstream-assets
Applies to: code
Rule: Ship no command, skill, or template that reproduces an asset OpenSpec or a community schema already maintains upstream.

gatedloop ships no command, skill, or template that reproduces an asset
maintained upstream by OpenSpec or by a community schema. Artifact-authoring
references point at `/opsx:*`; the `/gatedloop:*` namespace is reserved for
assets with no upstream equivalent.
A command MAY delegate to an upstream one in order to add a guarantee upstream
does not make, provided it holds no copy of the upstream prompt — one such
delegation exists (`commands/archive.md`, which adds the archive commit). A
delegation that grows a step reproducing upstream behaviour has become a fork
and this rule rejects it.

### commands-flat-skills-nested
Applies to: code
Rule: Keep commands as flat files under `commands/` and skills as `<name>/SKILL.md` under `skills/` — no redundant subdirectory namespace.

User commands are flat markdown files under `commands/`; skills are
`<name>/SKILL.md` directories under `skills/`. Do not reintroduce redundant
subdirectory namespaces (the plugin name is already the namespace).

### fail-loud-gates
Applies to: code
Rule: Fail validation and gate/marker checks loud, with a non-zero exit and an explicit message — never silently skip.

Manifest validation and marker/gate checks fail loud — a non-zero exit with an
explicit message. A missing required gate, a dangling rule-id, or an ungated
commit/merge is never silently skipped.

### self-contained-plugin
Applies to: code
Rule: Keep every runtime asset inside the plugin directory — never read from outside the plugin root.

Every asset a component needs at runtime lives inside the plugin directory.
No component reads from outside the plugin root (e.g. `~/.claude/`), and the
manifests keep `plugin.json` in `.claude-plugin/` with all other dirs at root.

### docs-follow-surface
Applies to: tasks, code
Rule: A change that adds, removes or alters an adopter-facing surface updates README.md and SETUP.md in the same change (and AUTOMATION.md when it changes enforcement).

An adopter learns gatedloop from README.md, SETUP.md and AUTOMATION.md, so a
change to what they use is not done until those files say so. An
adopter-facing surface is any of:

- a command, agent or skill;
- a `gates` subcommand or flag;
- a manifest key;
- a gate name;
- an exit code, or a hook's allow/deny behaviour.

A change touching one updates README.md and SETUP.md in the same change, and
AUTOMATION.md as well when it changes enforcement (a hook, a marker, a
denial). A plan carries that as a task; a task diff that adds, removes or
alters such a surface without the matching docs edit is a finding.

Internal refactors, tests and `openspec/` content are excluded: they change
nothing an adopter uses. This rule prevents drift per change; `scripts/release
docs` (run by `scripts/release cut`) catches the whole-set drift a per-change
rule misses.

### rejection-test
Applies to: proposal
Rule: Before proposing a new gatedloop capability, apply the rejection test — reject anything that only authors an artifact or only binds a stack command.

A positioning statement that only says what gatedloop *does* cannot settle a
scope argument; a test that a proposal has to pass can. Apply these four
questions to anything being proposed as a gatedloop capability:

| Question | Verdict | Where it belongs instead |
|---|---|---|
| Does it author an artifact (proposal, spec, design, ADR, …)? | not ours | an upstream OpenSpec schema |
| Does it know a stack command (a test runner, a linter, a framework)? | not ours | a gate in the adopter's `.gates.yaml` |
| Does it make a stated guarantee enforceable? | **ours** | — |
| Does it get a team running faster? | **ours** | — |

"Not ours" means the idea belongs upstream (OpenSpec, a community schema) or
in the adopting project's own configuration — never that it is a bad idea.
Ideas that pass the test but aren't scheduled belong in `docs/candidates.md`,
with the reason for waiting recorded next to the reason for wanting them.

**The four questions are instances of one.** Against the adoption ladder
(README.md, "Where gatedloop sits"): **does it move an SDLC phase from `act`
to `close`, or move a team up a rung faster?** Authoring an artifact is real
work, but it's a 0→3 move on the ladder — OpenSpec's, not gatedloop's. Naming
a stack command is a binding, and the adopter's. The four questions stay
because they're faster to apply at proposal-review speed; the single question
stays because it can be scored, and a scored test survives an argument a
checklist alone does not.

**Worked example, not a hypothetical.** The test's first real application was
against gatedloop's own shipped command set, and it produced an unwelcome
answer: `commands/explore.md`, `commands/propose.md`, and `commands/archive.md`
were renamed copies of OpenSpec's own commands. Applied to them, question one
rejects all three — they author artifacts, and upstream already maintains
better-kept originals. The copies had, in fact, already gone stale (missing
`--store`, the `planningHome`/`artifactPaths` fields, and `/opsx:sync`
entirely) — evidence the test would have caught the drift, not just the
duplication. `explore` and `propose` were deleted; `archive` was reduced to a
thin delegation that adds one guarantee upstream doesn't (it commits the
archive move) without holding a copy of the upstream prompt, which is the
`no-forked-upstream-assets` rule's own escape hatch. That the test rejected
work already shipped, rather than only hypothetical future work, is why it is
recorded here as a rule and not left as an argument to re-win each time.
