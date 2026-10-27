"""The git-layer `pre-commit` hook leaves a `no-transcript` usage row
(openspec change `token-ledger`, design D7).

A commit made through the git layer has no hook input and so no transcript:
inside a declared agent session the hook records the commit with null counts,
which never moves the task's window, so the next readable flush still covers
it. A human's commit is untouched, as before. A copy installed from the
earlier template is stale, and `gates hook install` refreshes it to the body
that records.

Stdlib only, per `zero-dep-shim`. The hook is installed into throwaway git
repos and fired by real commits. Run with: python3 -m unittest discover -s tests
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _hook_fixture import OLDER_COPY, default_hook, env_without_gates, write_hook  # noqa: E402
from _usage_fixture import (  # noqa: E402
    at, change_repo, git, run_gates, seed, task_start, usage_rows,
)


def _agent_env():
    return env_without_gates(CLAUDECODE="1")


def _human_env():
    return env_without_gates()


def _install(root):
    r = run_gates(root, "hook", "install", "--commit-only", env_=_agent_env())
    assert r.returncode == 0, r.stdout + r.stderr


def _commit_work(root, env_):
    """Stage work, earn a green `ci` on it, then commit through git."""
    (root / "work.txt").write_text("work\n")
    git(root, "add", "work.txt", env_=env_)
    r = run_gates(root, "run", "ci", "--task", "1.1", env_=env_)
    assert r.returncode == 0, r.stderr
    return git(root, "commit", "-m", "work", env_=env_)


class TestTheGitLayerRecordsNoTranscript(unittest.TestCase):
    def test_an_agent_commit_leaves_a_null_count_usage_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = change_repo(tmp)
            seed(root, task_start(at(0), "1.1"))
            _install(root)
            _commit_work(root, _agent_env())
            (row,) = usage_rows(root)
            self.assertEqual(row["source"], "no-transcript")
            self.assertIsNone(row["tokens"])
            self.assertEqual(row["task"], "1.1")

    def test_a_human_commit_records_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = change_repo(tmp)
            seed(root, task_start(at(0), "1.1"))
            _install(root)
            _commit_work(root, _human_env())
            self.assertEqual(usage_rows(root), [])


class TestAnEarlierCopyIsRefreshed(unittest.TestCase):
    def test_install_replaces_an_earlier_copy_with_the_recording_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = change_repo(tmp)
            seed(root, task_start(at(0), "1.1"))
            write_hook(default_hook(root), OLDER_COPY)
            _install(root)
            _commit_work(root, _agent_env())
            self.assertEqual(len(usage_rows(root)), 1)


if __name__ == "__main__":
    unittest.main()
