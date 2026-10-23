"""Cross-worktree gate mutex (design D6 of `worktree-native-loop`, task 6.2).

A gate named in `concurrency.serialize` acquires an exclusive `fcntl.flock`
on `<git-common-dir>/gatedloop/locks/<gate>.lock` for the duration of the
gate COMMAND only -- marker writes and ledger rows happen outside it. An
undeclared gate never locks at all, identical to today. A lane waiting on
the lock prints a periodic notice naming the holder, never hangs silently.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

MANIFEST_NO_LOCK = 'gatesVersion: 1\ngates:\n  ci: "true"\n'
MANIFEST_SERIALIZED_CI = (
    'gatesVersion: 1\n'
    'gates:\n  ci: "true"\n'
    'concurrency:\n  serialize:\n    - ci\n'
)


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _init_repo(root: Path, manifest: str) -> None:
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(manifest)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")


def _run_gates(root, *args) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GATES_SHIM), *args], cwd=root, capture_output=True, text=True,
    )


def _spawn_gates(root, *args) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, str(GATES_SHIM), *args], cwd=root,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )


def _lock_path(root: Path, gate: str) -> Path:
    return root / ".git" / "gatedloop" / "locks" / f"{gate}.lock"


class TestUndeclaredGateNeverLocks(unittest.TestCase):
    def test_no_lock_file_is_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root, MANIFEST_NO_LOCK)
            r = _run_gates(root, "run", "ci")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertFalse(_lock_path(root, "ci").exists())


class TestDeclaredGateLocks(unittest.TestCase):
    def test_lock_file_is_created_under_the_common_git_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root, MANIFEST_SERIALIZED_CI)
            r = _run_gates(root, "run", "ci")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(_lock_path(root, "ci").exists())

    def test_lock_scoped_to_the_named_gate_only(self):
        """A gate NOT in the declared list never locks, even when another
        gate is declared serialized in the same manifest."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = (
                'gatesVersion: 1\n'
                'gates:\n  ci: "true"\n  unit: "true"\n'
                'concurrency:\n  serialize:\n    - ci\n'
            )
            _init_repo(root, manifest)
            r = _run_gates(root, "run", "unit")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertFalse(_lock_path(root, "unit").exists())


class TestTwoProcessContention(unittest.TestCase):
    def test_second_process_waits_then_runs_serialized(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            marker_file = root / "order.txt"
            manifest = (
                'gatesVersion: 1\n'
                f'gates:\n  ci: "echo start >> {marker_file} && sleep 1 && echo end >> {marker_file}"\n'
                'concurrency:\n  serialize:\n    - ci\n'
            )
            _init_repo(root, manifest)

            p1 = _spawn_gates(root, "run", "ci")
            time.sleep(0.3)  # let p1 acquire the lock and start sleeping
            p2 = _spawn_gates(root, "run", "ci")

            out1, err1 = p1.communicate(timeout=15)
            out2, err2 = p2.communicate(timeout=15)

            self.assertEqual(p1.returncode, 0, err1)
            self.assertEqual(p2.returncode, 0, err2)
            # p2 must have printed the waiting notice naming the holder.
            self.assertIn("waiting for gate 'ci'", err2)
            self.assertIn("held by pid", err2)

            # Serialized, not interleaved: start/end pairs never overlap.
            lines = marker_file.read_text().splitlines()
            self.assertEqual(lines, ["start", "end", "start", "end"])


class TestKilledHolderFreesTheLock(unittest.TestCase):
    """flock dies with the fd (task 6.3): a holder killed with SIGKILL --
    no chance to run any cleanup code -- must not wedge the lock for every
    later run. The OS itself releases the lock when the process's file
    descriptors close, which is the whole reason a flock (not a lockfile
    some process is trusted to remove) is the right primitive here."""

    def test_reacquired_promptly_after_kill_9(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # `ci` itself is instant -- what's slow is the HOLDER script
            # below, which acquires the same lock directly and sleeps under
            # it, independent of the gate command's own duration.
            _init_repo(root, MANIFEST_SERIALIZED_CI)

            holder_script = (
                "import importlib.machinery, importlib.util, time\n"
                f"loader = importlib.machinery.SourceFileLoader('g', {str(GATES_SHIM)!r})\n"
                "spec = importlib.util.spec_from_loader(loader.name, loader)\n"
                "g = importlib.util.module_from_spec(spec)\n"
                "loader.exec_module(g)\n"
                f"root = g.Path({str(root)!r})\n"
                "m = g._load(root / '.gates.yaml')\n"
                "with g._gate_lock(root, m, 'ci'):\n"
                "    time.sleep(30)\n"
            )
            holder = subprocess.Popen(
                [sys.executable, "-c", holder_script], cwd=root,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            time.sleep(0.5)  # let it acquire the lock and start sleeping
            self.assertTrue(_lock_path(root, "ci").exists())
            holder.kill()  # SIGKILL -- no cleanup code runs
            holder.wait(timeout=5)

            started = time.monotonic()
            r = _run_gates(root, "run", "ci")
            elapsed = time.monotonic() - started
            self.assertEqual(r.returncode, 0, r.stderr)
            # A wedged lock would hang for the full 30s `sleep` above (or
            # forever); reacquiring promptly proves the OS freed it with
            # the killed process's file descriptors, not from any
            # cooperative cleanup.
            self.assertLess(elapsed, 10, "lock was not freed promptly after the holder was killed")


if __name__ == "__main__":
    unittest.main()
