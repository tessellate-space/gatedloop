"""End-to-end: two REAL git worktrees, each run as a serialized-merge-lane
would run them -- a green gate recorded, then a commit issued via
`cd <worktree> && git commit …` from a shared "session" directory (task 2.3
of `worktree-native-loop`, combining D1's command-derived cwd resolution
with D2's tree-keyed markers).

This is the scenario the whole change exists for: each lane accumulates
MULTIPLE green trees over several task commits, and neither lane's marker
store satisfies or invalidates the other's -- and no commit here ever needs
a second attempt (the "marker retry loop" #16 reported).

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
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
HOOK = REPO / "hooks" / "gate-commit.sh"

MANIFEST = 'gatesVersion: 1\ngates:\n  ci: "true"\n'


def _git(cwd, *args):
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
    ).stdout.strip()


def _run_gates(root, *args):
    return subprocess.run(
        [sys.executable, str(GATES_SHIM), *args], cwd=root, capture_output=True, text=True,
    )


def _commit_via_hook(session_cwd: Path, worktree: Path, message: str):
    """Fire `gate-commit.sh` exactly as a background agent would: a compound
    `cd <worktree> && git commit -m <message>` command, with the JSON hook
    input's own `cwd` left at the unrelated session directory."""
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    stdin = {
        "tool_input": {"command": f"cd {worktree} && git commit -m '{message}'"},
        "cwd": str(session_cwd),
    }
    hook = subprocess.run(
        ["bash", str(HOOK)], input=json.dumps(stdin), cwd=str(session_cwd),
        env=env, capture_output=True, text=True,
    )
    if hook.returncode != 0:
        return hook
    # The hook only judges; the actual commit still has to run (same split
    # a real background agent's two tool calls would have, minus the
    # Claude Code harness in between).
    return subprocess.run(
        ["git", "commit", "-m", message], cwd=worktree, capture_output=True, text=True,
    )


class TestTwoWorktreeLanesDoNotCrossInvalidate(unittest.TestCase):
    def test_alternating_commits_across_two_lanes_never_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            primary = tmp / "primary"
            primary.mkdir()
            _git(primary, "init", "-b", "main")
            _git(primary, "config", "user.email", "t@example.com")
            _git(primary, "config", "user.name", "T")
            (primary / ".gates.yaml").write_text(MANIFEST)
            _git(primary, "add", "-A")
            _git(primary, "commit", "-m", "init")

            _git(primary, "branch", "lane-a")
            _git(primary, "branch", "lane-b")
            wt_a = tmp / "wt-a"
            wt_b = tmp / "wt-b"
            _git(primary, "worktree", "add", str(wt_a), "lane-a")
            _git(primary, "worktree", "add", str(wt_b), "lane-b")

            # Each lane commits TWICE, interleaved, each time via its own
            # `cd <worktree> && git commit` from the shared "session" (the
            # primary checkout stays on `main` throughout -- it never itself
            # has any marker).
            for round_num in range(2):
                for name, wt in (("a", wt_a), ("b", wt_b)):
                    fname = f"round{round_num}.txt"
                    (wt / fname).write_text(f"{name}-{round_num}\n")
                    # Stage exactly the intended file -- never `-A`, which
                    # would also sweep up `.gatedloop/runs/**` (the durable
                    # ledger `run ci` just appended to on disk) and trip the
                    # unrelated, out-of-scope `git rm --cached` safety check
                    # `_normalize_tree` hits when a staged ledger blob has
                    # since diverged from the working-tree file (owned by
                    # `fix-marker-mechanics`, not this change).
                    _git(wt, "add", fname)
                    r = _run_gates(wt, "run", "ci")
                    self.assertEqual(r.returncode, 0, r.stderr)

                    result = _commit_via_hook(primary, wt, f"lane {name} round {round_num}")
                    self.assertEqual(
                        result.returncode, 0,
                        f"lane {name} round {round_num} needed a retry: {result.stderr or result.stdout}",
                    )

            # Both lanes' full commit history landed -- 1 init + 2 rounds each.
            log_a = _git(wt_a, "log", "--oneline")
            log_b = _git(wt_b, "log", "--oneline")
            self.assertEqual(len(log_a.splitlines()), 3)
            self.assertEqual(len(log_b.splitlines()), 3)

            # The primary checkout itself was never touched and still has no
            # marker of its own -- a commit attempted directly there (no
            # `cd`) is refused, proving the lanes' green markers never leaked
            # into it.
            (primary / "stray.txt").write_text("x\n")
            _git(primary, "add", "stray.txt")
            denied = _commit_via_hook(primary, primary, "should be denied")
            self.assertNotEqual(denied.returncode, 0)


if __name__ == "__main__":
    unittest.main()
