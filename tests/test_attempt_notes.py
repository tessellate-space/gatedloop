"""`gates attempt note` and `gates attempt notes` (openspec change
`retry-budget`, design D3; the retry-budget delta's "Attempt notes are
structured ledger rows" requirement).

Stdlib only, per `zero-dep-shim`. Drives the shim as a subprocess in a
throwaway git repo whose ledger is seeded with the rows a loop would have
written, then reads the durable `.gatedloop/runs/<change>.jsonl` back.

Run with:  python3 -m unittest discover -s tests
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"
CHANGE = "my-change"


def _env():
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["CLAUDECODE"] = "1"
    return env


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                          text=True, env=_env())


def _repo(tmp):
    root = Path(tmp)
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text('gatesVersion: 1\ngates:\n  ci: "true"\n')
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")
    _git(root, "checkout", "-b", CHANGE)
    (root / "openspec" / "changes" / CHANGE).mkdir(parents=True)
    return root


def _ledger(root):
    return root / ".gatedloop" / "runs" / f"{CHANGE}.jsonl"


def _rows(root):
    p = _ledger(root)
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


def _seed(root, rows):
    p = _ledger(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        for r in rows:
            full = {"change": CHANGE, "ts": "2026-10-01T00:00:00+00:00"}
            full.update(r)
            f.write(json.dumps(full) + "\n")


def _run(root, *args):
    return subprocess.run([sys.executable, str(GATES_SHIM), *args], cwd=root,
                          capture_output=True, text=True, env=_env(), timeout=60)


def _note(root, task="1.2", **overrides):
    fields = {"hypothesis": "the parser drops the last key",
              "changed": "flushed the pending key at end of input",
              "oracle": "test_last_key still red: KeyError 'b'",
              "next": "rule out the indentation path"}
    fields.update(overrides)
    args = ["attempt", "note", task]
    for k, v in fields.items():
        if v is not None:
            args += [f"--{k}", v]
    return _run(root, *args)


RED_THEN_ONE = [
    {"gate": "task-start", "task": "1.2", "tree": "t" * 40},
    {"gate": "unit", "task": "1.2", "exit": 1},
    {"gate": "unit", "task": "1.2", "exit": 1},
]


class TestAttemptNote(unittest.TestCase):
    def test_a_note_is_one_structured_row_numbered_by_the_attempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _seed(root, RED_THEN_ONE)
            r = _note(root)
            self.assertEqual(r.returncode, 0, r.stderr)
            row = _rows(root)[-1]
            self.assertEqual(row["gate"], "attempt-note")
            self.assertEqual(row["task"], "1.2")
            self.assertEqual(row["attempt"], 1)
            self.assertEqual(row["note"], {
                "hypothesis": "the parser drops the last key",
                "changed": "flushed the pending key at end of input",
                "oracle": "test_last_key still red: KeyError 'b'",
                "next": "rule out the indentation path",
            })

    def test_notes_prints_the_note_with_its_attempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _seed(root, RED_THEN_ONE)
            self.assertEqual(_note(root).returncode, 0)
            r = _run(root, "attempt", "notes", "1.2")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("attempt 1", r.stdout)
            for text in ("the parser drops the last key",
                         "flushed the pending key at end of input",
                         "test_last_key still red: KeyError 'b'",
                         "rule out the indentation path"):
                self.assertIn(text, r.stdout)

    def test_an_over_long_field_is_refused_naming_it_and_nothing_is_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _seed(root, RED_THEN_ONE)
            before = len(_rows(root))
            r = _note(root, oracle="x" * 201)
            self.assertEqual(r.returncode, 1)
            self.assertIn("oracle", r.stderr)
            self.assertEqual(len(_rows(root)), before)

    def test_exactly_200_characters_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _seed(root, RED_THEN_ONE)
            r = _note(root, next="y" * 200)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(_rows(root)[-1]["note"]["next"], "y" * 200)

    def test_a_multi_line_field_is_refused_naming_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _seed(root, RED_THEN_ONE)
            before = len(_rows(root))
            r = _note(root, hypothesis="line one\nline two")
            self.assertEqual(r.returncode, 1)
            self.assertIn("hypothesis", r.stderr)
            self.assertEqual(len(_rows(root)), before)

    def test_a_missing_or_empty_field_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _seed(root, RED_THEN_ONE)
            before = len(_rows(root))
            r = _note(root, changed=None)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("changed", r.stderr)
            r = _note(root, changed="   ")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("changed", r.stderr)
            self.assertEqual(len(_rows(root)), before)


class TestAttemptNotes(unittest.TestCase):
    def test_notes_are_oldest_first_across_restarts_and_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _seed(root, RED_THEN_ONE)
            self.assertEqual(_note(root, hypothesis="first idea").returncode, 0)
            _seed(root, [{"gate": "unit", "task": "1.2", "exit": 1},
                         {"gate": "restart", "task": "1.2"},
                         {"gate": "unit", "task": "1.2", "exit": 1}])
            self.assertEqual(_note(root, hypothesis="after the restart").returncode, 0)
            _seed(root, [{"gate": "attempt-note", "task": "2.1", "attempt": 1,
                          "note": {"hypothesis": "other task", "changed": "c",
                                   "oracle": "o", "next": "n"}}])

            r = _run(root, "attempt", "notes", "1.2")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertLess(r.stdout.index("first idea"), r.stdout.index("after the restart"))
            self.assertNotIn("other task", r.stdout)

            r = _run(root, "attempt", "notes", "1.2", "--json")
            self.assertEqual(r.returncode, 0, r.stderr)
            doc = json.loads(r.stdout)
            self.assertEqual(doc["task"], "1.2")
            self.assertEqual([n["hypothesis"] for n in doc["notes"]],
                             ["first idea", "after the restart"])
            self.assertEqual([n["attempt"] for n in doc["notes"]], [1, 1])
            self.assertEqual(set(doc["notes"][0]),
                             {"attempt", "hypothesis", "changed", "oracle", "next"})

    def test_no_notes_is_an_empty_list_not_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _seed(root, RED_THEN_ONE)
            r = _run(root, "attempt", "notes", "1.2", "--json")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.loads(r.stdout), {"task": "1.2", "notes": []})


if __name__ == "__main__":
    unittest.main()
