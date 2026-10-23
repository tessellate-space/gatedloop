# Design: test-quality-rule

## Context

The loop already has a place where judgement about a diff is applied and cited, and
that is convention review. It was empty on the question #34 raises, because only the
adopter writes rules, and no adopter wrote one for tests. Adopters shouldn't have to.
"The tests the loop writes fail for real regressions" is a guarantee about the loop,
so the loop owns it. The rejection test agrees: this makes a stated guarantee
enforceable, as far as a review can enforce anything. It also names no stack
command.

The adopter's own layer rules stay theirs. #34's item 5 says so: "domain modules import
no I/O library, enforced by an import lint" belongs in the project's conventions. What
the loop carries is the classification step, and the halt it takes instead of faking a
type the project doesn't own.

## Decisions

### D1. A plugin-shipped rules file, resolved by the shim

The rule lives at `rules/loop-rules.md` in the plugin root, as a `### specloop.test-quality`
section. The `specloop.` prefix is namespacing: it cannot collide with an adopter's
rule-ids, which are bare kebab-case, and a finding citing it tells the reader whose
rule it is.

`gates rules` resolves the file from its own location
(`Path(__file__).resolve().parent.parent / "rules" / "loop-rules.md"`), the same way
`gates init` finds its template. That keeps it plugin-relative and self-contained. The
output gains a second block after the surface rules:

```
Built-in loop rules (always apply):
  - specloop.test-quality

Resolve built-in rule-ids against: /…/specloop/rules/loop-rules.md
```

If the file or the section is missing, `gates rules` exits non-zero (fail-loud-gates),
because a silently absent rule is the failure mode `reposition-specloop` fixed once
already.

### D2. Always on, with no opt-out

The rule judges only tests, and only against properties no project wants: a test that
cannot fail, or the same assertion at three layers. A project that disagrees with an
item disputes the finding, which the loop already records as `oracle-conflict`. It
doesn't switch the rule off wholesale. If a real need for an opt-out appears, it is one
manifest key later. It is not built now.

### D3. The rule text

This text ships verbatim as the body of `### specloop.test-quality`. Items are
numbered, so a finding can cite `specloop.test-quality #4`.

> Applies to: code
> Rule: Every test the loop adds must fail for a real regression, at the lowest layer that can observe it.
>
> Where one of the project's own rules contradicts an item below, the project's rule
> wins, and the finding is not raised.
>
> A test the diff adds or changes is a finding when it:
>
> 1. **Executes no behaviour.** It asserts a default value, a constant, a declared
>    field of a schema or data class, a re-export, a test-only helper, or the test
>    framework itself.
> 2. **Repeats a layer.** The same behaviour is already asserted at another layer; the
>    lowest layer that owns it keeps the test.
> 3. **Adds no equivalence class.** A parametrised or copied case exercises the same
>    path as a sibling case; one route-walking or table-driven test replaces copies
>    of one precondition.
> 4. **Pins incidentals.** It asserts private state, the count or order of
>    interactions with a double, an exact type or element name, render order, or prose
>    wording. Wording gets at most one golden snapshot per locale; what a prompt makes
>    a model do is the `eval` gate's job.
> 5. **Tests the double.** A stubbed collaborator is asserted through what it
>    received, or a stub re-implements the code it stands in for.
> 6. **Is a tombstone.** It asserts that a removed feature is absent.
> 7. **Waits for real.** A unit test uses a real timer, timeout, sleep or retry
>    backoff.
> 8. **Copies a fixture.** A payload or fixture is inlined in more than one file
>    instead of shared.
> 9. **Checks an echo.** A self-test asserts what a dry run prints instead of the
>    effect of the command, or searches source text (that is a lint, not a test).
> 10. **Sits on the slowest layer without a reason.** An integration or acceptance
>     test has no stated reason why no cheaper layer can observe the behaviour, such as
>     a layer boundary, real rendering or input, or an external system's contract.
> 11. **Gates on a model.** Its verdict depends on a model's reply and it is bound to
>     a blocking gate rather than `eval`.
> 12. **Guesses its timing or geometry.** It waits with a fixed sleep, or it
>     re-derives application logic (coordinates, layout, business rules) inside a
>     test helper to aim an action.
> 13. **Has no oracle.** The task changes behaviour but adds no test and names no
>     existing test that covers it.

