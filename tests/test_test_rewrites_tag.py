"""The `rewrites:` clause of a task's oracle tag (openspec change
`test-rewrites`, design D1; the test-discipline delta's "A task may declare its
oracle in the plan" and "A task's oracle tag is held to the approved plan"
requirements).

A tag that names a gate may end with `rewrites: <path>[, <path>]...`: the
existing test files the task rewrites. The parsed oracle carries them as a
`rewrites` tuple in declared order; the canonical label appends the clause only
when it is non-empty, so a plan without it hashes exactly as before, and the
approval digest and the drift check cover it when it is there.

Stdlib only, per `zero-dep-shim`. The parser is tested directly; the approval
sha, `check-implement`, the handoff and `gates tests check --ref` on throwaway
git repositories with a local `main` as the merge target.

Run with:  python3 -m unittest discover -s tests
"""

import hashlib
import importlib.machinery
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

_loader = importlib.machinery.SourceFileLoader("gates_shim_test_rewrites_tag", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)

CHANGE = "rewrite-plan"
CDIR = f"openspec/changes/{CHANGE}"

MANIFEST = (
    'gatesVersion: 1\n'
    'approval:\n'
    '  plan: self\n'
    'gates:\n'
    '  ci: "true"\n'
    '  unit: "false"\n'
)

PROPOSAL = "# Proposal\n\nWhy.\n"
DESIGN = "# Design\n\nHow.\n"
SPEC = "## ADDED Requirements\n\n### Requirement: X\n"

TAGGED = """\
## 2. Work

- [ ] 2.1 Move the key [oracle: unit]
- [ ] 2.2 Add the parser [oracle: unit characterization]
"""


def _one(line):
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "tasks.md"
        p.write_text(f"## 1. Group\n\n{line}\n")
        out = gates._task_lines(p)
    if len(out) != 1:
        raise AssertionError(f"expected one task line, got {out!r}")
    return out[0]


def _rewrites(oracle):
    return tuple((oracle or {}).get("rewrites", ()))


class TestTheClause(unittest.TestCase):
    """Regression guarded: a declared rewrite read as a malformed tag, or
    dropped, so the plan's list of files the author may see never reaches the
    brief, the handoff or the approval digest."""

    def test_one_path(self):
        tid, text, oracle = _one("- [ ] 2.1 Move the key [oracle: unit rewrites: tests/a.test.ts]")
        self.assertEqual((tid, text), ("2.1", "Move the key"))
        self.assertEqual(oracle["gate"], "unit")
        self.assertFalse(oracle["characterization"])
        self.assertEqual(_rewrites(oracle), ("tests/a.test.ts",))

    def test_several_paths_in_declared_order(self):
        _tid, _text, oracle = _one(
            "- [ ] 2.1 Move [oracle: unit rewrites: tests/b.test.ts, tests/a.test.ts,infra/x_test.sh]")
        self.assertEqual(_rewrites(oracle),
                         ("tests/b.test.ts", "tests/a.test.ts", "infra/x_test.sh"))

    def test_stray_whitespace(self):
        _tid, _text, oracle = _one(
            "- [ ] 2.1 Move [ oracle:  unit   rewrites :  tests/a.test.ts ,   tests/b.test.ts  ]  ")
        self.assertEqual(oracle["gate"], "unit")
        self.assertEqual(_rewrites(oracle), ("tests/a.test.ts", "tests/b.test.ts"))

    def test_after_characterization(self):
        _tid, _text, oracle = _one(
            "- [ ] 2.1 Drop the timing [oracle: unit characterization rewrites: tests/a.test.ts]")
        self.assertEqual(oracle["gate"], "unit")
        self.assertTrue(oracle["characterization"])
        self.assertEqual(_rewrites(oracle), ("tests/a.test.ts",))

    def test_an_empty_clause_is_malformed(self):
        _tid, text, oracle = _one("- [ ] 2.1 Move [oracle: unit rewrites:]")
        self.assertIsNone(oracle)
        _tid, _text, oracle = _one("- [ ] 2.1 Move [oracle: unit rewrites:  ]")
        self.assertIsNone(oracle)

    def test_none_cannot_carry_it(self):
        _tid, _text, oracle = _one("- [ ] 2.1 Move [oracle: none rewrites: tests/a.test.ts]")
        self.assertIsNone(oracle)

    def test_the_clause_before_the_gate_is_malformed(self):
        _tid, _text, oracle = _one("- [ ] 2.1 Move [oracle: rewrites: tests/a.test.ts unit]")
        self.assertIsNone(oracle)

    def test_no_clause_means_no_rewrites(self):
        _tid, _text, oracle = _one("- [ ] 2.1 Move [oracle: unit]")
        self.assertEqual(_rewrites(oracle), ())

    def test_the_label_carries_the_clause_only_when_present(self):
        _t, _x, plain = _one("- [ ] 2.1 Move [oracle: unit characterization]")
        _t, _x, both = _one("- [ ] 2.1 Move [oracle: unit characterization rewrites: a/t.py,b/t.py]")
        self.assertEqual(gates._oracle_label(plain), "unit characterization")
        self.assertEqual(gates._oracle_label(both),
                         "unit characterization rewrites: a/t.py, b/t.py")


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
                          capture_output=True, text=True, env=_env(), timeout=60)


