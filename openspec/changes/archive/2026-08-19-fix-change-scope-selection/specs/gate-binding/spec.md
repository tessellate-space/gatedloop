# gate-binding delta

## ADDED Requirements

### Requirement: Change-level gates select against the change, not the working tree

The shim SHALL compute two changed-file baselines, chosen by what is being run and
never by a caller-remembered flag. Task-level selection (`gates rules`, `gates
surfaces`) SHALL use the working set (unstaged + staged + untracked). Change-level
gate execution (`gates run live-check`) SHALL use the union of the working set and
the diff between the merge target and `HEAD` (merge-base diff). The explicit
`--changed` and `--all` overrides SHALL continue to apply to both.

#### Scenario: Live-check on a clean change branch

- **WHEN** every task of a change is committed on its branch, the tree is clean,
  and `gates run live-check` runs with no override flags
- **THEN** the hot set is computed from the branch's diff against the merge target
- **AND** every hot surface's live-check runs, and the command exits non-zero if
  any probe fails

#### Scenario: Live-check mid-change with a dirty tree

- **WHEN** some tasks are committed and further edits are uncommitted
- **THEN** the hot set covers both the committed branch diff and the working set

#### Scenario: Task-level selection is unchanged

- **WHEN** `gates rules` or `gates surfaces` runs during a task with no override
- **THEN** the selection reads only the working set, so the per-task review scope
  does not grow with the change's earlier commits

### Requirement: Merge-target resolution is generic and degrades loudly

The shim SHALL resolve the merge target without hard-coding a branch name — the
remote's default branch when a remote exists, else a local `main` or `master`.
When no target resolves or no merge base exists, the shim SHALL fall back to the
working-set baseline and SHALL report the degradation; the fallback SHALL NOT be
silent.

#### Scenario: No merge target can be resolved

- **WHEN** `gates run live-check` runs in a repo with no remote and no
  `main`/`master` branch
- **THEN** selection falls back to the working set
- **AND** a message names the fallback and the reason

#### Scenario: Running on the target branch itself

- **WHEN** `gates run live-check` runs with the merge target checked out
- **THEN** the merge-base diff contributes nothing and the working set alone
  drives selection, without any degradation warning

### Requirement: An empty change-level hot set is reported with evidence

When change-level selection produces no hot surfaces, the shim SHALL report the
baseline kind, the resolved merge target, and the number of changed files
considered. The exit code SHALL remain zero — an empty hot set is a legitimate
outcome — but the skip SHALL never be a bare one-liner indistinguishable from a
selection defect.

#### Scenario: A docs-only change on a project with code-only surfaces

- **WHEN** the change's diff touches no surface's globs
- **THEN** `gates run live-check` exits 0 and its output names the baseline, the
  merge target, and the file count it selected against

### Requirement: Rule-ids resolve against headings, not substrings

`gates validate` SHALL resolve a rule-id only against the `### <id>` heading ids
of the conventions rules-doc. A rule-id that appears in the doc's prose but has no
heading SHALL fail validation as dangling.

#### Scenario: A dangling id mentioned in prose

- **WHEN** a surface names rule-id `retired-rule` and the rules-doc contains the
  string "retired-rule" only inside another rule's prose
- **THEN** `gates validate` exits non-zero naming the dangling id

#### Scenario: A heading without sync metadata still resolves

- **WHEN** a rules-doc section has a `### <id>` heading but no `Applies to:` or
  `Rule:` lines
- **THEN** the id resolves for validation and review purposes

### Requirement: Surface matching may only err hot

Glob matching SHALL NOT select fewer surfaces than a path-separator-exact reading
of the manifest would select. Over-selection is permitted and documented;
under-selection is a defect.

#### Scenario: The error direction is pinned

- **WHEN** a glob's approximate matching disagrees with its exact reading for some
  path
- **THEN** the disagreement selects a superset of surfaces, never a subset
