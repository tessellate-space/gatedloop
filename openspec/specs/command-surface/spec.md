# command-surface Specification

## Purpose
Which commands, skills and templates gatedloop ships, and which it leaves to upstream OpenSpec. Authoring stays with the maintained `/opsx:*` commands, a gatedloop command may only delegate to add a guarantee upstream lacks, and onboarding checks that the upstream commands the prompts reference are actually installed.

## Requirements
### Requirement: gatedloop ships no command that duplicates a maintained upstream asset
The plugin SHALL NOT ship a command, skill, or template that reproduces the content of an asset installed and maintained by OpenSpec or by a community schema. Artifact authoring SHALL be deferred to the upstream `/opsx:*` commands. A command MAY delegate to an upstream command in order to add a guarantee upstream does not make, provided it holds no copy of the upstream prompt.

#### Scenario: The forked authoring commands are gone
- **WHEN** the plugin's `commands/` directory is listed
- **THEN** it contains no `explore.md` or `propose.md`

#### Scenario: A contributor proposes re-adding an authoring command
- **WHEN** a command is proposed whose function is already provided by an upstream `/opsx:*` command
- **THEN** the `no-forked-upstream-assets` rule rejects it, and the reviewer can cite that rule-id

#### Scenario: A delegating command is proposed
- **WHEN** a command delegates to an upstream command and adds an enforceable guarantee, holding no copy of the upstream prompt
- **THEN** the rule permits it, and the retained delegation is the whole of its content

#### Scenario: A delegating command accumulates upstream logic
- **WHEN** a delegating command grows a step that reproduces upstream behaviour rather than adding a guarantee
- **THEN** it is treated as a fork and the rule rejects it

#### Scenario: Commands with no upstream equivalent are retained
- **WHEN** the retained command set is checked
- **THEN** it contains the onboarding command, the session-brief command, and the `tdd-apply` skill, none of which has an upstream equivalent

### Requirement: Archiving a change leaves no uncommitted move
Archiving SHALL record the archive in git rather than leaving the moved change directory in the working tree.

#### Scenario: The archive is committed
- **WHEN** a completed change is archived through gatedloop
- **THEN** the moved directory is staged and committed, and the working tree is clean with respect to the move

#### Scenario: The commit fails
- **WHEN** the archive commit cannot be made
- **THEN** the failure is surfaced and the command stops, rather than reporting success over an uncommitted archive

### Requirement: The upstream command surface is a checked prerequisite
Onboarding SHALL verify that OpenSpec's Claude Code integration is installed, rather than assuming it. Presence SHALL be established per referenced command, not by the existence of a containing directory, and OpenSpec's own presence SHALL be established from the root it resolves rather than from a command's exit status.

#### Scenario: The integration is missing
- **WHEN** onboarding runs in a project where `.claude/commands/opsx/` does not exist
- **THEN** it reports the missing prerequisite and offers to run `openspec init --tools claude`

#### Scenario: The integration is partially installed
- **WHEN** onboarding runs in a project where `.claude/commands/opsx/` exists but does not contain every command gatedloop's prompts reference
- **THEN** it names the specific missing commands and offers to run `openspec init --tools claude`, rather than reporting a pass

#### Scenario: OpenSpec is absent
- **WHEN** onboarding runs in a directory with no `openspec/` anywhere above it
- **THEN** it detects the absence from the resolved root being implicit, and does not treat the command's zero exit status as proof of initialization

#### Scenario: The integration is present
- **WHEN** onboarding runs in a project where every referenced upstream command is installed
- **THEN** the preflight passes without prompting

#### Scenario: The user declines installation
- **WHEN** the user declines the offer to install the upstream integration
- **THEN** onboarding reports that the authoring half of the workflow will be unavailable, and does not write a partial configuration

#### Scenario: The generated commands have been modified locally
- **WHEN** onboarding finds the upstream commands present but edited
- **THEN** it warns once that those edits may not survive an upstream update, and names the supported alternative

### Requirement: Customisation is directed at the schema, not the generated commands
Documentation SHALL identify forking a schema as the supported way to change how artifacts are authored, and SHALL state that editing OpenSpec's generated command files is not supported.

#### Scenario: An adopter wants different artifacts or different prompts
- **WHEN** a reader asks how to change what authoring produces
- **THEN** the docs direct them to fork the schema, which is their own file and survives an upstream update

#### Scenario: An adopter has already edited a generated command
- **WHEN** local edits exist in OpenSpec's generated commands
- **THEN** the docs explain that an upstream update may overwrite them and how to express the same intent as a schema fork

### Requirement: Cross-references point at the maintaining project
Every reference to artifact authoring in shipped prompts and documentation SHALL name the upstream command, and every reference to the loop SHALL name the gatedloop command.

#### Scenario: A shipped prompt refers to proposing a change
- **WHEN** any command, skill, agent, or hook output refers to creating a change proposal
- **THEN** it names `/opsx:propose` rather than a `/gatedloop:` equivalent

#### Scenario: The session brief offers next actions
- **WHEN** the SessionStart brief presents a menu grounded in live OpenSpec state
- **THEN** authoring actions are offered as upstream commands and loop actions as gatedloop commands

#### Scenario: The brief runs where a referenced command is not installed
- **WHEN** the SessionStart brief runs in a project missing one of the upstream commands its menu names
- **THEN** that entry is omitted rather than offered, so the menu never sends the user at a command that does not resolve

#### Scenario: The brief runs with no OpenSpec state
- **WHEN** the SessionStart brief runs in a project where OpenSpec is not initialized
- **THEN** it offers onboarding as the single next step instead of a menu of loop commands that have nothing to consume

#### Scenario: The README shows where the handoff happens
- **WHEN** a reader looks at the README's workflow diagram
- **THEN** it distinguishes the artifacts upstream produces from the loop gatedloop runs, rather than presenting one uniform `/gatedloop:` pipeline

### Requirement: The conventions rules-doc forbids future forks
The rules-doc SHALL carry a stable rule-id forbidding forked upstream assets, replacing the rule that mandated the `/gatedloop:` namespace for all references.

#### Scenario: The obsolete rule is retired
- **WHEN** the rules-doc is inspected after this change
- **THEN** it contains no rule describing `/opsx:` as a legacy prefix

#### Scenario: The replacement rule resolves
- **WHEN** `gates rules` resolves rule-ids for a diff touching `commands/`
- **THEN** `no-forked-upstream-assets` is among the resolvable ids, and a review finding can cite it

