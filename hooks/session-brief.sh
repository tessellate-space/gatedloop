#!/usr/bin/env bash
# SessionStart briefing: gather live project state (OpenSpec changes + git) and
# inject a directive so the agent opens its first reply with a short, tailored
# menu instead of a blank prompt. Emits SessionStart additionalContext JSON.
#
# Stack-agnostic: gate hints go through `gates run`, resolved from the
# project's .gates.yaml. Three states, not two: no OpenSpec (offer onboarding);
# OpenSpec present but no gate manifest yet — the likely brownfield-adopter
# state, where every loop command below would read a file that doesn't exist
# (offer /gatedloop:gates-init, and only that); OpenSpec + manifest (the full
# menu). Advertising a menu of commands that are not installed, or that read a
# manifest that isn't there, is worse than saying nothing, so every entry below
# is gated on the command actually being present.
set -uo pipefail

# The helper ships with the plugin; CLAUDE_PLUGIN_ROOT points at the plugin dir.
# Falling back to this script's own directory means NOT re-appending `hooks/` —
# the script already lives there. (Getting this wrong silently drops the OpenSpec
# half of the brief, because the pipeline below swallows the error.)
if [ -n "${CLAUDE_PLUGIN_ROOT:-}" ]; then
  HELPER="${CLAUDE_PLUGIN_ROOT}/hooks/_session_brief.py"
else
  HELPER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_session_brief.py"
fi

# Fallback PATH entry for the shim (gates-on-path D1, issue #40). Claude Code
# runs $CLAUDE_ENV_FILE before each Bash command; where the plugin's bin/ was
# not injected, this line makes `gates` resolve anyway. Appended to PATH so an
# existing `gates` still wins, appended to the file so other writers' lines
# survive, written once per file, and never allowed to fail the brief.
if [ -n "${CLAUDE_ENV_FILE:-}" ] && [ -n "${CLAUDE_PLUGIN_ROOT:-}" ] \
  && [ -x "${CLAUDE_PLUGIN_ROOT}/bin/gates" ]; then
  path_line="export PATH=\"\$PATH:${CLAUDE_PLUGIN_ROOT}/bin\""
  { grep -qxF "${path_line}" "${CLAUDE_ENV_FILE}" \
    || printf '%s\n' "${path_line}" >> "${CLAUDE_ENV_FILE}"; } 2>/dev/null || true
fi
cd "${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}" 2>/dev/null || true

branch=$(git branch --show-current 2>/dev/null || echo "?")
dirty=$(git status --porcelain 2>/dev/null | grep -c . || true)

changes_summary=$(openspec list --json 2>/dev/null | python3 "${HELPER}" 2>/dev/null || true)

# `openspec list --json` exits 0 even with no openspec/ anywhere, so its status
# proves nothing. root.source == "implicit" is the real absence signal.
os_source=$(openspec list --json 2>/dev/null \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["root"]["source"])' 2>/dev/null \
  || echo "implicit")
opsx() { [ -f ".claude/commands/opsx/$1.md" ]; }

# Same manifest names `bin/gates` itself resolves — the legacy `.harness.*`
# fallback is retired (`remove-harness-compat`), so this check can't disagree
# with what `gates` sees.
gate_manifest_exists() {
  for f in .gates.yaml .gates.yml .gates.json; do
    [ -f "${f}" ] && return 0
  done
  return 1
}

ctx="Session brief — git: on '${branch}', ${dirty} uncommitted file(s)."
if [ -n "${changes_summary}" ]; then
  ctx="${ctx}
OpenSpec:
${changes_summary}"
fi

if [ "${os_source}" = "implicit" ]; then
  # Nothing to run the loop over. One honest next step beats a dead menu.
  ctx="${ctx}

This project has no OpenSpec state, so the gatedloop loop has nothing to consume yet.
At the START of your first reply, greet in one line, say that plainly, and offer exactly ONE next step: /gatedloop:gates-init, which checks the prerequisites and offers to run 'openspec init --tools claude' before writing anything. Do not list the loop commands — they have nothing to act on. Start nothing unprompted."
elif ! gate_manifest_exists; then
  # The half-onboarded state: OpenSpec is set up but gatedloop's own manifest
  # isn't. Every loop command below reads .gates.yaml — offering them here
  # would send the user at commands that fail for a reason the brief already
  # knows and didn't say.
  ctx="${ctx}

OpenSpec is set up, but this project has no gatedloop gate manifest (.gates.yaml) yet, so none of the loop commands below can run.
At the START of your first reply, greet in one line, say that plainly, and offer exactly ONE next step: /gatedloop:gates-init, which detects candidate gates, confirms them with you, and writes a valid manifest. Do not list the loop commands — they would read a file that doesn't exist. Start nothing unprompted."
else
  menu=""
  if opsx explore || opsx propose; then
    menu="${menu}
- think through an idea, or author a change: /opsx:explore, then /opsx:propose"
  fi
  menu="${menu}
- continue a change already underway: /gatedloop:tdd-apply <name>
- for a change the status above lists as \"approved and ready to implement\":
  offer spawning the tdd-implementer subagent (Sonnet, resumable, halts on
  ambiguity, STOPS before the merge) with the change name as the DEFAULT action —
  it is the cheapest path and the plan is already reviewed — with
  /gatedloop:tdd-apply <name> (interactive, pauses on ambiguity) as the alternative.
  When its line says \"dispatch test-author, then the implementer\", the default
  is to dispatch the test-author subagent with the change name first and spawn
  the implementer once its tests are handed off and committed — without them it
  halts missing-oracle.
  Say the specs are worth reading first, and never start either path unprompted.
- for a change the status above lists as apply-ready but \"not yet approved\": name
  the missing approval step it reports instead of offering to spawn the implementer
  — implementation cannot start until the plan is merged and approved."
  if opsx sync; then
    menu="${menu}
- sync edited specs back: /opsx:sync"
  fi
  menu="${menu}
- verify a change before archiving: run the verify skill"
  if opsx archive; then
    menu="${menu}
- archive a completed change: /gatedloop:archive"
  fi
  menu="${menu}
- run the local gates: gates run ci (or gates run live-check, needs the stack up)"

  ctx="${ctx}

At the START of your first reply, greet in one line and present a SHORT tailored menu of what to do next, grounded in the status above. Offer concrete entry points and let the user pick.

Two projects own two halves, so name the right one: OpenSpec (/opsx:) authors the artifacts, gatedloop (/gatedloop:) runs the loop over them.${menu}
Keep it to a few lines — surface only the entries the status above makes relevant. Do not run tools before greeting unless the user already gave a concrete task."
fi

python3 -c 'import json,sys; print(json.dumps({"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":sys.argv[1]}}))' "${ctx}"
