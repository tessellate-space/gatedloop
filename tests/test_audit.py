"""Tests for the post-hoc reflog audit + ledger taint (enforce-at-the-effect
§4, design D6/D7).

Stdlib only, per `zero-dep-shim`. Builds throwaway git repos, drives real
`gates run ci` / `gates audit` as subprocesses (the join is on real git trees
and real ledger rows, so a black-box test is the honest one), and inspects the
durable `.gatedloop/runs/<change>.jsonl`.

Run with:  python3 -m unittest discover -s tests
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

MANIFEST = 'gatesVersion: 1\ngates:\n  ci: "true"\n'


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _run_gates(root, *args):
    return subprocess.run(
        [sys.executable, str(GATES_SHIM), *args],
        cwd=root, capture_output=True, text=True,
    )


def _rows(root, change):
    p = root / ".gatedloop" / "runs" / f"{change}.jsonl"
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


def _taints(root, change):
    return [r for r in _rows(root, change) if r.get("gate") == "taint"]


def _new_change_repo(tmp):
    root = Path(tmp)
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(MANIFEST)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")
    _git(root, "checkout", "-b", "my-change")
    return root


def _gated_commit(root, fname, msg):
    """Reproduce the tdd-apply order: stage, run `ci` (records a green-ci row for
    the staged tree), then commit that same tree."""
    (root / fname).write_text(fname + "\n")
    _git(root, "add", fname)
    r = _run_gates(root, "run", "ci", "--change", "my-change")
    assert r.returncode == 0, r.stderr
    _git(root, "commit", "-m", msg)


def _ungated_commit(root, fname, msg):
    (root / fname).write_text(fname + "\n")
    _git(root, "add", fname)
    _git(root, "commit", "-m", msg)  # no `gates run ci` — no green row for this tree


class TestAuditGatedBranchIsClean(unittest.TestCase):
    def test_all_gated_commits_produce_no_taint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _new_change_repo(tmp)
            _gated_commit(root, "a.txt", "task 1")
            _gated_commit(root, "b.txt", "task 2")
            r = _run_gates(root, "audit", "--change", "my-change")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(_taints(root, "my-change"), [])


class TestAuditDetectsUngatedCommit(unittest.TestCase):
    def test_ungated_commit_taints_once_and_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _new_change_repo(tmp)
            _gated_commit(root, "a.txt", "task 1")
            _ungated_commit(root, "b.txt", "bypass")

            head = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True,
            ).stdout.strip()

            r = _run_gates(root, "audit", "--change", "my-change")
            self.assertEqual(r.returncode, 1, "a new taint must be a non-zero exit (fail-loud)")
            self.assertIn("AUDIT", r.stderr)
            self.assertIn(head, r.stderr, "the report names the offending SHA")

            taints = _taints(root, "my-change")
            self.assertEqual(len(taints), 1)
            self.assertEqual(taints[0]["sha"], head)
            self.assertEqual(taints[0]["exit"], 1)
            self.assertIsNotNone(taints[0]["tree"])
            # Every row still carries the full fixed shape (gate-preconditions
            # design D3 widened it by three additive fields, None here).
            self.assertEqual(
                set(taints[0].keys()),
                {"ts", "gate", "exit", "duration_ms", "change", "task",
                 "tree", "attempt", "approved_by", "sha", "verdict",
                 "outcome", "precondition", "precondition_exit", "scope",
                 "cause", "detail", "session", "accepted_by",
                 "author", "tests", "base", "no_behaviour", "note", "restart_available", "characterization", "kind",
         "tokens", "window", "messages", "source"},
            )

    def test_second_pass_does_not_re_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _new_change_repo(tmp)
            _ungated_commit(root, "b.txt", "bypass")

            r1 = _run_gates(root, "audit", "--change", "my-change")
            self.assertEqual(r1.returncode, 1)
            self.assertEqual(len(_taints(root, "my-change")), 1)

            r2 = _run_gates(root, "audit", "--change", "my-change")
            self.assertEqual(r2.returncode, 0, "cursor advanced — nothing new to audit")
            self.assertEqual(len(_taints(root, "my-change")), 1, "no duplicate taint row")


class TestAuditNoOpOffChangeBranch(unittest.TestCase):
    def test_main_is_never_audited(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _new_change_repo(tmp)
            _git(root, "checkout", "main")
            r = _run_gates(root, "audit")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertFalse((root / ".gatedloop" / "runs" / "main.jsonl").exists())


def _new_change_repo_custom_default(tmp, default_branch):
    """Like `_new_change_repo`, but the repo's own-branch is neither `main`
    nor `master` and there is no `origin` remote — `_resolve_merge_target`
    cannot resolve anything (design D3 / task 1.3)."""
    root = Path(tmp)
    _git(root, "init", "-b", default_branch)
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(MANIFEST)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")
    _git(root, "checkout", "-b", "my-change")
    return root


def _build_adopted_repo(tmp):
    """Change branch with one gated task commit, audited once (so the cursor
    is seeded at that commit), then fast-forwarded onto `main` after `main`
    picked up a further commit that was never gated for this change — the
    fast-forward-onto-a-moved-main repro from issue #11 / design D1."""
    root = _new_change_repo(tmp)
    _gated_commit(root, "a.txt", "task 1")
    seed = _run_gates(root, "audit", "--change", "my-change")
    assert seed.returncode == 0, seed.stderr  # nothing new yet; seeds the cursor

    # "my-change" lands on main (here, via an actual fast-forward), then main
    # gains a further commit gated by its own PR elsewhere -- never audited
    # for "my-change".
    _git(root, "checkout", "main")
    _git(root, "merge", "--ff-only", "my-change")
    (root / "unrelated.txt").write_text("unrelated\n")
    _git(root, "add", "unrelated.txt")
    _git(root, "commit", "-m", "adopted elsewhere")  # no `gates run ci` here on purpose

    # the change branch fast-forwards onto the moved main.
    _git(root, "checkout", "my-change")
    _git(root, "merge", "--ff-only", "main")
    return root


