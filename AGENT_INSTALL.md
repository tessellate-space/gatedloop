# Agent install guide — gatedloop's workflow packs

Use this flow to install `bugfix` or `architecture` — the two OpenSpec workflow packs shipped in this plugin at `packs/` — into a target project, following the same install convention as the community schema catalog at <https://github.com/intent-driven-dev/openspec-schemas> (its own `AGENT_INSTALL.md` is the model this one follows). Inside a Claude Code session with gatedloop installed, the `workflow-select` skill runs this same procedure interactively and is the easier path (`/gatedloop:workflow-select`); this file exists so an agent with only a raw URL, or a project using gatedloop's packs without the rest of the plugin, can install them without that skill.

## Prerequisites

1. Run `openspec --version` in the target project. Confirm OpenSpec is installed and the CLI version is at least `1.0.0`.
2. If `openspec --version` fails, reports a version below `1.0.0`, or `openspec/config.yaml` is missing, stop and tell the user to install or upgrade OpenSpec and run `openspec init` first. Do not continue until these prerequisites are met.

## Step 1 — Get this repository

If you don't already have it locally:
```bash
git clone https://github.com/tessellate-space/gatedloop.git /tmp/gatedloop-packs
```
(If gatedloop is already installed as a plugin, its bundled files serve the same purpose — use `${CLAUDE_PLUGIN_ROOT}` as the source instead of cloning.)

## Step 2 — Select a pack

**If the user already named one** (`bugfix` or `architecture`), check it exists:
```bash
ls /tmp/gatedloop-packs/packs/<pack-name>
```
If it does not exist, fall through to the enumeration path below.

**If no pack was named**, list what's available and ask the user to pick exactly one:
```bash
ls /tmp/gatedloop-packs/packs/
```
| Pack | Flow | Use when |
|---|---|---|
| `bugfix` | `report → spec-delta → tasks` | The starting point is a failing reproduction, not a proposal |
| `architecture` | `explore → design → adr`, no `apply` | The work ends at an accepted decision, not code |

Do not proceed with copy/activation until exactly one pack name is confirmed.

## Step 3 — Copy the pack

Copy the chosen pack directory (`<pack-name>` below) into the target project, preserving structure — `schema.yaml` and the whole `templates/` directory travel together:

**Option A — Project local (recommended):**
```bash
mkdir -p ./openspec/schemas
cp -R /tmp/gatedloop-packs/packs/<pack-name> ./openspec/schemas/<pack-name>
```

**Option B — User level (available across projects):**
```bash
cp -R /tmp/gatedloop-packs/packs/<pack-name> $HOME/.openspec/schemas/<pack-name>
```

## Step 4 — Activate

Update `openspec/config.yaml` (project default) or the specific change's `.openspec.yaml` (per-change — the more common case; most projects don't want every change on the same schema):
```yaml
schema: <pack-name>
```
Also update the `rules:` keys to match the pack's artifact ids — `bugfix` uses `report`, `spec-delta`, `tasks`; `architecture` uses `explore`, `design`, `adr`.

## Step 5 — Validate

```bash
openspec schema validate <pack-name>
```
Expected success output: `✓ <pack-name>`. If validation fails, report the error output to the user verbatim — do not silently drop the pack or retry with a modified copy.

## Step 6 — Inspect it before trusting it

Neither pack declares companion skills (no `skills.txt` — that step from the community catalog's own guide doesn't apply here), but gatedloop ships a deterministic inspector for exactly this moment:
```bash
gates schema inspect <pack-name> --json
```
Reports the artifact flow, whether an `apply` block exists (neither pack surprises you here — `bugfix` has one, `architecture` doesn't, by design), and any tool-name-shaped string found (this repo's own two packs report none). This is advisory only — it never blocks the install, and a flagged name is a finding, not a verdict.

## The one limitation, disclosed here and not only in SETUP.md

**Installed packs have no upstream update path.** This is a snapshot at today's commit of this repository — there is no registry, no version pin, and no `openspec schema update`. A later improvement to `bugfix` or `architecture` reaches this project only by re-running this procedure and re-applying any local fork changes by hand. This is the same limitation the community catalog carries (D6) — accepted, not solved, by design.
