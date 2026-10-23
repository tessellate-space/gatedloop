## Why

The word "harness" denotes three different things in this system, and ours is the odd one out:

| Term | Means | Whose |
|---|---|---|
| agentic harness | the execution environment — Claude Code, OpenCode | industry usage |
| **intent harness** | *"the layer that transforms raw ideas into structured, durable instructions the agent can act on"* — schemas, spec discipline, articulation | upstream (intent-driven.dev) |
| `bin/harness`, `.harness.yaml` | binds abstract gate names to this project's real commands | **ours** |

The collision is not just an overloaded word. Ours names the **most concrete, execution-facing** thing in the system, while the established meaning is the **most abstract** layer. A reader arriving from the OpenSpec corpus opens `.harness.yaml` expecting proposal-quality configuration and finds test commands. Precisely inverted.

The name is a leftover: it came from an internal audit doc that called the whole dev-workflow setup "the harness", and it survived the rename of the plugin itself to Specloop. It was recorded as an open question in `reposition-specloop`; this change closes it.

**"Gates" is what the thing actually is.** The file is a gate table. `gates` is already the core noun in every shipped prompt, in `harness.schema.json`'s vocabulary, in the gate contract table in `CLAUDE.md`, and in the two gate families (execution and authoring) that `reposition-specloop` D6 defines. Renaming to it removes a collision and adds a description, at the cost of the link to the product name — which the plugin namespace (`/specloop:*`) already carries.

**Timing is the argument for doing it now.** The migration cost is bounded only while adoption is one project that has not migrated yet. The window closes the moment anyone else installs. And `harden-unattended-loop` adds substantial new surface to this shim (`harness gate-marker check`, ledger writes, four new hook scripts) — renaming after it means renaming twice as much.

## What Changes

- **Rename the shim**: `bin/harness` → `bin/gates`. Every subcommand keeps its name: `gates validate`, `gates run <gate>`, `gates surfaces`, `gates rules`, `gates init`.
- **Rename the manifest**: `.harness.yaml` → `.gates.yaml`, and `schema/harness.schema.json` → `schema/gates.schema.json`.
- **Rename the manifest's version key**: `harnessVersion: 1` → `gatesVersion: 1`.
- **Rename the onboarding command**: `/specloop:harness-init` → `/specloop:gates-init`, and `templates/harness.yaml.template` → `templates/gates.yaml.template`.
- **Ship a deprecation shim for one release.** `bin/harness` remains as a thin forwarder that prints a deprecation notice to stderr and execs `bin/gates`; `gates validate` accepts a `.harness.yaml` with a loud warning naming the new filename. Both are removed in a later change.
- **Update every reference.** Shipped prompts (`skills/`, `agents/`, `commands/`), hooks, `README.md`, `SETUP.md`, `CLAUDE.md`, `AUTOMATION.md`, the rules-doc, and the in-flight change artifacts that name `harness run`.

## Capabilities

### New Capabilities
- `gate-binding`: the seam that binds abstract gate names to a project's real commands is named for what it does, with a bounded deprecation path off the old name.

### Modified Capabilities
- `manifest-parsing`: the "shipped starter template validates unmodified" requirement's `harness validate` / `/specloop:harness-init` wording is renamed to `gates validate` / `/specloop:gates-init`; no behavior changes.
- `command-surface`: the "conventions rules-doc forbids future forks" requirement's `harness rules` wording is renamed to `gates rules`; no behavior changes.

## Impact

- **Files renamed**: `bin/harness`, `.harness.yaml` (in adopting projects), `schema/harness.schema.json`, `templates/harness.yaml.template`, `commands/harness-init.md`.
- **BREAKING for adopters**: the manifest filename and the command name both change. Mitigated by the one-release forwarder and the warning path, so no adopter breaks silently — they get a message naming exactly what to rename.
- **PATH surface**: in an installed plugin `bin/` is on the Bash tool's PATH, so adopters type `gates …`. Both names resolve during the deprecation window.
- **Ordering**: this should land **before** `harden-unattended-loop`, which otherwise adds marker/ledger surface under the old name and doubles the rename.
- **No behaviour change.** Exit codes, gate semantics, surface selection, and the hot-set computation are untouched.

## Non-goals

- **Changing gate semantics or the manifest schema's shape.** Only names change; the required/optional gate contract, `surfaces[]`, and the hot-set rule are identical.
- **Renaming the plugin.** Specloop stays Specloop; `/specloop:*` remains the command namespace.
- **Renaming `.specloop/runs/`.** The ledger already sits in the plugin's own namespace and has no collision.
- **Keeping the deprecation forwarder indefinitely.** It exists for one release and its removal is a named follow-up, not an open-ended compatibility promise.
