---
description: Project brief — show a tailored menu of what to work on next
---

Current project status:

!`bash "${CLAUDE_PLUGIN_ROOT}/hooks/session-brief.sh" 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin)["hookSpecificOutput"]["additionalContext"])' 2>/dev/null`

The status above is produced by the same hook that runs at SessionStart, and it already
carries the tailored directive — including a menu built from the entry points this project
**actually has installed**. Follow that directive.

Offer only what it lists. Do not restore an entry it leaves out: an omission means the
command is not installed here, and naming it would send the user at something that does not
resolve. If it reports no OpenSpec state, offer onboarding only.

Then ask which they want. Don't start work until they choose — this holds even when
the status above names spawning the tdd-implementer subagent as the default action
for an approved, unimplemented change: "default" means which option to lead with,
never permission to start it unprompted.
