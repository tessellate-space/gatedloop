"""The reflog audit's vouching by the head (`taint-preclear`, design D1/D2,
issue #132).

A commit with no green `ci` row of its own is recorded `vouched`, not
tainted, when it is an ancestor of the audited head and a green UNSCOPED
`ci` row names the head's tree, compared ledger-blind. A scoped head `ci`,
or none, taints as before; a `vouched` row counts as already classified.

Stdlib only, per `zero-dep-shim`. Real git repositories and real `gates run
ci` / `gates audit` subprocesses: the join is on real trees and real ledger
rows. `CLAUDECODE` is set explicitly, never inherited.

Run with:  python3 -m unittest tests.test_audit_vouched
"""

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
CHANGE = "my-change"

_loader = importlib.machinery.SourceFileLoader("gates_shim_audit_vouched", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)

MANIFEST = 'gatesVersion: 1\ngates:\n  ci: "true"\n'

# One non-catch-all surface with its own `ci`: a staged diff touching only
# `docs/**` runs the scoped command and records `scope: docs`.
SCOPED_MANIFEST = """\
gatesVersion: 1
gates:
  ci: "true"
surfaces:
  - name: docs
    match: "docs/**"
    gates:
      ci: "true"
"""


def _env():
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["CLAUDECODE"] = "1"
    return env


def _git(cwd, *args):
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True, env=_env(),
    ).stdout.strip()


def _gates(root, *args):
    return subprocess.run(
        [sys.executable, str(GATES_SHIM), *args],
        cwd=root, capture_output=True, text=True, env=_env(),
    )


def _rows(root):
    p = root / ".gatedloop" / "runs" / f"{CHANGE}.jsonl"
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


def _of(root, gate):
    return [r for r in _rows(root) if r.get("gate") == gate]


def _repo(tmp, manifest=MANIFEST):
    root = Path(tmp)
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(manifest)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")
    _git(root, "checkout", "-b", CHANGE)
    return root


def _ungated(root, rel):
    f = root / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(rel + "\n")
    _git(root, "add", rel)
    _git(root, "commit", "-m", f"ungated {rel}")
    return _git(root, "rev-parse", "HEAD")


def _gated(root, rel, with_ledger=False):
    """Stage, a green `gates run ci` on the staged tree, commit. With
    `with_ledger`, the ledger row that run appended is committed too, as
    tdd-apply does -- the commit's raw tree then differs from the ci row's
    by the ledger alone."""
    f = root / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(rel + "\n")
    _git(root, "add", rel)
    r = _gates(root, "run", "ci", "--change", CHANGE)
    assert r.returncode == 0, r.stderr
    if with_ledger:
        _git(root, "add", ".gatedloop/runs")
    _git(root, "commit", "-m", f"gated {rel}")
    return _git(root, "rev-parse", "HEAD")


def _audit(root):
    return _gates(root, "audit", "--change", CHANGE)


class VouchedByAnUnscopedHeadCi(unittest.TestCase):
    def test_an_ungated_ancestor_is_vouched_not_tainted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            c1 = _ungated(root, "a.txt")
            _gated(root, "b.txt")

            r = _audit(root)

            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(_of(root, "taint"), [])
            vouched = _of(root, "vouched")
            self.assertEqual([v["sha"] for v in vouched], [c1])
            self.assertEqual(vouched[0]["tree"], _git(root, "rev-parse", f"{c1}^{{tree}}"))
            self.assertEqual(vouched[0]["change"], CHANGE)

    def test_the_head_tree_is_compared_ledger_blind(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            c1 = _ungated(root, "a.txt")
            _gated(root, "b.txt", with_ledger=True)

            r = _audit(root)

            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(_of(root, "taint"), [])
            self.assertEqual([v["sha"] for v in _of(root, "vouched")], [c1])

    def test_an_individually_gated_commit_is_not_recorded_as_vouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            c1 = _ungated(root, "a.txt")
            head = _gated(root, "b.txt")

            _audit(root)

            shas = [v["sha"] for v in _of(root, "vouched")]
            self.assertIn(c1, shas)
            self.assertNotIn(head, shas, "the head has its own green ci row")


class NoVouchWithoutAnUnscopedHeadCi(unittest.TestCase):
    def test_a_scoped_head_ci_vouches_for_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, SCOPED_MANIFEST)
            c1 = _ungated(root, "a.txt")
            _gated(root, "docs/x.md")
            self.assertEqual([r.get("scope") for r in _of(root, "ci")], ["docs"],
                             "fixture: the head's ci must have run scoped")

            r = _audit(root)

            self.assertEqual(r.returncode, 1)
            self.assertEqual([t["sha"] for t in _of(root, "taint")], [c1])
            self.assertEqual(_of(root, "vouched"), [])

    def test_a_commit_after_the_head_ci_is_not_vouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            c1 = _ungated(root, "a.txt")
            _gated(root, "b.txt")
            c3 = _ungated(root, "c.txt")

            r = _audit(root)

            self.assertEqual(r.returncode, 1)
            self.assertEqual([t["sha"] for t in _of(root, "taint")], [c1, c3])
            self.assertEqual(_of(root, "vouched"), [])

    def test_no_head_ci_taints_as_before(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            c1 = _ungated(root, "a.txt")
            c2 = _ungated(root, "b.txt")

            r = _audit(root)

            self.assertEqual(r.returncode, 1)
            self.assertEqual([t["sha"] for t in _of(root, "taint")], [c1, c2])
            self.assertEqual(_of(root, "vouched"), [])


class VouchedIsClassified(unittest.TestCase):
    def test_a_vouched_commit_is_not_re_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _ungated(root, "a.txt")
            _gated(root, "b.txt")
            self.assertEqual(_audit(root).returncode, 0)
            before = _rows(root)

            # Drop the cursor so the walk covers the same commits again; the
            # sha dedupe alone must keep the commit from being recorded twice.
            cursor = Path(_git(root, "rev-parse", "--absolute-git-dir")) / "gatedloop" / "audit" / f"{CHANGE}.head"
            self.assertTrue(cursor.exists())
            cursor.unlink()
            r = _audit(root)

            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(_rows(root), before, "neither re-vouched nor tainted")

    def test_vouched_rows_count_as_classified(self):
        rows = [{"gate": "vouched", "sha": "abc"}]
        self.assertIn("abc", gates._existing_classified_shas(rows))

    def test_vouched_is_not_a_gate_outcome(self):
        self.assertIn("vouched", gates.NON_GATE_EVENTS)


if __name__ == "__main__":
    unittest.main()
