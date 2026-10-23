"""Selection-layer tests for the `gates` shim: `_changed_files`, `hot_surfaces`,
`_matches`, and `cmd_run`'s live-check path (F1-F4, `fix-change-scope-selection`).

Stdlib only, per `zero-dep-shim`. These tests build throwaway git repos under
a temp directory and clean up after themselves, deliberately independent of
the host's global git config (`user.name`/`user.email`, `init.defaultBranch`).

Run with:  python3 -m unittest discover -s tests
"""

import contextlib
import importlib.machinery
import importlib.util
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

# `bin/gates` has no `.py` suffix, so it is loaded by path (matches
# test_manifest.py) for the tests below that call its functions in-process
# (`TestGlobMatchingIsFailHot`) rather than through the subprocess helpers.
_loader = importlib.machinery.SourceFileLoader("gates_shim_selection", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)

VACUOUS_MANIFEST = """\
gatesVersion: 1
gates:
  ci: "true"
surfaces:
  - name: all
    match: "**"
    live-check: "echo LIVE-CHECK-RAN && false"
"""


# ---------- fixture helpers -------------------------------------------------
#
# Selection depends on real git plumbing (`git diff`, `git merge-base`, branch
# state), so these tests exercise it against throwaway repos rather than
# mocking git out. Identity is configured locally on each repo — never read
# from the host's global config — so the tests do not depend on (or pollute)
# whatever `user.name`/`user.email`/`init.defaultBranch` happen to be set on
# the machine running them. Every repo lives under a `TemporaryDirectory` and
# is removed on exit, including on failure.

def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


@contextlib.contextmanager
def scratch_repo(files: dict, branch: str = "main"):
    """Build a throwaway git repo: `init -b <branch>`, a locally-scoped
    identity, `files` (relpath -> content) written and committed. Yields the
    repo root; the temp dir is removed when the `with` block exits.
    """
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _git(root, "init", "-b", branch)
        _git(root, "config", "user.email", "test@example.com")
        _git(root, "config", "user.name", "Test")
        for relpath, content in files.items():
            path = root / relpath
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        _git(root, "add", "-A")
        _git(root, "commit", "-m", "initial")
        yield root


def new_branch(root, name):
    """Cut and check out a new branch from the current HEAD."""
    _git(root, "checkout", "-b", name)


def commit_all(root, message="more"):
    """Stage everything (including untracked) and commit."""
    _git(root, "add", "-A")
    _git(root, "commit", "-m", message)


def run_gates(root, *args):
    """Invoke the shim as a subprocess (black-box, matches how the loop
    actually calls it) with `root` as the cwd."""
    return subprocess.run(
        [sys.executable, str(GATES_SHIM), *args],
        cwd=root, capture_output=True, text=True,
    )


@contextlib.contextmanager
def fake_origin(root: Path, default_branch: str):
    """Add a bare 'remote' (its own temp dir, so it is cleaned up
    independently of `root`) as `origin`, with `origin/HEAD` set to
    `default_branch` — entirely locally, no network — so
    `_resolve_merge_target`'s `origin/HEAD` path can be exercised against a
    default branch name that isn't `main`/`master`.
    """
    with tempfile.TemporaryDirectory() as remote_tmp:
        bare = Path(remote_tmp) / "origin.git"
        _git(Path(remote_tmp), "init", "--bare", "-b", default_branch, str(bare))
        _git(root, "remote", "add", "origin", str(bare))
        _git(root, "push", "origin", f"HEAD:{default_branch}")
        _git(root, "remote", "set-head", "origin", default_branch)
        yield bare