def _plan_repo(tmp, tasks):
    root = Path(tmp)
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    _write(root, ".gates.yaml", MANIFEST)
    _write(root, "src/app.py", "def app():\n    return 1\n")
    _write(root, "tests/test_app.py", "def test_app():\n    assert True\n")
    _write(root, f"{CDIR}/.openspec.yaml", "schema: spec-driven\n")
    _write(root, f"{CDIR}/proposal.md", PROPOSAL)
    _write(root, f"{CDIR}/design.md", DESIGN)
    _write(root, f"{CDIR}/specs/x/spec.md", SPEC)
    _write(root, f"{CDIR}/tasks.md", tasks)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "plan")
    return root


def _sha(root):
    result = _gates(root, "approval", "sha", CHANGE)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def _sha_before_the_clause(tasks):
    """The approval sha as 0.11.0 computed it for a tagged plan: the plan
    artifacts in path order, then the tag digest of `(id, [oracle: label])`."""
    h = hashlib.sha256()
    for rel, text in sorted({"design.md": DESIGN, "proposal.md": PROPOSAL,
                             "specs/x/spec.md": SPEC}.items()):
        h.update(rel.encode() + b"\n")
        h.update(text.encode())
        h.update(b"\n")
    h.update(b"tasks.md#oracle-tags\n")
    for tid, tag in tasks:
        h.update(f"{tid} {tag}\n".encode())
    return h.hexdigest()


def _approve(root):
    sha = _sha(root)
    _write(root, f"{CDIR}/.openspec.yaml",
           "schema: spec-driven\n"
           'x-gatedloop-approved-by: "tester (local)"\n'
           'x-gatedloop-approved-at: "2026-11-04T00:00:00Z"\n'
           f'x-gatedloop-approved-sha: "{sha}"\n')
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "approve")


WITH_CLAUSE = TAGGED.replace("2.1 Move the key [oracle: unit]",
                             "2.1 Move the key [oracle: unit rewrites: tests/test_app.py]")


class TestTheApprovalDigest(unittest.TestCase):
    """Regressions guarded: upgrading voiding every tagged approval in flight,
    and a rewrite added to an approved plan without re-approval."""

    def test_a_tag_without_the_clause_hashes_as_before(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _plan_repo(tmp, TAGGED)
            self.assertEqual(_sha(root), _sha_before_the_clause(
                [("2.1", "[oracle: unit]"), ("2.2", "[oracle: unit characterization]")]))

    def test_the_clause_moves_the_sha(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _plan_repo(tmp, TAGGED)
            before = _sha(root)
            _write(root, f"{CDIR}/tasks.md", WITH_CLAUSE)
            with_one = _sha(root)
            self.assertNotEqual(with_one, before)
            _write(root, f"{CDIR}/tasks.md", WITH_CLAUSE.replace(
                "tests/test_app.py]", "tests/test_app.py, tests/test_b.py]"))
            self.assertNotEqual(_sha(root), with_one)

    def test_a_clause_added_on_the_target_voids_check_implement(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _plan_repo(tmp, TAGGED)
            _approve(root)
            self.assertEqual(_gates(root, "discipline", "check-implement", CHANGE).returncode, 0)
            _write(root, f"{CDIR}/tasks.md", WITH_CLAUSE)
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "declare a rewrite")
            result = _gates(root, "discipline", "check-implement", CHANGE)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("approved_sha", result.stdout + result.stderr)


class TestAClauseAddedOnTheBranch(unittest.TestCase):
    """Regression guarded: the branch declaring a rewrite the approved plan does
    not, which would let the author see a test no human chose to show it."""

    def test_the_handoff_refuses_naming_both_tags(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _plan_repo(tmp, TAGGED)
            _git(root, "checkout", "-b", CHANGE)
            _write(root, f"{CDIR}/tasks.md", WITH_CLAUSE)
            held = root / ".gatedloop" / "authored" / CHANGE
            _write(held, "2.1/tests/test_app.py.authored", "def test_app():\n    assert False\n")
            _write(held, "2.2/tests/test_p.py.authored", "def test_p():\n    assert True\n")
            _write(held, "2.2/CHARACTERIZATION", "pins the tree\n")
            result = _gates(root, "tests", "handoff", CHANGE)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("2.1", result.stderr)
            self.assertIn("[oracle: unit]", result.stderr)
            self.assertIn("[oracle: unit rewrites: tests/test_app.py]", result.stderr)

    def test_check_ref_refuses_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _plan_repo(tmp, TAGGED)
            _git(root, "checkout", "-b", CHANGE)
            held = root / ".gatedloop" / "authored" / CHANGE
            _write(held, "2.1/tests/test_k.py.authored", "def test_k():\n    assert False\n")
            _write(held, "2.2/tests/test_p.py.authored", "def test_p():\n    assert True\n")
            _write(held, "2.2/CHARACTERIZATION", "pins the tree\n")
            handed = _gates(root, "tests", "handoff", CHANGE)
            self.assertEqual(handed.returncode, 0, handed.stderr)
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "author tests")
            self.assertEqual(_gates(root, "task", "start", "2.1").returncode, 0)
            placed = _gates(root, "tests", "place", "2.1")
            self.assertEqual(placed.returncode, 0, placed.stderr)
            ran = _gates(root, "run", "unit", "--task", "2.1")
            self.assertNotIn(ran.returncode, (0, 75), ran.stderr)
            _write(root, f"{CDIR}/tasks.md", WITH_CLAUSE)
            _write(root, "src/app.py", "def app():\n    return 2\n")
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "task 2.1")
            result = _gates(root, "tests", "check", "--ref", "HEAD", "--change", CHANGE)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("2.1", result.stderr)
            self.assertIn("[oracle: unit rewrites: tests/test_app.py]", result.stderr)


if __name__ == "__main__":
    unittest.main()
