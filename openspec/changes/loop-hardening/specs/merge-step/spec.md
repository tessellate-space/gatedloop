## ADDED Requirements

### Requirement: Proving the head checks the plan approval

`gates merge` SHALL, at step 1 in both local and pull-request mode, refuse a change whose plan artifacts on the merge target, or at the change branch's head, do not hash to the `approved_sha` recorded on the merge target. The refusal SHALL name the re-approval route. A `tasks.md` outside the approval digest SHALL never cause this refusal.

#### Scenario: The plan was amended on the target without re-approval

- **WHEN** a change's `design.md` was amended on the merge target after its approval was recorded, and the approval was not re-attested
- **THEN** `gates merge <change>` halts at step 1 naming the stale approval and the re-attest route, and nothing is squashed

#### Scenario: The branch edited its own plan

- **WHEN** the change branch's head changes a file in the change's `specs/` after approval
- **THEN** `gates merge <change>` halts at step 1 naming the stale approval

#### Scenario: A tick is not an amendment

- **WHEN** only untagged lines of the change's `tasks.md` changed since approval
- **THEN** step 1 does not refuse for the approval

#### Scenario: Pull-request mode

- **WHEN** `gates merge <change>` runs in pull-request mode and the approval is stale
- **THEN** it halts before publishing any status or opening a pull request
