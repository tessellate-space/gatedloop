# Design

## Context

`rename-to-gates` set the precedent (archived design, D3 and D5):
- a forwarder with a stated expiry, never silent;
- the removal created as a named follow-up when the rename lands;
- completion defined mechanically, by a grep that returns only allowed hits.

What it renamed was one binary and one file. This rename reaches committed state in adopters' repositories, a forge-side contract (status contexts), and the plugin identity Claude Code installs by.

## Decisions

### D1. The name map

| Kind | Was | Now |
|---|---|---|
| plugin and marketplace name | `specloop` | `gatedloop` |
| command namespace | `/specloop:*` | `/gatedloop:*` |
| state directory | `.specloop/` | `.gatedloop/` |
| change metadata | `x-specloop-approved-*`, `x-specloop-epic` | `x-gatedloop-…` |
| commit statuses | `specloop/<gate>` | `gatedloop/<gate>` |
| record branches | `specloop/record-merged-<sha>` | `gatedloop/record-merged-<sha>` |
| built-in rule ids | `specloop.test-quality`, … | `gatedloop.…` |
| composed hook markers | `# >>> specloop …` / `SPECLOOP_HOOK_*` | `gatedloop` |
| message prefix | `specloop: …` | `gatedloop: …` |
| docs memo | `docs/specloop-map.html` | `docs/gatedloop-map.html` |
| repository | `tessellate-space/specloop` | `tessellate-space/gatedloop` |

`gates`, `.gates.yaml` and every gate name stay as they are. They are the contract, and they never carried the product name.

### D2. Read-both, loud, for one release

One helper resolves each renamed identifier, preferring the new name:
- `_state_dir(root)`;
- the metadata readers, which already fall back field by field;
- the status reader in `marker check-remote`;
- the rule-id resolver;
- the hook-marker detector;
- the record-branch matcher.

When an old spelling is read, the command prints **one** stderr line: `gatedloop: read the earlier name '<old>'; run gates migrate-name (old names stop working in 0.8.0)`.

Writes always use the new spelling, with two exceptions for the whole release:
1. **`marker publish`** posts both `gatedloop/<gate>` and `specloop/<gate>`, so branch protection keeps passing until the adopter updates it.
2. **A project with only `.specloop/`** keeps writing there until it migrates. Writing a second directory would split the ledger.

`.specloop/` and `.gatedloop/` both existing is refused loudly, naming `gates migrate-name`.

### D3. `gates migrate-name`

It runs from the repository root and makes local edits only, never committing and never pushing:
1. **The state directory.** If `.specloop/` exists and `.gatedloop/` doesn't, it runs `git mv .specloop .gatedloop`, falling back to a plain rename when the directory is untracked.
2. **Change metadata.** It rewrites `x-specloop-*` keys in every active change's `.openspec.yaml`, keeping values. Archived changes are left alone.
3. **Hook markers.** It rewrites the markers in a composed hook it recognises; a direct copy is refreshed by `gates hook install`.
4. **Edits it won't make.** It prints:
   - `enabledPlugins` and marketplace entries in Claude Code settings;
   - the permission `ask` rule;
   - branch-protection contexts (`specloop/ci` → `gatedloop/ci`).

Each comes with the exact replacement.

It is idempotent and exits 0 when there's nothing to do. Its commit is planning- and ledger-grade, except for the hook file, which lives outside the tree.

`gates doctor` gains a `name` row that warns while any old identifier remains. The adoption catalogue gains `rename`: recurring, `since: 0.7.0`, applies when `.specloop/` exists or a `specloop` marker is found, with a `confirm` action naming `gates migrate-name`.

### D4. The old plugin name

Claude Code installs a plugin by `name@marketplace`, and its commands are namespaced by plugin name. Renaming the plugin can't keep `/specloop:*` working from the same plugin.

For one release, `marketplace.json` lists two plugins:
- **`gatedloop`**, the plugin;
- **`specloop`**, a forwarder in `forwarder/specloop/`. It has a SessionStart hook printing a notice, and a stub for each former command that prints the same notice and does nothing else. The notice reads: "Specloop is now gatedloop. Install it: `/plugin install gatedloop@gatedloop`, then run `gates migrate-name` in each project."

**Task 1.1 is a spike before anything else.** It verifies, against Claude Code's documentation and a local marketplace, what an existing `specloop@specloop` install sees when the marketplace's own name changes. If the existing install can't reach the renamed marketplace, the forwarder reaches no one, and the plan says so. The notice then moves to the last `specloop`-named release, and README and SETUP carry the manual steps. The task's result is recorded in this design before 1.2 starts.

#### Spike result (task 1.1)

