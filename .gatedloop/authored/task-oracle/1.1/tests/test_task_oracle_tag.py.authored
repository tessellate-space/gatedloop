"""The per-task oracle tag on a `tasks.md` line (openspec change `task-oracle`,
design D1 and D2; the test-discipline delta's "A task may declare its oracle in
the plan" requirement).

`_task_lines` is the one parser every consumer reads: it returns each task's
id, its text with the tag stripped, and the declared oracle -- `None` for an
untagged task, `{"gate": <name>, "characterization": <bool>}` for a gate, and
`{"gate": None, "characterization": False}` for `[oracle: none]`.

Stdlib only, per `zero-dep-shim`. Pure: the parser is tested directly on a
written file.

Run with:  python3 -m unittest discover -s tests
"""

import importlib.machinery
import importlib.util
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

_loader = importlib.machinery.SourceFileLoader("gates_shim_task_oracle_tag", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)


def _lines(text):
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "tasks.md"
        p.write_text(text)
        return gates._task_lines(p)


def _one(line):
    out = _lines(f"## 1. Group\n\n{line}\n")
    if len(out) != 1:
        raise AssertionError(f"expected one task line, got {out!r}")
    return out[0]


class TestTheTagForms(unittest.TestCase):
    """Regression guarded: a tag read as part of the task's prose, so the
    plan's declared oracle never reaches the author, the handoff or the lock."""

    def test_a_gate(self):
        self.assertEqual(
            _one("- [ ] 1.1 Parse the tag [oracle: unit]"),
            ("1.1", "Parse the tag", {"gate": "unit", "characterization": False}),
        )

    def test_a_gate_with_characterization(self):
        self.assertEqual(
            _one("- [ ] 3.1 Verify written data [oracle: integration characterization]"),
            ("3.1", "Verify written data",
             {"gate": "integration", "characterization": True}),
        )

    def test_none(self):
        self.assertEqual(
            _one("- [ ] 4.2 Edit the prompt [oracle: none]"),
            ("4.2", "Edit the prompt", {"gate": None, "characterization": False}),
        )

    def test_a_checked_task_carries_its_tag_too(self):
        self.assertEqual(
            _one("- [x] 2.1 Done already [oracle: unit]"),
            ("2.1", "Done already", {"gate": "unit", "characterization": False}),
        )

    def test_an_untagged_task_has_no_oracle(self):
        self.assertEqual(_one("- [ ] 1.2 Plain task"), ("1.2", "Plain task", None))


class TestWhitespace(unittest.TestCase):
    """Regression guarded: a hand-typed tag with an extra space read as no tag."""

    def test_stray_whitespace_inside_and_after_the_tag(self):
        self.assertEqual(
            _one("- [ ] 1.4 Do it   [ oracle:   unit    characterization ]   "),
            ("1.4", "Do it", {"gate": "unit", "characterization": True}),
        )

    def test_no_space_after_the_colon(self):
        self.assertEqual(
            _one("- [ ] 1.5 Do it [oracle:none]"),
            ("1.5", "Do it", {"gate": None, "characterization": False}),
        )


class TestOnlyATrailingSpanIsATag(unittest.TestCase):
    """Regression guarded: prose that mentions the syntax mid-line (a plan
    task that documents the tag, say) mistaken for a declaration."""

    def test_a_tag_mid_line_is_not_a_tag(self):
        tid, text, oracle = _one("- [ ] 1.6 Document [oracle: unit] in SETUP.md")
        self.assertEqual(tid, "1.6")
        self.assertIsNone(oracle)
        self.assertEqual(text, "Document [oracle: unit] in SETUP.md")

    def test_only_the_last_span_is_read(self):
        tid, text, oracle = _one("- [ ] 1.7 Mention [oracle: none] then tag [oracle: unit]")
        self.assertEqual(oracle, {"gate": "unit", "characterization": False})
        self.assertEqual(text, "Mention [oracle: none] then tag")


class TestConsumersReadTheStrippedText(unittest.TestCase):
    """Regression guarded: every other consumer of the task text (the brief's
    task list among them) carrying the tag as if it were part of the task."""

    def test_no_returned_text_carries_the_tag(self):
        out = _lines(
            "## 1. G\n\n"
            "- [ ] 1.1 One [oracle: unit]\n"
            "- [ ] 1.2 Two [oracle: integration characterization]\n"
            "- [ ] 1.3 Three [oracle: none]\n"
            "- [ ] 1.4 Four\n"
        )
        self.assertEqual([t for t, _x, _o in out], ["1.1", "1.2", "1.3", "1.4"])
        for _tid, text, _oracle in out:
            self.assertNotIn("[oracle", text)

    def test_non_oracle_gates(self):
        self.assertEqual(set(gates.NON_ORACLE_GATES), {"ci", "live-check", "eval", "confirm"})


if __name__ == "__main__":
    unittest.main()
