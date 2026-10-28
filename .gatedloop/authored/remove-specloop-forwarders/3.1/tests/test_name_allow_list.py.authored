"""The rename is complete only by grep (change `rename-to-gatedloop`, design
D6, after `rename-to-gates` D5), and from 0.9.0 the list holds only what
remains of the earlier name (change `remove-specloop-forwarders`, design D3).

`git grep -n -i specloop -- . ':!openspec/changes/archive' ':!CHANGELOG.md'`
may return only the hits allowed below, each with its reason. Any other hit
is a defect: most likely a prompt that still reads correctly to a reviewer
while naming a command, directory or key that no longer exists. An entry
naming something removed is deleted with it, so the list never allows a hit
nothing should produce. This is a lint rather than a behaviour test
(`gatedloop.test-quality` item 9); design D6 asks for it as a test so the
allow-list holds after the change too, and the project's design outranks the
built-in item.

Read-only against this repository. Stdlib only, per `zero-dep-shim`.

Run with:  python3 -m unittest discover -s tests
"""

from __future__ import annotations

import fnmatch
import os
import re
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Text that names something real by its earlier spelling, allowed on any line.
ALLOWED_TOKENS = (
    # A change's name, D7: the expiry is a follow-up change named for what it removes.
    "remove-specloop-forwarders",
    # A real repository a past end-to-end run used (AUTOMATION.md); renaming it would be false.
    "radub21/specloop-e2e",
    # An archived change's name (openspec/changes/archive/2026-08-18-reposition-specloop).
    "reposition-specloop",
)

# Patterns of text allowed on any line, as regexes rather than literals.
ALLOWED_TOKEN_PATTERNS = (
    # Names a PR in the private archive repository, the history this one was exported from.
    r"specloop PR \d+",
)

# (path glob, scope, reason). A scope is None (the whole file),
# ("lines", regex) (a matching line), ("region", begin, end) (from a line
# containing `begin` through the next line containing `end`), or
# ("section", heading) (a Markdown heading, through the line before the next
# heading of the same or a higher level).
ALLOWED = (
    ("bin/gates", ("region", "# ---------- the earlier name (rename-to-gatedloop",
                   "# ---------- end of the earlier name"),
     "D3's `gates migrate-name`, the scan doctor reads, and the 0.9.0 refusal, kept in one region"),
    ("adoption/catalog.json", ("region", '"id": "rename"', '"action"'),
     "the recurring `rename` item, which names what it migrates, D3"),
    ("tests/test_migrate_name.py", None, "`gates migrate-name` tests"),
    ("tests/test_name_doctor_catalogue.py", None, "the doctor row and catalogue item tests"),
    ("tests/test_name_allow_list.py", None, "this allow-list"),
    ("README.md", ("section", "## Migrating from Specloop"), "the migration notes, D6"),
    ("SETUP.md", ("section", "## Migrating from Specloop"), "the migration notes, D6"),
    ("RELEASING.md", ("section", "## Releasing through the rename"), "the migration notes, D6"),
    # Archiving the change syncs its two read-both requirements into the main
    # spec, where they name the earlier identifiers by design.
    ("openspec/specs/plugin-positioning/spec.md",
     ("section", "### Requirement: The earlier name is read loudly for one release"),
     "the synced read-both requirement, D2"),
    ("openspec/specs/plugin-positioning/spec.md",
     ("section", "### Requirement: A project migrates to the new name by one command"),
     "the synced migration requirement, D3"),
    ("openspec/changes/remove-specloop-forwarders/*", None, "the expiry's plan, D7"),
    ("scripts/go-public", None, "the migration tool names the private archive"),
    ("tests/test_go_public.py", None, "the migration tool names the private archive"),
    ("RELEASING.md", ("section", "## Publishing the public repository"),
     "the migration tool names the private archive"),
    ("openspec/changes/go-public-migration/*", None,
     "an approved plan, hashed by its approval: it names the private archive repository"),
    ("openspec/changes/role-commands/proposal.md", None,
     "an approved plan, hashed by its approval, so it is not rewritten here"),
    (".gatedloop/*", None, "this repository's own state directory: ledger rows are data"),
)


def _hits() -> list[tuple[str, int, str]]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    r = subprocess.run(
        ["git", "grep", "-n", "-I", "-i", "specloop", "--", ".",
         ":!openspec/changes/archive", ":!CHANGELOG.md"],
        cwd=REPO, capture_output=True, text=True, env=env,
    )
    if r.returncode not in (0, 1):
        raise AssertionError(f"git grep failed: {r.stderr}")
    out = []
    for line in r.stdout.splitlines():
        path, number, text = line.split(":", 2)
        out.append((path, int(number), text))
    return out


def _region_lines(lines: list[str], begin: str, end: str) -> set[int]:
    allowed, inside = set(), False
    for number, text in enumerate(lines, 1):
        if not inside:
            if begin in text:
                inside = True
                allowed.add(number)
            continue
        allowed.add(number)
        if end in text:
            inside = False
    return allowed


def _section_lines(lines: list[str], heading: str) -> set[int]:
    level = len(heading) - len(heading.lstrip("#"))
    allowed, inside = set(), False
    for number, text in enumerate(lines, 1):
        if text.strip() == heading:
            inside = True
        elif inside and re.match(r"^#{1,%d} " % level, text):
            inside = False
        if inside:
            allowed.add(number)
    return allowed


class TestEarlierNameAllowList(unittest.TestCase):
    @unittest.skipUnless((REPO / ".git").exists(), "not a git checkout")
    def test_every_earlier_name_hit_is_allowed(self):
        cache: dict = {}

        def scope_lines(path: str, scope) -> set[int]:
            key = (path, scope)
            if key not in cache:
                lines = (REPO / path).read_text().splitlines()
                if scope[0] == "region":
                    cache[key] = _region_lines(lines, scope[1], scope[2])
                else:
                    cache[key] = _section_lines(lines, scope[1])
            return cache[key]

        def allowed(path: str, number: int, text: str) -> bool:
            rest = text
            for token in ALLOWED_TOKENS:
                rest = re.sub(re.escape(token), "", rest, flags=re.IGNORECASE)
            for pattern in ALLOWED_TOKEN_PATTERNS:
                rest = re.sub(pattern, "", rest, flags=re.IGNORECASE)
            if "specloop" not in rest.lower():
                return True
            for glob, scope, _reason in ALLOWED:
                if not fnmatch.fnmatch(path, glob):
                    continue
                if scope is None:
                    return True
                if scope[0] == "lines":
                    if re.search(scope[1], text):
                        return True
                elif number in scope_lines(path, scope):
                    return True
            return False

        stray = [f"{p}:{n}: {t.strip()}" for p, n, t in _hits() if not allowed(p, n, t)]

        self.assertEqual(stray, [], "earlier-name hits outside the allow-list:\n" + "\n".join(stray))


if __name__ == "__main__":
    unittest.main()
