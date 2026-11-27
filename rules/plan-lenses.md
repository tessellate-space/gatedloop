# gatedloop plan lenses

Lenses the plan loop judges a plan through, shipped inside the plugin. A plan
review runs through one lens at a time, reads the plan cold, and cites each
finding as `<lens-id> #<n>`, the way a convention review cites a rule-id. Each
`### <lens-id>` section is shaped like a rule in a project's rules-doc.

Every id here is prefixed `gatedloop.`, so it cannot collide with a project's
own ids. `gates plan brief <change>` lists the lenses the plan's tier runs
(light: `gatedloop.implementability`; full: it and `gatedloop.zero-decision`),
and `gates plan brief <change> --lens <id>` prints this file's path, the
plan's artifacts and each path the plan names with whether it exists at
`HEAD`. `gatedloop.blast-radius` is the built-in tier classifier, run only on
a light floor when no classifier of the project's own gave a verdict.

### gatedloop.implementability
Applies to: plan
Rule: The plan is right about the code.

A plan is a finding under this lens when:

1. **It names what is not there.** A path, rule id, command, gate name or
   configuration key the plan names neither exists at the base nor is created
   by an earlier task, or does not say what the plan assumes it says (a line
   the plan expects a generator to write that the generator never writes); or
   a task that changes code does not name the files it changes.
2. **Its order is not executable.** A task's work or its oracle needs an
   artifact that only a later task creates.
3. **It needs what it removed.** A task that deletes or renames a file is
   followed by a task, or preceded by a `rewrites:` clause, that still needs
   the file.
4. **Its tests have nothing to target.** An interface a task's tests would
   target is neither stated by the design nor present at the base.

### gatedloop.zero-decision
Applies to: plan
Rule: No task leaves a decision to the implementer.

A plan is a finding under this lens when:

1. **A choice is left open.** A task says "either", "as appropriate", "TBD",
   or gives "for example" where the example is the decision.
2. **A behaviour change has no scenario.** A task changes behaviour that no
   spec scenario states.
3. **An oracle tag does not fit its task.** A behaviour change is tagged
   `none`; a task that can only pass on the tree is not `characterization`;
   or a change to behaviour an existing test pins does not declare
   `rewrites:`.
4. **A decision is only implied.** A task relies on a design decision that
   `design.md` does not state.

A finding only a human can settle (a product choice, or a trade-off the specs
do not decide) is a `question`, stated with its options.

### gatedloop.blast-radius
Applies to: plan
Rule: Answer how far the plan reaches, dimension by dimension, and return only the verdict object.

Run through this lens, plan review classifies the plan's tier; it reports no
findings. It may only raise the tier: the shim combines the answers with the
floor, so the lens decides no tier by itself.

1. **Read the brief's JSON.** `gates plan brief <change> --lens
   gatedloop.blast-radius` prints the plan digest (no limit), the effective
   dimensions, the signals and the floor. The plan's artifacts may be read in
   full.
2. **Weigh what the plan reaches.** The data it persists or migrates, the
   contracts others depend on (public interfaces, formats, ledgers, schemas),
   the surfaces it crosses, what a defect would cost to undo, and how much of
   the plan's behaviour no existing test observes.
3. **Answer every dimension.** For each effective dimension, a value of its
   kind (a probability from 0 to 1, one of a choice's options, or a score on
   its levels) and a confidence from 0 to 1, as one evidence item
   `{dimension, value, confidence}`.
4. **Return only the `schema/plan-tier.schema.json` object.** An overall
   `tier` (`light` or `full`), an overall `confidence`, the `evidence` items
   and a one-line `reason`, as one JSON object and nothing else.