The audit's own examples (pydantic, zod, vitest, WebGL and so on) are deliberately
absent. A test in `tests/` runs the same stack-name audit the packs already get over
this file.

### D4. The RED step's four questions

`tdd-apply` 5c becomes an ordered checklist, answered before any test is written:

1. **Which real regression makes this test fail?** Name it in one line. If none can
   be named, don't write the test.
2. **Is it already tested one layer down?** Name the test (`gates task changed` and
   a search of the test tree). If it is, add none, and go to D5.
3. **Domain or I/O?** Domain logic gets a pure test at its public seam, with no fakes.
   An adapter gets one contract test against the real system at the integration gate,
   and nothing in between.
4. **Would this need a fake of a type the project doesn't own?** Stop. Extract the
   domain logic behind an interface the project owns and test that. If the
   extraction is outside this task's stated scope, halt with `weak-spec`, detail
   "needs a domain seam for <thing>". This is the "extract before faking" halt from
   #34, mapped onto the existing closed cause set. The plan didn't provide a seam, so
   the spec is what's weak.

Then write the test and run it red, exactly as today. The line the audit singled out,
"a red-first test that only proved the loop went red", goes into 5d. Once the
behaviour test exists, delete any scaffolding test that fails for the same regression.

`agents/tdd-implementer.md` gains the same four questions in one short section, and
points at the skill for detail. The 5-bugfix route is unchanged in substance, since
its oracle is the recorded repro. It gains one line: the repro test is subject to
questions 3 and 4 like any other.

### D4a. The project's architecture answers questions 3 and 4

"Domain or I/O?" and "extract the domain first" are architectural decisions. The loop
must make them the way the host application already does, and never by a general
theory of its own. If the loop's answer diverges from the app's architecture, that's a
worse defect than the waste #34 measured, because it lands in production code, not
only in tests.

**Where the rules live.** One place: the conventions source that `.gates.yaml`'s
`conventions.rules-doc` names. It already has two consumers, and this change adds a
third use of the first one:

| Consumer | How it reads the rules | Since |
|---|---|---|
| OpenSpec's artifact steps | `openspec/config.yaml` `rules:`, generated by `gates conventions sync` from rules tagged `Applies to: <artifact-id>`, so `design.md` is authored under them | `reposition-specloop` |
| Convention review | `gates rules` → hot-surface rule-ids, resolved in the rules-doc | the loop's start |
| The RED step (new) | the same `gates rules --changed <paths>` call, made **before** writing the test rather than after | this change |

A layering rule is written once, for example "domain modules import no I/O library;
every I/O dependency sits behind a port in `<dir>`; fakes implement the port". Tagged
`Applies to: design, code`, it shapes the design when the plan is authored, the test
the loop writes, and the review that checks both. Nothing new is added to
`.gates.yaml`. The binding it already has is the "somewhere in gates" these rules
belong in, and `openspec/config.yaml` stays a generated copy for OpenSpec's own use.
Writing it by hand is the defect `reposition-specloop` fixed.

**The RED step's order becomes:**

0. `gates rules --changed <paths the task touches>`, then read those rules and the
   change's `design.md`. The paths are taken from the task line and the design.
