"""Shared fixtures for the `gates merge` tests (change `merge-step`).

Two kinds of fixture live here so no test file copies one (`gatedloop.test-
quality` item 8):

- `HeldLock` / `FakeTime`: another process holding a machine-wide lock, and
  an injected clock for the wait loop, so a lock test never waits for real
  (item 7).
- `MergeRepo`: a real repository with a bare `origin`, a change planned on
  `main`, and a change branch carried through the loop's own gates. The
  merge step's behaviour IS git's -- detaching, squashing, conflicting,
  pushing against a moved remote -- so those tests sit on the git layer
  boundary on purpose; no cheaper layer can observe a rejected push.

Stdlib only, per `zero-dep-shim`. Not a test module (no `test` prefix), so
discovery imports it only through the tests that use it.
"""

from __future__ import annotations

import datetime
import fcntl
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

CHANGE = "add-thing"
LEDGER_REL = f".gatedloop/runs/{CHANGE}.jsonl"
PROPOSAL_TITLE = "Add the thing"
SCENARIO_TITLE = "It works"

BASE_MANIFEST = 'gatesVersion: 1\ngates:\n  ci: "true"\n'

WALL_BASE = 1_800_000_000.0

# A stand-in for the OpenSpec CLI on PATH. `gates merge` calls only
# `openspec archive <name> --yes`; this one performs the three-path move
# commands/archive.md describes (change dir out, archive dir in, spec deltas
# promoted into openspec/specs). Anything else answers success with `{}`.
FAKE_OPENSPEC = r"""#!/bin/sh
if [ "$1" = "archive" ]; then
  name="$2"
  if [ -n "$FAKE_OPENSPEC_ARCHIVE_FAILS" ]; then
    echo "archive refused for $name" >&2
    exit 1
  fi
  dest="openspec/changes/archive/$(date -u +%Y-%m-%d)-$name"
  mkdir -p openspec/changes/archive
  if [ -d "openspec/changes/$name/specs" ]; then
    mkdir -p openspec/specs
    cp -R "openspec/changes/$name/specs/." openspec/specs/
  fi
  mv "openspec/changes/$name" "$dest"
  echo "Change '$name' archived as '$dest'."
  exit 0
fi
echo '{}'
exit 0
"""


def _iso(epoch: float) -> str:
    return datetime.datetime.fromtimestamp(epoch, datetime.timezone.utc).isoformat()


class FakeTime:
    """A clock the lock's wait loop reads and a sleep that advances it,
    calling `on_release` once `release_at` fake seconds have passed (never,
    when `release_at` is None)."""

    def __init__(self, release_at=None, on_release=None):
        self.t = 0.0
        self.release_at = release_at
        self.on_release = on_release
        self.released = False

    def clock(self) -> float:
        return self.t

    def wall(self) -> float:
        return WALL_BASE + self.t

    def sleep(self, seconds: float) -> None:
        self.t += seconds
        if self.t > 7200:
            raise AssertionError("the wait never ended: two hours of fake time passed")
        if self.release_at is not None and not self.released and self.t >= self.release_at:
            self.released = True
            if self.on_release:
                self.on_release()