class TestF1LiveCheckVacuousOnCleanBranch(unittest.TestCase):
    """F1 (review 2026-08-18): a change branch with everything committed has
    an empty working-tree diff, so `gates run live-check` selected no hot
    surfaces and exited 0 without ever running the always-failing probe below
    — a BLOCKING gate passing vacuously. This test must fail red against the
    unmodified shim; the fix makes change-level selection read the branch's
    diff against the merge target instead of the working tree.
    """

    def test_live_check_runs_and_fails_on_a_clean_change_branch(self):
        with scratch_repo({".gates.yaml": VACUOUS_MANIFEST}) as root:
            new_branch(root, "a-change")
            # A task's file, committed on the branch — like tdd-apply's
            # per-task commits, not left dirty. The working tree is clean by
            # the time `live-check` runs at change completion (§7.5); only
            # the branch's own history (vs. `main`) shows this happened.
            (root / "task.txt").write_text("done\n")
            commit_all(root, "add task file")

            result = run_gates(root, "run", "live-check")

            self.assertNotEqual(
                result.returncode, 0,
                "live-check exited 0 on a clean change branch without running "
                f"the always-failing probe (F1). stdout={result.stdout!r} "
                f"stderr={result.stderr!r}",
            )
            self.assertIn("LIVE-CHECK-RAN", result.stdout)


class TestDirtyTreeUnion(unittest.TestCase):
    """Design D1 scenario 2: mid-change, some tasks are committed on the
    branch and further edits are uncommitted — the hot set must cover both,
    not just whichever baseline happens to see a given file."""

    MANIFEST = """\
gatesVersion: 1
gates:
  ci: "true"
surfaces:
  - name: committed-surface
    match: "committed/**"
    live-check: "echo COMMITTED-RAN"
  - name: dirty-surface
    match: "dirty/**"
    live-check: "echo DIRTY-RAN"
"""

    def test_union_of_branch_diff_and_working_set(self):
        with scratch_repo({".gates.yaml": self.MANIFEST}) as root:
            new_branch(root, "a-change")
            (root / "committed").mkdir()
            (root / "committed" / "f.txt").write_text("x\n")
            commit_all(root, "committed task")
            (root / "dirty").mkdir()
            (root / "dirty" / "f.txt").write_text("y\n")
            # Left uncommitted deliberately — only the working-set half sees it.

            result = run_gates(root, "run", "live-check")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("COMMITTED-RAN", result.stdout)
            self.assertIn("DIRTY-RAN", result.stdout)


class TestOnTargetBranchItself(unittest.TestCase):
    """Design D2: running with the merge target checked out contributes an
    empty merge-base diff by construction, and that is not a degraded state —
    the working set alone drives selection, with no fallback warning."""

    MANIFEST = """\
gatesVersion: 1
gates:
  ci: "true"
surfaces:
  - name: all
    match: "**"
    live-check: "echo ON-TARGET-RAN"
"""

    def test_no_degradation_warning_on_target_branch(self):
        with scratch_repo({".gates.yaml": self.MANIFEST}) as root:
            # No new branch: HEAD is already `main`, the resolved target.
            (root / "extra.txt").write_text("x\n")  # dirty, working-set-visible

            result = run_gates(root, "run", "live-check")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("ON-TARGET-RAN", result.stdout)
            self.assertNotIn("fallback", result.stderr)
            self.assertNotIn("fall back", result.stderr)


class TestNoMergeTargetFallback(unittest.TestCase):
    """Design D2: no remote and no local `main`/`master` — resolution finds
    nothing, and the shim falls back to the working set with a loud stderr
    notice rather than silently selecting nothing."""

    MANIFEST = """\
gatesVersion: 1
gates:
  ci: "true"
surfaces:
  - name: all
    match: "**"
    live-check: "echo FALLBACK-RAN"
"""

    def test_fallback_to_working_set_with_loud_notice(self):
        with scratch_repo({".gates.yaml": self.MANIFEST}, branch="wip") as root:
            new_branch(root, "a-change")
            (root / "extra.txt").write_text("x\n")  # working-set-visible

            result = run_gates(root, "run", "live-check")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("FALLBACK-RAN", result.stdout)
            self.assertIn("no merge target resolved", result.stderr)
            self.assertIn("falling back to the working-set baseline", result.stderr)


class TestChangeLevelOverrides(unittest.TestCase):
    """`--changed`/`--all` continue to override change-level selection too
    (design D1's last sentence), even in a state (clean tree, on the target
    branch) where the computed baseline would otherwise select nothing."""

    MANIFEST = """\
gatesVersion: 1
gates:
  ci: "true"
surfaces:
  - name: all
    match: "**"
    live-check: "echo OVERRIDE-RAN"
"""

    def test_all_override_forces_selection(self):
        with scratch_repo({".gates.yaml": self.MANIFEST}) as root:
            result = run_gates(root, "run", "live-check", "--all")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("OVERRIDE-RAN", result.stdout)

    def test_changed_override_forces_selection(self):
        with scratch_repo({".gates.yaml": self.MANIFEST}) as root:
            result = run_gates(root, "run", "live-check", "--changed", "some/file.txt")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("OVERRIDE-RAN", result.stdout)


