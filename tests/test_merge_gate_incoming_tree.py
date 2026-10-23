"""Tests for the merge gate validating the INCOMING tree (design D4,
`fix-marker-mechanics`, issue #17 item 5).

`gates run live-check` records the branch head's tree -- correct, since that
is where the probes ran. The old `hooks/gate-merge.sh` always compared
against the CURRENT HEAD tree, which at squash-merge time is the *target's*
(e.g. `main`'s), never the branch's -- so a real squash-merge could never
satisfy the gate even with a perfectly green live-check on the change branch.
The fix extracts the merge source ref from the `git merge` invocation and
checks the marker against `<ref>^{tree}` first, falling back to HEAD's tree
when no source ref resolves (`git merge --continue`, an octopus, ...).

Stdlib only, per `zero-dep-shim`. Run with:  python3 -m unittest discover -s tests
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
MERGE_HOOK = REPO / "hooks" / "gate-merge.sh"

MANIFEST = """\
gatesVersion: 1
gates:
  ci: "true"
surfaces:
  - name: all
    match: "**"
    live-check: "true"
"""


def _git(cwd, *args):
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
    ).stdout.strip()


def _run_gates(root, *args):
    return subprocess.run(
        [sys.executable, str(GATES_SHIM), *args], cwd=root, capture_output=True, text=True,
    )


def _run_hook(hook: Path, root: Path, command: str):
    env = dict(os.environ)
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    env["CLAUDE_PROJECT_DIR"] = str(root)
    payload = json.dumps({"tool_input": {"command": command}, "cwd": str(root)})
    return subprocess.run(
        ["bash", str(hook)], input=payload, cwd=str(root), env=env, capture_output=True, text=True,
    )


def _init_repo(root: Path) -> None:
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(MANIFEST)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")


class TestSquashMergeChecksSourceBranchTree(unittest.TestCase):
    """Issue #17 item 5's exact repro: only the branch-head marker exists
    (written by `gates run live-check` on the change branch); the merge
    happens from `main`, where HEAD's tree has never carried a marker. The
    fixed hook must resolve the merge source ref (`my-change`, the trailing
    non-flag argument of `git merge --squash my-change`) and check the
    marker against ITS tree, not `main`'s.
    """

    def test_squash_merge_allowed_on_branch_head_marker_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _git(root, "checkout", "-b", "my-change")
            (root / "openspec" / "changes" / "my-change").mkdir(parents=True, exist_ok=True)
            (root / "task.txt").write_text("done\n")
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "task work")

            # scale-gate-cost D2: the merge also requires an unscoped `ci`
            # marker on the same head -- run it with nothing staged so the
            # index tree IS the head tree and the scope is "full".
            ci = _run_gates(root, "run", "ci", "--change", "my-change")
            self.assertEqual(ci.returncode, 0, ci.stderr)
            result = _run_gates(root, "run", "live-check", "--all", "--change", "my-change")
            self.assertEqual(result.returncode, 0, result.stderr)

            _git(root, "checkout", "main")
            r = _run_hook(MERGE_HOOK, root, "git merge --squash my-change")
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_squash_merge_still_denied_with_no_marker_anywhere(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _git(root, "checkout", "-b", "my-change")
            (root / "openspec" / "changes" / "my-change").mkdir(parents=True, exist_ok=True)
            (root / "task.txt").write_text("done\n")
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "task work")

            _git(root, "checkout", "main")
            r = _run_hook(MERGE_HOOK, root, "git merge --squash my-change")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("live-check", r.stderr)


class TestMergeGateAuditsBeforeTheTaintCheck(unittest.TestCase):
    """escalation-outcomes D5 part 3: a commit created after the last
    session stop has never been audited. The merge gate runs `gates audit`
    itself, immediately before `gates taint check`, so such a commit is
    tainted (no green record) before the merge is decided."""

    def test_unaudited_ungated_commit_is_tainted_and_the_merge_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _git(root, "checkout", "-b", "my-change")
            (root / "openspec" / "changes" / "my-change").mkdir(parents=True, exist_ok=True)

            # An ungated commit: no `gates run ci` ever saw its tree.
            (root / "bypass.txt").write_text("bypass\n")
            _git(root, "add", "bypass.txt")
            _git(root, "commit", "-m", "bypass")

            # A properly gated head, with fresh ci + live-check markers, so
            # the merge reaches the taint check at all.
            (root / "task.txt").write_text("done\n")
            _git(root, "add", "task.txt")
            ci = _run_gates(root, "run", "ci", "--change", "my-change")
            self.assertEqual(ci.returncode, 0, ci.stderr)
            _git(root, "commit", "-m", "task work")
            lc = _run_gates(root, "run", "live-check", "--all", "--change", "my-change")
            self.assertEqual(lc.returncode, 0, lc.stderr)

            # No audit has run yet (no Stop since the bypass).
            self.assertNotEqual(_run_gates(root, "taint", "check").returncode, 1)

            # One command that switches to the target and integrates: the
            # hook runs on the change branch, so the change resolves, and the
            # merge is gated because it lands on the target (hook-correctness
            # D2). A bare `git merge main` here is a sync, and not gated.
            r = _run_hook(MERGE_HOOK, root, "git checkout main && git merge --squash my-change")
            self.assertEqual(r.returncode, 2, r.stderr)
            self.assertIn("taint", r.stderr)
            rows = [
                json.loads(x) for x in
                (root / ".gatedloop" / "runs" / "my-change.jsonl").read_text().splitlines()
                if x.strip()
            ]
            self.assertEqual([x["gate"] for x in rows].count("taint"), 1)


class TestMergeGateAuditsTheIncomingChangeFromThePrimary(unittest.TestCase):
    """The audit before the taint check must audit the change the incoming
    ref names. Run bare, it resolved the change from the current branch --
    the target during an integrating merge -- so from a primary on `main`
    it audited nothing and an unaudited ungated commit on the lane slipped
    through. The audit now runs where the branch lives, so the taint lands in
    the ledger `taint check --ref` reads."""

    def _env(self, root: Path) -> dict:
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env.pop("CLAUDE_PLUGIN_ROOT", None)
        env["CLAUDECODE"] = "1"  # an agent session, never inherited from the host
        env["CLAUDE_PROJECT_DIR"] = str(root)
        return env

    def test_unaudited_ungated_lane_commit_is_tainted_from_the_primary(self):
        with tempfile.TemporaryDirectory() as tmp:
            primary = Path(tmp) / "primary"
            primary.mkdir()
            _init_repo(primary)
            (primary / "openspec" / "changes" / "my-change").mkdir(parents=True)
            (primary / "openspec" / "changes" / "my-change" / ".openspec.yaml").write_text("schema: spec-driven\n")
            _git(primary, "add", "-A")
            _git(primary, "commit", "-m", "plan my-change")
            lane = Path(tmp) / "lane"
            _git(primary, "worktree", "add", "-b", "my-change", str(lane))
            env = self._env(primary)

            def gates(cwd, *args):
                return subprocess.run([sys.executable, str(GATES_SHIM), *args], cwd=cwd,
                                      capture_output=True, text=True, env=env)

            # An ungated commit in the lane: no `gates run ci` ever saw its tree.
            (lane / "bypass.txt").write_text("bypass\n")
            _git(lane, "add", "bypass.txt")
            _git(lane, "commit", "-m", "bypass")
            # A gated head with fresh lane markers, so the merge reaches the
            # taint check (cross-worktree-evidence: the lane's store counts).
            (lane / "task.txt").write_text("done\n")
            _git(lane, "add", "task.txt")
            self.assertEqual(gates(lane, "run", "ci").returncode, 0)
            _git(lane, "commit", "-m", "task work")
            self.assertEqual(gates(lane, "run", "live-check", "--all").returncode, 0)

            payload = json.dumps({"tool_input": {"command": "git merge --squash my-change"},
                                  "cwd": str(primary)})
            r = subprocess.run(["bash", str(MERGE_HOOK)], input=payload, cwd=str(primary),
                               env=env, capture_output=True, text=True)

            self.assertEqual(r.returncode, 2, r.stderr)
            self.assertIn("taint", r.stderr)
            lane_rows = [json.loads(x) for x in
                         (lane / ".gatedloop" / "runs" / "my-change.jsonl").read_text().splitlines()
                         if x.strip()]
            self.assertEqual([x["gate"] for x in lane_rows].count("taint"), 1)
            self.assertFalse((primary / ".gatedloop" / "runs" / "main.jsonl").exists())


class TestDenialGuidanceNamesTheChangeBranchHead(unittest.TestCase):
    """Task 4.2: the denial guidance said "the branch head" when the check
    itself only ever looked at the current HEAD tree -- accurate only by
    coincidence, since `main`'s HEAD is also "a branch head". Now that the
    check validates the incoming (change branch's) tree first, the message
    must say so explicitly rather than continue to describe the OLD,
    target-tree-only semantics.
    """

    def test_denial_names_the_change_branchs_head(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _git(root, "branch", "feature")
            r = _run_hook(MERGE_HOOK, root, "git merge feature")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("the change branch's head", r.stderr)


class TestNoResolvableRefFallsBackToHeadTree(unittest.TestCase):
    """`git merge --continue` (and any other invocation with no single
    resolvable source ref) keeps the old behavior -- checking the current
    HEAD tree -- which remains correct for the run-after-fast-forward case.
    """

    def test_merge_continue_checks_head_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)

            head_tree = _git(root, "rev-parse", "HEAD^{tree}")
            r = _run_gates(root, "gate-marker", "check", "live-check", head_tree)
            self.assertNotEqual(r.returncode, 0)  # no marker yet

            # scale-gate-cost D2: the merge also requires an unscoped `ci`
            # marker on the head (nothing staged -> index tree == head tree).
            ci = _run_gates(root, "run", "ci", "--change", "my-change")
            self.assertEqual(ci.returncode, 0, ci.stderr)
            result = _run_gates(root, "run", "live-check", "--all", "--change", "my-change")
            self.assertEqual(result.returncode, 0, result.stderr)

            r = _run_hook(MERGE_HOOK, root, "git merge --continue")
            self.assertEqual(r.returncode, 0, r.stderr)


class TestUnparsableRefIsNamedNotStale(unittest.TestCase):
    """hook-correctness D1 (#33 item 1): when a merge matched but no single
    incoming ref could be read from it, the hook fell back to the target's
    own tree and denied with "marker is stale" -- sending the operator to
    re-run a live-check that was already green. The denial now names the
    real cause."""

    def test_denial_says_no_ref_was_parsed_and_never_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _green_branch(root, MANIFEST)
            _git(root, "checkout", "main")
            r = _run_hook(MERGE_HOOK, root, "git merge --squash my-change other-change")
            self.assertEqual(r.returncode, 2, r.stderr)
            self.assertIn("no incoming ref could be parsed", r.stderr)
            self.assertIn("git merge --squash <change>", r.stderr)
            self.assertNotIn("stale", r.stderr)

    def test_merge_continue_is_not_an_unparsable_ref(self):
        out = subprocess.run(
            [sys.executable, str(REPO / "hooks" / "_gate_match.py"), "git-merge"],
            input=json.dumps({"tool_input": {"command": "git merge --continue"}}),
            capture_output=True, text=True,
        ).stdout
        self.assertNotIn("ref_parse=failed", out)


MANIFEST_ACCEPTANCE = MANIFEST +"approval:\n  plan: self\n  acceptance: self\n"

ACCEPTANCE_BLOCK_BEGIN = "# >>> acceptance-gate D4"
ACCEPTANCE_BLOCK_END = "# <<< acceptance-gate D4"


def _green_branch(root: Path, manifest: str) -> None:
    """A change branch whose head carries fresh unscoped-ci and live-check
    markers and no taint -- every pre-existing merge check passes."""
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(manifest)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")
    _git(root, "checkout", "-b", "my-change")
    (root / "openspec" / "changes" / "my-change").mkdir(parents=True, exist_ok=True)
    (root / "task.txt").write_text("done\n")
    _git(root, "add", "task.txt")
    ci = _run_gates(root, "run", "ci", "--change", "my-change")
    assert ci.returncode == 0, ci.stderr
    _git(root, "commit", "-m", "task work")
    lc = _run_gates(root, "run", "live-check", "--all", "--change", "my-change")
    assert lc.returncode == 0, lc.stderr


class TestMergeRequiresAcceptanceUnderADeclaredPolicy(unittest.TestCase):
    """acceptance-gate design D4 / task 3.3: with `approval.acceptance`
    declared, a merge whose incoming tree has a green live-check and no
    taint is still denied until an `accept` row pins that tree."""

    def test_denied_without_acceptance_then_allowed_after_attest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _green_branch(root, MANIFEST_ACCEPTANCE)

            _git(root, "checkout", "main")
            denied = _run_hook(MERGE_HOOK, root, "git merge --squash my-change")
            self.assertEqual(denied.returncode, 2, denied.stderr)
            self.assertIn("acceptance", denied.stderr)
            self.assertIn("gates acceptance brief", denied.stderr)
            self.assertIn("gates acceptance attest", denied.stderr)

            _git(root, "checkout", "my-change")
            att = _run_gates(root, "acceptance", "attest", "my-change", "--local")
            self.assertEqual(att.returncode, 0, att.stderr)
            _git(root, "checkout", "main")

            allowed = _run_hook(MERGE_HOOK, root, "git merge --squash my-change")
            self.assertEqual(allowed.returncode, 0, allowed.stderr)

    def test_rejection_denies_naming_the_cause(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _green_branch(root, MANIFEST_ACCEPTANCE)
            self.assertEqual(
                _run_gates(root, "acceptance", "attest", "my-change", "--local").returncode, 0,
            )
            rej = _run_gates(
                root, "acceptance", "reject", "my-change",
                "--cause", "missing-oracle", "--detail", "nothing checked the export",
            )
            self.assertEqual(rej.returncode, 0, rej.stderr)
            _git(root, "checkout", "main")

            r = _run_hook(MERGE_HOOK, root, "git merge --squash my-change")
            self.assertEqual(r.returncode, 2, r.stderr)
            self.assertIn("missing-oracle", r.stderr)


def _hook_without_acceptance_block(dest_dir: Path) -> Path:
    """The merge hook as it was before acceptance-gate: the real hook with
    its delimited acceptance block removed. Run with CLAUDE_PLUGIN_ROOT set
    so both copies resolve the same shim and matcher."""
    text = MERGE_HOOK.read_text()
    begin = text.index(ACCEPTANCE_BLOCK_BEGIN)
    end = text.index(ACCEPTANCE_BLOCK_END) + len(ACCEPTANCE_BLOCK_END)
    stripped = text[:begin] + text[end:]
    dest = dest_dir / "gate-merge.sh"
    dest.write_text(stripped)
    return dest


def _run_hook_with_plugin_root(hook: Path, root: Path, command: str):
    env = dict(os.environ)
    env["CLAUDE_PLUGIN_ROOT"] = str(REPO)
    env["CLAUDE_PROJECT_DIR"] = str(root)
    payload = json.dumps({"tool_input": {"command": command}, "cwd": str(root)})
    return subprocess.run(
        ["bash", str(hook)], input=payload, cwd=str(root), env=env, capture_output=True, text=True,
    )


class TestNoPolicyIsByteIdentical(unittest.TestCase):
    """Task 3.3: with no acceptance policy declared, the hook's exit code,
    stdout and stderr are exactly those of the hook without the acceptance
    check, on both an allowed and a denied merge."""

    def _assert_identical(self, root: Path, command: str, old_hook: Path):
        new = _run_hook_with_plugin_root(MERGE_HOOK, root, command)
        old = _run_hook_with_plugin_root(old_hook, root, command)
        self.assertEqual(
            (new.returncode, new.stdout, new.stderr),
            (old.returncode, old.stdout, old.stderr),
        )
        return new

    def test_allowed_merge_is_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as hook_tmp:
            root = Path(tmp)
            _green_branch(root, MANIFEST)
            _git(root, "checkout", "main")
            old_hook = _hook_without_acceptance_block(Path(hook_tmp))
            r = self._assert_identical(root, "git merge --squash my-change", old_hook)
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_denied_merge_is_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as hook_tmp:
            root = Path(tmp)
            _init_repo(root)
            _git(root, "branch", "feature")
            old_hook = _hook_without_acceptance_block(Path(hook_tmp))
            r = self._assert_identical(root, "git merge feature", old_hook)
            self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