class TestAuditScopedToBranchCommits(unittest.TestCase):
    """scope-audit-to-branch-commits: task 1.1/1.2 — the fast-forward-adoption
    repro (issue #11) and the preserved local-taint invariant."""

    def test_adopted_merge_target_commit_does_not_taint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _build_adopted_repo(tmp)
            adopted_head = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True,
            ).stdout.strip()

            r = _run_gates(root, "audit", "--change", "my-change")
            self.assertEqual(r.returncode, 0, r.stderr)
            taints = _taints(root, "my-change")
            shas = [t["sha"] for t in taints]
            self.assertNotIn(
                adopted_head, shas,
                "a commit already reachable from the resolved merge target must "
                "be exempt from tainting",
            )
            self.assertEqual(taints, [], "the adopted commit is the only new one in range")

    def test_local_ungated_commit_still_taints_after_adoption(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _build_adopted_repo(tmp)
            # First audit after adoption advances the cursor past the adopted
            # commit. Its own exemption is task 1.1's assertion, not this
            # one's -- deliberately not checked here so this test pins only
            # the preserved invariant and passes both before and after the fix.
            _run_gates(root, "audit", "--change", "my-change")

            _ungated_commit(root, "c.txt", "bypass after adoption")
            local_head = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True,
            ).stdout.strip()

            r2 = _run_gates(root, "audit", "--change", "my-change")
            self.assertEqual(r2.returncode, 1, "a genuinely ungated local commit must still taint")
            taints = _taints(root, "my-change")
            shas = [t["sha"] for t in taints]
            self.assertIn(local_head, shas, "the local ungated commit must be tainted")