class TestNonMainDefaultBranchViaOriginHead(unittest.TestCase):
    """Design D2: a repo whose default branch is neither `main` nor `master`
    still resolves a merge target, via `origin/HEAD`, with no code that
    hard-codes either name."""

    MANIFEST = """\
gatesVersion: 1
gates:
  ci: "true"
surfaces:
  - name: all
    match: "**"
    live-check: "echo TRUNK-RAN && false"
"""

    def test_resolves_origin_head_default_branch_named_trunk(self):
        with scratch_repo({".gates.yaml": self.MANIFEST}, branch="trunk") as root:
            with fake_origin(root, "trunk"):
                new_branch(root, "a-change")
                (root / "task.txt").write_text("done\n")
                commit_all(root, "add task file")

                result = run_gates(root, "run", "live-check")

                self.assertNotEqual(
                    result.returncode, 0,
                    f"expected the always-failing probe to run via origin/HEAD "
                    f"-> trunk. stdout={result.stdout!r} stderr={result.stderr!r}",
                )
                self.assertIn("TRUNK-RAN", result.stdout)
                self.assertNotIn("fallback", result.stderr)
                self.assertNotIn("fall back", result.stderr)


class TestEmptyChangeLevelHotSetIsLoud(unittest.TestCase):
    """Design D3: a docs-only change against code-only surfaces is a
    legitimate empty hot set — the shim must still exit 0, but the skip
    message must name the baseline kind, resolved target, and files
    considered, not be a bare one-liner indistinguishable from a selection
    defect."""

    MANIFEST = """\
gatesVersion: 1
gates:
  ci: "true"
surfaces:
  - name: code
    match: "src/**"
    live-check: "echo SHOULD-NOT-RUN && false"
"""

    def test_evidence_named_when_hot_set_is_empty(self):
        with scratch_repo({".gates.yaml": self.MANIFEST}) as root:
            new_branch(root, "docs-only-change")
            (root / "docs").mkdir()
            (root / "docs" / "README.md").write_text("hello\n")
            commit_all(root, "docs-only change")

            result = run_gates(root, "run", "live-check")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("SHOULD-NOT-RUN", result.stdout)
            self.assertIn("baseline=merge-target diff against 'main'", result.stdout)
            self.assertIn("file(s) considered", result.stdout)


class TestGlobMatchingIsFailHot(unittest.TestCase):
    """F3 (review 2026-08-18) / design D5: `_matches` collapses `**` -> `*`
    and delegates to `fnmatch`, whose `*` crosses `/` — so a surface can
    select MORE than a path-separator-exact reading of its glob would. That
    is the documented, permitted direction of error (SETUP.md); this pins it
    so a future matcher change cannot silently flip to under-matching, which
    would let a real change miss its surface.
    """

    def _exact_match(self, path: str, glob: str) -> bool:
        """Reference path-separator-exact semantics, for comparison only —
        not what the shim implements: `*` matches within one path segment,
        `**` matches across segments, mirroring the glob's literal reading.
        """
        pattern = []
        i = 0
        while i < len(glob):
            if glob[i:i + 2] == "**":
                pattern.append(".*")
                i += 2
            elif glob[i] == "*":
                pattern.append("[^/]*")
                i += 1
            elif glob[i] == "?":
                pattern.append("[^/]")
                i += 1
            else:
                pattern.append(re.escape(glob[i]))
                i += 1
        return re.match("".join(pattern) + "$", path) is not None

    CASES = [
        ("*.md", "x.md"),
        ("*.md", "docs/deep/x.md"),  # the F3 example: fnmatch's '*' crosses '/'
        ("backend/app/**", "backend/app/routers/x.py"),
        ("backend/app/**", "backend/app/x.py"),
        ("docs/**/*.py", "docs/a/b/c.py"),
        ("**", "anything/at/all.txt"),
        ("**", "top.txt"),
    ]

    def test_approximate_matching_never_undermatches_the_exact_reading(self):
        for glob, path in self.CASES:
            with self.subTest(glob=glob, path=path):
                if self._exact_match(path, glob):
                    self.assertTrue(
                        gates._matches(path, glob),
                        f"_matches({path!r}, {glob!r}) under-matched: the exact "
                        "path-separator reading selects this path but the "
                        "shim's approximate matcher does not — fail-hot "
                        "contract violated",
                    )

    def test_the_pinned_overmatch_example_from_f3(self):
        """`*.md` crossing `/` is the concrete over-match case F3 found —
        pinned directly so it can never silently start under-matching."""
        self.assertTrue(gates._matches("docs/deep/x.md", "*.md"))
        self.assertFalse(self._exact_match("docs/deep/x.md", "*.md"))


