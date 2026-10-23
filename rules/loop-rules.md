# gatedloop loop rules

Review rules the loop itself owns, shipped inside the plugin. They guard
guarantees about the loop, so no adopter has to write them. Each
`### <rule-id>` section is shaped like a rule in a project's rules-doc, and a
review finding cites it the same way.

Every id here is prefixed `gatedloop.`, so it cannot collide with a project's
own rule-ids and a finding shows whose rule it is. `gates rules` always lists
these ids, with this file's path, for every diff, whatever surfaces are hot.

### gatedloop.test-quality
Applies to: code
Rule: Every test the loop adds must fail for a real regression, at the lowest layer that can observe it.

Where one of the project's own rules contradicts an item below, the project's rule
wins, and the finding is not raised.

A test the diff adds or changes is a finding when it:

1. **Executes no behaviour.** It asserts a default value, a constant, a declared
   field of a schema or data class, a re-export, a test-only helper, or the test
   framework itself.
2. **Repeats a layer.** The same behaviour is already asserted at another layer; the
   lowest layer that owns it keeps the test.
3. **Adds no equivalence class.** A parametrised or copied case exercises the same
   path as a sibling case; one route-walking or table-driven test replaces copies
   of one precondition.
4. **Pins incidentals.** It asserts private state, the count or order of
   interactions with a double, an exact type or element name, render order, or prose
   wording. Wording gets at most one golden snapshot per locale; what a prompt makes
   a model do is the `eval` gate's job.
5. **Tests the double.** A stubbed collaborator is asserted through what it
   received, or a stub re-implements the code it stands in for.
6. **Is a tombstone.** It asserts that a removed feature is absent.
7. **Waits for real.** A unit test uses a real timer, timeout, sleep or retry
   backoff.
8. **Copies a fixture.** A payload or fixture is inlined in more than one file
   instead of shared.
9. **Checks an echo.** A self-test asserts what a dry run prints instead of the
   effect of the command, or searches source text (that is a lint, not a test).
10. **Sits on the slowest layer without a reason.** An integration or acceptance
    test has no stated reason why no cheaper layer can observe the behaviour, such as
    a layer boundary, real rendering or input, or an external system's contract.
11. **Gates on a model.** Its verdict depends on a model's reply and it is bound to
    a blocking gate rather than `eval`.
12. **Guesses its timing or geometry.** It waits with a fixed sleep, or it
    re-derives application logic (coordinates, layout, business rules) inside a
    test helper to aim an action.
13. **Has no oracle.** The task changes behaviour but adds no test and names no
    existing test that covers it.