class TestAuditNoMergeTargetKeepsCurrentBehaviour(unittest.TestCase):
    """task 1.3: with no resolvable merge target, the walk is unchanged --
    the exemption never widens into skipping commits it can't scope."""

    def test_ungated_commit_still_taints_with_no_merge_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _new_change_repo_custom_default(tmp, "trunk")
            _gated_commit(root, "a.txt", "task 1")
            seed = _run_gates(root, "audit", "--change", "my-change")
            self.assertEqual(seed.returncode, 0, seed.stderr)  # seeds the cursor

            _ungated_commit(root, "b.txt", "bypass")
            local_head = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True,
            ).stdout.strip()

            r = _run_gates(root, "audit", "--change", "my-change")
            self.assertEqual(r.returncode, 1, "no target resolves -- the cursor-based walk still audits")
            taints = _taints(root, "my-change")
            self.assertEqual(len(taints), 1)
            self.assertEqual(taints[0]["sha"], local_head)


# ---------- escalation-outcomes D5: human-commit classification ------------

import os  # noqa: E402  (kept beside the helpers that need it)


def _env(session):
    """A copy of the environment with the session marker set ("agent") or
    removed ("human"). Passed to a subprocess only — this process's own
    `os.environ` is never mutated, so nothing needs restoring."""
    env = dict(os.environ)
    env.pop("CLAUDECODE", None)
    if session == "agent":
        env["CLAUDECODE"] = "1"
    return env


def _run_gates_env(root, session, *args):
    return subprocess.run(
        [sys.executable, str(GATES_SHIM), *args],
        cwd=root, capture_output=True, text=True, env=_env(session),
    )


def _head(root):
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True,
    ).stdout.strip()


def _session_commit(root, fname, session, with_ledger=False):
    (root / fname).write_text(fname + "\n")
    _git(root, "add", fname)
    r = _run_gates_env(root, session, "run", "ci", "--change", "my-change")
    assert r.returncode == 0, r.stderr
    if with_ledger:
        _git(root, "add", ".gatedloop/runs")  # the documented discipline (tdd-apply 5h)
    _git(root, "commit", "-m", fname)


def _interventions(root):
    return [r for r in _rows(root, "my-change") if r.get("gate") == "intervention"]


def _unclassified(root):
    return [r for r in _rows(root, "my-change") if r.get("gate") == "unclassified-commit"]


