## Context

The scaffold change (PR specloop PR 1) built Specloop's command set by copying OpenSpec's Claude Code commands and renaming the namespace. At the time this looked like packaging: a single plugin offering one coherent set of `/specloop:*` commands.

Investigation for `reposition-specloop` established that the artifact-authoring half of the workflow is upstream's and maintained there. Verifying that against the shipped files showed the overlap is not conceptual but literal — the files are copies, and they have drifted behind their originals.

## Goals / Non-Goals

**Goals:** stop shadowing maintained upstream assets; recover the upstream features the fork lost; make the boundary true in code, not only in prose; leave the loop untouched.

**Non-Goals:** changing the loop, the gates, enforcement, or the shim; renaming `harness`; re-exporting upstream commands under our namespace.

## Decisions

### D1: Delete, do not wrap
Three options were available for each forked command:

| Option | Effect |
|---|---|
| **(a) Keep the fork** | permanent divergence; every upstream fix must be manually mirrored |
| **(b) Wrap** — `/specloop:propose` delegates to `/opsx:propose` | preserves our namespace, but adds an indirection that must itself be maintained, and still shadows the name in the user's command palette |
| **(c) Delete and point** | zero maintenance; users get upstream's current version; one-time migration cost |

**Chosen: (c).** (b) is tempting because it preserves a tidy single-namespace story, but the story is the thing that caused the fork. A wrapper is a fork with an extra file: it still has to track upstream's arguments, its `--store` flag, its status-JSON fields. The only version of "defer to upstream" that stays deferred is the one with no file in it.

The migration cost is a real cost and it is paid by the one project using Specloop today. It never gets cheaper.

### D2: Ours is what has no upstream equivalent
Applying the rejection test to each shipped command gives a determinate answer, which is the test working as intended:

| Command | Authors an artifact? | Upstream equivalent | Verdict |
|---|---|---|---|
| `explore` | yes | `/opsx:explore` | **delete** |
| `propose` | yes | `/opsx:propose` | **delete** |
| `archive` | yes | `/opsx:archive` | **delete** |
| `harness-init` | no — binds gates to commands | none | **keep** |
| `start` | no — reports live state | none | **keep** |
| `tdd-apply` (skill) | no — runs a gated loop | `/opsx:apply` is *not* equivalent | **keep** |

`/opsx:apply` deserves the explicit note because the names collide and the functions do not. Upstream's `apply` walks a task list. `tdd-apply` runs red → green → `ci` → convention-review → atomic commit per task, then `verify` → `live-check` → merge, and under `harden-unattended-loop` those steps become hook-enforced. The overlap is the task cursor; everything Specloop exists for is the part upstream's `apply` does not do.

### D3: The upstream command surface becomes a checked prerequisite
Deleting our copies means the adopter must have run `openspec init --tools claude`. Today that is assumed; after this change it is load-bearing, because without it the workflow has no entry point at all.

`README.md` already names OpenSpec as a prerequisite, but a README sentence is exactly the class of guarantee this project exists to stop trusting. So `/specloop:harness-init` gains a preflight: check `.claude/commands/opsx/` exists, and offer to run `openspec init --tools claude` if not. Consistent with the existing preflight that already checks `openspec list --json` succeeds.

### D4: Replace `namespaced-refs` with `no-forked-upstream-assets`
The current rule reads:

> Internal command/skill cross-references use the `/specloop:` namespace, never the legacy `/opsx:` prefix.

Both halves are wrong. `/opsx:` is current, not legacy; and mandating our namespace for *every* reference is what made the fork feel correct. The replacement inverts it and generalises past commands, since the same pressure will recur with skills and templates once `workflow-packs` starts installing schemas:

> **no-forked-upstream-assets** — Specloop MUST NOT ship a command, skill, or template that shadows an asset maintained upstream by OpenSpec or a community schema. Artifact-authoring references point at `/opsx:*`; the `/specloop:*` namespace is reserved for assets with no upstream equivalent.

