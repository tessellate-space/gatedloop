"""Union-scoped `ci` under `loop.ci-scope: union` (openspec change `ci-at`,
design D8; the gate-binding delta's "A surface may bind scoped commit
oracles" and "Union-scoped ci is declared by `loop.ci-scope`" requirements).

Under `union`, a staged diff that hits two or more non-catch-all surfaces,
every one declaring a `ci` override, runs those overrides instead of the
global `ci`. The regressions: an override skipped, a red one hidden by a
later green, a duplicate run, a command run past a failed precondition, the
union taken when a hot surface has no override or a path is unmatched, the
union marker satisfying READY, the merge's full-scope check or vouching, and
the union taken with the key absent or `single`.

Each command appends a line to a file outside the repository, so what ran is
read from that file. Real git, stdlib only, per `zero-dep-shim`.
Run with: python3 -m unittest discover -s tests
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"
CHANGE = "union-change"
LEDGER = f".gatedloop/runs/{CHANGE}.jsonl"

_loader = importlib.machinery.SourceFileLoader("gates_shim_ci_scope_union", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)


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


class _Case(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.root = base / "repo"
        self.root.mkdir()
        self.ran = base / "ran.txt"

    def tearDown(self):
        self._tmp.cleanup()

    def cmd(self, word, exit_code=0):
        tail = f"; exit {exit_code}" if exit_code else ""
        return f'"echo {word} >> {self.ran}{tail}"'

    def manifest(self, api=None, web=None, scope="union", api_requires=None):
        def surface(name, override, requires=None):
            text = f"  - name: {name}\n    match: \"{name}/**\"\n"
            if override and requires:
                text += (f"    gates:\n      ci:\n        run: {override}\n"
                         f"        requires: {requires}\n")
            elif override:
                text += f"    gates:\n      ci: {override}\n"
            return text
        text = (
            "gatesVersion: 1\ngates:\n"
            f"  ci: {self.cmd('GLOBAL')}\n  unit: \"true\"\n"
            "surfaces:\n"
            + surface("api", api, api_requires) + surface("web", web)
            + '  - name: all\n    match: "**"\n'
        )
        if scope:
            text += f"loop:\n  ci-scope: {scope}\n"
        return text

    def init(self, manifest):
        _git(self.root, "init", "-q", "-b", "main")
        _git(self.root, "config", "user.email", "t@example.com")
        _git(self.root, "config", "user.name", "T")
        (self.root / ".gates.yaml").write_text(manifest)
        (self.root / "openspec" / "changes" / CHANGE).mkdir(parents=True)
        (self.root / "openspec" / "changes" / CHANGE / "tasks.md").write_text("- [ ] 1.1 a\n")
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-q", "-m", "init")
        _git(self.root, "checkout", "-q", "-b", CHANGE)

    def stage(self, *rels):
        for rel in rels:
            p = self.root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(rel + "\n")
            _git(self.root, "add", rel)

    def lines(self):
        return self.ran.read_text().splitlines() if self.ran.exists() else []

    def ci_rows(self):
        p = self.root / LEDGER
        rows = [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []
        return [r for r in rows if r.get("gate") == "ci"]

    def marker(self):
        d = Path(_git(self.root, "rev-parse", "--absolute-git-dir")) / "gatedloop" / "markers" / "ci"
        files = list(d.glob("*.json")) if d.exists() else []
        return [json.loads(f.read_text()) for f in files]


class TestUnion(_Case):
    def test_both_overrides_run_and_the_scope_names_both(self):
        self.init(self.manifest(self.cmd("API"), self.cmd("WEB")))
        self.stage("api/a.py", "web/w.js")

        r = _gates(self.root, "run", "ci")

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(sorted(self.lines()), ["API", "WEB"])
        self.assertEqual(self.ci_rows()[-1]["scope"], "api+web")
        self.assertEqual([mk["scope"] for mk in self.marker()], ["api+web"])

    def test_the_first_non_zero_exit_wins_and_every_command_runs(self):
        self.init(self.manifest(self.cmd("API", 3), self.cmd("WEB", 5)))
        self.stage("api/a.py", "web/w.js")

        r = _gates(self.root, "run", "ci")

        self.assertEqual(r.returncode, 3, r.stderr)
        self.assertEqual(sorted(self.lines()), ["API", "WEB"])
        self.assertEqual(self.marker(), [])

    def test_identical_commands_run_once(self):
        self.init(self.manifest(self.cmd("SAME"), self.cmd("SAME")))
        self.stage("api/a.py", "web/w.js")

        r = _gates(self.root, "run", "ci")

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.lines(), ["SAME"])

    def test_a_failed_precondition_runs_nothing(self):
        self.init(self.manifest(self.cmd("API"), self.cmd("WEB"), api_requires='"false"'))
        self.stage("api/a.py", "web/w.js")

        r = _gates(self.root, "run", "ci")

        self.assertEqual(r.returncode, 75, r.stderr)
        self.assertEqual(self.lines(), [])

    def test_a_hot_surface_without_an_override_runs_the_global_alone(self):
        self.init(self.manifest(self.cmd("API"), None))
        self.stage("api/a.py", "web/w.js")

        r = _gates(self.root, "run", "ci")

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.lines(), ["GLOBAL"])
        self.assertEqual(self.ci_rows()[-1]["scope"], "full")

    def test_an_unmatched_path_runs_the_global_and_names_it(self):
        self.init(self.manifest(self.cmd("API"), self.cmd("WEB")))
        self.stage("api/a.py", "web/w.js", "loose.txt")

        r = _gates(self.root, "run", "ci")

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.lines(), ["GLOBAL"])
        self.assertIn("loose.txt", r.stderr)


class TestTheUnionMarkerIsScoped(_Case):
    def setUp(self):
        super().setUp()
        self.init(self.manifest(self.cmd("API"), self.cmd("WEB")) + "  ci-at: ready\n")
        self.stage("api/a.py", "web/w.js")
        r = _gates(self.root, "run", "ci")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.tree = _git(self.root, "write-tree")

    def test_it_allows_the_commit(self):
        r = _gates(self.root, "discipline", "check-commit", self.tree)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_it_fails_the_full_scope_check(self):
        r = _gates(self.root, "gate-marker", "check", "ci", self.tree, "--require-scope", "full")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)

    def test_it_satisfies_neither_ready_nor_vouching(self):
        _git(self.root, "add", LEDGER)
        _git(self.root, "commit", "-q", "--no-verify", "-m", "1.1")
        rows = gates._read_ledger_rows(self.root, CHANGE)
        m = {"gates": {"ci": "true"}}
        head = _git(self.root, "rev-parse", "HEAD^{tree}")
        self.assertEqual(gates._ready_gates(m, self.root, CHANGE, head)["ci"], "fail")
        self.assertFalse(gates._GreenCiMatcher(self.root, rows).has_unscoped(head))
        r = _gates(self.root, "ledger", "record-ready", CHANGE)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)


class TestSingleOrAbsent(_Case):
    def test_absent_or_single_runs_the_global(self):
        for scope in (None, "single"):
            with self.subTest(scope=scope):
                self.tearDown()
                self.setUp()
                self.init(self.manifest(self.cmd("API"), self.cmd("WEB"), scope=scope))
                self.stage("api/a.py", "web/w.js")

                r = _gates(self.root, "run", "ci")

                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(self.lines(), ["GLOBAL"])

    def test_an_unknown_value_fails_validation(self):
        self.init(self.manifest(self.cmd("API"), self.cmd("WEB"), scope="all"))
        r = _gates(self.root, "validate")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("loop.ci-scope", r.stderr)
        self.assertIn("'single'", r.stderr)
        self.assertIn("'union'", r.stderr)

    def test_the_mode_helper_and_the_schema(self):
        self.assertEqual(gates._ci_scope_mode({}), "single")
        self.assertEqual(gates._ci_scope_mode({"loop": {"ci-scope": "union"}}), "union")
        self.assertEqual(gates._ci_scope_mode({"loop": {"ci-scope": "all"}}), "single")
        schema = json.loads((REPO / "schema" / "gates.schema.json").read_text())
        self.assertEqual(sorted(schema["properties"]["loop"]["properties"]["ci-scope"]["enum"]),
                         ["single", "union"])


if __name__ == "__main__":
    unittest.main()
