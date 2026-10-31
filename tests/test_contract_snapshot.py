"""The contract snapshot's generator and comparison (stability-contract D3, D4).

`tests/test_contract.py` regenerates the public surface from the code and
compares it with the checked-in `tests/contract.json`. These tests drive
its three pieces directly, so no test edits the shim to provoke a diff:

- `generate()` -> the snapshot of the code as it is;
- `compare(snapshot, actual)` -> `None` when they agree, else the failure
  message: a unified diff and the command that rewrites the snapshot;
- `write(path, snapshot)` and `python3 tests/test_contract.py --write
  [--out PATH]` -> the rewrite.

The regressions: a renamed flag, an added subcommand, a removed status
context or a removed ledger field passing unnoticed; a failure that does
not say what changed or how to accept it; a rewrite that leaves the test
failing; and an `internal` mark that is guessed instead of listed with a
reason.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

from __future__ import annotations

import copy
import importlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _merge_fixture import clean_env

TESTS = Path(__file__).resolve().parent
REWRITE = "python3 tests/test_contract.py --write"


def _contract():
    if importlib.util.find_spec("test_contract") is None:
        raise AssertionError("tests/test_contract.py does not exist yet")
    return importlib.import_module("test_contract")


class _SnapshotCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = None
        cls.snapshot = None

    def setUp(self):
        if type(self).snapshot is None:
            type(self).module = _contract()
            type(self).snapshot = type(self).module.generate()
        self.contract = type(self).module

    def changed(self):
        return copy.deepcopy(type(self).snapshot)

    def assert_fails_naming(self, actual, *names):
        message = self.contract.compare(type(self).snapshot, actual)
        self.assertIsNotNone(message, "a difference passed the comparison")
        for name in names:
            self.assertIn(name, message)
        self.assertIn(REWRITE, message)
        self.assertRegex(message, r"(?m)^[-+]", "the message carries no diff")


class GeneratedSnapshotTest(_SnapshotCase):
    def test_internal_subcommands_are_listed_with_their_reason(self):
        subs = self.snapshot["subcommands"]
        self.assertEqual(subs["discipline"]["visibility"], "internal")
        self.assertTrue(self.contract.CONTRACT_INTERNAL["discipline"].strip())
        self.assertEqual(subs["discipline"].get("reason"), self.contract.CONTRACT_INTERNAL["discipline"])
        self.assertEqual(subs["discipline check-implement"]["visibility"], "internal")
        self.assertEqual(subs["run"]["visibility"], "public")
        self.assertEqual(subs["hook install"]["visibility"], "public")
        self.assertEqual(subs["hook git-cwd"]["visibility"], "internal")
        for path, entry in subs.items():
            if entry["visibility"] == "internal":
                self.assertTrue(entry.get("reason"), f"{path} is internal with no reason")

    def test_flags_and_positionals_are_recorded_per_subcommand(self):
        run = self.snapshot["subcommands"]["run"]
        self.assertIn("--task", run["options"])
        self.assertIn("--attempt", run["options"])
        self.assertNotIn("-h", run["options"], "argparse's own help flag is not the contract")
        self.assertIn("gate", run["positionals"])

    def test_every_listed_surface_is_named(self):
        snap = self.snapshot
        self.assertIn("75", snap["exit_codes"])
        for code in ("0", "1", "2"):
            self.assertIn(code, snap["exit_codes"])
        self.assertEqual(sorted(snap["status_contexts"]),
                         ["gatedloop/ci", "gatedloop/live-check", "gatedloop/tests"])
        for key in ("gatesVersion", "gates", "surfaces"):
            self.assertIn(key, snap["manifest_keys"])
        for key in ("change", "approval", "tasks", "verify"):
            self.assertIn(key, snap["documents"]["handoff"])
        for key in ("changes", "totals"):
            self.assertIn(key, snap["documents"]["stats"])
        self.assertIn("gate", snap["ledger_fields"])
        self.assertIn("v", snap["ledger_fields"])
        self.assertEqual(snap["ledger_row_version"], 1)

    def test_the_snapshot_is_deterministic(self):
        self.assertEqual(self.contract.generate(), self.snapshot)
        self.assertIsNone(self.contract.compare(self.snapshot, self.changed()))


class DifferenceFailsTest(_SnapshotCase):
    def test_a_renamed_flag_names_the_old_flag_and_the_new_one(self):
        actual = self.changed()
        options = actual["subcommands"]["run"]["options"]
        options[options.index("--task")] = "--work-item"
        actual["subcommands"]["run"]["options"] = sorted(options)
        self.assert_fails_naming(actual, "--task", "--work-item")

    def test_an_added_subcommand_fails_naming_it(self):
        actual = self.changed()
        actual["subcommands"]["frobnicate"] = {"visibility": "public", "options": [], "positionals": []}
        self.assert_fails_naming(actual, "frobnicate")

    def test_a_removed_status_context_fails_naming_it(self):
        actual = self.changed()
        actual["status_contexts"] = [c for c in actual["status_contexts"] if c != "gatedloop/tests"]
        self.assert_fails_naming(actual, "gatedloop/tests")

    def test_a_removed_ledger_field_fails_naming_it(self):
        actual = self.changed()
        actual["ledger_fields"] = [f for f in actual["ledger_fields"] if f != "accepted_by"]
        self.assert_fails_naming(actual, "accepted_by")


class RewriteTest(_SnapshotCase):
    def test_write_makes_the_comparison_pass_again(self):
        actual = self.changed()
        actual["subcommands"]["frobnicate"] = {"visibility": "public", "options": [], "positionals": []}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "contract.json"
            path.write_text(json.dumps(self.snapshot))
            self.assertIsNotNone(self.contract.compare(json.loads(path.read_text()), actual))
            self.contract.write(path, actual)
            self.assertIsNone(self.contract.compare(json.loads(path.read_text()), actual))

    def test_the_command_line_rewrite_writes_the_generated_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "contract.json"
            r = subprocess.run([sys.executable, str(TESTS / "test_contract.py"), "--write",
                                "--out", str(out)], capture_output=True, text=True, env=clean_env())
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIsNone(self.contract.compare(json.loads(out.read_text()), self.snapshot))
            self.assertTrue(out.read_text().endswith("\n"))


if __name__ == "__main__":
    unittest.main()
