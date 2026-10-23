## Context

`reposition-specloop` recorded the three-way "harness" collision as an open question with a leaning toward `bin/specloop` + `.specloop.yaml`, and deferred the decision on the grounds that renaming a shipped contract is its own change. This is that change, and the decision landed differently from the leaning.

## Goals / Non-Goals

**Goals:** remove the collision with the two established meanings of "harness"; name the seam for what it does; migrate without breaking the one adopting project silently; land before the enforcement change enlarges the surface.

**Non-Goals:** any semantic change to gates, surfaces, or the hot set; renaming the plugin; an open-ended compatibility layer.

## Decisions

### D1: `gates`, not `specloop`, not `contract`
Three candidates were on the table:

| Candidate | For | Against |
|---|---|---|
| `.specloop.yaml` + `bin/specloop` | self-consistent; `.specloop/runs/` already claims the namespace | says nothing about what the file *is*; a reader still has to open it to find out |
| **`.gates.yaml` + `bin/gates`** | the file **is** a gate table; `gates` is already the core noun in every prompt and in the schema; zero collision in the OpenSpec ecosystem | loses the link to the product name |
| `.contract.yaml` | matches the "gate contract" language already in `CLAUDE.md` | vaguer — a contract of what? |

**Chosen: `gates`.** The objection to it — losing the product-name link — is answered by the `/specloop:*` command namespace and the `.specloop/runs/` ledger, both of which already carry the brand. A configuration file's job is to say what it configures, and `.specloop.yaml` would have reproduced the original error in a new word: naming the file after the project rather than the thing.

The collision turned out to be worse than a naming preference. The coverage audit cited in `reposition-specloop` D3 — a real artifact scoring a real project, written for exactly the audience this plugin is for — heads its metadata block with **`Harness: Claude Code`**. In material this plugin's own readers have already seen, "harness" means the agentic harness. Keeping the word for a gate table would not create ambiguity so much as inherit an established definition and then quietly disagree with it.

`gates` also covers the *intended* surface, not just the current one: `reposition-specloop` D6 splits gates into two families — execution gates that run on code, authoring gates that run on artifacts — and leaves the door open to the second. A file named for gates accommodates both. A file named for the harness accommodates whatever "harness" turns out to mean next year.

### D2: Rename the version key too, and use it as the format discriminator
`harnessVersion: 1` becomes `gatesVersion: 1`. Renaming the file while leaving a `harnessVersion` key inside it would leave the collision half-fixed in the place a reader looks second.

This also gives migration a free, unambiguous discriminator: the loader detects which key is present and therefore which vintage of manifest it is reading, with no filename sniffing and no version negotiation. A manifest carrying `harnessVersion` is old and gets the warning; one carrying `gatesVersion` is current.

### D3: Deprecate loudly for exactly one release, then delete
The alternatives were a hard break (rename and let it fail) and indefinite dual support.

A hard break is defensible at one adopter but produces a `command not found` — the least informative possible failure, and it violates `fail-loud-gates`, which requires an explicit message rather than a bare non-zero exit. Indefinite dual support means the collision never actually goes away; a reader still finds `.harness.yaml` in real projects and stays confused, which is the entire cost this change is paying to remove.

**Chosen: a forwarder with a stated expiry.** `bin/harness` becomes a few lines that print a deprecation notice to stderr and `exec` `bin/gates` with the same arguments; `gates validate` reads a `.harness.yaml` when no `.gates.yaml` exists, warns loudly, and names the new filename. Removal of both is a named follow-up change, not a vague intention — an unbounded shim is how the original name survived long enough to become a problem.

The forwarder must **not** be silent. A silent forwarder means the migration never happens and this change delivers a second name rather than a better one.

### D4: Rename before enforcement, not after
`harden-unattended-loop` adds `harness gate-marker check`, ledger writes at every `harness run` call site, and four hook scripts that shell out to the shim. Renaming after it lands means touching all of that twice, and the second pass is over hook scripts where a missed reference fails at runtime inside a `PreToolUse` handler — the worst place to discover a typo.

So the ordering is: `unfork-commands` → **`rename-to-gates`** → `reposition-specloop` → `harden-unattended-loop` → `workflow-packs`. `reposition-specloop` sits after the rename because it rewrites the reader-facing docs, and it should write them in the final vocabulary rather than write them twice.

### D5: The rename is mechanical, so verify it mechanically
The failure mode for a rename is a missed reference, and the highest-risk references are the ones inside prompt prose — a shipped skill that says `harness run ci` still *reads* correctly to a human reviewer while being wrong.

So completion is defined by a grep returning empty, not by review: after the change, `grep -rn '\bharness\b'` across the repo returns only (a) the deprecation forwarder, (b) the migration notes in README/SETUP, and (c) historical references in archived changes and the design memo. Any other hit is a defect. This is cheap enough to be a task rather than a gate.

## Risks / Trade-offs

- **A missed reference in a shipped prompt fails at the adopter's machine, not ours** → mitigated by D5's exhaustive grep and by the forwarder, which makes a missed `harness run` still work (loudly) rather than break.
- **The in-flight changes reference `harness run` throughout** → they are planning artifacts, so their references are updated as part of this change's task list; `reposition-specloop` and `harden-unattended-loop` are re-read afterwards to confirm.
- **"Gates" could be read as CI-only** → the two-family framing (execution + authoring) is documented in `reposition-specloop` D6 and restated in SETUP, so the broader meaning is stated where an adopter meets it.
- **Two renames in flight at once** (this and `unfork-commands`) → they touch disjoint surfaces: `unfork-commands` removes `commands/*.md`, this one renames `bin/`, `schema/`, `templates/` and the manifest. The only overlap is `commands/harness-init.md`, which one edits and the other renames — sequenced, not merged.

## Open Questions

- **Does the plugin's `bin/` PATH injection pick up a renamed file automatically**, or is the binary name recorded anywhere in `.claude-plugin/plugin.json`? Verify before relying on `gates` resolving on PATH.
- **Should `gates init` keep writing `.gates.yaml` at the repo root**, or move to `.specloop/gates.yaml` alongside the ledger? Root is more discoverable; `.specloop/` is tidier and groups the plugin's two owned files. Not urgent — the rename is orthogonal to the location, and moving later is a one-line loader change.
- **When exactly does the forwarder get deleted?** Proposal says "one release"; the follow-up change should be created at the same time as this one lands so the expiry has a ticket rather than a memory.
