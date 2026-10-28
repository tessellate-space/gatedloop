"""A task's oracle tag is held to the approved plan (openspec change
`task-oracle`, design D9; the test-discipline delta's "A task's oracle tag is
held to the approved plan" requirement and its scenarios).

On the merge target: when `tasks.md` carries a tag, the approval sha also
covers its `(task id, tag)` pairs, leaving out checkbox state and task text; an
untagged plan hashes exactly as before. On the change branch: the handoff, the
lock and `gates tests check --ref` refuse a task whose tag differs from its tag
in the target's `tasks.md`, naming the task, both tags and the
amend-and-re-attest route. A task absent from the target is not compared.

Stdlib only, per `zero-dep-shim`. Throwaway git repositories with a local
`main` as the merge target; the shim is driven as a subprocess.

Run with:  python3 -m unittest discover -s tests
"""

import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"
CHANGE = "held-plan"
CDIR = f"openspec/changes/{CHANGE}"

MANIFEST = (
    'gatesVersion: 1\n'
    'approval:\n'
    '  plan: self\n'
    'gates:\n'
    '  ci: "true"\n'
    '  unit: "false"\n'
    '  integration: "false"\n'
)

PROPOSAL = "# Proposal\n\nWhy.\n"
DESIGN = "# Design\n\nHow.\n"
SPEC = "## ADDED Requirements\n\n### Requirement: X\n"

TAGGED = """\
## 5. Work

- [ ] 5.1 Wire the e2e step [oracle: integration]
- [ ] 5.2 Add the parser [oracle: unit]
"""

UNTAGGED = """\
## 5. Work

- [ ] 5.1 Wire the e2e step
- [ ] 5.2 Add the parser
"""


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


def _plan_only_sha():
    """The approval sha as it was before tags existed: proposal, design and
    specs only, in path order."""
    h = hashlib.sha256()
    for rel, text in sorted({"design.md": DESIGN, "proposal.md": PROPOSAL,
                             "specs/x/spec.md": SPEC}.items()):
        h.update(rel.encode() + b"\n")
        h.update(text.encode())
        h.update(b"\n")
    return h.hexdigest()


def _approve(root):
    """Attest the plan on main by writing the approval keys, as `gates
    approval attest` writes them, over the sha the shim computes."""
    sha = _sha(root)
    _write(root, f"{CDIR}/.openspec.yaml",
           "schema: spec-driven\n"
           'x-gatedloop-approved-by: "tester (local)"\n'
           'x-gatedloop-approved-at: "2026-10-28T00:00:00Z"\n'
           f'x-gatedloop-approved-sha: "{sha}"\n')
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "approve")


def _check_implement(root):
    return _gates(root, "discipline", "check-implement", CHANGE)


class TestTheApprovalSha(unittest.TestCase):
    """Regressions guarded: upgrading voiding every approval in flight (an
    untagged plan hashing differently), ticking a task voiding its own plan's
    approval, and a retag passing as the approved plan."""

    def test_an_untagged_plan_hashes_as_before(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _plan_repo(tmp, UNTAGGED)
            self.assertEqual(_sha(root), _plan_only_sha())

    def test_a_tagged_plan_covers_its_tags(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _plan_repo(tmp, TAGGED)
            tagged = _sha(root)
            self.assertNotEqual(tagged, _plan_only_sha())
            _write(root, f"{CDIR}/tasks.md",
                   TAGGED.replace("[oracle: integration]", "[oracle: unit characterization]"))
            self.assertNotEqual(_sha(root), tagged)

    def test_a_tick_leaves_the_sha_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _plan_repo(tmp, TAGGED)
            before = _sha(root)
            _write(root, f"{CDIR}/tasks.md", TAGGED.replace("- [ ] 5.1", "- [x] 5.1"))
            self.assertEqual(_sha(root), before)

    def test_task_text_is_left_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _plan_repo(tmp, TAGGED)
            before = _sha(root)
            _write(root, f"{CDIR}/tasks.md", TAGGED.replace("Add the parser", "Add a parser"))
            self.assertEqual(_sha(root), before)


class TestARetagOnTheTarget(unittest.TestCase):
    """Regression guarded: a plan amendment that moves a task's oracle on the
    target without anyone re-approving it."""

    def test_voids_check_implement_until_re_attested(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _plan_repo(tmp, TAGGED)
            _approve(root)
            self.assertEqual(_check_implement(root).returncode, 0)
            _write(root, f"{CDIR}/tasks.md",
                   TAGGED.replace("[oracle: integration]", "[oracle: unit characterization]"))
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "retag")
            result = _check_implement(root)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("approved_sha", result.stdout + result.stderr)

    def test_a_tick_on_the_target_does_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _plan_repo(tmp, TAGGED)
            _approve(root)
            _write(root, f"{CDIR}/tasks.md", TAGGED.replace("- [ ] 5.2", "- [x] 5.2"))
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "tick")
            result = _check_implement(root)
            self.assertEqual(result.returncode, 0, result.stderr)


def _branch_with_handoff(tmp):
    """main holds the tagged plan; the change branch hands off tests that
    agree with it and commits them."""
    root = _plan_repo(tmp, TAGGED)
    _git(root, "checkout", "-b", CHANGE)
    held = root / ".gatedloop" / "authored" / CHANGE
    _write(held, "5.1/tests/test_e2e.py.authored", "def test_e2e():\n    assert False\n")
    _write(held, "5.2/tests/test_parse.py.authored", "def test_parse():\n    assert False\n")
    result = _gates(root, "tests", "handoff", CHANGE)
    assert result.returncode == 0, result.stderr
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "author tests")
    return root


