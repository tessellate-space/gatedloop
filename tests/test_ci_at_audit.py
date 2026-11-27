"""The audit under `loop.ci-at: ready` (openspec change `ci-at`, design D4;
the loop-enforcement delta's "An ungated commit is detected after the fact
and taints the change" requirement).

Under `ready` the commit hook allows a task commit on a `unit` marker, and the
`Stop` hook audits on every stop, before any full `ci` exists. The
regressions: such a commit tainted (a bypass incident for a rule-following
commit) or recorded `vouched`; a `unit` row matching under `task`; a `unit`
row vouching for an ancestor; and the merge's read-only check of a branch no
worktree holds naming a unit-gated commit as unrecorded.

Real git repositories and real `gates run` / `gates audit` subprocesses: the
join is on real trees and real ledger rows. `CLAUDECODE` is set explicitly.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
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
LEDGER = f".gatedloop/runs/{CHANGE}.jsonl"

_loader = importlib.machinery.SourceFileLoader("gates_shim_ci_at_audit", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)

BASE = 'gatesVersion: 1\ngates:\n  ci: "true"\n  unit: "true"\n'
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


def _rows(root):
    p = root / LEDGER
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


def _of(root, gate):
    return [r for r in _rows(root) if r.get("gate") == gate]


def _repo(tmp, manifest):
    root = Path(tmp)
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(manifest)
    d = root / "openspec" / "changes" / CHANGE
    d.mkdir(parents=True)
    (d / "tasks.md").write_text("## 1. Work\n\n- [ ] 1.1 a\n- [ ] 1.2 b\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    _git(root, "checkout", "-q", "-b", CHANGE)
    return root


def _commit_on(root, gate, rel):
    """Stage `rel`, run `gate` green on the staged tree, commit it with the
    ledger row (tdd-apply 5h). `gate` None: no run, the commit has no row."""
    f = root / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(rel + "\n")
    _git(root, "add", rel)
    if gate:
        r = _gates(root, "run", gate)
        assert r.returncode == 0, r.stdout + r.stderr
        _git(root, "add", LEDGER)
    _git(root, "commit", "-q", "--no-verify", "-m", f"{gate or 'no gate'}: {rel}")
    return _git(root, "rev-parse", "HEAD")


def _audit(root):
    return _gates(root, "audit", "--change", CHANGE)


class UnderReady(unittest.TestCase):
    def test_a_unit_gated_commit_before_any_full_ci_is_neither_tainted_nor_vouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, READY)
            _commit_on(root, "unit", "a.txt")

            r = _audit(root)

            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(_of(root, "taint"), [])
            self.assertEqual(_of(root, "vouched"), [])
            # Classified by session as a ci-gated commit is: an agent's row
            # records nothing, never an unclassified disclosure.
            self.assertEqual(_of(root, "unclassified-commit"), [])
            self.assertEqual(_of(root, "intervention"), [])

    def test_a_unit_gated_commit_outside_a_session_is_a_human_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, READY)
            env = _env()
            env.pop("CLAUDECODE", None)
            (root / "a.txt").write_text("a\n")
            _git(root, "add", "a.txt")
            r = subprocess.run([sys.executable, str(GATES_SHIM), "run", "unit"], cwd=root,
                               capture_output=True, text=True, env=env, timeout=120)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            _git(root, "add", LEDGER)
            _git(root, "commit", "-q", "--no-verify", "-m", "human")

            _audit(root)

            self.assertEqual(_of(root, "taint"), [])
            self.assertEqual([x.get("cause") for x in _of(root, "intervention")],
                             ["human-commit"])

    def test_a_commit_with_no_row_taints_until_the_ready_ci_vouches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, READY)
            _commit_on(root, "unit", "a.txt")
            bad = _commit_on(root, None, "b.txt")

            r = _audit(root)

            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertEqual([x["sha"] for x in _of(root, "taint")], [bad])

            # The READY ci, unscoped on the head, clears it.
            ci = _gates(root, "run", "ci")
            self.assertEqual(ci.returncode, 0, ci.stdout + ci.stderr)
            self.assertEqual(len(_of(root, "taint-clear")), 1)

    def test_a_row_less_commit_audited_after_the_ready_ci_is_vouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, READY)
            _commit_on(root, "unit", "a.txt")
            bad = _commit_on(root, None, "b.txt")
            _commit_on(root, "unit", "c.txt")
            ci = _gates(root, "run", "ci")
            self.assertEqual(ci.returncode, 0, ci.stdout + ci.stderr)

            _audit(root)

            self.assertEqual(_of(root, "taint"), [])
            self.assertEqual([x["sha"] for x in _of(root, "vouched")], [bad])

    def test_a_unit_row_on_the_head_never_vouches_for_an_ancestor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, READY)
            bad = _commit_on(root, None, "a.txt")
            _commit_on(root, "unit", "b.txt")

            r = _audit(root)

            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertEqual([x["sha"] for x in _of(root, "taint")], [bad])
            self.assertEqual(_of(root, "vouched"), [])

    def test_the_merge_read_only_check_names_no_unit_gated_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, READY)
            _commit_on(root, "unit", "a.txt")
            _commit_on(root, "ci", "b.txt")
            bad = _commit_on(root, None, "c.txt")
            _git(root, "checkout", "-q", "main")  # no worktree holds the branch
            rows = [json.loads(x) for x in
                    _git(root, "show", f"{CHANGE}:{LEDGER}").splitlines() if x.strip()]
            m = {"gates": {"ci": "true", "unit": "true"}, "loop": {"ci-at": "ready"}}

            self.assertEqual(gates._unrecorded_commits(root, CHANGE, rows, m), [bad])


class UnderTask(unittest.TestCase):
    def test_a_unit_only_commit_taints(self):
        for manifest in (BASE, BASE + "loop:\n  ci-at: task\n"):
            with self.subTest(manifest=manifest), tempfile.TemporaryDirectory() as tmp:
                root = _repo(tmp, manifest)
                sha = _commit_on(root, "unit", "a.txt")

                r = _audit(root)

                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertEqual([x["sha"] for x in _of(root, "taint")], [sha])

    def test_the_merge_read_only_check_names_a_unit_only_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, BASE)
            sha = _commit_on(root, "unit", "a.txt")
            _git(root, "checkout", "-q", "main")
            rows = [json.loads(x) for x in
                    _git(root, "show", f"{CHANGE}:{LEDGER}").splitlines() if x.strip()]
            m = {"gates": {"ci": "true", "unit": "true"}}

            self.assertEqual(gates._unrecorded_commits(root, CHANGE, rows, m), [sha])


if __name__ == "__main__":
    unittest.main()
