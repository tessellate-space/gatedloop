"""Summarize `openspec list --json` (piped on stdin) for the SessionStart brief.

Kept as a separate file so the shell hook never has to nest quotes around Python.
Prints a short human-readable summary; silent (empty) on any parse failure.
"""

import json
import os
import subprocess
import sys


def _gates_bin() -> str:
    """Resolve the `gates` shim the same way the shell hooks do (design D4,
    `solo-approval-mode`): prefer the plugin root env var Claude Code sets,
    falling back to a path relative to this file (this repo's own dev
    checkout), and finally to whatever `gates` resolves to on PATH (an
    installed plugin puts `bin/` there)."""
    root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if root:
        candidate = os.path.join(root, "bin", "gates")
        if os.path.exists(candidate):
            return candidate
    here = os.path.dirname(os.path.abspath(__file__))
    candidate = os.path.join(os.path.dirname(here), "bin", "gates")
    if os.path.exists(candidate):
        return candidate
    return "gates"


def _approval_status(change: str) -> tuple[bool, str]:
    """`gates approval check <change>` (design D4): exit 0 + a reason string
    when the change's plan is merged AND its approval keys are present and
    still sha-matched; exit 1 + a reason naming what's missing otherwise.
    Never raises -- an environment where `gates`/git can't run at all is
    reported as "not approved" rather than crashing the whole brief."""
    try:
        out = subprocess.run(
            [_gates_bin(), "approval", "check", change],
            capture_output=True, text=True, timeout=15,
        )
        reason = (out.stdout or out.stderr).strip()
        return out.returncode == 0, reason
    except Exception as e:
        return False, f"could not run `gates approval check` ({e})"


def _needs_test_author(change: str) -> bool:
    """`gates tests show <change> --json` (design D6, `split-test-author`):
    True when the project's `loop.test-author` is `separate` and the change
    has no handoff yet -- the implementer would halt `missing-oracle`, so the
    author is offered first. An unreadable answer assumes the default
    (separate, not yet authored) rather than offering a spawn that halts."""
    try:
        out = subprocess.run(
            [_gates_bin(), "tests", "show", change, "--json"],
            capture_output=True, text=True, timeout=15,
        )
        doc = json.loads(out.stdout)
        return doc.get("mode") != "inline" and not doc.get("handoff")
    except Exception:
        return True


def _adoption_line() -> "str | None":  # quoted: Python 3.9 has no `X | None`
    """`gates adoption status --json` (design D4, `adoption-prompts`): one line
    when settings this plugin version introduced are still undecided, one line
    when the check cannot run, None when nothing waits. Never raises, and never
    asks: only /gatedloop:upgrade asks."""
    try:
        out = subprocess.run(
            [_gates_bin(), "adoption", "status", "--json"],
            capture_output=True, text=True, timeout=15,
        )
        if out.returncode != 0:
            detail = (out.stderr or out.stdout).strip().splitlines()
            reason = detail[-1] if detail else f"exit {out.returncode}"
            return f"adoption check could not run ({reason})"
        doc = json.loads(out.stdout)
        count = len(doc["undecided"])
        if not count:
            return None
        return (f"gatedloop {doc['version']} added {count} setting(s) this project "
                "hasn't decided on — run /gatedloop:upgrade")
    except Exception as e:
        return f"adoption check could not run ({e})"


_EPIC_STATES = ("archived", "merged", "halted", "ready", "implementing", "approved", "proposed")


def _active_epics() -> list:
    """`gates epics --json` (design D7, `epic-linkage`): the active epics, each
    with its children's states. A fast read that runs no gates. Never raises:
    anything unreadable is no epics, so the brief is exactly what it was."""
    try:
        out = subprocess.run(
            [_gates_bin(), "epics", "--json"],
            capture_output=True, text=True, timeout=15,
        )
        if out.returncode != 0:
            return []
        return [e for e in json.loads(out.stdout).get("epics", []) if not e.get("archived")]
    except Exception:
        return []


