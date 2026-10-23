# Design

## Context

What Claude Code's documentation says:

- **Plugin `bin/`.** "Files in `bin/` at the plugin root are on the `PATH` of the Bash tool's shell while the plugin is enabled." Nothing says when that can fail beyond claude.ai and Cowork.
- **`CLAUDE_ENV_FILE`.** It is written by `SessionStart` (and `CwdChanged`) hooks, and Claude Code runs it "as a script preamble before each Bash command". The docs don't say whether plugin-defined hooks receive it, whether subagents' Bash calls get it, or how several writers combine.
- **`CLAUDE_PLUGIN_ROOT`.** Documented for hook and MCP processes. The docs don't say it is in the Bash tool's environment, and in a live session it is not.

## Decisions

### D1. The brief appends a fallback, never a replacement

In `hooks/session-brief.sh`, before the brief is printed:

```sh
if [ -n "${CLAUDE_ENV_FILE:-}" ] && [ -n "${CLAUDE_PLUGIN_ROOT:-}" ] && [ -x "${CLAUDE_PLUGIN_ROOT}/bin/gates" ]; then
  line="export PATH=\"\$PATH:${CLAUDE_PLUGIN_ROOT}/bin\""
  grep -qxF "$line" "$CLAUDE_ENV_FILE" 2>/dev/null || printf '%s\n' "$line" >> "$CLAUDE_ENV_FILE"
fi
```

How the line is built:
- **Appended to PATH, not prepended,** so an existing `gates` keeps precedence: the normal injection, or an adopter's own wrapper.
- **The plugin root is expanded when written,** so the line names this install. The next session, after an update, writes the new path.
- **Idempotent.** A resume or a second SessionStart in the same session doesn't stack duplicates.
- **Appended to the file, never truncating it,** so another hook's lines in the same file survive.
- **Failures are ignored,** like every other part of the brief. The brief never blocks a session.

If plugin hooks don't receive `CLAUDE_ENV_FILE`, the first test shows it, and nothing changes. D2's row then names the manual remedy.

### D2. `gates-on-path`

`doctor_checks` takes a new primitive: the path `shutil.which("gates")` returns, which `cmd_doctor` gathers.

- **Found:** ok, naming the path. If it isn't the running shim, the row also says so, because a stale copy on PATH is worth knowing about.
- **Not found:** warn: "`gates` is not on this shell's PATH, so every `gates …` step in Specloop's commands and skills fails." The remedies are:
  1. start a new session, which re-runs the SessionStart fallback;
  2. `export PATH="$PATH:<this shim's bin dir>"`, with the dir computed from the shim's own path, never hard-coded;
  3. see SETUP's note.

This is the check #40 needed: the symptom, not a proxy for it.

### D3. `plugin-registered` stops reading `CLAUDE_PLUGIN_ROOT`

The row is renamed `shim-location` and reports one of three things, worked out from the running shim's resolved path:
- **The installed plugin.** The path has a `plugins/cache/<marketplace>/<plugin>/<version>/bin/gates` shape; the row names the version.
- **A checkout.** The shim lives in a git work tree with `.claude-plugin/plugin.json`: "running from a checkout, not the installed plugin".
- **Elsewhere.** It names the path.

All three are `ok`, because none of them is a fault. The row adds one sentence: whether the plugin's commands and hooks are registered for this session can't be seen from the Bash tool, and if no Specloop command, skill or session brief appears at all, see the `CLAUDE_CONFIG_DIR` note. That keeps the guidance the old warning carried, without the false alarm.

### D4. SETUP

Under troubleshooting, a new entry: **"The plugin is active but `gates` is not found."**
- the symptom;
- that the SessionStart hook now adds a fallback PATH entry in a new session;
- the manual export line, using the plugin root rather than a versioned path;
- that `gates doctor`'s `gates-on-path` row reports it.

The existing `CLAUDE_CONFIG_DIR` entry stays, for the case where nothing from Specloop appears at all.

## Risks

- **A PATH preamble in `CLAUDE_ENV_FILE` interacts with an adopter's own direnv hook.** Both append to one file, and D1 never truncates, so both survive. If direnv rewrites PATH completely afterwards, the fallback is lost and `gates-on-path` reports it.
