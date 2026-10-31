"""End to end: a tagged plan through the whole loop (openspec change
`task-oracle`, task 6.1).

A fixture change with an `integration`-tagged task, a characterization task on
`integration` and a `none` task goes through validate, the handoff, placement,
the red (or green-first) step on each declared gate, one commit per task with
the lock passing, and the `gates merge` step-1 head proof on the finished
branch. This pins the composition of tasks 1.1-3.3, each tested on its own
already, so it is a characterization test: it passes on the tree it is placed
on.

Stdlib only, per `zero-dep-shim`. A throwaway git repository with a local
`main` as the merge target; the shim is driven as a subprocess, and the step-1
proof is the shim's own function, run against that repository.

Run with:  python3 -m unittest discover -s tests
"""

import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from _approved_plan import record_approval

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"
CHANGE = "tagged-e2e"
CDIR = f"openspec/changes/{CHANGE}"

MANIFEST = """\
gatesVersion: 1
gates:
  ci: "true"
  unit: "sh -c 'exit $(cat unit.rc)'"
  integration: "sh -c 'exit $(cat integration.rc)'"
"""

TASKS = """\
## 1. Work

- [ ] 1.1 Wire the e2e step [oracle: integration]
- [ ] 1.2 Pin the rows 1.1 wrote [oracle: integration characterization]
- [ ] 1.3 Describe it in the README [oracle: none]
"""

PROVE_HEAD = textwrap.dedent("""\
    import importlib.machinery, importlib.util, sys
    from pathlib import Path
    loader = importlib.machinery.SourceFileLoader("gates_e2e_prove", sys.argv[1])
    spec = importlib.util.spec_from_loader(loader.name, loader)
    gates = importlib.util.module_from_spec(spec)
    loader.exec_module(gates)
    root = Path(sys.argv[2])
    m, _path = gates.load_manifest()
    try:
        tree = gates._merge_prove_head(m, root, sys.argv[3], require_acceptance=False)
    except gates._MergeHalt as halt:
        print(f"refused at step {halt.step}: {halt.message}", file=sys.stderr)
        sys.exit(1)
    print(tree)
""")


def _env():
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.pop("CLAUDE_PROJECT_DIR", None)
    env["CLAUDECODE"] = "1"
    return env


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                          text=True, env=_env())


def _write(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def _gates(root, *args):
    return subprocess.run([sys.executable, str(GATES_SHIM), *args], cwd=root,
                          capture_output=True, text=True, env=_env(), timeout=120)


def _ok(test, result, what):
    test.assertEqual(result.returncode, 0, f"{what}: {result.stdout}{result.stderr}")


def _tick(root, task):
    p = root / CDIR / "tasks.md"
    p.write_text(p.read_text().replace(f"- [ ] {task} ", f"- [x] {task} "))


class TestATaggedPlanEndToEnd(unittest.TestCase):
    """Regression guarded: the pieces each working alone while the loop as a
    whole cannot carry a tagged plan from handoff to a provable head (a lock
    reading one gate while the brief, the handoff or the merge proof reads
    another)."""

    def test_handoff_to_head_proof(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _git(root, "init", "-b", "main")
            _git(root, "config", "user.email", "t@example.com")
            _git(root, "config", "user.name", "T")
            _write(root, ".gates.yaml", MANIFEST)
            _write(root, ".gitignore", "unit.rc\nintegration.rc\n")
            _write(root, f"{CDIR}/proposal.md", "# Proposal: tagged\n\n## Why\n\nBecause.\n")
            _write(root, f"{CDIR}/tasks.md", TASKS)
            # `gates merge` step 1 proves the plan approval first (loop-hardening D1).
            record_approval(root, CHANGE)
            _write(root, "src/app.py", "def app():\n    return 1\n")
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "plan")
            _ok(self, _gates(root, "validate"), "validate")
            _git(root, "checkout", "-b", CHANGE)
            _write(root, "unit.rc", "0\n")

            held = root / ".gatedloop" / "authored" / CHANGE
            _write(held, "1.1/tests/test_e2e.py.authored", "def test_e2e():\n    assert False\n")
            _write(held, "1.2/tests/test_rows.py.authored", "def test_rows():\n    assert True\n")
            _write(held, "1.2/CHARACTERIZATION", "pins the rows task 1.1 already wrote\n")
            _write(held, "1.3/NO-TESTS", "a README paragraph; no behaviour\n")
            _ok(self, _gates(root, "tests", "handoff", CHANGE), "handoff")
            _git(root, "add", "-A")
            _ok(self, _gates(root, "run", "ci"), "ci on the authoring commit")
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "author tests")

            steps = {
                "1.1": ("integration", "1\n", False),   # red first on its gate
                "1.2": ("integration", "0\n", True),    # green first on its gate
                "1.3": (None, None, None),              # no tests, no red step
            }
            for task, (gate, rc, green_first) in steps.items():
                _ok(self, _gates(root, "task", "start", task), f"task start {task}")
                _ok(self, _gates(root, "tests", "place", task), f"place {task}")
                if gate is not None:
                    _write(root, f"{gate}.rc", rc)
                    first = _gates(root, "run", gate, "--task", task)
                    if green_first:
                        self.assertEqual(first.returncode, 0, first.stderr)
                    else:
                        self.assertNotIn(first.returncode, (0, 75), first.stdout)
                    _write(root, f"{gate}.rc", "0\n")
                _write(root, "src/app.py", f"def app():\n    return 1  # {task}\n")
                _tick(root, task)
                _git(root, "add", "-A")
                _ok(self, _gates(root, "run", "ci", "--task", task), f"ci {task}")
                _git(root, "add", "-A")
                _ok(self, _gates(root, "tests", "check"), f"tests check {task}")
                _git(root, "commit", "-m", f"task {task}")

            _ok(self, _gates(root, "tests", "check", "--ref", "HEAD", "--change", CHANGE),
                "tests check --ref")
            _ok(self, _gates(root, "run", "ci"), "unscoped ci on the head")
            _ok(self, _gates(root, "run", "live-check"), "live-check on the head")
            proof = subprocess.run(
                [sys.executable, "-c", PROVE_HEAD, str(GATES_SHIM), str(root), CHANGE],
                cwd=root, capture_output=True, text=True, env=_env(), timeout=120)
            _ok(self, proof, "merge step 1")


if __name__ == "__main__":
    unittest.main()
