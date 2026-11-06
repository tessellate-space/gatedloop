"""`gates ledger record-ready` under `loop.ci-at: ready` (openspec change
`ci-at`, design D4; the loop-enforcement delta's "The READY report's gate
fields are read from the ledger" requirement).

Under `ready` task commits run `unit`, so READY is where the full `ci` must
run. The regressions: a `ready` row appended with no green unscoped `ci` on
the head; a scoped or union-scoped `ci` row accepted as the full one; a
refusal that writes a row anyway; and `task` (or no key) starting to refuse.

Real git in a throwaway repository. Stdlib only, per `zero-dep-shim`.
Run with: python3 -m unittest discover -s tests
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

CHANGE = "demo-change"
LEDGER = f".gatedloop/runs/{CHANGE}.jsonl"
BASE = (
    'gatesVersion: 1\ngates:\n  ci: "true"\n  unit: "true"\n'
    'surfaces:\n  - name: app\n    match: "app/**"\n    gates:\n      ci: "true"\n'
)
READY = BASE + "loop:\n  ci-at: ready\n"


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
                          capture_output=True, text=True, env=_env(), timeout=120)


class _Repo(unittest.TestCase):
    MANIFEST = READY

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        _git(self.root, "init", "-q", "-b", "main")
        _git(self.root, "config", "user.email", "t@example.com")
        _git(self.root, "config", "user.name", "T")
        (self.root / ".gates.yaml").write_text(self.MANIFEST)
        d = self.root / "openspec" / "changes" / CHANGE
        d.mkdir(parents=True)
        (d / "tasks.md").write_text("## 1. Work\n\n- [x] 1.1 do it\n")
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-q", "-m", "init")
        _git(self.root, "checkout", "-q", "-b", CHANGE)
        # One task commit, gated on a scoped `ci` (its surface declares one).
        (self.root / "app").mkdir()
        (self.root / "app" / "a.py").write_text("x = 1\n")
        _git(self.root, "add", "app/a.py")
        r = _gates(self.root, "run", "ci")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("ci[app]", r.stderr)
        _git(self.root, "add", LEDGER)
        _git(self.root, "commit", "-q", "--no-verify", "-m", "task 1.1")

    def tearDown(self):
        self._tmp.cleanup()

    def _rows(self):
        p = self.root / LEDGER
        return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]

    def _ready_rows(self):
        return [r for r in self._rows() if r.get("gate") == "ready"]

    def _record_ready(self):
        return _gates(self.root, "ledger", "record-ready", CHANGE)


class TestUnderReady(_Repo):
    def test_refused_with_only_a_scoped_ci_row(self):
        r = self._record_ready()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(self._ready_rows(), [])
        self.assertIn("gates run ci", r.stderr)
        self.assertIn("nothing staged", r.stderr)

    def test_refused_with_no_ci_row_at_all(self):
        (self.root / "b.txt").write_text("b\n")
        _git(self.root, "add", "b.txt")
        _git(self.root, "commit", "-q", "--no-verify", "-m", "no gate")
        r = self._record_ready()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(self._ready_rows(), [])

    def test_refused_with_only_a_union_ci_row_on_the_head(self):
        tree = _git(self.root, "rev-parse", "HEAD^{tree}")
        with (self.root / LEDGER).open("a") as f:
            f.write(json.dumps({"gate": "ci", "exit": 0, "change": CHANGE, "task": None,
                                "tree": tree, "scope": "app+web",
                                "ts": "2026-11-01T00:00:00+00:00"}) + "\n")
        r = self._record_ready()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(self._ready_rows(), [])

    def test_allowed_after_an_unscoped_ci_on_the_head(self):
        ci = _gates(self.root, "run", "ci")
        self.assertEqual(ci.returncode, 0, ci.stdout + ci.stderr)
        self.assertIn("ci[full]", ci.stderr)
        # The run's own row is uncommitted: the comparison is ledger-blind.
        r = self._record_ready()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(len(self._ready_rows()), 1)
        self.assertIn('"ci": "pass"', r.stdout)


class TestUnderTask(_Repo):
    MANIFEST = BASE

    def test_appended_and_reports_fail_as_before(self):
        r = self._record_ready()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(len(self._ready_rows()), 1)
        self.assertIn('"ci": "fail"', r.stdout)


if __name__ == "__main__":
    unittest.main()