1. Then questions 1–4 from D4. Questions 3 and 4 are answered by those rules and that
   design:
   - **Classification.** "Domain" and "I/O" mean what the project's rules say they
     mean. Where the rules name the layers (ports, adapters, services, stores),
     those names are used.
   - **Seams.** An extraction follows the seam pattern the rules or the design
     define: where the interface lives, what it is called, and what implements it.
   - **No seam defined.** When neither defines where a seam belongs, the loop
     doesn't design one. It halts with `weak-spec`, detail "needs a domain seam for
     <thing>; neither the project's conventions nor the design define where it
     belongs". A seam is an architecture decision, and those are made in the plan.
   - **Precedence.** A project rule outranks any `specloop.test-quality` item it
     contradicts. The project knows its stack; the built-in rule doesn't.

**A project with no rules-doc, or no layering rule.** The loop can't obey a rule that
isn't written. Questions 1, 2 and 3 still apply, using the plain meaning of domain and
I/O. Question 4's extraction halts as above, because with nothing written there is no
sanctioned seam. The `gates-init` conventions capture already harvests layering rules
from the project's agent files and existing OpenSpec `context:`. SETUP.md's
conventions section gains one sentence naming layering rules as the ones the loop
consults before writing code.

This reuses `gates rules --changed`, which exists today. The shim changes only in the
built-in block that D1 adds.

### D5. Oracle per task, recorded in the commit

A task that adds no test names its oracle in a commit trailer:

```
Covered-by: <test identifier as the project's runner names it>
```

A trailer is used because it survives the squash-merge in the PR body only if a human
keeps it. The durable record is the task commit on the branch, which the ledger already
points at. The review sees the commit message draft as part of the task gate (5f passes
it along with the diff), and item 13 flags a behaviour change with neither a new test
nor a trailer. No ledger field or shim check is added. Whether a named test really
covers the behaviour is a judgement, and the review is where judgement lives.

### D6. Steps 6 and 7 stop re-proving lower layers

- **Step 6 (integration from specs):** for each WHEN/THEN, first ask D4's question 2
  at the integration layer. A scenario gets an integration case only when it crosses a
  layer boundary or no lower-layer test covers it. Otherwise the step names the
  covering test in its report. This replaces "each scenario → one or more integration
  cases".
- **Step 7 (acceptance step definitions):** an undefined step is a failure to fix,
  never a skip. The step also carries rule items 10–12 explicitly: justify the layer,
  keep model-dependent verdicts in `eval`, and use no fixed sleeps or re-derived
  geometry.

Neither step can check the runner's behaviour on an undefined step. That lives in the
adopter's runner configuration (D7).

### D7. Gate-binding guidance, stated as the adopter's to honour

SETUP.md's gate contract section gains a short "a blocking gate's runner must" list:

- fail on an undefined or skipped-for-missing-implementation test;
- not retry a failure to green, because a retry that passes hides a flaky test on a
  blocking path;
- and keep model-dependent checks under `eval`.

`commands/gates-init.md` says the same in one line when it binds `verify` or
`live-check`. `gates validate` doesn't check it, since a command string can't be
inspected for runner flags without naming a stack.

### D8. What convention-review changes

Step 3 of `agents/convention-review.md` now reads: "Read ONLY those rules: the hot
surfaces' rules from the rules-doc, and the built-in rules from the path `gates rules`
prints." The agent applies `specloop.test-quality` only to test code in the diff, and
decides for itself what counts as test code. Deciding that from globs would need an
adopter-declared test layout, which this change doesn't introduce. The ~10 tool call
budget holds, because the rules file is one short read.

## Risks

- **Review cost rises slightly.** It's one extra file read per review, plus judgement
  over the test hunks. That's cheap next to #34's measured cost of the waste: minutes
  of gate time per run, and hours per fortnight at the end-to-end layer.
- **An LLM applies the rule unevenly.** That's true of every convention rule. The
  measured cure for the root cause is `split-test-author`: a test author who never
  saw the implementation can't write most of these tests in the first place.

## Out of scope

- Splitting the test author from the implementer: `split-test-author`.
- Harness speed fixes (unpatched timeouts, slow selectors). #34 found these dominate
  runtime, but they are project code, not the loop's.
- Deleting existing waste in adopters' suites. The rule applies to what the diff adds
  or changes.
