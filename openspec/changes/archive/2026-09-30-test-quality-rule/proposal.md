# Proposal: test-quality-rule

## Why

Issue #34 is an audit of every test the loop wrote in one adopter project over two
weeks: about 110 merged changes, 2,321 unit tests and 154 end-to-end scenarios. Between
14% and 25% of each unit suite cannot fail for a real reason. At the end-to-end layer,
73 of 145 merge-blocking scenarios re-prove a rule that a named unit test already
covers, through a five-second browser round trip.

The waste falls into a few repeatable patterns:

- one test per new field;
- the same behaviour asserted at two or three layers;
- copy-paste per variant;
- pinned wording and constants;
- mock-the-child-and-assert-its-props;
- tombstones for removed features.

The issue traces the waste to the loop itself, and the loop's prompts confirm each
cause:

- **The RED step rewards the easiest failing test.** `tdd-apply` 5c says "tests assert
  the task's behavior" and nothing more. A default, a mock call or a substring goes red
  fastest and is never wrong, so that is what gets written.
- **Nothing asks "what real regression would fail this?" or "is this already covered
  one layer down?".** Convention review checks only the project's own rules, and no
  project wrote one for tests.
- **Step 6 turns every scenario into an integration case**, whatever lower layer
  already covers it. Step 7 wires "the missing step definitions" but never says that a
  missing one must fail.

About 70% of every suite is good, and the waste is a handful of patterns. That is what
makes the problem fixable in the loop rather than in each project.

This change covers items 1–5 of the issue: the review criteria and the questions the
loop asks at RED. Item 6, splitting the test author from the implementer, is
`split-test-author`, a separate change that builds on this one.

## What Changes

- **Specloop ships one built-in review rule, `specloop.test-quality`.** It is
  stack-agnostic prose in `rules/loop-rules.md` inside the plugin. `gates rules` always
  lists it, with its plugin-relative source, next to the hot surfaces' own rules. The
  `convention-review` agent applies it to every test the diff adds or changes, and each
  finding cites the rule and its numbered item. The rule restates the issue's list
  without naming a stack:
  - tests of defaults, constants, schema field declarations, re-exports, test helpers,
    or the framework itself;
  - the same behaviour asserted at more than one layer;
  - a parametrised case that adds no equivalence class;
  - assertions on private state, interaction counts or order, or exact prose;
  - a stubbed collaborator asserted through its inputs;
  - tombstones;
  - real timers in unit tests;
  - fixtures copied across files;
  - self-tests that assert an echo instead of an effect, or grep source;
  - a slowest-layer test with no reason no cheaper layer can observe the behaviour;
  - a model-dependent verdict on a blocking gate;
  - a fixed sleep, or application logic re-derived in a test helper.
- **The RED step asks its questions before writing.** `tdd-apply` 5c and the
  implementer brief put four questions to every test, in order:
  1. Which real regression would make it fail?
  2. Is the behaviour already tested one layer down? If so, name that test and add
     none.
  3. Is the code under test domain logic or I/O? Domain logic gets a pure test with no
     fakes; an adapter gets one contract test at the integration gate.
  4. Am I about to fake a type the project doesn't own? Then extract the domain first,
     and halt with `weak-spec` if that extraction falls outside the task.

  A red test that only proved the loop went red is deleted once the behaviour test
  exists.
- **The questions are answered by the project's architecture, not the loop's.**
  Questions 3 and 4 lead to code decisions: what counts as domain, where a seam goes,
  and what may be faked. Those decisions must match the architecture of the app the
  loop is running in. So before answering them, the RED step reads the project's own
  rules for the paths the task touches (`gates rules --changed <paths>`), resolved from
  the same rules-doc that `.gates.yaml` points at and that `openspec/config.yaml`'s
  `rules:` block is generated from. A project rule outranks the built-in rule. When
  neither the project's rules nor the change's design says where a seam belongs, the
  loop doesn't invent one. It halts with `weak-spec`.
- **"Every task ships a test" becomes "every task names its oracle."** A task whose
  behaviour an existing test already covers names that test in its commit body and
  adds none. That is recorded and never assumed.
- **The integration and acceptance steps stop re-proving lower layers.** Step 6 derives
  an integration case only for a scenario that crosses a layer or has no covering test.
  Step 7 treats an undefined step as a failure, never a skip, and never pins a verdict
  on a model's reply to a blocking gate.
- **Gate-binding guidance.** SETUP.md tells adopters that a blocking gate must fail on
  an undefined or skipped test and must not retry to green. `gates-init` says the same
  when it binds `verify` or `live-check`. Only the adopter's runner configuration can
  honour this, so Specloop documents it and does not enforce it.

## Capabilities

### New Capabilities

- `test-discipline`: what the loop requires of the tests it writes. It covers the
  built-in test-quality rule, the RED-step questions, the oracle-per-task rule, and
  where each kind of test belongs.

## Impact

- New `rules/loop-rules.md`, holding one `### specloop.test-quality` section.
- `bin/gates`: `cmd_rules` lists built-in rules and their plugin-relative path, and a
  test checks that the file and section exist.
- `skills/tdd-apply/SKILL.md`: steps 5c, 5f, 6 and 7, and the 5-bugfix route's
  "write tests first" line. `agents/tdd-implementer.md`: the brief carries the RED
  questions. `agents/convention-review.md`: step 3 always resolves the built-in rules.
- SETUP.md: the gate-binding guidance and a note that the built-in rule exists.
  `commands/gates-init.md`: one line when binding `verify` or `live-check`.
- No change to gates, hooks, markers or the ledger schema. The rule is judged by the
  review agent, like every convention rule. Its selection is deterministic: always on.
- The next release is held until this and `split-test-author` land.
