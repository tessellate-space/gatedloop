## Why

Running the plugin live against real fixtures during `unfork-commands` task 7.1
surfaced two shim-level correctness defects: the zero-dependency YAML fallback in
`bin/harness` silently corrupts inline prose rules that contain a colon, and the
starter template Specloop ships fails `harness validate` the moment an adopter
drops it in. Both break the adopter's very first experience, and the first one
breaks it *only* for adopters (it depends on whether PyYAML is importable), so the
author never sees it.

## What Changes

- **Fix `_mini_yaml` colon handling.** A block-list item that is a quoted scalar
  (e.g. `- "Prefer composition: avoid deep inheritance"`) is currently parsed as a
  map because `parse_list` treats any `":" in rest` as a key/value entry. It must
  be preserved as a string. Colon detection for the map-vs-scalar decision must
  ignore colons inside quotes, matching how `_strip_comment` already scans quoted
  spans. This only manifests when the stdlib fallback runs (PyYAML absent), so the
  fix restores parity between the fallback and PyYAML.
- **Make the shipped starter template validate out of the box.**
  `templates/harness.yaml.template` references a `conventions` rule-id that no
  rules-doc defines, so a fresh `harness validate` fails immediately —
  contradicting `/specloop:harness-init`, whose stated goal is that
  `harness validate` passes afterwards. The template will ship an example that
  self-validates (or ships no rule-id example at all; resolved in design).
- **Add regression tests** that would have caught each finding: a parser test
  asserting prose-with-colons rules parse to `list[str]` under the fallback, and a
  template test asserting the shipped starter passes `harness validate`.

## Capabilities

### New Capabilities
- `manifest-parsing`: the correctness contract for how `bin/harness` reads a
  `.harness.yaml` manifest — specifically that the stdlib YAML fallback preserves
  prose scalars byte-for-byte with PyYAML, and that the starter template the plugin
  ships validates unmodified.

### Modified Capabilities
<!-- No landed spec's requirements change; the affected behavior has no existing
     spec. `reposition-specloop` section 1 owns the conventions rules-doc knot that
     Finding 2 touches, but that change has not landed and this one does not modify
     its delta. -->

## Impact

- **Code**: `bin/harness` (`_mini_yaml` / `parse_list` and the colon-scan helper),
  `templates/harness.yaml.template`. A new regression test harness for the shim
  (the repo currently ships no test suite — see design for placement).
- **Docs**: none required, but the inline-prose-rules example in `CLAUDE.md` and the
  template comments are the documented contract this fix protects.
- **Cross-change ordering**: Finding 2 touches the same knot as
  `reposition-specloop` section 1, which moves rule-id prose out of
  `openspec/config.yaml` into a dedicated conventions source and generates the
  `config.yaml` `rules:` block from it. This change ships a template that validates
  *today*; `reposition-specloop` must then reconcile that template with the new
  conventions source. Onboarding was already observed working around Finding 2 by
  writing a second conventions source (`docs/specloop-conventions.md`) — that
  duplication is `reposition-specloop`'s to resolve, not this change's.
- **Adopter-facing**: no breaking change. Manifests that parse correctly under
  PyYAML today keep parsing correctly; only the broken fallback path changes.
