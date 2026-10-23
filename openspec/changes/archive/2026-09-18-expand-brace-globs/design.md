# Design: expand-brace-globs

## Context

See `proposal.md` — Why. `bin/gates` matches with `fnmatch.fnmatch(path,
glob.replace("**", "*"))` (`_matches`). `fnmatch` treats `{` as a literal, so a brace
pattern matches only a path that literally contains `{` — in practice, nothing. The
selection drives both convention-review scope and live-check probes, so an empty
selection silently disables both. `zero-dep-shim` forbids reaching for a globbing
library.

## Goals / Non-Goals

**Goals:** correct expansion for the manifest subset people actually write (one or
more groups, possibly nested, no escaping); loud rejection of everything else; the
repo's own manifest as the fixture.

**Non-Goals:** full bash brace semantics (numeric ranges `{1..9}`, escaped braces,
empty alternatives as a feature); touching the `**`→`*` approximation, which is a
separate, documented "err hot" trade-off.

## Decisions

### D1: Pre-expand at manifest load, not per match call

Expansion happens once when surfaces are read: each `match` pattern becomes a list of
brace-free patterns, and `_matches` tests the path against each. Expanding at load
time keeps the per-path hot loop unchanged and gives `gates validate` one place to
reject unexpandable patterns — the same expansion function, so validation and matching
cannot disagree.

**Rejected — expand inside `_matches`:** re-expands on every call and leaves
validation to reimplement (or skip) the same parsing.

### D2: A small recursive expander, strict about what it accepts

Stdlib-only: scan for the first `{`, find its balanced `}`, split top-level commas,
recurse on each alternative. Rules: unbalanced braces → error; an empty group `{}` or
empty alternative → error (an accident, not a feature); a pattern with no `{` passes
through unchanged. An expansion cap (e.g. 512 alternatives) guards against a
pathological manifest, failing loud when exceeded.

**Rejected — regex-based single-level expansion:** silently wrong on nesting, which is
exactly the silent-wrongness this change removes.

### D3: Validation rejects, matching never sees an invalid pattern

`gates validate` runs the expander over every surface's `match` and reports all
failures at once (existing validate style: collect, then exit 1). Because runtime
selection uses the same loader, an invalid pattern can only reach `_matches` in a
project that never validates — and there the loader raises the same named error rather
than degrading to empty selection (`fail-loud-gates`).

## Risks / Trade-offs

- **[Behavior change for dead patterns]** Adopter manifests with brace globs suddenly
  start selecting surfaces, enlarging review scope / live-check runs. → This is the
  spec's pinned error direction (err hot); release note says so explicitly.
- **[Divergence from bash semantics]** Someone expects `{1..3}`. → Strict rejection at
  validate names the pattern; the error message states the supported subset.

## Open Questions

None.
