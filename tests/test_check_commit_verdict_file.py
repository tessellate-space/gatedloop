"""`gates discipline check-commit --verdict-file <path>` (change
`unblock-authored-lock`, design D1).

The commit hooks must know whether a commit was allowed at ledger grade, so
they can skip the authored-test lock for it, and must not learn it by
matching the human-readable line, which is free to change. The regressions:
a token that is missing, wrong for its verdict, or written on a denial; and
the flag changing the exit status or the printed text, which every other
caller of `check-commit` reads.

Real git in a throwaway repository: the verdict is a function of the staged
index, which only a real repository has.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

MANIFEST = 'gatesVersion: 1\ngates:\n  ci: "true"\n'


def _env():
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.pop("CLAUDE_PROJECT_DIR", None)
    env["CLAUDECODE"] = "1"
    return env


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                          text=True, env=_env()).stdout.strip()


def _gates(root, *args):
    return subprocess.run([sys.executable, str(GATES_SHIM), *args], cwd=root,
                          capture_output=True, text=True, env=_env())


class VerdictFileTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "repo"
        self.root.mkdir()
        self.verdict = Path(self._tmp.name) / "verdict"
        _git(self.root, "init", "-q", "-b", "main")
        _git(self.root, "config", "user.email", "t@example.com")
        _git(self.root, "config", "user.name", "T")
        (self.root / ".gates.yaml").write_text(MANIFEST)
        (self.root / "openspec").mkdir()
        (self.root / "openspec" / "config.yaml").write_text("schema: spec-driven\n")
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-q", "-m", "init")
        _git(self.root, "checkout", "-q", "-b", "my-change")
        (self.root / "openspec" / "changes" / "my-change").mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    def _stage_ledger_only(self):
        ledger = self.root / ".gatedloop" / "runs" / "my-change.jsonl"
        ledger.parent.mkdir(parents=True, exist_ok=True)
        ledger.write_text('{"gate": "halt", "task": "1.1", "change": "my-change"}\n')
        _git(self.root, "add", str(ledger.relative_to(self.root)))

    def _stage_planning_only(self):
        (self.root / "openspec" / "config.yaml").write_text("schema: spec-driven\n# edited\n")
        _git(self.root, "add", "openspec/config.yaml")

    def _stage_code_with_a_green_ci(self):
        (self.root / "app.py").write_text("print('hi')\n")
        _git(self.root, "add", "app.py")
        r = _gates(self.root, "run", "ci")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        _git(self.root, "add", "-A")

    def _check(self, *extra):
        tree = _git(self.root, "write-tree")
        return _gates(self.root, "discipline", "check-commit", tree, *extra)

    def test_each_allowed_verdict_writes_its_one_token(self):
        cases = (
            ("ledger", self._stage_ledger_only),
            ("planning", self._stage_planning_only),
            ("marker", self._stage_code_with_a_green_ci),
        )
        for token, stage in cases:
            with self.subTest(verdict=token):
                _git(self.root, "reset", "-q", "--hard")
                _git(self.root, "clean", "-qfdx", "-e", "openspec/changes")
                self.verdict.unlink(missing_ok=True)
                stage()

                r = self._check("--verdict-file", str(self.verdict))

                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertEqual(self.verdict.read_text().strip(), token)

    def test_the_flag_changes_neither_the_exit_status_nor_the_printed_text(self):
        for name, stage in (("ledger", self._stage_ledger_only),
                            ("planning", self._stage_planning_only),
                            ("marker", self._stage_code_with_a_green_ci)):
            with self.subTest(verdict=name):
                _git(self.root, "reset", "-q", "--hard")
                _git(self.root, "clean", "-qfdx", "-e", "openspec/changes")
                stage()

                without = self._check()
                with_flag = self._check("--verdict-file", str(self.verdict))

                self.assertEqual(without.returncode, 0, without.stdout + without.stderr)
                self.assertEqual(with_flag.returncode, without.returncode)
                self.assertEqual(with_flag.stdout, without.stdout)
                self.assertEqual(with_flag.stderr, without.stderr)

    def test_a_denial_writes_no_token_and_keeps_its_exit_and_text(self):
        (self.root / "app.py").write_text("print('no ci ran on this')\n")
        _git(self.root, "add", "app.py")

        without = self._check()
        with_flag = self._check("--verdict-file", str(self.verdict))

        self.assertEqual(without.returncode, 1, without.stdout + without.stderr)
        self.assertEqual(with_flag.returncode, 1)
        self.assertEqual(with_flag.stdout, without.stdout)
        self.assertEqual(with_flag.stderr, without.stderr)
        self.assertFalse(self.verdict.exists() and self.verdict.read_text().strip(),
                         "a denied commit wrote a verdict token")


if __name__ == "__main__":
    unittest.main()