def _epic_line(epic: dict) -> str:
    """One line per active epic: each state's count, in derivation order, naming
    the implementing children with their progress and the halted ones' cause."""
    kids = epic.get("children", [])
    parts = []
    for state in _EPIC_STATES:
        group = [k for k in kids if k.get("state") == state]
        if not group:
            continue
        part = f"{len(group)} {state}"
        if state == "implementing":
            part += " (" + ", ".join(
                f"{k.get('change')} {k.get('tasks', {}).get('done', 0)}/{k.get('tasks', {}).get('total', 0)}"
                for k in group) + ")"
        elif state == "halted":
            part += " (" + ", ".join(f"{k.get('change')}: {k.get('halt_cause')}" for k in group) + ")"
        parts.append(part)
    line = f"Epic {epic.get('epic')}: " + ", ".join(parts)
    if epic.get("drained"):
        line += " — drained, ready to archive the epic"
    return line


raw = sys.stdin.read()
i = raw.find("{")
if i < 0:
    sys.exit(0)
try:
    data = json.loads(raw[i:])
except Exception:
    sys.exit(0)

changes = data.get("changes", [])
# An active epic's children are summarised on its line, not repeated below.
epics = _active_epics()
epic_children = {k.get("change") for e in epics for k in e.get("children", [])}
changes = [c for c in changes if c.get("name") not in epic_children]
inprog = [c for c in changes if c.get("status") == "in-progress"]
done = [c for c in changes if c.get("status") == "complete"]

# A change with tasks but none done has its artifacts written and the loop not yet
# started — the moment to offer the two implementation paths, and to ask for spec
# approval first. (This offer used to live at the end of the forked propose command;
# grounding it in live state means it fires whenever it applies, not only right after.)
started = [c for c in inprog if c.get("completedTasks", 0) > 0]
apply_ready = [c for c in inprog if c.get("completedTasks", 0) == 0 and c.get("totalTasks", 0) > 0]

# Onboarding-asks-first: split apply-ready further on approval status (design D4,
# `solo-approval-mode`) -- a change whose plan is merged and approved is ready for
# the implementer to be SPAWNED as the default action; one that isn't names the
# missing step instead of dangling an offer that would just refuse.
approved_ready = []
needs_approval = []
for c in apply_ready:
    ok, reason = _approval_status(str(c.get("name")))
    if ok:
        approved_ready.append(c)
    else:
        needs_approval.append((c, reason))


def frac(c):
    return c.get("completedTasks", 0) / max(c.get("totalTasks", 1), 1)


out = [_epic_line(e) for e in epics]
if started:
    out.append(f"{len(started)} change(s) underway (most-complete first):")
    for c in sorted(started, key=frac, reverse=True)[:6]:
        out.append(f"  - {c.get('name')} ({c.get('completedTasks', 0)}/{c.get('totalTasks', 0)})")
if approved_ready:
    out.append(f"{len(approved_ready)} change(s) approved and ready to implement (spawn the implementer by default):")
    for c in approved_ready[:6]:
        if _needs_test_author(str(c.get("name"))):
            offer = ("dispatch test-author, then the implementer: offer dispatching "
                     "test-author for it and then spawning tdd-implementer, or "
                     "/gatedloop:tdd-apply interactively (it dispatches the author itself)")
        else:
            offer = "offer spawning tdd-implementer, or /gatedloop:tdd-apply interactively"
        out.append(f"  - {c.get('name')} (0/{c.get('totalTasks', 0)}) — approved; {offer}")
if needs_approval:
    out.append(f"{len(needs_approval)} change(s) apply-ready but not yet approved:")
    for c, reason in needs_approval[:6]:
        out.append(f"  - {c.get('name')} (0/{c.get('totalTasks', 0)}) — {reason}")
if done:
    out.append(f"{len(done)} complete & ready to archive: " + ", ".join(str(c.get("name")) for c in done[:5]))
adoption = _adoption_line()
if adoption:
    out.append(adoption)

print("\n".join(out))
