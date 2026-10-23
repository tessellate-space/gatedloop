# Design: adoption-prompts

## Context

`gates-init` is the one place an adopter is asked what they want, and it runs once.
Every later release that adds something to decide relies on the adopter reading the
changelog. For the release this change joins, that fails at the worst point. The test
author (`split-test-author`) works well on Sonnet only when the project's test
conventions are written down, and an upgraded project has none.

The design follows three rules this repo already applies:

- **Selection in code, judgement in prompts.** Whether an item is decided is a
  deterministic fact the shim computes, like `gates rules`. The questions are asked by
  a command.
- **No copies.** Where onboarding already has the step, the upgrade walk invokes it,
  the same way onboarding invokes `workflow-select`.
- **Never ask unattended.** The brief informs. Only an interactive command asks.

## Decisions

### D1. The catalogue: shipped JSON, closed detector kinds

`adoption/catalog.json` at the plugin root is resolved from the shim's own location,
like `templates/`. It is JSON so the shim parses it with the standard library. Shape:

```json
{"items": [{
  "id": "test-conventions",
  "since": "0.5.0",
  "what": "Your project's test rules, which the test author and the RED step follow.",
  "question": "Capture this project's test conventions now?",
  "options": [
    {"answer": "adopted",  "label": "Capture them now (Recommended)"},
    {"answer": "declined", "label": "No — the author follows the built-in rule only"}
  ],
  "detector": {"kind": "rules-target", "target": "tests"},
  "applies_when": null,
  "action": {"kind": "onboarding-step", "step": "gates-init §6 test-conventions pass"}
}]}
```

`"later"` is always offered by the walk and is never listed in `options`.

**Detector kinds** answer "has the project already acted?":

| Kind | Acted when |
|---|---|
| `manifest-key` | the dotted `key` is present in `.gates.yaml` |
| `rules-target` | the rules-doc has a rule whose `Applies to:` includes `target` |
| `schema-key` | some project-local `openspec/schemas/*/schema.yaml` has the top-level `key` |
| `decision-only` | never; only a recorded decision closes the item |

**Predicate kinds** (`applies_when`) are `manifest-key` (with `any_of` for a list of
keys), `path-exists` (a glob), `surface-key` (some `surfaces[]` entry declares the
given key, e.g. `live-check`), and `any` (holds when any of its nested predicates
holds). `null` means the item always applies.

**Action kinds** tell `/specloop:upgrade` what to do on `adopted`:
- `manifest-key` edits `.gates.yaml` to set `key` to the chosen value, then runs
  `gates validate`;
- `onboarding-step` invokes the named `gates-init` step;
- `confirm` shows `what` plus a `detail` text and records the answer.

Every kind set is closed and lives in `bin/gates`. An unknown kind exits non-zero,
naming the item (fail-loud-gates). A test in this repo's `ci` loads the catalogue and
checks its required fields, its kinds, and that every `since` is a valid
`MAJOR.MINOR.PATCH`.

**Unreleased items** (amendment, after implementation reached task 3.2): an item is
added to the catalogue *with the change that introduces its setting*, so on `main` it
carries the next release's version while `plugin.json` still names the current one.
That is the normal state between releases, not an error, so two rules replace the
original "`since` ≤ plugin version" ci check:
- `gates adoption status` ignores an item whose `since` is later than the installed
  version (D3). An installed plugin never carries such an item; only this repo
  between releases does, and nothing should be asked about an unreleased setting.
- `scripts/release publish` refuses, before its first write, while any item's `since`
  is later than the version being published. After `cut`, every item for the release
  carries exactly that version, so the check passes; an item mistakenly tagged for a
  later release blocks publication with its id named.

A `schema-key` detector reads raw schema text with a column-0 key match. It needs only
a key's presence, which the `schema-declared-flow` D4 reasoning covers without PyYAML.

### D2. The record: `.specloop/adoption.json`, shim-written, committed

```json
{"decisions": {
  "loop.test-author": {"decision": "adopted", "by": "Name <email>",
                       "at": "2026-…Z", "version": "0.5.0"}
}}
```

- **Written only by `gates adoption record <id> <adopted|declined|later>`.** It
  refuses an unknown id or decision. The write is atomic: a temp file, then a rename.
  `by` comes from `git config user.name`/`user.email`, the same way approval
  attestation gets it.
- **It lives under `.specloop/`, not in `.gates.yaml`.** A shim that rewrote the
  manifest would have to preserve the adopter's comments and layout, and
  `_mini_yaml` can't round-trip them. The manifest keeps the *settings*, and this file
  keeps the *decisions about whether to set them*.
- **It is committed.** Adoption is a team decision, and `.specloop/` is already
  tracked for the ledger.

### D3. `gates adoption status`

An item is listed when all four hold:
0. its `since` is no later than the installed version (D1, unreleased items);
1. `applies_when` is null or holds;
2. the detector says not acted on;
3. there is no applicable decision. `adopted` and `declined` always apply. `later`
   applies only while the installed plugin version equals the recorded `version`.