class TestAuditClassifiesHumanCommits(unittest.TestCase):
    def test_human_gated_commit_is_an_intervention_not_a_taint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _new_change_repo(tmp)
            _session_commit(root, "a.txt", "human")
            sha = _head(root)
            r = _run_gates_env(root, "agent", "audit", "--change", "my-change")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(_taints(root, "my-change"), [])
            rows = _interventions(root)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["cause"], "human-commit")
            self.assertEqual(rows[0]["sha"], sha)
            self.assertIsNotNone(rows[0]["tree"])
            self.assertIn(sha, r.stderr, "one stderr line per classification")

    def test_agent_gated_commit_yields_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _new_change_repo(tmp)
            _session_commit(root, "a.txt", "agent")
            r = _run_gates_env(root, "agent", "audit", "--change", "my-change")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(_taints(root, "my-change"), [])
            self.assertEqual(_interventions(root), [])
            self.assertEqual(_unclassified(root), [])

    def test_any_agent_row_wins_over_human_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _new_change_repo(tmp)
            (root / "a.txt").write_text("a\n")
            _git(root, "add", "a.txt")
            _run_gates_env(root, "human", "run", "ci", "--change", "my-change")
            _run_gates_env(root, "agent", "run", "ci", "--change", "my-change")
            _git(root, "commit", "-m", "a")
            _run_gates_env(root, "agent", "audit", "--change", "my-change")
            self.assertEqual(_interventions(root), [])

    def test_pre_era_rows_yield_neither_taint_nor_intervention(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _new_change_repo(tmp)
            (root / "a.txt").write_text("a\n")
            _git(root, "add", "a.txt")
            tree = subprocess.run(
                ["git", "write-tree"], cwd=root, capture_output=True, text=True,
            ).stdout.strip()
            runs = root / ".gatedloop" / "runs"
            runs.mkdir(parents=True)
            # A green ci row written before the `session` field existed.
            (runs / "my-change.jsonl").write_text(json.dumps({
                "ts": "2026-01-01T00:00:00+00:00", "gate": "ci", "exit": 0,
                "duration_ms": 1, "change": "my-change", "task": None,
                "tree": tree, "attempt": 1, "approved_by": None, "sha": None,
            }) + "\n")
            _git(root, "commit", "-m", "a")
            sha = _head(root)
            r = _run_gates_env(root, "agent", "audit", "--change", "my-change")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(_taints(root, "my-change"), [])
            self.assertEqual(_interventions(root), [])
            # D5 implementer's choice: the audit discloses the commit it could
            # not classify, so `--outcomes` counts it from ledger rows alone.
            disclosed = _unclassified(root)
            self.assertEqual([d["sha"] for d in disclosed], [sha])

    def test_audit_never_classifies_the_same_commit_twice(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _new_change_repo(tmp)
            _session_commit(root, "a.txt", "human")
            _run_gates_env(root, "agent", "audit", "--change", "my-change")
            # Drop the cursor so the second pass re-walks the same commit:
            # the SHA dedupe, not the cursor, must hold.
            cursor = root / ".git" / "gatedloop" / "audit" / "my-change.head"
            self.assertTrue(cursor.exists())
            cursor.unlink()
            _run_gates_env(root, "agent", "audit", "--change", "my-change")
            self.assertEqual(len(_interventions(root)), 1)

    def test_no_green_row_still_taints_exactly_as_before(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _new_change_repo(tmp)
            _ungated_commit(root, "b.txt", "bypass")
            r = _run_gates_env(root, "agent", "audit", "--change", "my-change")
            self.assertEqual(r.returncode, 1)
            self.assertEqual(len(_taints(root, "my-change")), 1)
            self.assertEqual(_interventions(root), [])


class TestAuditJoinIsLedgerBlind(unittest.TestCase):
    """The documented discipline commits the ledger row with the task
    (tdd-apply 5h), so the commit's tree differs from the tree `gates run ci`
    recorded by exactly the ledger. The join ignores `.gatedloop/runs/**`, the
    same normalization the `ci` marker uses (fix-marker-mechanics D1) —
    otherwise every rule-following commit would taint and no human-gated one
    could ever be classified."""

    def test_task_commit_carrying_its_ledger_row_is_not_tainted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _new_change_repo(tmp)
            _session_commit(root, "a.txt", "agent", with_ledger=True)
            r = _run_gates_env(root, "agent", "audit", "--change", "my-change")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(_taints(root, "my-change"), [])

    def test_human_commit_carrying_its_ledger_row_is_classified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _new_change_repo(tmp)
            _session_commit(root, "a.txt", "human", with_ledger=True)
            sha = _head(root)
            _run_gates_env(root, "agent", "audit", "--change", "my-change")
            self.assertEqual(_taints(root, "my-change"), [])
            self.assertEqual([i["sha"] for i in _interventions(root)], [sha])

    def test_ledger_only_commit_after_a_gated_one_is_not_tainted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _new_change_repo(tmp)
            _session_commit(root, "a.txt", "agent", with_ledger=True)
            _run_gates_env(root, "agent", "halt", "record", "stalled", "--change", "my-change")
            _git(root, "add", ".gatedloop/runs")
            _git(root, "commit", "-m", "record halt")
            r = _run_gates_env(root, "agent", "audit", "--change", "my-change")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(_taints(root, "my-change"), [])

    def test_code_change_beyond_the_ledger_still_taints(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _new_change_repo(tmp)
            (root / "a.txt").write_text("a\n")
            _git(root, "add", "a.txt")
            _run_gates_env(root, "agent", "run", "ci", "--change", "my-change")
            (root / "a.txt").write_text("changed after the gate\n")
            _git(root, "add", "a.txt", ".gatedloop/runs")
            _git(root, "commit", "-m", "a")
            r = _run_gates_env(root, "agent", "audit", "--change", "my-change")
            self.assertEqual(r.returncode, 1)
            self.assertEqual(len(_taints(root, "my-change")), 1)


if __name__ == "__main__":
    unittest.main()
