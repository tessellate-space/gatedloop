"""`gates lock status` (design D3 of `lock-and-ledger-hygiene`, #33 item 5).

A hung holder -- an orphaned suite on a wedged socket, holding `ci` for
6.5 h -- looked exactly like a busy one, because nothing reported the lock's
state. `gates lock status` probes each serialized gate's lock with a
non-blocking flock on its own handle: acquired means free, whatever the
metadata says; refused means held, by the pid the metadata names. A live
holder past an hour is flagged "possibly hung" with a command a human can
inspect it with. Nothing is ever killed.

Driven through the CLI, the seam an operator and #37's dispatch use. The
holder is this test process, holding a real flock on a separate handle --
so a status command that killed a "possibly hung" holder would kill the
test run itself.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

import datetime
import fcntl
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

MANIFEST = (
    'gatesVersion: 1\n'
    'gates:\n  ci: "true"\n'
    'concurrency:\n  serialize:\n    - ci\n'
)


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _lock_path(root: Path) -> Path:
    return root / ".git" / "gatedloop" / "locks" / "ci.lock"


def _write_holder(path: Path, fh, pid: int, hours_ago: float) -> None:
    since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours_ago)
    fh.seek(0)
    fh.truncate()
    fh.write(json.dumps({"pid": pid, "ts": since.isoformat()}))
    fh.flush()


def _dead_pid() -> int:
    p = subprocess.Popen([sys.executable, "-c", ""])
    p.wait()
    return p.pid


class TestLockStatus(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        _git(self.root, "init", "-b", "main")
        (self.root / ".gates.yaml").write_text(MANIFEST)
        path = _lock_path(self.root)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.fh = open(path, "a+")

    def tearDown(self):
        self.fh.close()
        self._tmp.cleanup()

    def _status(self, *extra) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(GATES_SHIM), "lock", "status", *extra],
            cwd=self.root, capture_output=True, text=True,
        )

    def _json(self) -> dict:
        r = self._status("--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        locks = {entry["gate"]: entry for entry in json.loads(r.stdout)["locks"]}
        return locks["ci"]

    def test_a_free_lock_with_stale_metadata_is_free(self):
        _write_holder(_lock_path(self.root), self.fh, _dead_pid(), hours_ago=7)
        self.assertEqual(self._json()["state"], "free")

    def test_a_live_holder_past_an_hour_is_possibly_hung(self):
        fcntl.flock(self.fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        _write_holder(_lock_path(self.root), self.fh, os.getpid(), hours_ago=6.2)
        entry = self._json()
        self.assertEqual(entry["state"], "held")
        self.assertEqual(entry["pid"], os.getpid())
        self.assertTrue(entry["alive"])
        self.assertTrue(entry["possibly_hung"])
        human = self._status()
        self.assertEqual(human.returncode, 0, human.stderr)
        # A lower bound, not an exact duration: the clock runs on between the
        # holder write and this call, by minutes on a loaded machine.
        held = re.search(rf"held by pid {os.getpid()} \(alive\) for (\d+)h(\d+)m", human.stdout)
        self.assertIsNotNone(held, human.stdout)
        self.assertGreaterEqual(int(held.group(1)) * 60 + int(held.group(2)), 6 * 60 + 12)
        self.assertIn("possibly hung", human.stdout)
        self.assertIn(f"ps -o pid,etime,command -p {os.getpid()}", human.stdout)

    def test_a_recent_live_holder_is_held_not_hung(self):
        fcntl.flock(self.fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        _write_holder(_lock_path(self.root), self.fh, os.getpid(), hours_ago=0.1)
        entry = self._json()
        self.assertEqual(entry["state"], "held")
        self.assertFalse(entry["possibly_hung"])


if __name__ == "__main__":
    unittest.main()