Run on 2026-10-22 against Claude Code 2.1.299, with the shell `claude plugin …` commands (the same operations as `/plugin …` in a session) under an isolated `CLAUDE_CONFIG_DIR` and a local directory marketplace. It was cross-checked against the docs pages "Create a marketplace" and "Host and maintain a marketplace".

What an existing install sees:
1. **The marketplace keeps its add-time name.** A marketplace is registered under the `name` its manifest had when it was added. When the manifest's `name` later changes to `gatedloop`, `claude plugin marketplace update specloop` succeeds without a warning, and the marketplace stays registered as `specloop`. An existing install remains `specloop@specloop`.
2. **The forwarder reaches it.** With the renamed marketplace listing a `specloop` entry at `./forwarder/specloop`, `claude plugin update specloop@specloop` moves the install to the forwarder (0.6.0 → 0.7.0, "Read from: …/forwarder/specloop"). The adopter has to update, because background auto-update is off by default for a third-party marketplace. The alternative, a notice in the last `specloop` release, depends on that same update.
3. **Without a `specloop` entry, the install breaks without saying why.** The update fails with `Plugin "specloop" not found`, and `claude plugin list` shows `✘ failed to load — Plugin specloop not found in marketplace specloop`. Nothing names gatedloop.
4. **`gatedloop@gatedloop` doesn't resolve through the old registration.** It fails with `Plugin "gatedloop" not found in marketplace "gatedloop"`, because that registration is still keyed `specloop`. Only `gatedloop@specloop` resolves. A fresh `marketplace add` of the renamed marketplace registers as `gatedloop` and installs `gatedloop@gatedloop`. Both registrations can exist side by side, keyed `specloop` and `gatedloop`.
5. **The docs describe a third option, a top-level `renames` map** (`"renames": {"specloop": "gatedloop"}`). Tested, it rewrites `enabledPlugins` from `specloop@specloop` to `gatedloop@specloop` and shows a one-time "Renamed to" notice. That keeps the adopter on the `specloop` registration, which points at this private repository. Under D5 that repository becomes a frozen archive, so `renames` would quietly leave adopters on a source that never updates again, with no step that re-points them. It's rejected for the same reason as D3 of `rename-to-gates`: a migration that's silent never actually happens.

**Decision: the forwarder plugin.** It's the only option that reaches an existing install with a message. It also keeps the loop from running under the old name. The notice in D4 needs one correction, because of finding 4: on its own, `/plugin install gatedloop@gatedloop` fails for an existing adopter. It has to add the new marketplace first. The notice therefore reads:

"Specloop is now gatedloop. Run `/plugin marketplace add tessellate-space/gatedloop`, then `/plugin install gatedloop@gatedloop`, then `/plugin uninstall specloop@specloop` and `/plugin marketplace remove specloop`. Then run `gates migrate-name` in each project. This plugin no longer runs the loop."

The forwarder reaches only adopters who update from the `specloop` registration, which is this repository. So it has to be on this repository's `main` before `go-public-migration` freezes it.

### D5. The repository

The public repository is a fresh `tessellate-space/gatedloop`, created from a clean copy of the tree by `go-public-migration`, not by `gh repo rename`. Its procedure and tool are `scripts/go-public` and RELEASING.md's "Publishing the public repository". This private repository stays as the archive, so there is **no** URL redirect. The README's migration notes give the new marketplace and install commands instead. The implementer updates:
- every link in the repository;
- `AGENT_INSTALL.md`'s clone URL, stale since the repository moved from `radub21/specloop`;
- `.claude-plugin/marketplace.json` sources;
- the workflow's name.

The Azure DevOps mirror workflow is checked for a hard-coded repository name.

### D6. Mechanical completion

The change is done when `git grep -n -i specloop -- . ':!openspec/changes/archive' ':!CHANGELOG.md'` returns only:
- the read-both helpers and their tests;
- the forwarder plugin;
- `gates migrate-name` and its tests;
- the migration notes in README, SETUP and RELEASING;
- this change's own artifacts.

Any other hit is a defect. A test encodes the allow-list, so it holds afterwards too.

### D7. Expiry

`remove-specloop-forwarders` is proposed in the same PR as this plan's implementation lands. It removes, in 0.8.0:
- D2's read-both;
- the dual status publishing;
- the forwarder plugin;
- the old-name warnings.

`gates migrate-name` stays one release longer, so a late adopter can still move across.

## Risks

- **A missed reference in a shipped prompt.** D6's grep catches it, and read-both makes a missed old name still work loudly rather than break.
- **Branch protection mid-migration.** D2's dual publishing keeps both contexts green until the adopter edits protection.
- **Tests and fixtures named after the old identifiers.** They move with the rename. Read-both has its own tests that use old names on purpose.
