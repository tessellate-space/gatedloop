# Proposal: adoption-prompts

## Why

Adopters get a Specloop change only when the version is bumped. They get the code, but
nothing tells them what the new version needs them to *decide*. The upcoming release is
the first where that matters:

- `approval.acceptance`, which asks whether a human accepts the behaviour before merge
  (acceptance-gate);
- `loop.test-author`, a separate test author or inline authoring (`split-test-author`);
- **test conventions** tagged `Applies to: tests`, which the Sonnet test author and the
  RED step depend on (`split-test-author` D9, `test-quality-rule` D4a). The maintainer
  called this crucial: without them the author writes to generic rules;
- **runner strictness**, meaning that a blocking gate's runner must fail on undefined
  steps and must not retry to green (`test-quality-rule` D7).

Nothing that exists today covers this:

- **`/specloop:gates-init` can be re-run, but it re-walks all of onboarding**, and
  nothing prompts anyone to run it after an upgrade.
- **`gates doctor` checks only `gatesVersion`,** the manifest format. It knows nothing
  about new optional settings.
- **The session brief does not know that the plugin version changed.**

As a result, a project upgrades, keeps working, and silently runs on defaults it never
chose. The test conventions stay unwritten, and the new author works without them.
The rejection test puts this squarely in Specloop's scope: it gets a team running
faster, and it keeps the loop's guarantees resting on decisions the team actually made.

## What Changes

- **A shipped adoption catalogue,** `adoption/catalog.json` in the plugin. It is JSON so
  the shim needs no parser. Each item has:
  - `id` and `since` (the version that introduced it);
  - a one-line `what`;
  - the `question`, with options and the recommended one first;
  - a `detector` from a closed set of kinds, evaluated in code, that says whether the
    project has already acted on it;
  - an optional `applies_when` predicate;
  - an `action` naming how each answer is carried out: a manifest key, a
    `gates-init` step it reuses, or a confirmation only.
- **A committed record of the project's answers,** `.specloop/adoption.json`, written
  only by the shim. It holds `adopted`, `declined` or `later` per item, with who
  decided, when, and at which plugin version. A declined item is never
  raised again. A `later` item comes back only when the plugin version changes.
- **`gates adoption status [--json]`** lists undecided items in code. An item is
  undecided when its detector says the project hasn't acted, it has no recorded
  decision, and its `applies_when` holds. **`gates adoption record <id> <decision>`**
  writes a decision.
- **A one-line nudge in the session brief** when undecided items exist, for example:
  "Specloop 0.5.0 added 3 settings this project hasn't decided on — run
  `/specloop:upgrade`". A headless run gets the line and is never asked anything.
- **`/specloop:upgrade`** walks only the undecided items, one question each through
  AskUserQuestion, recommended answer first. Where an item has an onboarding step,
  such as capturing test conventions, it runs that step. It holds no second copy of the
  step, following the pattern `workflow-select` set for onboarding. After each answer it
  records the decision.
- **Onboarding records what it covered.** At the end, `gates-init` records a decision
  for every catalogue item it walked. Its last step runs the same walk for anything
  still undecided. A freshly onboarded project is never nagged about settings it just chose.
- **Releases must answer "what do adopters decide?".** `scripts/release cut` warns when
  a shipped change since the last tag touched the manifest schema, and no catalogue
  item carries the new version as `since`. RELEASING.md gains the step.
- **The catalogue is seeded** with the four items above for the next release, plus a
  fifth that applies only to projects with their own schemas: whether any of them
  wants the regression-first flow (`schema-declared-flow`).

## Capabilities

### New Capabilities

- `upgrade-adoption`: the catalogue, the recorded decisions, detection, the nudge and
  the upgrade walk.

### Modified Capabilities

- `onboarding`: onboarding records the adoption decisions it covered.
- `plugin-release`: a release that adds a decision carries a catalogue entry.

## Impact

- New files:
  - `adoption/catalog.json`;
  - `commands/upgrade.md`;
  - `.specloop/adoption.json`, in adopter projects, written by the shim.
- `bin/gates`: `adoption status` and `adoption record`, the detector kinds, and reading
  the plugin version from `.claude-plugin/plugin.json`.
- `hooks/_session_brief.py`: the one-line nudge.
- `commands/gates-init.md`: a closing step that records decisions.
- `scripts/release`: the `cut` warning; `adoption/` is added to `SHIPPED_PATHS`.
  RELEASING.md gains the catalogue step.
- README and SETUP.md: an "Upgrading" section.
- Depends on `test-quality-rule` and `split-test-author` for two of the seeded items'
  actions (the runner guidance and the test-conventions pass). This change is
  implemented after them, and all three ride in the same release.
