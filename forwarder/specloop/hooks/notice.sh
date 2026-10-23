#!/usr/bin/env bash
# SessionStart: the forwarder's one job (rename-to-gatedloop, design D4). An
# existing install of the earlier plugin name updates onto this forwarder, so
# every session it starts shows the user how to switch, and tells Claude to
# say so before anything else. It runs nothing else: no gate, no loop.
set -uo pipefail

root="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

python3 - "${root}/NOTICE" <<'PY'
import json
import sys

notice = open(sys.argv[1]).read().strip()
print(json.dumps({
    "systemMessage": notice,
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": (
            "At the START of your first reply, show the user this notice verbatim, "
            "then continue with what they asked. Run none of the earlier plugin's "
            "commands: they are stubs that only repeat it.\n\n" + notice
        ),
    },
}))
PY