class TestBraceGlobSurfaceSelection(unittest.TestCase):
    """expand-brace-globs design D1/D3 (issue #1): a surface whose `match`
    is a brace pattern like `{bin,tests}/**` must go hot for a file under
    either alternative, and `gates rules` must return its rules — the exact
    selection issue #1 observed silently returning empty. The fixture
    mirrors this repo's own `.gates.yaml` shapes (two directories in one
    group, `**` suffix)."""

    MANIFEST = """\
gatesVersion: 1
gates:
  ci: "true"
surfaces:
  - name: shim
    match: "{bin,tests}/**"
    rules:
      - zero-dep-shim
"""

    def test_file_under_first_alternative_goes_hot(self):
        with scratch_repo({".gates.yaml": self.MANIFEST}) as root:
            new_branch(root, "a-change")
            (root / "bin").mkdir()
            (root / "bin" / "gates").write_text("changed\n")
            commit_all(root, "touch bin/gates")

            result = run_gates(root, "surfaces", "--changed", "bin/gates")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("shim", result.stdout)

    def test_file_under_second_alternative_goes_hot(self):
        with scratch_repo({".gates.yaml": self.MANIFEST}) as root:
            result = run_gates(root, "surfaces", "--changed", "tests/test_x.py")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("shim", result.stdout)

    def test_gates_rules_returns_the_brace_surfaces_rules(self):
        with scratch_repo({".gates.yaml": self.MANIFEST}) as root:
            result = run_gates(root, "rules", "--changed", "bin/gates")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("zero-dep-shim", result.stdout)

    def test_file_outside_either_alternative_is_not_hot(self):
        with scratch_repo({".gates.yaml": self.MANIFEST}) as root:
            result = run_gates(root, "surfaces", "--changed", "docs/README.md")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("no hot surfaces", result.stdout)


class TestThisReposOwnManifestSelectsOnABraceGlobDiff(unittest.TestCase):
    """expand-brace-globs task 3.1 / issue #1, proven against the real
    `.gates.yaml` this repo ships (the proposal's own regression fixture,
    not a synthetic one): both brace-glob surfaces, `shim`
    (`{bin,tests}/**`) and `prompts` (`{commands,skills,agents,hooks,
    templates}/**`), must go hot — with their rule-ids — for a diff that
    touches one file under each. Before this change both silently selected
    nothing (the exact defect issue #1 reported)."""

    def test_surfaces_and_rules_report_shim_and_prompts_hot(self):
        manifest_path = REPO / ".gates.yaml"
        if not manifest_path.exists():
            self.skipTest("no .gates.yaml at repo root")

        surfaces_result = run_gates(
            REPO, "surfaces", "--changed", "bin/gates", "commands/start.md",
        )
        self.assertEqual(surfaces_result.returncode, 0, surfaces_result.stderr)
        self.assertIn("shim", surfaces_result.stdout)
        self.assertIn("prompts", surfaces_result.stdout)

        rules_result = run_gates(
            REPO, "rules", "--changed", "bin/gates", "commands/start.md",
        )
        self.assertEqual(rules_result.returncode, 0, rules_result.stderr)
        self.assertIn("zero-dep-shim", rules_result.stdout)
        self.assertIn("fail-loud-gates", rules_result.stdout)
        self.assertIn("stack-agnostic-prompts", rules_result.stdout)


if __name__ == "__main__":
    unittest.main()