RETAGGED = TAGGED.replace("[oracle: integration]", "[oracle: unit characterization]")


def _place_and_red(root, task, gate):
    assert _gates(root, "task", "start", task).returncode == 0
    placed = _gates(root, "tests", "place", task)
    assert placed.returncode == 0, placed.stderr
    ran = _gates(root, "run", gate, "--task", task)
    assert ran.returncode not in (0, 75), ran.stderr


class TestARetagOnTheBranch(unittest.TestCase):
    """Regression guarded: the implementer (or anyone on the branch) choosing
    a task's oracle by editing its tag, which is the choice the tag exists to
    take away from it."""

    def test_the_lock_refuses_naming_the_task_both_tags_and_the_route(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _branch_with_handoff(tmp)
            _place_and_red(root, "5.1", "integration")
            _write(root, f"{CDIR}/tasks.md", RETAGGED)
            _write(root, "src/app.py", "def app():\n    return 2\n")
            _git(root, "add", "-A")
            result = _gates(root, "tests", "check")
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("5.1", result.stderr)
            self.assertIn("[oracle: integration]", result.stderr)
            self.assertIn("[oracle: unit characterization]", result.stderr)
            self.assertIn("re-attest", result.stderr)

    def test_the_commit_check_refuses_it_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _branch_with_handoff(tmp)
            _place_and_red(root, "5.1", "integration")
            _write(root, f"{CDIR}/tasks.md", RETAGGED)
            _write(root, "src/app.py", "def app():\n    return 2\n")
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "task 5.1")
            result = _gates(root, "tests", "check", "--ref", "HEAD", "--change", CHANGE)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("5.1", result.stderr)
            self.assertIn("[oracle: integration]", result.stderr)

    def test_an_unchanged_tag_holds(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _branch_with_handoff(tmp)
            _place_and_red(root, "5.1", "integration")
            _write(root, f"{CDIR}/tasks.md", TAGGED.replace("- [ ] 5.1", "- [x] 5.1"))
            _write(root, "src/app.py", "def app():\n    return 2\n")
            _git(root, "add", "-A")
            result = _gates(root, "tests", "check")
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_the_handoff_refuses_a_retag(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _plan_repo(tmp, TAGGED)
            _git(root, "checkout", "-b", CHANGE)
            _write(root, f"{CDIR}/tasks.md", TAGGED.replace("[oracle: unit]", "[oracle: none]"))
            held = root / ".gatedloop" / "authored" / CHANGE
            _write(held, "5.1/tests/test_e2e.py.authored", "def test_e2e():\n    assert False\n")
            _write(held, "5.2/NO-TESTS", "no behaviour\n")
            result = _gates(root, "tests", "handoff", CHANGE)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("5.2", result.stderr)
            self.assertIn("[oracle: unit]", result.stderr)
            self.assertIn("[oracle: none]", result.stderr)

    def test_a_task_absent_from_the_target_is_not_compared(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _plan_repo(tmp, TAGGED)
            _git(root, "checkout", "-b", CHANGE)
            _write(root, f"{CDIR}/tasks.md", TAGGED + "- [ ] 5.3 Document it [oracle: none]\n")
            held = root / ".gatedloop" / "authored" / CHANGE
            _write(held, "5.1/tests/test_e2e.py.authored", "def test_e2e():\n    assert False\n")
            _write(held, "5.2/tests/test_parse.py.authored", "def test_parse():\n    assert False\n")
            _write(held, "5.3/NO-TESTS", "docs only\n")
            result = _gates(root, "tests", "handoff", CHANGE)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
