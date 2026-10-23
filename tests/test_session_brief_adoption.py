"""The session brief's adoption line (openspec change `adoption-prompts`,
design D4): one line when settings wait, one line when the check fails,
nothing otherwise, and never a question.

`hooks/_session_brief.py` runs against a stub `gates` (a fixture plugin root's
`bin/gates`) whose `adoption status --json` answer each test chooses, so the
line is tested without a real catalogue or plugin version. The stub answers
nothing else, so the payload carries no change that would ask it more.

Stdlib only. Run with:  python3 -m unittest discover -s tests
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BRIEF_HELPER = REPO / "hooks" / "_session_brief.py"

STUB = """\
#!{python}
import sys
if sys.argv[1:] == ["adoption", "status", "--json"]:
    sys.stdout.write({stdout!r})
    sys.stderr.write({stderr!r})
    sys.exit({code})
sys.exit(2)
"""

# A complete change, so the brief has a line of its own to keep.
PAYLOAD = json.dumps({"changes": [
    {"name": "done-change", "status": "complete", "completedTasks": 2, "totalTasks": 2}]})


def brief(stdout="", stderr="", code=0):
    with tempfile.TemporaryDirectory() as tmp:
        plugin = Path(tmp) / "plugin"
        (plugin / "bin").mkdir(parents=True)
        stub = plugin / "bin" / "gates"
        stub.write_text(STUB.format(python=sys.executable, stdout=stdout, stderr=stderr,
                                    code=code))
        stub.chmod(0o755)
        env = dict(os.environ, CLAUDE_PLUGIN_ROOT=str(plugin))
        proc = subprocess.run([sys.executable, str(BRIEF_HELPER)], cwd=tmp, input=PAYLOAD,
                              env=env, capture_output=True, text=True, timeout=30)
        return proc.stdout


def status_doc(n):
    return json.dumps({"version": "0.5.0", "undecided": [
        {"id": f"item-{i}", "since": "0.5.0", "what": "w"} for i in range(n)]})


class TestAdoptionLine(unittest.TestCase):
    def adoption_lines(self, out):
        return [line for line in out.splitlines() if "/gatedloop:upgrade" in line
                or "adoption check" in line]

    def test_undecided_items_add_one_line_naming_version_count_and_command(self):
        out = brief(stdout=status_doc(3))
        lines = self.adoption_lines(out)
        self.assertEqual(len(lines), 1, out)
        for needle in ("0.5.0", "3", "/gatedloop:upgrade"):
            self.assertIn(needle, lines[0])
        self.assertIn("done-change", out)

    def test_nothing_undecided_adds_nothing(self):
        out = brief(stdout=status_doc(0))
        self.assertEqual(self.adoption_lines(out), [])
        self.assertIn("done-change", out)

    def test_failed_check_says_so_in_one_line_and_keeps_the_rest(self):
        out = brief(stderr="gatedloop: adoption status: the adoption catalogue is unreadable\n",
                    code=1)
        lines = self.adoption_lines(out)
        self.assertEqual(len(lines), 1, out)
        self.assertIn("adoption check could not run", lines[0])
        self.assertIn("unreadable", lines[0])
        self.assertIn("done-change", out)


if __name__ == "__main__":
    unittest.main()
