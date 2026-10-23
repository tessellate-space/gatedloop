# Proposal

## Why

Issue #40: in a fresh local session, `gates` was not on the Bash tool's PATH (`which gates` → not found), although the plugin was enabled, its SessionStart brief printed and its PreToolUse hooks fired. The binary existed in the plugin cache and worked by full path. No plugin's `bin/` was on PATH. The session ran under a non-default `CLAUDE_CONFIG_DIR`. The Claude Code-side cause is unverified.

Every shipped prompt runs `gates …` by name, so the whole loop fails on the first gate call. The obvious workaround, the versioned cache path, breaks on the next update.

Claude Code's docs say a plugin's `bin/` is on the Bash tool's PATH "while the plugin is enabled". They say nothing on the conditions the report hit.

`gates doctor` didn't catch it, and couldn't. Its `plugin-registered` row decides on `CLAUDE_PLUGIN_ROOT`, which is set for hook processes but not in the Bash tool's environment. Verified in a live session: unset. So, run from Bash, the row warns whether or not the plugin is loaded. It misled this report towards the config-profile case, and it misleads everyone else too.

## What Changes

- **A fallback PATH from the brief.** When the SessionStart hook runs with both `CLAUDE_PLUGIN_ROOT` and `CLAUDE_ENV_FILE` set, it appends `export PATH="$PATH:$CLAUDE_PLUGIN_ROOT/bin"` to `$CLAUDE_ENV_FILE`, unless that line is already there. Claude Code runs `$CLAUDE_ENV_FILE` as a preamble before each Bash command. The entry goes last, so a `gates` already on PATH, including the normal injection, still wins. When either variable is absent, the hook writes nothing, because the docs don't say whether plugin hooks receive `CLAUDE_ENV_FILE`.
- **A doctor row for what actually matters.** `gates-on-path` checks that `gates` resolves on PATH. It reports ok with the path it found, or warns with the remedy: start a new session, add the export line, or see SETUP's troubleshooting note.
- **An honest `plugin-registered` row.** It no longer warns because `CLAUDE_PLUGIN_ROOT` is unset. It reports where the running shim lives instead: an installed plugin copy (with its version, from the path), or a checkout. It says plainly that registration for the session can't be seen from the Bash tool, and keeps the `CLAUDE_CONFIG_DIR` pointer for the case where no Specloop surface appears at all.
- **Docs.** SETUP gets a troubleshooting note for "plugin active, but `gates` not found", separate from the profile-mismatch note.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `onboarding`:
  - the doctor reports whether `gates` resolves and where the shim runs from;
  - the session brief adds the fallback PATH entry.

## Impact

- `hooks/session-brief.sh`
- `bin/gates`: `doctor_checks` and `cmd_doctor`
- `SETUP.md`
- tests
