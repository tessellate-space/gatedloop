# Design

## Context

What the shim does with approval keys today:
- `_write_approval_keys` writes three top-level keys into `openspec/changes/<change>/.openspec.yaml`.
- `_read_approved_by`, and the `git show <ref>:…/.openspec.yaml` read in `check-implement`, read them back through `_load`, which is PyYAML or `_mini_yaml`.
- The approval sha hashes `proposal.md`, `design.md` and `specs/**` only, never `.openspec.yaml`.

OpenSpec 1.14.3 recognises these keys in `.openspec.yaml`: `schema`, `created`, `goal`, `affected_areas`, `initiative`, `skip_specs` and `retire_capabilities`. It also accepts any key matching lowercase `x-…`. Everything else is reported, and fails `validate --strict`.

## Decisions

### D1. The spelling

| Was | Now |
|---|---|
| `approved_by` | `x-specloop-approved-by` |
| `approved_at` | `x-specloop-approved-at` |
| `approved_sha` | `x-specloop-approved-sha` |

The keys are flat, not a nested `x-specloop:` mapping, because the writer edits lines and a flat key needs no structural YAML edit. The `x-specloop-` prefix also namespaces future metadata: `epic-linkage` uses `x-specloop-epic`.

### D2. Read either, write new

A single helper, `_approval_meta(data) -> (by, at, sha)`, reads the new key and falls back to the old one, field by field. Every reader goes through it:
- the working-tree read;
- `check-implement`'s read from the merge target;
- `approval check`;
- the acceptance brief, if it reads approvals.

`_write_approval_keys` writes the new keys and deletes any old-spelled ones in the same file, so a re-attest migrates as a side effect.

Reading both spellings means nothing breaks for:
- a plan merged under 0.5.0 and implemented under 0.5.1;
- an adopter who upgrades mid-change.

Archived changes are never rewritten; nothing reads their approvals.

### D3. `gates approval migrate [<change>]`

For each active change (or the one named), it rewrites old-spelled keys to the new spelling in place and prints each file it changed. Values and order are kept. A change with no old keys is left alone. It exits 0 when there is nothing to do. The approval sha is unaffected (see Context), so a migrated approval still checks.

The rewrite is a planning-path edit, so its commit is planning-grade. The command doesn't commit.

### D4. Doctor

A new row, `approval-keys`:
- **ok** when no active change carries an old-spelled key;
- **warn** otherwise, naming the changes and `gates approval migrate`, and saying that `openspec validate --strict` fails on those keys from OpenSpec 1.14.

Like every doctor row, it is advisory.

### D4a. The upgrade walk offers the migration

The adoption catalogue gains `approval-keys`, `since: 0.5.1`:

| Field | Value |
|---|---|
| detector | `old-approval-keys`, a new detector kind: acted on unless an active change's `.openspec.yaml` carries an earlier-spelled approval key |
| applies when | always |
| action | `confirm`, whose detail names `gates approval migrate` and its effect |
| recurs | yes: a change attested by an older Specloop on another machine can reappear |

`/specloop:upgrade` then offers it, as issue #39 asks, and `RELEASING.md`'s upgrade notes name it.

### D5. Not interactive

A helper, `_openspec(args, cwd, **kw)`, runs every `openspec` subprocess with `OPEN_SPEC_INTERACTIVE=0`, added to a copy of the environment. The roughly seven existing call sites use it. The variable is harmless on versions that don't read it, so no version check is needed.

### D6. The tested version

`TESTED_OPENSPEC_VERSION = "1.14.3"`, and the workflow's npm pin moves to `@fission-ai/openspec@1.14.3`. The suite already passes on 1.14.3 locally: the maintainer's machine has it, and `ci` was green on it for `retry-budget`'s plan PR.

### D7. Candidates, not this change

`docs/candidates.md` gains three entries, each with its reason to wait:
- **Split this repository's over-long requirements.** 16 of 19 specs fail `--strict`, 55 requirements in all. It's repo-internal: adopters never validate Specloop's specs, and the loop runs non-strict. It's large spec-authoring work that should be its own reviewed change.
- **Use `openspec list --archived --json`** for archive lookups (`scripts/release status`, `epic-linkage`). The shim reads the archive directory directly today, which works on every version. Waiting keeps the minimum OpenSpec version where it is.
- **Use requirement names from `openspec show --json`** in the acceptance brief, and **`openspec version --check --json`** in doctor ("an OpenSpec update is available"). Both are useful, but neither is needed now.

## Risks

- **An adopter's tooling greps for `approved_by`.** It still finds the old spelling until `migrate` runs. SETUP's migration row names the rename.
