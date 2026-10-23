## Context

See `proposal.md — Why` for motivation. Two facts about the current shim shape the
fix:

- **The parser.** `bin/harness` parses the manifest with PyYAML when importable and
  otherwise with `_mini_yaml`, a stdlib fallback that keeps the plugin dependency-free
  (`zero-dep-shim`). In `_mini_yaml`, `parse_list` (bin/harness:150) classifies a
  block-list item as a mapping whenever `":" in rest and not rest.startswith("[")`.
  A quoted scalar item such as `- "Prefer composition: avoid deep inheritance"`
  therefore partitions on its first colon into `{'"Prefer composition': 'avoid deep
  inheritance"'}`. The colon-scan is quote-blind, unlike `_strip_comment`
  (bin/harness:77), which already walks a line tracking quote state.

- **The validator.** `_errors` (bin/harness:207) classifies each `rules` entry with
  `is_id = (" " not in rule) and len(rule) <= 60`: an entry with a space or over 60
  chars is treated as inline prose and never resolved; a short spaceless entry is a
  rule-id and must appear in `conventions.rules-doc`. The shipped template's
  `rules: [conventions]` is a rule-id by that test, and neither an adopter's repo nor
  this one defines a `conventions` id, so a fresh `harness validate` fails.

## Goals / Non-Goals

**Goals:**

- The stdlib fallback parses a quoted block-list scalar containing a colon as a
  string, matching PyYAML.
- The shipped starter template passes `harness validate` when copied unmodified.
- A regression test exists for each finding, runnable with the stdlib alone.

**Non-Goals:**

- A general-purpose YAML parser. `_mini_yaml` stays a minimal parser for the manifest
  subset; we fix the colon classification, not the long tail of YAML.
- Resolving the `openspec/config.yaml` conventions double-duty defect — that is
  `reposition-specloop` section 1's, and this change only ships a template that
  validates today so that change can reconcile it (see Risks).
- Standing up a full test framework. One stdlib `unittest` file is enough.

## Decisions

### D1 — Classify a block-list item as a mapping only on a colon *outside quotes*

Replace the quote-blind `":" in rest` test in `parse_list` with a helper that reports
whether a line contains a colon outside quoted spans, reusing the same quote-tracking
loop `_strip_comment` already uses. A fully-quoted scalar item then has no
bare colon → it is parsed as a scalar via `_scalar`. A genuine `key: value` item
(e.g. `- name: all`) still has a bare colon → still a mapping.

*Alternative considered — special-case items that start and end with a quote.* Works
for the reported case but misses `- foo: "a: b"` (bare colon before a quoted colon)
and duplicates quote logic ad hoc. A single "colon outside quotes" predicate is the
same tool `_strip_comment` uses and covers both. Chosen.

*Note on the inline-flow form.* `rules: ["…: …"]` already parses correctly today
(`_scalar` splits the flow body on commas, and a single element with a colon survives),
so D1 targets the block-list form. The spec still pins the inline-flow behavior with a
scenario so a future refactor of `_scalar` can't regress it.

### D2 — Ship a template that self-validates on inline prose; demote rule-ids to commented guidance

The default surface's `rules` becomes a single inline-prose entry (contains spaces →
`is_id` is false → never resolved against a rules-doc → validates with no external
file). The rule-id + `conventions.rules-doc` form stays in the template as commented
guidance, so both documented styles are still taught but the out-of-the-box file is
green.

*Alternative considered — ship a rules-doc plus a resolvable rule-id.* Rejected: the
template alone cannot guarantee the adopter's repo contains the referenced rules-doc
file, so `harness validate` would still fail for anyone who copies only the manifest;
and hard-coding this repo's own rule-ids into an adopter-facing template is exactly the
`openspec/config.yaml` double-duty knot `reposition-specloop` is untangling. Inline
prose is self-contained and needs no companion file.

The prose example may include a colon, which makes the shipped template itself an
end-to-end exercise of D1 under the fallback — but the template's *validity* must not
silently depend on the parser fix, so the template regression test (D3) asserts both
that it parses to the expected shape and that it validates.

### D3 — One stdlib `unittest` file, loading the shim by path

The repo ships no test suite; add a single `unittest` module (stdlib only, no new
dependency — `zero-dep-shim`). Because `bin/harness` has no `.py` extension, the test
loads it with `importlib.util.spec_from_file_location` and exercises `_mini_yaml`,
`_load`, and `_errors` directly. Coverage:

- Finding 1: a manifest with a colon-bearing prose rule in both block-list and
  inline-flow form parses to `list[str]` under `_mini_yaml`; and, when PyYAML is
  importable, `_mini_yaml` output equals PyYAML output for that manifest.
- Finding 2: the shipped `templates/harness.yaml.template`, parsed and passed to
  `_errors`, yields no errors.

Running the tests is `python3 -m unittest` from the repo root — documented in
`CLAUDE.md`'s Commands section alongside the shim invocations.

## Risks / Trade-offs

- **Template collides with `reposition-specloop`.** → That change moves rule-id prose
  into a dedicated conventions source and generates `config.yaml`'s `rules:` from it;
  it must then reconcile this template's inline-prose default and remove the
  workaround second source `docs/specloop-conventions.md` that onboarding wrote to
  dodge Finding 2. Recorded here and cross-referenced in the proposal so it is not
  lost; this change deliberately does **not** pre-empt that work.
- **A "colon outside quotes" predicate is still not full YAML.** → It handles the
  manifest subset (`'` and `"` quoting, no block scalars, no anchors), which is all
  the manifest allows; the spec's parity scenario guards against divergence from
  PyYAML for documented manifests.
- **First test file sets a precedent.** → Keeping it stdlib `unittest` with no runner
  or config avoids implying a heavier framework; it is a regression net, not a suite.

## Open Questions

None. The template's inline-prose default and the test's placement are settled above;
neither changes the specs or the task breakdown.