The installed version is read from `.claude-plugin/plugin.json`, beside the shim.

Output: a human list, or `--json`:

```json
{"version": "0.5.0", "undecided": [{"id": "…", "since": "…", "what": "…"}]}
```

It exits 0 whether or not anything is listed. It exits non-zero only when it can't
decide: a bad catalogue, an unreadable record, or an unknown kind.

**Detector beats record.** If the manifest already sets the key, the item is not
listed, whatever was recorded. The adopter acted, and that is the decision.

### D4. The session brief line

`hooks/_session_brief.py` runs `gates adoption status --json`, the same subprocess
pattern as `_approval_status`, and never raises:
- with items, it prints one line: `Specloop <version> added <n> setting(s) this
  project hasn't decided on — run /specloop:upgrade`;
- on failure, it prints `adoption check could not run (<reason>)`;
- with nothing listed, it prints nothing.

The line is the same in headless and interactive sessions. The brief never asks,
because a SessionStart hook can't and shouldn't.

### D5. `/specloop:upgrade`

`commands/upgrade.md` is a flat command (commands-flat-skills-nested). There is no
upstream equivalent, so it qualifies for the `/specloop:` namespace. It does this:

1. Runs `gates adoption status --json`. If the list is empty, it says so and stops.
2. Shows the list once, each item with `since` and `what`, and says the walk can stop
   at any point and resume.
3. Takes the items in `since` order, then catalogue order. For each, it asks one
   AskUserQuestion with the catalogue's options, recommended option first, plus
   "Decide later". On `adopted` it carries out the action (D1). It then records the
   answer immediately with `gates adoption record`. On `declined` or `later` it records
   only.
4. Closes with `gates adoption status` to show what is left, which should be nothing
   except `later` items.

Recording each answer as soon as it's given makes an interrupted walk resumable, the
same principle as done ⟺ committed. The command doesn't commit
`.specloop/adoption.json` or the manifest. It names both files and leaves the commit
to the adopter, who owns their repository's history.

### D6. Onboarding

`commands/gates-init.md` changes in two ways:
- **Record at the source.** A step that corresponds to a catalogue item records the
  adopter's answer there and then. For example, the §6 test-conventions pass records
  `adopted` or `declined`.
- **A last step.** It runs the D5 walk over anything still undecided, so a new
  project leaves onboarding with every current item decided or deferred.

Items an onboarding step already satisfied are detected, not recorded (D3's "detector
beats record"), so the walk skips them.

### D7. The release check

In `scripts/release cut`, before the first write, it runs
`git diff --name-only <tag>..HEAD -- schema/gates.schema.json`. If that is non-empty
and no catalogue item has `since == <new version>`, it prints a warning naming both
files, and the cut continues.

It stays a warning because a schema change can be a fix, not a new decision. The
maintainer reads the draft diff anyway, and RELEASING.md's checklist gains "add an
adoption item for every new decision". `adoption/` joins `SHIPPED_PATHS`.

### D8. The seeded items

| id | since | detector | applies when | action | recommended |
|---|---|---|---|---|---|
| `approval.acceptance` | 0.5.0 | `manifest-key approval.acceptance` | — | `manifest-key`: `self` or `review` | `self`, with `review` offered for PR-mode teams |
| `loop.test-author` | 0.5.0 | `manifest-key loop.test-author` | — | `manifest-key`: `separate` or `inline` | `separate` |
| `test-conventions` | 0.5.0 | `rules-target tests` | — | `onboarding-step` §6 test-conventions pass | capture now |
| `runner-strictness` | 0.5.0 | `decision-only` | `any` of `manifest-key gates.verify`, `manifest-key gates.integration`, `surface-key live-check` (live-checks are declared per surface, not under `gates`) | `confirm`, with the D7 text from `test-quality-rule` | confirm |
| `schema-flow` | 0.5.0 | `schema-key specloop` | `path-exists openspec/schemas/*/schema.yaml` | `confirm`, explaining `specloop.flow` and naming the local schemas | review now |

For `approval.acceptance`, `declined` means "no acceptance step", which is today's
behaviour. `review` needs PR mode, which `gates validate` already enforces after the
edit.

The `since` values assume the next release is 0.5.0. If the maintainer cuts a
different number, the catalogue is corrected at `cut` time, and D7's warning points at
it.

## Risks

- **Nagging.** There is one line per session, and only while items are undecided.
  "Decide later" silences an item until the next version. "No" silences it for good.
- **A detector misreads a project,** listing a decided item or hiding an undecided
  one. The kinds are few and each is tested. A wrongly listed item costs one "no"; a
  wrongly hidden one costs what the adopter would have had without this change.
- **Catalogue drift.** Future releases forget to add items. D7 warns, and the
  checklist asks.

## Out of scope

- Migrating `gatesVersion`. `doctor` already reports it, and a format migration is a
  different act from a decision.
- Adopting settings automatically. Every change to an adopter's project goes through
  a question.
