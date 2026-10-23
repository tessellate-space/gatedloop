# manifest-parsing — delta for gate-preconditions

## ADDED Requirements

### Requirement: The gate mapping form parses identically on both YAML paths

The stdlib fallback parser SHALL parse the gate/live-check mapping form —
block form and single-level inline flow form (`{run: "...", requires: "..."}`,
string values, comma- and quote-aware) — to the same structure PyYAML produces
for the same text. A flow mapping MUST never silently parse as a literal string
on a PyYAML-less machine: it either parses as a mapping or the manifest load
fails loudly.

#### Scenario: Block mapping form agrees

- **WHEN** a manifest declares a gate in block form (`run:` and `requires:` as nested keys) and is parsed with and without PyYAML available
- **THEN** both paths produce the same mapping with the same string values

#### Scenario: Inline flow mapping form agrees

- **WHEN** a manifest declares `integration: {run: "just it", requires: "just stack-check"}` (including quoted values containing commas or colons) and is parsed with and without PyYAML available
- **THEN** both paths produce the same mapping with the same string values

#### Scenario: A flow mapping never degrades to a string

- **WHEN** the stdlib fallback encounters a `{...}` value it cannot parse as the supported flow-mapping subset
- **THEN** the load or validation fails loudly naming the value; the text is never returned as a command string
