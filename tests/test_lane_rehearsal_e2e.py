"""Scripted lane rehearsal (task 8.2 of `worktree-native-loop`): one scratch
repo exercises every scenario the change's specs name, in sequence, proving
they compose rather than merely pass in isolation:

1. Two worktree lanes commit gated work concurrently -- neither's marker
   satisfies or invalidates the other's (D1/D2).
2. A proposal-only backlog entry commits alone, no filler delta spec (D4).
3. A declared branch pattern authors without any rename ritual (D3).
4. A serialized gate blocks its twin, with a visible waiting heartbeat (D6).
5. An unpushed local merge archives with the advisory (D5).

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"
HOOK = REPO / "hooks" / "gate-commit.sh"

MANIFEST = (
    'gatesVersion: 1\n'
    'gates:\n  ci: "true"\n'
    'approval:\n  plan: self\n'
    'discipline:\n  propose-branches:\n    - "worktree/*"\n'
    'concurrency:\n  serialize:\n    - ci\n'
)


def _git(cwd, *args):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r


def _run_gates(root, *args):
    return subprocess.run(
        [sys.executable, str(GATES_SHIM), *args], cwd=root, capture_output=True, text=True,
    )


def _spawn_gates(root, *args) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, str(GATES_SHIM), *args], cwd=root,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )


def _commit_via_hook(session_cwd: Path, worktree: Path, message: str):
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
    return subprocess.run(
        ["git", "commit", "-m", message], cwd=worktree, capture_output=True, text=True,
    )


class TestScriptedLaneRehearsal(unittest.TestCase):
    def test_full_rehearsal(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as remote_tmp:
            tmp, remote_tmp = Path(tmp), Path(remote_tmp)
            primary = tmp / "primary"
            primary.mkdir()
            _git(primary, "init", "-b", "main")
            _git(primary, "config", "user.email", "t@example.com")
            _git(primary, "config", "user.name", "T")
            (primary / ".gates.yaml").write_text(MANIFEST)
            _git(primary, "add", "-A")
            _git(primary, "commit", "-m", "init")

            # A bare origin, at this initial state -- so anything committed
            # to local main afterward is a genuine unpushed merge (step 5).
            bare = remote_tmp / "origin.git"
            _git(remote_tmp, "init", "--bare", "-b", "main", str(bare))
            _git(primary, "remote", "add", "origin", str(bare))
            _git(primary, "push", "origin", "HEAD:main")
            _git(primary, "remote", "set-head", "origin", "main")

            # --- 3. A declared branch pattern authors without a rename.
            _git(primary, "checkout", "-b", "worktree/lane-a")
            scaffold_a = _run_gates(primary, "discipline", "check-propose", "--scaffold")
            self.assertEqual(scaffold_a.returncode, 0, scaffold_a.stderr)
            _git(primary, "checkout", "main")

            # --- 1. Two worktree lanes, each with the declared pattern's
            # naming, commit gated work concurrently -- no cross-invalidation.
            _git(primary, "branch", "worktree/lane-b")
            wt_a = tmp / "wt-a"
            wt_b = tmp / "wt-b"
            _git(primary, "worktree", "add", str(wt_a), "worktree/lane-a")
            _git(primary, "worktree", "add", str(wt_b), "worktree/lane-b")

            for name, wt in (("a", wt_a), ("b", wt_b)):
                (wt / "task.txt").write_text(f"lane {name}\n")
                _git(wt, "add", "task.txt")
                r = _run_gates(wt, "run", "ci")
                self.assertEqual(r.returncode, 0, r.stderr)
                result = _commit_via_hook(primary, wt, f"lane {name} task")
                self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

            # --- 2. A proposal-only backlog entry commits alone, on main,
            # with no filler delta spec.
            backlog = primary / "openspec" / "changes" / "backlog-idea"
            backlog.mkdir(parents=True)
            (backlog / "proposal.md").write_text("just an idea\n")
            (backlog / ".openspec.yaml").write_text("schema: spec-driven\ncreated: 2026-08-19\n")
            _git(primary, "add", "-A")
            tree = subprocess.run(
                ["git", "write-tree"], cwd=primary, capture_output=True, text=True,
            ).stdout.strip()
            check = _run_gates(primary, "discipline", "check-commit", tree)
            self.assertEqual(check.returncode, 0, check.stderr)
            self.assertIn("proposal-only", check.stdout + check.stderr)
            _git(primary, "commit", "-m", "propose backlog-idea (no deltas yet)")

            # --- 5. `backlog-idea` was just committed to local main and
            # never pushed -- archiving it now exercises the local-merge
            # advisory (its own local counterpart of the merge target
            # carries it, origin doesn't).
            archive = _run_gates(primary, "discipline", "check-archive", "backlog-idea")
            self.assertEqual(archive.returncode, 0, archive.stderr)
            self.assertIn("not yet", archive.stdout + archive.stderr)

            # --- 4. A serialized gate blocks its twin, with a visible
            # waiting heartbeat.
            marker_file = primary / "order.txt"
            serialized_manifest = (
                'gatesVersion: 1\n'
                f'gates:\n  ci: "echo start >> {marker_file} && sleep 1 && echo end >> {marker_file}"\n'
                'concurrency:\n  serialize:\n    - ci\n'
            )
            (primary / ".gates.yaml").write_text(serialized_manifest)
            p1 = _spawn_gates(primary, "run", "ci")
            time.sleep(0.3)
            p2 = _spawn_gates(primary, "run", "ci")
            out1, err1 = p1.communicate(timeout=15)
            out2, err2 = p2.communicate(timeout=15)
            self.assertEqual(p1.returncode, 0, err1)
            self.assertEqual(p2.returncode, 0, err2)
            self.assertIn("waiting for gate 'ci'", err2)
            lines = marker_file.read_text().splitlines()
            self.assertEqual(lines, ["start", "end", "start", "end"])


if __name__ == "__main__":
    unittest.main()