This keeps a rule-id in the position the old one occupied, so `harness rules` and any surface referencing it keep resolving.

### D5: The README diagram shows the seam
The current diagram presents one continuous `/specloop:*` pipeline, which is the visual form of the claim this change retracts. The replacement marks the handoff explicitly:

```
   UPSTREAM (OpenSpec)                │  SPECLOOP
   ───────────────────────────────────┼──────────────────────────────────
   /opsx:explore   think              │
   /opsx:propose   proposal+specs     │
                   +design+tasks      │
                                      │  /specloop:tdd-apply
                                      │    red → green → ci → review
                                      │    → atomic commit, per task
                                      │  verify → live-check → merge
   /opsx:archive   promote specs      │
```

A reader can now see what they get from each side, which is the whole point of `reposition-specloop` and is better carried by a diagram than a paragraph.

### D6: Adopters who customised the opsx commands get a supported surface, not a rescue
Deleting our copies raises a question about someone else's files: an adopter who hand-edited `.claude/commands/opsx/propose.md` holds a generated file with local changes and no merge story, which `openspec update` may overwrite. Three things are true about that, and only the second is ours to act on.

**It is not a problem this change creates.** The exposure comes from `openspec init` generating files into a repository, and it exists identically today, before Specloop touches anything. After this change Specloop holds no file in that directory at all.

**The customisation almost always has a supported home, and it is not a command file.** OpenSpec already ships the right lever: `openspec schema fork <source> <name>` copies a schema into `openspec/schemas/<name>/` as an independent local schema, leaving the original alone, and `config.yaml` then names the fork. Most "I edited `propose.md`" is really "I wanted different artifacts, or different instructions" — which is a schema concern. A fork survives `openspec update` by construction, because it is the adopter's own file rather than a regenerated one. So the documentation states the lever: **customise the schema, not the command.**

**Detect rather than defend.** D3's preflight already checks that `.claude/commands/opsx/` exists. It can also notice the commands are present-but-modified and say so once, before anything runs — so a clobber becomes a risk the adopter accepted rather than one they discovered afterwards. That is the whole of the mitigation, and it is deliberately not more.

What we do *not* do is vendor the commands back to protect local edits. That is the fork this change deletes, re-created with a more sympathetic justification. The residual case — a customisation that genuinely cannot be expressed as a schema fork — is a gap in upstream's extension surface and belongs in an issue there.

### D7: `archive` is kept as a thin composition — D1 revised for one command
The delta audit found two behaviours upstream does not have. Their disposition differs
because one is a guarantee and the other is a prompt at the wrong moment.

**The archive commit is kept, as a delegating command.** `/specloop:archive` runs
upstream's archive and then commits the move, failing loudly if the commit fails. This
is the wrap option D1 rejected, and the decision to take it here is deliberate: the
behaviour is a *stated guarantee made enforceable* — the third question of the rejection
test, and an unambiguous **ours**. Upstream's archive leaves the working tree dirty; a
loop that ends "verified on main" cannot end with an uncommitted move.

D1's argument against wrapping still holds and is now a cost we carry: the wrapper must
track upstream's arguments, and the name occupies `/specloop:archive` next to
`/opsx:archive` in the palette. Two constraints keep that cost bounded:

- **The wrapper holds no copy of upstream's prompt.** It delegates and adds one step. If
  it ever grows a second — re-implementing a status check, a spec-sync prompt, a path
  derivation — it has become a fork again and must be re-deleted.
- **It is a placeholder for enforcement, not the final form.** `harden-unattended-loop`
  makes guarantees marker-backed rather than prompt-backed; the archive commit belongs
  there, at which point this command loses its reason to exist. An upstream issue asking
  for a commit affordance is the other exit.

`explore` and `propose` are deleted outright, as D1 decided — neither carries a guarantee.

