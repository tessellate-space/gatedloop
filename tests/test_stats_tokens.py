"""`gates stats` reports token spend from usage rows (openspec change
`token-ledger`, design D6; the gate-economics delta's "`gates stats` reports
token spend from usage rows").

Per change, the report sums counted usage rows into tokens per task and per
model, and discloses what is unrecorded: tasks with no counted usage row, and
how much of the ledger's span no counted window covers. `--json` carries it
under each change's `tokens` key (and a `tokens` total under `totals`);
`--epic` rolls it up per child. Usage rows never move the time figures: the
report's time sections are byte-identical with or without them. A ledger with
no usage row says token spend was not recorded.

JSON shape fixed by these tests, per change:
    "tokens": {"recorded", "total", "models": {model: {input, output,
               cache_read, cache_write, total}}, "tasks": {task: {"total",
               "models"}}, "unattributed": {"total", "models"},
               "unrecorded": {"tasks", "count", "uncovered_ms", "span_ms"}}

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _epic_fixture import EpicRepo  # noqa: E402
from _epic_fixture import row as epic_row  # noqa: E402
from _usage_fixture import (  # noqa: E402
    CHANGE, MODEL_A, MODEL_B, at, change_repo, counts, run_gates, seed, task_start,
    usage_row,
)

TIME_ROWS = [
    task_start(at(0), "1.1"),
    {"ts": at(2), "gate": "unit", "task": "1.1", "exit": 1, "duration_ms": 60000},
    {"ts": at(4), "gate": "ci", "task": "1.1", "exit": 0, "duration_ms": 60000},
    task_start(at(5), "1.2"),
    {"ts": at(8), "gate": "ci", "task": "1.2", "exit": 0, "duration_ms": 60000},
    task_start(at(9), "1.3"),
    {"ts": at(12), "gate": "ci", "task": "1.3", "exit": 0, "duration_ms": 60000},
]

USAGE_ROWS = [
    usage_row(at(4, second=30), "1.1",
              {MODEL_A: counts(input=100, output=50, cache_read=1000, cache_write=10)},
              window_from=at(0)),
    usage_row(at(8, second=30), "1.2",
              {MODEL_A: counts(input=5), MODEL_B: counts(output=7)}, window_from=at(5)),
    usage_row(at(13), None, {MODEL_B: counts(input=3)}, window_from=at(12)),
    usage_row(at(13, second=10), "1.3", None, source="no-transcript"),
]


def _repo(tmp, with_usage):
    root = change_repo(tmp)
    rows = TIME_ROWS + (USAGE_ROWS if with_usage else [])
    seed(root, *sorted(rows, key=lambda r: r["ts"]))
    return root


def _doc(root, *flags):
    r = run_gates(root, "stats", "--change", CHANGE, "--json", *flags)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def _without_tokens(doc):
    doc = copy.deepcopy(doc)
    for c in doc["changes"]:
        c.pop("tokens", None)
    doc["totals"].pop("tokens", None)
    return doc


def _before_tokens(text):
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("tokens"):
            return lines[:i]
    return lines


class TestTokensBesideTime(unittest.TestCase):
    def test_tokens_per_task_and_model_with_the_unrecorded_disclosed(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = _doc(_repo(tmp, with_usage=True))
            (c,) = doc["changes"]
            t = c["tokens"]
            self.assertTrue(t["recorded"])
            self.assertEqual(t["tasks"]["1.1"]["total"], 1160)
            self.assertEqual(t["tasks"]["1.2"]["total"], 12)
            self.assertEqual(t["tasks"]["1.2"]["models"][MODEL_B]["output"], 7)
            self.assertNotIn("1.3", t["tasks"])
            self.assertEqual(t["unattributed"]["total"], 3)
            self.assertEqual(t["total"], 1175)
            self.assertEqual(t["models"][MODEL_A]["total"], 1165)
            self.assertEqual(t["models"][MODEL_B], {"input": 3, "output": 7, "cache_read": 0,
                                                    "cache_write": 0, "total": 10})
            self.assertEqual(t["unrecorded"]["tasks"], ["1.3"])
            self.assertEqual(t["unrecorded"]["count"], 1)
            self.assertGreater(t["unrecorded"]["uncovered_ms"], 0)
            self.assertGreater(t["unrecorded"]["span_ms"], t["unrecorded"]["uncovered_ms"])
            self.assertEqual(doc["totals"]["tokens"], 1175)

    def test_the_human_report_shows_tokens_and_the_unrecorded_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = run_gates(_repo(tmp, with_usage=True), "stats").stdout
            tokens = "\n".join(out.splitlines()[len(_before_tokens(out)):])
            self.assertIn("1160", tokens)
            self.assertIn(MODEL_B, tokens)
            self.assertRegex(tokens, r"1\.3\s+unrecorded")
            self.assertRegex(tokens, r"1 of 3 task")


class TestTimeIsUntouched(unittest.TestCase):
    def test_time_figures_are_byte_identical_with_and_without_usage_rows(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            with_usage, without = _repo(a, True), _repo(b, False)
            self.assertEqual(_without_tokens(_doc(with_usage)), _without_tokens(_doc(without)))
            self.assertEqual(_before_tokens(run_gates(with_usage, "stats").stdout),
                             _before_tokens(run_gates(without, "stats").stdout))

    def test_a_ledger_with_no_usage_row_says_spend_was_not_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, with_usage=False)
            (c,) = _doc(root)["changes"]
            self.assertFalse(c["tokens"]["recorded"])
            self.assertEqual(c["tokens"]["total"], 0)
            out = run_gates(root, "stats").stdout
            self.assertRegex(out, r"(?m)^tokens: not recorded")


class TestEpicRollup(unittest.TestCase):
    def test_the_epic_sums_its_childrens_tokens(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = EpicRepo(tmp)
            repo.change("the-epic")
            repo.change("child-a", epic="the-epic", approved=True, tasks=(1, 2))
            repo.ledger("child-a", epic_row("task-start", 0, task="1.1"),
                        usage_row(at(1), "1.1", {MODEL_A: counts(input=40)}))
            repo.change("child-b", epic="the-epic", approved=True, tasks=(0, 1))
            repo.ledger("child-b", epic_row("task-start", 0, task="1.1"),
                        usage_row(at(1), "1.1", {MODEL_B: counts(output=2)}))
            repo.commit("children")
            doc = repo.gates_json("stats", "--epic", "the-epic", "--json")
            by_child = {c["change"]: c["tokens"] for c in doc["children"]}
            self.assertEqual(by_child, {"child-a": 40, "child-b": 2})
            self.assertEqual(doc["totals"]["tokens"], 42)


if __name__ == "__main__":
    unittest.main()
