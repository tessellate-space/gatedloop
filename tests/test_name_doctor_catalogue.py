"""The doctor `name` row and the recurring `rename` adoption item (change
`rename-to-gatedloop`, design D3).

Both read one scan of what earlier names a project still holds: a
`.specloop/` state directory, `x-specloop-*` keys in an active change, and
the earlier markers in a composed git hook. The regressions caught here:

- the scan missing an identifier `gates migrate-name` would move, so doctor
  reads "ok" while the project still stops working in 0.9.0;
- the scan counting an archived change, which nothing migrates, so the
  warning never clears;
- doctor never showing the row, or showing it without naming the command;
- the catalogue item not offered to an unmigrated project, offered to a
  migrated one, or -- being recurring -- silenced for good by an earlier
  "declined" or by an "adopted" the project never acted on.

Stdlib only, per `zero-dep-shim`. Every repository is a throwaway one.

Run with:  python3 -m unittest discover -s tests
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _hook_fixture import default_hook, init_repo, write_hook

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

_loader = importlib.machinery.SourceFileLoader("gates_shim_name_doctor", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)

EARLIER_BLOCK = ("# >>> specloop pre-commit (enforce-at-the-effect) >>>\n"
                 'if [ -n "${CLAUDECODE:-}" ]; then :; fi\n'
                 "# <<< specloop pre-commit (enforce-at-the-effect) <<<\n")


def _env() -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["CLAUDECODE"] = "1"
    return env


def _change(root: Path, name: str, meta: str, archived: bool = False) -> None:
    base = root / "openspec" / "changes"
    d = base / "archive" / f"2026-01-01-{name}" if archived else base / name
    d.mkdir(parents=True)
    (d / ".openspec.yaml").write_text("schema: spec-driven\n" + meta)


def _earlier_state(root: Path) -> None:
    (root / ".specloop" / "runs").mkdir(parents=True)


def _earlier_key(root: Path) -> None:
    _change(root, "alpha", "x-specloop-epic: big\n")


def _earlier_marker(root: Path) -> None:
    write_hook(default_hook(root), "#!/bin/sh\necho lint\n" + EARLIER_BLOCK)


class TestEarlierNameScan(unittest.TestCase):
    def test_each_earlier_identifier_is_found_on_its_own(self):
        for name, plant in (("state directory", _earlier_state),
                            ("change metadata", _earlier_key),
                            ("hook markers", _earlier_marker)):
            with self.subTest(name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                init_repo(root)
                plant(root)

                self.assertEqual(len(gates._earlier_name_remnants(root)), 1)

    def test_a_project_on_the_new_names_holds_none_whatever_its_archive_says(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_repo(root)
            (root / ".gatedloop" / "runs").mkdir(parents=True)
            _change(root, "alpha", "x-gatedloop-epic: big\n")
            _change(root, "old", "x-specloop-approved-by: Someone\n", archived=True)
            write_hook(default_hook(root), "#!/bin/sh\necho lint\n" + gates._composed_hook_snippet())

            self.assertEqual(gates._earlier_name_remnants(root), [])


class TestDoctorNameRow(unittest.TestCase):
    def _row(self, **kw):
        rows = [c for c in gates.doctor_checks("1.14.3", 1, **kw) if c[1] == "name"]
        return rows[0] if rows else None

    def test_the_row_warns_while_anything_earlier_remains_and_names_the_command(self):
        level, _title, detail = self._row(earlier_names=[".specloop/", "x-specloop-epic in alpha"])

        self.assertEqual(level, "warn")
        self.assertIn("gates migrate-name", detail)
        self.assertIn(".specloop/", detail)
        self.assertIn("x-specloop-epic in alpha", detail)

    def test_the_row_is_ok_when_nothing_remains_and_absent_when_not_checked(self):
        self.assertEqual(self._row(earlier_names=[])[0], "ok")
        self.assertIsNone(self._row())

    def test_doctor_reports_an_unmigrated_project(self):
        for plant, tag in ((_earlier_state, "[WARN] name:"), (lambda root: None, "[ok  ] name:")):
            with self.subTest(tag), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                init_repo(root)
                plant(root)

                r = subprocess.run([sys.executable, str(GATES_SHIM), "doctor"], cwd=root,
                                   capture_output=True, text=True, env=_env(), timeout=120)

                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                rows = [line for line in r.stdout.splitlines() if tag in line]
                self.assertEqual(len(rows), 1, r.stdout)


class TestRenameAdoptionItem(unittest.TestCase):
    def setUp(self):
        self.items = gates._shipped_adoption_catalog()
        self.item = next(i for i in self.items if i["id"] == "rename")

    def _undecided(self, root: Path, decisions: dict, version: str) -> list[str]:
        facts = gates._adoption_project_facts(root, {}, self.items)
        return [i["id"] for i in gates.adoption_undecided(self.items, facts, decisions, version)]

    def test_the_item_is_recurring_from_0_7_0_and_names_the_command(self):
        self.assertIs(self.item.get("recurs"), True)
        self.assertEqual(self.item["since"], "0.7.0")
        self.assertEqual(self.item["action"]["kind"], "confirm")
        self.assertIn("gates migrate-name", self.item["action"]["detail"])

    def test_it_is_asked_while_earlier_names_remain_and_never_after(self):
        cases = (
            ("unmigrated, undecided", True, {}, "0.7.0", True),
            ("migrated", False, {}, "0.7.0", False),
            ("declined at this version", True,
             {"rename": {"decision": "declined", "version": "0.7.0"}}, "0.7.0", False),
            ("declined at an earlier version", True,
             {"rename": {"decision": "declined", "version": "0.7.0"}}, "0.7.1", True),
            ("adopted but not acted on", True,
             {"rename": {"decision": "adopted", "version": "0.7.0"}}, "0.7.0", True),
        )
        for name, unmigrated, decisions, version, asked in cases:
            with self.subTest(name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                init_repo(root)
                if unmigrated:
                    _earlier_state(root)
                else:
                    (root / ".gatedloop" / "runs").mkdir(parents=True)

                self.assertEqual("rename" in self._undecided(root, decisions, version), asked)


if __name__ == "__main__":
    unittest.main()