**The propose handoff moves to the session brief.** The "offer two implementation paths,
and wait for spec approval" prompt is not a guarantee, it is a menu, and a menu tied to
the end of `propose` only fires if you just ran `propose`. `hooks/_session_brief.py` is
grounded in live OpenSpec state, so it can offer the same choice whenever a change is
apply-ready — a strictly better home. Task 5.3 carries it.

## Risks / Trade-offs

- **Users lose muscle memory for `/specloop:propose`** → real but small at one adopting project; a `README` migration note covers it. Deferring makes it worse, not better.
- **Upstream could change `/opsx:` naming or drop the Claude Code integration** → then we are in the same position as every other consumer of it, and can re-evaluate with a maintained upstream to diff against. Strictly better than silently diverging now.
- **Two namespaces in one workflow reads as less polished** → accepted, and arguably honest: it shows the user exactly which project maintains which half, and where to file a bug.
- **`harness-init` grows a second responsibility** (prerequisite installation) → bounded, and it is already the onboarding command; `reposition-specloop` promotes onboarding to a first-class owned surface, so this is on-boundary rather than scope creep.

## Delta audit (task 1.2, recorded 2026-08-07)

Baseline: `openspec init --tools claude` at CLI **v1.6.0** in a throwaway repo, installing
`.claude/commands/opsx/{apply,archive,explore,propose,sync}.md` and
`.claude/skills/openspec-{apply,archive,explore,propose,sync}-*/SKILL.md`.

Every delta between our three forked commands and their upstream counterparts, classified:

| File | Delta | Class |
|---|---|---|
| all three | frontmatter `name:` `"OPSX: …"` → `"Specloop: …"`; `/opsx:` → `/specloop:` in prose | rename (fork artifact) |
| all three | `allowed-tools: Bash(openspec:*)` dropped | staleness — widens tool surface past upstream's intent |
| all three | `--store` selection paragraph dropped | staleness |
| all three | `planningHome` / `changeRoot` / `artifactPaths` / `actionContext` guidance dropped; paths hard-coded to `openspec/changes/<name>/` | staleness |
| `explore`, `propose` | `model: opus` added to frontmatter | tuning — not artifact behaviour |
| `explore` | ASCII diagram box and insight table re-indented | cosmetic regression |
| `propose` | `resolvedOutputPath` → `outputPath` | staleness |
| `propose` | completion prompt replaced: offers **two implementation paths** (`/specloop:tdd-apply` interactive, or spawn the `tdd-implementer` subagent) and **waits for the user to approve the specs** before either | **intentional improvement** |
| `archive` | new step 6 **"Commit the archive"** — `git add` + `git commit -m "archive change: <name>"`, and stop loudly if the commit fails | **intentional improvement** |

**Result: the proposal's premise is falsified.** Its non-goal says "the fork's deltas are
staleness, not improvements; there is nothing to send back." Two deltas are genuine
behaviour upstream does not have, verified against the CLI: `openspec archive --help`
exposes no commit behaviour, and neither upstream command mentions git or a loop handoff.
Deleting the files as-is would silently drop both. Task 1.3's HALT condition is met — see
D7 for the disposition.

## Open Questions

- ~~**What can we do about adopters who customised the opsx commands?**~~ — **RESOLVED (D6)**: point them at `openspec schema fork` as the supported customisation surface, and have the preflight warn when the generated commands are modified. ~~Whether `openspec update` actually clobbers them is still worth confirming before the migration note recommends running it~~ — **confirmed at v1.6.0 (task 6.6)**: plain `openspec update` compares only the `generatedBy` version stamped in the generated skills' frontmatter, so at a matching version it is a no-op and local edits survive; `openspec update --force` regenerates in place with no backup and no prompt, and a version bump takes the same path. So the exposure is real but latent — the warning should say edits are lost on `--force` or at the next version bump, not that any update clobbers them.
- **Should `start.md`'s menu offer `/opsx:` entries directly, or describe them?** A slash command inside another command's prompt is a suggestion to the model, not a link — the brief may read better naming them as text.
