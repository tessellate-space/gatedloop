## Description

<!-- Write a comprehensive description with focus on the WHY, not on the WHAT.
     Provide references — file paths, code lines, external/internal URLs, related
     changes or design docs — wherever necessary. -->

## How to verify

<!-- How a reviewer exercises this change. Where relevant, contrast before/after:
     - Before: what wasn't possible / didn't work without this change
     - After: the exact commands to run and the expected result
     e.g. `gates validate`, `/plugin install gatedloop`, `/opsx:propose <name>` -->

## Output / screenshots

<!-- Terminal transcripts, command output, or screenshots showing the change in
     action (before/after where applicable). Omit if not applicable. -->

## Checklist

- [ ] Prompts stay stack-agnostic — no project-specific commands hard-coded (gates/surfaces via `.gates.yaml`)
- [ ] `gates validate` passes on the sample manifest; shim changes are exercised
- [ ] README / SETUP updated if the contract changed
