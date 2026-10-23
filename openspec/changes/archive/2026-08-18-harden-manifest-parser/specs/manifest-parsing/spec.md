## Purpose

Defines the correctness contract for how the `harness` shim reads a project
manifest: the stdlib YAML fallback must agree with PyYAML on every value the
manifest can hold, and the starter template the plugin ships must validate
unmodified.

## ADDED Requirements

### Requirement: Stdlib fallback preserves prose scalars containing colons

The manifest reader SHALL parse a block-list item that is a quoted scalar as a
string, even when that string contains a colon, and SHALL NOT reinterpret it as a
key/value mapping. The stdlib fallback (used when PyYAML is not importable) SHALL
produce the same parsed value as PyYAML for any manifest the plugin documents as
valid, so that a manifest that works for an author with PyYAML installed does not
corrupt for an adopter without it.

Inline prose rules are a documented alternative to rule-ids; prose routinely
contains colons.

#### Scenario: Block-list prose rule with a colon parses to a string

- **WHEN** a surface declares `rules:` as a block list whose item is the quoted
  scalar `"Prefer composition: avoid deep inheritance"` and the manifest is read
  through the stdlib fallback
- **THEN** the surface's `rules` is a list of strings whose single element is the
  exact string `Prefer composition: avoid deep inheritance`
- **AND** no element is a mapping

#### Scenario: Inline flow prose rule with a colon parses to a string

- **WHEN** a surface declares `rules: ["Prefer composition: avoid deep inheritance"]`
  as an inline flow list and the manifest is read through the stdlib fallback
- **THEN** the surface's `rules` is a list of strings whose single element is the
  exact string `Prefer composition: avoid deep inheritance`

#### Scenario: Fallback and PyYAML agree

- **WHEN** the same manifest containing prose rules with colons is parsed once
  through the stdlib fallback and once through PyYAML
- **THEN** the two parse results are equal

#### Scenario: A genuine block-list mapping still parses as a mapping

- **WHEN** a block-list item is an unquoted `key: value` entry (for example a
  `surfaces` entry such as `- name: all`)
- **THEN** the item parses to a mapping, preserving existing manifest behavior

### Requirement: The shipped starter template validates unmodified

The starter manifest template the plugin ships SHALL pass `harness validate` when
copied to a repository without edits. Any rule-id the template references SHALL be
resolvable in the rules-doc the template points at, or the template SHALL ship no
rule-id example at all. This upholds the stated goal of `/specloop:harness-init`
that `harness validate` passes after initialization.

#### Scenario: Fresh template validates

- **WHEN** the shipped starter template is dropped into a repository as the
  manifest and `harness validate` is run against it
- **THEN** validation exits 0 with no unresolved rule-id error

#### Scenario: No dangling rule-id reference

- **WHEN** the starter template references a rule-id in a surface's `rules`
- **THEN** that rule-id is defined in the rules-doc the template's `conventions`
  block points at
