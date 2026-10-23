## Purpose

A permanent, privacy-bounded channel from a running Specloop back to its own repository: a skill that files structured GitHub issues — bug/friction reports and positive confirmations alike — gathering only whitelisted context and never sending anything a human has not seen and approved.

## ADDED Requirements

### Requirement: Context is collected only from a fixed whitelist

The `/specloop:feedback` skill SHALL gather report context deterministically and only from a fixed allowlist: plugin version, OpenSpec CLI version, `gates doctor` / `gates validate` output, the command or gate the report concerns, the `.gates.yaml` *shape* (gate names and surface globs), and OS/platform. It SHALL NOT read or include any item outside that list — in particular, diff content, file contents from the adopter's project, or gate command bodies. The boundary SHALL be a positive allowlist, so that a context source not explicitly whitelisted is excluded by default rather than stripped by exception.

#### Scenario: Whitelisted context is gathered

- **WHEN** the skill prepares a report
- **THEN** it collects the plugin version, OpenSpec CLI version, `gates doctor`/`gates validate` output, the command or gate involved, the `.gates.yaml` gate names and surface globs, and the OS/platform, and nothing else

#### Scenario: Gate command bodies are never read

- **WHEN** the skill records the `.gates.yaml` shape
- **THEN** it includes the gate names and the surface globs only, and never the command string a gate name maps to

#### Scenario: A non-whitelisted source is not collected

- **WHEN** the report concerns a failure whose fullest context would be a project file or a diff
- **THEN** the skill does not read or attach that content, and instead directs the tester to paste by hand only what they choose to disclose

### Requirement: The complete issue body is shown and approved before any send

The skill SHALL present the complete, literal issue body — the exact text that will be posted — to the tester, and SHALL post nothing until the tester explicitly approves. A summary or description of what will be sent SHALL NOT substitute for the literal body.

#### Scenario: The tester approves the literal body

- **WHEN** the skill has assembled the issue body and the tester reviews it
- **THEN** the exact markdown that will be posted is shown in full, and only an explicit approval causes it to be sent

#### Scenario: The tester declines

- **WHEN** the tester does not approve the shown body
- **THEN** nothing is posted, and the report is not sent by any other path

#### Scenario: No send precedes the approval

- **WHEN** the skill runs to the point of showing the body
- **THEN** no network call that could publish the report has yet been made

### Requirement: Reports go to Specloop's own repository, resolved from plugin metadata

The skill SHALL file issues against Specloop's own repository, and SHALL resolve the repository slug from the plugin's own metadata (`plugin.json`'s `repository`) rather than hard-coding it in prompt prose. It SHALL NOT target the adopter's project repository.

#### Scenario: The target repository is Specloop's own

- **WHEN** the skill posts a report
- **THEN** the destination is the repository named in the plugin's metadata, not the repository of the project under test

#### Scenario: The slug has a single source

- **WHEN** the skill or a shipped issue template needs the repository slug
- **THEN** it derives it from the plugin metadata, so a fork or rename does not leave a stale slug pointing reports at the wrong tracker

### Requirement: A missing forge CLI degrades loud, never silent

When the forge CLI (`gh`) is absent, unauthenticated, or offline, the skill SHALL print the full issue body and a manual-filing URL for Specloop's issue tracker, and SHALL state plainly that it did not post. It SHALL NOT drop the report silently and SHALL NOT fall back to any unbounded collection.

#### Scenario: gh is unavailable

- **WHEN** `gh` is not installed, not authenticated, or cannot reach the network at post time
- **THEN** the skill prints the complete issue body and the issues URL for manual filing, and reports that nothing was posted automatically

#### Scenario: The report is never silently lost

- **WHEN** any step of the automatic post fails
- **THEN** the tester is left with the full body to file by hand, rather than a success message over an unsent report

### Requirement: Both positive and negative reports are supported, distinguished at the source

The skill SHALL collect both friction/bug reports and positive "this worked" confirmations, applying a label that distinguishes the two at creation time. The whitelist, the show-before-send approval, and the degradation path SHALL be identical for both kinds.

#### Scenario: A positive confirmation is filed

- **WHEN** a tester reports that Specloop worked in their stack
- **THEN** the skill files it as a field report distinguished by label from a bug/friction report, under the same privacy and approval rules

#### Scenario: A friction report is filed

- **WHEN** a tester reports a bug or friction
- **THEN** the skill files it with the bug/friction label, under the same privacy and approval rules

### Requirement: Issue templates mirror the skill's fields

The repository SHALL ship `.github/ISSUE_TEMPLATE/` entries whose fields mirror the skill's whitelisted structure, so that a report filed directly on GitHub — outside the skill — carries the same shape and prompts for the same bounded context.

#### Scenario: A report arrives outside the skill

- **WHEN** a contributor opens an issue on the tracker without using the skill
- **THEN** a template for a bug/friction report and one for a positive field report are offered, each asking for the same whitelisted fields the skill collects

#### Scenario: Templates do not solicit unbounded context

- **WHEN** an issue template asks for context
- **THEN** it asks only for the whitelisted fields, and does not instruct the reporter to paste diffs, project files, or gate command bodies
