"""Diagnosing the old permission checkpoint (design D5 of
`merge-lane-friction`, issue #44).

Earlier `gates-init` scaffolding wrote `"ask": ["Bash(git merge *)"]` into
`.claude/settings.local.json`, so every `git merge` an agent issues prompts,
and an unattended lane's routine sync stalls on a prompt nobody answers.
The checkpoint now belongs on `gates merge`. Three things find the old rule:

- the doctor row `merge-checkpoint`: warn when the file asks on
  `Bash(git merge *)`, naming `Bash(gates merge *)`; ok otherwise, including
  when the file is absent;
- the detector kind `file-contains` (`path`, `text`): acted on unless the
  file at `path` contains `text`. Pure;
- the recurring catalogue item `merge-checkpoint`, since 0.6.0, which
  applies when the settings file exists.

The regressions: the doctor not flagging the old rule (or flagging a
project with no settings file), the doctor row computed but never passed
from `cmd_doctor`, a `file-contains` detector that reads acted when the text
is there, a catalogue accepting a `file-contains` detector with no `text`,
and the shipped item never coming up for a project carrying the old rule.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _merge_fixture import GATES_SHIM, clean_env, git

_loader = importlib.machinery.SourceFileLoader("gates_shim_merge_checkpoint", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)

OLD_RULE = "Bash(git merge *)"
NEW_RULE = "Bash(gates merge *)"
SETTINGS_REL = ".claude/settings.local.json"


def _settings(ask: list[str]) -> str:
    return json.dumps({"permissions": {
        "allow": ["Bash(gates *)", "Bash(openspec *)", "Bash(git commit *)"],
        "ask": ask,
    }}, indent=2)


def _row(checks: list, title: str):
    return next((c for c in checks if c[1] == title), None)


class DoctorMergeCheckpointTest(unittest.TestCase):
    def _doctor(self, local_settings):
        return gates.doctor_checks(gates.TESTED_OPENSPEC_VERSION, 1, "/p",
                                   local_settings=local_settings)

    def test_settings_asking_on_every_git_merge_warn_and_name_the_replacement(self):
        row = _row(self._doctor(_settings([OLD_RULE])), "merge-checkpoint")
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "warn")
        self.assertIn(NEW_RULE, row[2])

    def test_settings_without_the_old_rule_or_no_settings_file_are_ok(self):
        for label, text in (("new rule", _settings([NEW_RULE])), ("no ask", _settings([])),
                            ("absent", None)):
            with self.subTest(label):
                row = _row(self._doctor(text), "merge-checkpoint")
                self.assertIsNotNone(row)
                self.assertEqual(row[0], "ok")

    def test_gates_doctor_reads_the_projects_local_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            git(root, "init", "-q", "-b", "main")
            (root / ".claude").mkdir()
            (root / SETTINGS_REL).write_text(_settings([OLD_RULE]))
            r = subprocess.run([sys.executable, str(GATES_SHIM), "doctor"], cwd=root,
                               capture_output=True, text=True, env=clean_env())
        self.assertEqual(r.returncode, 0, r.stderr)
        line = next((x for x in r.stdout.splitlines() if "merge-checkpoint" in x), None)
        self.assertIsNotNone(line, f"no merge-checkpoint row in: {r.stdout!r}")
        self.assertIn("WARN", line)


class FileContainsDetectorTest(unittest.TestCase):
    DETECTOR = {"kind": "file-contains", "path": SETTINGS_REL, "text": OLD_RULE}

    def test_acted_unless_the_file_contains_the_text(self):
        cases = (
            ("contains it", _settings([OLD_RULE]), False),
            ("lacks it", _settings([NEW_RULE]), True),
            ("no such file", None, True),
        )
        for label, text, acted in cases:
            with self.subTest(label):
                facts = {"files": {SETTINGS_REL: text}}
                self.assertIs(gates.adoption_detector_acted(self.DETECTOR, facts), acted)

    def test_a_catalogue_detector_without_its_text_is_refused(self):
        catalogue = json.loads(gates.ADOPTION_CATALOG_FILE.read_text())
        item = next(i for i in catalogue["items"] if i["id"] == "merge-checkpoint")
        item["detector"] = {"kind": "file-contains", "path": SETTINGS_REL}
        with self.assertRaises(gates.AdoptionError):
            gates.load_adoption_catalog({"items": [item]})


class MergeCheckpointItemTest(unittest.TestCase):
    """The shipped item, evaluated against a real project directory."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        git(self.root, "init", "-q", "-b", "main")

    def tearDown(self):
        self._tmp.cleanup()

    def _undecided_ids(self, version: str = "0.6.0") -> list[str]:
        items = gates._shipped_adoption_catalog()
        facts = gates._adoption_project_facts(self.root, {}, items)
        return [i["id"] for i in gates.adoption_undecided(items, facts, {}, version)]

    def _write_settings(self, ask: list[str]) -> None:
        (self.root / ".claude").mkdir(exist_ok=True)
        (self.root / SETTINGS_REL).write_text(_settings(ask))

    def test_a_project_asking_on_every_git_merge_is_asked_about_it(self):
        self._write_settings([OLD_RULE])
        self.assertIn("merge-checkpoint", self._undecided_ids())

    def test_a_project_already_asking_on_gates_merge_is_not(self):
        self._write_settings([NEW_RULE])
        self.assertNotIn("merge-checkpoint", self._undecided_ids())

    def test_a_project_with_no_local_settings_is_not(self):
        self.assertNotIn("merge-checkpoint", self._undecided_ids())

    def test_it_recurs_after_being_adopted_while_the_old_rule_is_back(self):
        self._write_settings([OLD_RULE])
        items = gates._shipped_adoption_catalog()
        facts = gates._adoption_project_facts(self.root, {}, items)
        decisions = {"merge-checkpoint": {"decision": "adopted", "version": "0.6.0"}}
        ids = [i["id"] for i in gates.adoption_undecided(items, facts, decisions, "0.6.0")]
        self.assertIn("merge-checkpoint", ids)


if __name__ == "__main__":
    unittest.main()