class HeldLock:
    """Another process holding the named machine-wide lock: a real flock on
    its own file handle under the common git dir, with holder metadata."""

    def __init__(self, git_common_dir: Path, name: str, pid: int):
        path = Path(git_common_dir) / "gatedloop" / "locks" / f"{name}.lock"
        path.parent.mkdir(parents=True, exist_ok=True)
        self.fh = open(path, "a+")
        fcntl.flock(self.fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.fh.seek(0)
        self.fh.truncate()
        self.fh.write(json.dumps({"pid": pid, "ts": _iso(WALL_BASE - 60)}))
        self.fh.flush()
        self.open = True

    def release(self) -> None:
        if self.open:
            fcntl.flock(self.fh.fileno(), fcntl.LOCK_UN)
            self.fh.close()
            self.open = False


def clean_env(extra=None, path_prefix=None) -> dict:
    """The parent environment minus any GIT_* variable (a test run from a
    git hook would otherwise point every child git at the wrong index), with
    the agent-session marker pinned on. The merge runs inside an agent
    session; inheriting `CLAUDECODE` from the host instead made the reflog
    audit read the fixture's own commits as human commits on CI runners
    only, and step 1 then committed those `intervention` rows on the branch.
    A test that needs a human context passes `CLAUDECODE=None`."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["CLAUDECODE"] = "1"
    # No automatic maintenance: git detaches it into the background after a
    # commit or fetch, and a detached writer still adding to `.git/objects`
    # made a test's temp-dir cleanup fail with "Directory not empty" on CI.
    env.update({"GIT_CONFIG_COUNT": "2",
                "GIT_CONFIG_KEY_0": "maintenance.auto", "GIT_CONFIG_VALUE_0": "false",
                "GIT_CONFIG_KEY_1": "gc.auto", "GIT_CONFIG_VALUE_1": "0"})
    if path_prefix:
        env["PATH"] = f"{path_prefix}{os.pathsep}{env.get('PATH', '')}"
    for k, v in (extra or {}).items():
        if v is None:
            env.pop(k, None)
        else:
            env[k] = v
    return env


def git(cwd, *args, check=True) -> str:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env=clean_env())
    if check and r.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed in {cwd}: {r.stderr}")
    return r.stdout.strip()


def rows_from_text(text: str) -> list:
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except ValueError:
                pass
    return rows


class MergeRepo:
    """A primary checkout on `main` tracking a bare `origin`, with change
    `add-thing` planned on `main`. `start_change(lane=...)` cuts the change
    branch either in the primary itself or in a separate lane worktree."""

    def __init__(self, tmp: Path, manifest_extra: str = "", manifest: str | None = None):
        self.tmp = Path(tmp)
        self.primary = self.tmp / "primary"
        self.bare = self.tmp / "origin.git"
        self.other = self.tmp / "other"
        self.bin = self.tmp / "bin"
        self.push_log = self.tmp / "pushes.log"
        self.lane = None
        self.bin.mkdir(parents=True)
        fake = self.bin / "openspec"
        fake.write_text(FAKE_OPENSPEC)
        fake.chmod(0o755)
        self.manifest = (manifest if manifest is not None else BASE_MANIFEST) + manifest_extra
        self._init_main()

    # ---- running things -------------------------------------------------

    def env(self, **extra) -> dict:
        return clean_env(extra, path_prefix=str(self.bin))

    def gates(self, *args, cwd=None, **env) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(GATES_SHIM), *args],
            cwd=cwd or self.primary, capture_output=True, text=True, env=self.env(**env),
        )

    def merge(self, cwd=None, **env) -> subprocess.CompletedProcess:
        return self.gates("merge", CHANGE, cwd=cwd, **env)

    # ---- building the history ------------------------------------------

    def _init_main(self) -> None:
        p = self.primary
        p.mkdir(parents=True)
        git(p, "init", "-q", "-b", "main")
        git(p, "config", "user.email", "t@example.com")
        git(p, "config", "user.name", "T")
        (p / ".gates.yaml").write_text(self.manifest)
        (p / "shared.txt").write_text("one\ntwo\nthree\n")
        change = p / "openspec" / "changes" / CHANGE
        (change / "specs" / "cap").mkdir(parents=True)
        (change / "proposal.md").write_text(
            f"# Proposal: {PROPOSAL_TITLE}\n\n## Why\n\nBecause.\n"
        )
        (change / "tasks.md").write_text("## 1. Do it\n\n- [x] 1.1 Add the thing\n")
        (change / "specs" / "cap" / "spec.md").write_text(
            "## ADDED Requirements\n\n### Requirement: Thing\n\nThe system SHALL work.\n\n"
            f"#### Scenario: {SCENARIO_TITLE}\n\n- **WHEN** it runs\n- **THEN** it works\n"
        )
        git(p, "add", "-A")
        git(p, "commit", "-q", "-m", "plan: add-thing")

        git(self.tmp, "init", "-q", "--bare", "-b", "main", str(self.bare))
        hook = self.bare / "hooks" / "post-receive"
        hook.write_text(f"#!/bin/sh\ncat >/dev/null\necho push >> '{self.push_log}'\n")
        hook.chmod(0o755)
        git(p, "remote", "add", "origin", str(self.bare))
        git(p, "push", "-q", "origin", "HEAD:main")
        git(p, "remote", "set-head", "origin", "main")
        self.push_log.write_text("")  # the setup push is not the merge's
        git(self.tmp, "clone", "-q", str(self.bare), str(self.other))
        git(self.other, "config", "user.email", "o@example.com")
        git(self.other, "config", "user.name", "O")

    def start_change(self, lane: bool) -> Path:
        """Cut branch `add-thing` off `main`: in the primary checkout
        (`lane=False`), or in a separate lane worktree, leaving the primary
        on `main` (`lane=True`)."""
        if lane:
            self.lane = self.tmp / "lane"
            git(self.primary, "worktree", "add", "-q", "-b", CHANGE, str(self.lane), "main")
        else:
            git(self.primary, "checkout", "-q", "-b", CHANGE)
            self.lane = self.primary
        return self.lane

    def task_commit(self, rel: str, content: str, subject: str) -> str:
        """One task, the loop's way: edit, stage, a green `gates run ci`,
        then commit the code with the ledger row that run appended."""
        f = self.lane / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content)
        git(self.lane, "add", "-A")
        r = self.gates("run", "ci", "--task", "1.1", cwd=self.lane)
        if r.returncode != 0:
            raise AssertionError(f"fixture ci red: {r.stdout}{r.stderr}")
        git(self.lane, "add", "-A")
        git(self.lane, "commit", "-q", "-m", subject)
        return git(self.lane, "rev-parse", "HEAD")

    def prove_head(self, ci: bool = True, live_check: bool = True, verify: bool = False) -> None:
        """Change completion on the branch head, leaving the rows those runs
        append uncommitted -- the trailing rows `gates merge` step 1 commits."""
        for gate, wanted in (("ci", ci), ("verify", verify), ("live-check", live_check)):
            if not wanted:
                continue
            r = self.gates("run", gate, cwd=self.lane)
            if r.returncode != 0:
                raise AssertionError(f"fixture {gate} red: {r.stdout}{r.stderr}")

    def append_lane_row(self, row: dict) -> None:
        path = self.lane / LEDGER_REL
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as f:
            f.write(json.dumps(row) + "\n")

    def advance_origin(self, rel: str, content: str, subject: str) -> str:
        """Another integrator lands a commit on origin's main."""
        git(self.other, "pull", "-q", "--ff-only", "origin", "main")
        f = self.other / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content)
        git(self.other, "add", "-A")
        git(self.other, "commit", "-q", "-m", subject)
        git(self.other, "push", "-q", "origin", "HEAD:main")
        self.push_log.write_text("")
        return git(self.other, "rev-parse", "HEAD")

    # ---- reading the outcome -------------------------------------------

    def origin_main(self) -> str:
        return git(self.bare, "rev-parse", "refs/heads/main")

    def head_state(self, cwd=None) -> tuple:
        cwd = cwd or self.primary
        return (
            git(cwd, "branch", "--show-current"),
            git(cwd, "rev-parse", "HEAD"),
            git(cwd, "status", "--porcelain"),
        )

    def pushes(self) -> int:
        return len([x for x in self.push_log.read_text().splitlines() if x.strip()])

    def rows_at(self, ref: str, cwd=None) -> list:
        r = subprocess.run(
            ["git", "show", f"{ref}:{LEDGER_REL}"], cwd=cwd or self.primary,
            capture_output=True, text=True, env=clean_env(),
        )
        return rows_from_text(r.stdout) if r.returncode == 0 else []

    def files_in_commit(self, sha: str, cwd=None) -> list:
        out = git(cwd or self.primary, "diff-tree", "--no-commit-id", "-r", "--name-only", f"{sha}~1", sha)
        return [x for x in out.splitlines() if x.strip()]

    def origin_log(self, since: str) -> list:
        """`[(sha, subject, body)]` on origin's main after `since`, oldest first."""
        out = git(self.bare, "log", "--reverse", "--format=%H%x1f%s%x1f%b%x1e", f"{since}..main")
        entries = []
        for rec in out.split("\x1e"):
            rec = rec.strip("\n")
            if not rec.strip():
                continue
            sha, subject, body = (rec.split("\x1f") + ["", ""])[:3]
            entries.append((sha.strip(), subject, body))
        return entries


def combined(proc: subprocess.CompletedProcess) -> str:
    return (proc.stdout or "") + (proc.stderr or "")
