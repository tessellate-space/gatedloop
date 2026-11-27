"""`gates plan check <change> [--json]` (openspec change `plan-preflight`,
design D10; task 3.1).

The static half of a plan preflight: this change's oracle-tag errors and
warnings in `validate`'s words, its untagged tasks under `loop.task-oracle:
required`, and each `rewrites:` path absent at `HEAD` (naming the earlier
task that creates it, when one does). Exit 1 on any finding, 0 on a clean
plan, 1 for an unknown change; it writes nothing.

A `rewrites:` path that does not look like a test path is an advisory, not a
finding (openspec change `advisory-rewrite-paths`, D1 and D2): it is printed,
listed under `advisories`, and neither sets the exit status nor stops
`gates plan round` from opening a round.

Stdlib only, per `zero-dep-shim`. Real git repositories, the shim driven as
a subprocess. Run with:  python3 -m unittest discover -s tests
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

from _preflight_fixture import CHANGE, MANIFEST, PreflightRepo, git, write  # noqa: E402

REQUIRED = MANIFEST + "loop:\n  task-oracle: required\n"
FEATURE = "e2e/features/login.feature"


def commit_feature(r: PreflightRepo) -> PreflightRepo:
    """Commit a non-test file a task can rewrite: a feature file present at HEAD."""
    write(r.root, FEATURE, "Feature: login\n  Scenario: signs in\n")
    git(r.root, "add", FEATURE)
    git(r.root, "commit", "-m", "feature")
    return r


class PlanCheckTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def repo(self, **kw) -> PreflightRepo:
        return PreflightRepo(self.tmp / "work", **kw)

    def check(self, r: PreflightRepo, *extra):
        out = r.gates("plan", "check", CHANGE, "--json", *extra)
        return out.returncode, json.loads(out.stdout)

    def kinds(self, doc) -> list[tuple[str, str | None, str | None]]:
        return [(f["kind"], f["task"], f["path"]) for f in doc["findings"]]

    def advisories(self, doc) -> list[tuple[str, str | None, str | None]]:
        return [(a["kind"], a["task"], a["path"]) for a in doc["advisories"]]

    def feature_repo(self, tasks: str) -> PreflightRepo:
        """A plan whose task rewrites a feature file committed at HEAD."""
        return commit_feature(self.repo(tasks=tasks))

    def test_a_clean_plan_exits_0_and_writes_nothing(self):
        r = self.repo()
        before = r.status()
        out = r.gates("plan", "check", CHANGE)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        code, doc = self.check(r)
        self.assertEqual((code, doc["findings"]), (0, []))
        self.assertEqual(r.status(), before)
        self.assertFalse((r.root / ".gatedloop").exists())

    def test_json_shape(self):
        code, doc = self.check(self.repo())
        self.assertEqual(set(doc), {"change", "preflight", "tier", "against", "findings",
                                    "advisories"})
        self.assertEqual(doc["change"], CHANGE)
        self.assertEqual(doc["preflight"], "skip")
        self.assertEqual(doc["tier"]["tier"], "light")  # group 4 fills it (task 4.4)
        self.assertIsNone(doc["against"])

    def test_a_clean_plan_carries_empty_advisories_and_findings(self):
        code, doc = self.check(self.repo())
        self.assertEqual((code, doc["findings"], doc["advisories"]), (0, [], []))

    def test_an_unknown_change_exits_1(self):
        r = self.repo()
        out = r.gates("plan", "check", "missing")
        self.assertEqual(out.returncode, 1)
        self.assertIn("missing", out.stderr)

    def test_an_oracle_tag_error_is_reported_for_its_task(self):
        r = self.repo(tasks="- [ ] 1.1 Add the widget [oracle: e2e]\n")
        code, doc = self.check(r)
        self.assertEqual(code, 1)
        self.assertEqual(self.kinds(doc), [("oracle-error", "1.1", None)])
        self.assertIn("`e2e`", doc["findings"][0]["detail"])
        text = r.gates("plan", "check", CHANGE)
        self.assertEqual(text.returncode, 1)
        self.assertIn("task 1.1", text.stdout)

    def test_rewriting_a_feature_file_prints_an_advisory_and_is_clean(self):
        r = self.feature_repo(f"- [ ] 1.1 Rework login [oracle: unit rewrites: {FEATURE}]\n")
        out = r.gates("plan", "check", CHANGE)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn(f"advisory: 1.1 {FEATURE}: ", out.stdout)
        self.assertIn("is clean", out.stdout)
        self.assertLess(out.stdout.index("advisory:"), out.stdout.index("is clean"))
        code, doc = self.check(r)
        self.assertEqual(code, 0)
        self.assertEqual(doc["findings"], [])
        self.assertEqual(self.advisories(doc), [("rewrite-not-test-path", "1.1", FEATURE)])
        self.assertIn("does not look like a test path", doc["advisories"][0]["detail"])

    def test_an_advisory_does_not_hide_a_finding(self):
        r = self.feature_repo(
            f"- [ ] 1.1 Rework login [oracle: unit rewrites: {FEATURE}]\n"
            "- [ ] 1.2 Add the widget [oracle: e2e]\n")
        out = r.gates("plan", "check", CHANGE)
        self.assertEqual(out.returncode, 1)
        self.assertIn(f"advisory: 1.1 {FEATURE}: ", out.stdout)
        self.assertLess(out.stdout.index("oracle-error"), out.stdout.index("advisory:"))
        code, doc = self.check(r)
        self.assertEqual(code, 1)
        self.assertEqual(self.kinds(doc), [("oracle-error", "1.2", None)])
        self.assertEqual(self.advisories(doc), [("rewrite-not-test-path", "1.1", FEATURE)])

    def test_an_absent_rewrite_path_is_still_an_oracle_warning_finding(self):
        r = self.repo(tasks="- [ ] 2.1 Rework [oracle: unit rewrites: tests/gone_test.py]\n")
        code, doc = self.check(r)
        self.assertEqual(code, 1)
        self.assertIn(("oracle-warning", "2.1", "tests/gone_test.py"), self.kinds(doc))
        self.assertEqual(doc["advisories"], [])
        self.assertEqual(r.gates("plan", "check", CHANGE).returncode, 1)

    def test_untagged_tasks_under_a_required_oracle(self):
        r = self.repo(manifest=REQUIRED,
                      tasks="- [ ] 1.1 Add it [oracle: unit]\n- [ ] 3.2 Untagged work\n")
        code, doc = self.check(r)
        self.assertEqual(code, 1)
        self.assertEqual(self.kinds(doc), [("untagged", "3.2", None)])

    def test_untagged_tasks_pass_when_the_oracle_is_optional(self):
        r = self.repo(tasks="- [ ] 3.2 Untagged work\n")
        self.assertEqual(self.check(r)[0], 0)

    def test_a_rewrite_of_a_file_an_earlier_task_creates(self):
        r = self.repo(tasks=(
            "- [ ] 1.1 Add `tests/new_test.py` [oracle: unit]\n"
            "- [ ] 2.1 Rework it [oracle: unit rewrites: tests/new_test.py]\n"))
        code, doc = self.check(r)
        self.assertEqual(code, 1)
        absent = [f for f in doc["findings"] if f["kind"] == "rewrite-absent"]
        self.assertEqual([(f["task"], f["path"]) for f in absent], [("2.1", "tests/new_test.py")])
        self.assertIn("task 1.1 creates the file", absent[0]["detail"])

    def test_a_rewrite_of_a_file_nothing_creates(self):
        r = self.repo(tasks="- [ ] 2.1 Rework [oracle: unit rewrites: tests/gone_test.py]\n")
        code, doc = self.check(r)
        absent = [f for f in doc["findings"] if f["kind"] == "rewrite-absent"]
        self.assertEqual([(f["task"], f["path"]) for f in absent], [("2.1", "tests/gone_test.py")])
        self.assertNotIn("creates the file", absent[0]["detail"])

    def test_a_rewrite_present_only_in_the_working_tree_is_absent_at_head(self):
        r = self.repo(tasks="- [ ] 2.1 Rework [oracle: unit rewrites: tests/test_new.py]\n")
        write(r.root, "tests/test_new.py", "def test_x():\n    pass\n")
        code, doc = self.check(r)
        self.assertEqual(code, 1)
        self.assertEqual(self.kinds(doc), [("rewrite-absent", "2.1", "tests/test_new.py")])

    def test_another_changes_findings_are_not_this_plans(self):
        r = self.repo()
        write(r.root, "openspec/changes/other/tasks.md", "- [ ] 1.1 Bad [oracle: e2e]\n")
        git(r.root, "add", "-A")
        git(r.root, "commit", "-m", "other")
        self.assertEqual(self.check(r)[0], 0)


class PlanRoundAdvisoryTest(unittest.TestCase):
    """`gates plan round` prints advisories and opens the round past them."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def repo(self, tasks: str) -> PreflightRepo:
        r = commit_feature(PreflightRepo(self.tmp / "work", tasks=tasks))
        classify = r.gates("plan", "classify", CHANGE, "--unavailable", "no classifier in test")
        self.assertEqual(classify.returncode, 0, classify.stdout + classify.stderr)
        return r

    def opened(self, r: PreflightRepo) -> list[dict]:
        return [x for x in r.rows() if x.get("gate") == "plan-round" and x.get("outcome") == "open"]

    def test_a_round_opens_past_an_advisory(self):
        r = self.repo(f"- [ ] 1.1 Rework login [oracle: unit rewrites: {FEATURE}]\n")
        out = r.gates("plan", "round", CHANGE)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn(f"advisory: 1.1 {FEATURE}: ", out.stdout)
        self.assertIn("does not look like a test path", out.stdout)
        self.assertEqual(len(self.opened(r)), 1)

    def test_a_finding_still_stops_the_round_and_the_advisory_is_printed(self):
        r = self.repo(f"- [ ] 1.1 Rework login [oracle: unit rewrites: {FEATURE}]\n"
                      "- [ ] 1.2 Add the widget [oracle: e2e]\n")
        out = r.gates("plan", "round", CHANGE)
        self.assertEqual(out.returncode, 1)
        self.assertIn(f"advisory: 1.1 {FEATURE}: ", out.stdout)
        self.assertLess(out.stdout.index("oracle-error"), out.stdout.index("advisory:"))
        self.assertEqual(self.opened(r), [])


if __name__ == "__main__":
    unittest.main()
