"""A change under `loop.ci-at: ready`, end to end (openspec change `ci-at`,
task 8.1; design D2-D4 "How it composes").

One fixture change on a real repository with a bare `origin`, implemented in
a linked lane worktree with the git-layer `pre-commit` hook installed. Two
tasks go through placement, the red run, a green `unit` on the staged tree
and a commit that passes both commit layers (the tool-level hook driven with
the commit's command, then a real `git commit` that fires the git layer);
the `Stop` hook's audit runs between them. `record-ready` is refused until an
unscoped `ci` passes on the head, then allowed, and `gates merge` proves the
head (step 1) and integrates. No `ci` runs before READY, and the ledger holds
no taint row.

A characterization test: everything here composes behaviour the earlier
tasks of `ci-at` built, so it passes on its first run.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _merge_fixture import CHANGE, MergeRepo, combined, git

REPO = Path(__file__).resolve().parent.parent
TOOL_HOOK = REPO / "hooks" / "gate-commit.sh"
STOP_HOOK = REPO / "hooks" / "continue-loop.sh"
GIT_HOOK = REPO / "templates" / "git-hooks" / "pre-commit"

MANIFEST = (
    'gatesVersion: 1\ngates:\n  ci: "true"\n  unit: "sh scripts/unit.sh"\n'
    "loop:\n  ci-at: ready\n  test-author: inline\n"
)

# `unit` is red while any test asks for a token (`WANT:<token>`) the
# implementation does not yet hold.
UNIT_SH = """\
for want in $(grep -ho 'WANT:[a-z]*' tests/*.txt 2>/dev/null | sed 's/WANT://'); do
  grep -q "$want" src/impl.txt 2>/dev/null || exit 1
done
exit 0
"""

TASKS = """\
## 1. Two things

- [ ] 1.1 Add the first thing
- [ ] 1.2 Add the second thing
"""


class ReadyRepo(MergeRepo):
    def __init__(self, tmp: Path):
        super().__init__(tmp, manifest=MANIFEST)
        p = self.primary
        for rel, text in {
            "scripts/unit.sh": UNIT_SH,
            "src/impl.txt": "base\n",
            f"openspec/changes/{CHANGE}/tasks.md": TASKS,
        }.items():
            (p / rel).parent.mkdir(parents=True, exist_ok=True)
            (p / rel).write_text(text)
        self.approve_plan()
        git(p, "add", "-A")
        git(p, "commit", "-q", "-m", "plan: two things")
        git(p, "push", "-q", "origin", "HEAD:main")
        self.push_log.write_text("")
        hooks = Path(git(p, "rev-parse", "--git-common-dir"))
        hooks = (hooks if hooks.is_absolute() else p / hooks) / "hooks"
        hooks.mkdir(exist_ok=True)
        shutil.copy(GIT_HOOK, hooks / "pre-commit")
        (hooks / "pre-commit").chmod(0o755)

    def must(self, *args):
        r = self.gates(*args, cwd=self.lane)
        if r.returncode != 0:
            raise AssertionError(f"`gates {' '.join(args)}` exited {r.returncode}: {combined(r)}")
        return r

    def write(self, rel, text):
        f = self.lane / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text)

    def tick(self, task):
        rel = f"openspec/changes/{CHANGE}/tasks.md"
        text = (self.lane / rel).read_text()
        (self.lane / rel).write_text(text.replace(f"- [ ] {task} ", f"- [x] {task} "))

    def hook_env(self):
        return self.env(CLAUDE_PLUGIN_ROOT=str(REPO))

    def commit_through_both_layers(self, subject):
        """The tool-level hook first, as Claude Code runs it before the Bash
        call, then a real `git commit` that fires the git-layer hook."""
        tool = subprocess.run(
            ["bash", str(TOOL_HOOK)], cwd=self.lane, env=self.hook_env(),
            capture_output=True, text=True,
            input=json.dumps({"tool_input": {"command": f"git commit -m '{subject}'"},
                              "cwd": str(self.lane)}),
        )
        if tool.returncode != 0:
            raise AssertionError(f"tool hook denied: {combined(tool)}")
        done = subprocess.run(["git", "commit", "-q", "-m", subject], cwd=self.lane,
                              env=self.hook_env(), capture_output=True, text=True)
        if done.returncode != 0:
            raise AssertionError(f"git commit denied: {combined(done)}")
        return tool, done

    def stop_audit(self):
        return subprocess.run(["bash", str(STOP_HOOK)], cwd=self.lane, env=self.hook_env(),
                              capture_output=True, text=True,
                              input=json.dumps({"cwd": str(self.lane)}))

    def rows(self):
        p = self.lane / ".gatedloop" / "runs" / f"{CHANGE}.jsonl"
        return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


class ReadyEndToEnd(unittest.TestCase):
    def run_task(self, repo, task, token):
        repo.must("task", "start", task)
        repo.must("tests", "place", task)
        red = repo.gates("run", "unit", "--task", task, "--attempt", "1", cwd=repo.lane)
        self.assertNotIn(red.returncode, (0, 75), combined(red))
        impl = (repo.lane / "src" / "impl.txt").read_text()
        repo.write("src/impl.txt", impl + token + "\n")
        repo.tick(task)
        git(repo.lane, "add", "-A")
        green = repo.must("run", "unit", "--task", task, "--attempt", "2")
        self.assertIn("unit", green.stderr)
        repo.must("review", "record", "clean", "--task", task)
        git(repo.lane, "add", "-A")
        tool, done = repo.commit_through_both_layers(f"task {task}")
        for out in (tool.stdout, done.stdout + done.stderr):
            self.assertIn("'unit' marker matches", out)
            self.assertIn("loop.ci-at: ready", out)

    def test_the_whole_route_exits_as_specified(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = ReadyRepo(Path(tmp))
            repo.start_change(lane=True)

            held = f".gatedloop/authored/{CHANGE}"
            repo.write(f"{held}/1.1/tests/one.txt.authored", "WANT:alpha\n")
            repo.write(f"{held}/1.2/tests/two.txt.authored", "WANT:beta\n")
            handed = repo.must("tests", "handoff", CHANGE, "--inline")
            self.assertIn("commit gate: gates run unit", handed.stderr)
            git(repo.lane, "add", "-A")
            repo.must("run", "unit")
            git(repo.lane, "add", "-A")
            repo.commit_through_both_layers(f"author tests: {CHANGE}")

            self.run_task(repo, "1.1", "alpha")
            audit = repo.stop_audit()
            self.assertNotIn("AUDIT", audit.stderr, combined(audit))
            self.run_task(repo, "1.2", "beta")
            repo.stop_audit()

            self.assertFalse([r for r in repo.rows() if r.get("gate") == "ci"],
                             "no ci ran before READY")
            refused = repo.gates("ledger", "record-ready", CHANGE, cwd=repo.lane)
            self.assertEqual(refused.returncode, 1, combined(refused))
            self.assertFalse([r for r in repo.rows() if r.get("gate") == "ready"])

            repo.prove_head()  # the unscoped ci (and live-check) on the head
            ready = repo.must("ledger", "record-ready", CHANGE)
            self.assertIn('"ci": "pass"', ready.stdout)
            git(repo.lane, "add", f".gatedloop/runs/{CHANGE}.jsonl")
            repo.commit_through_both_layers("record ready")

            self.assertEqual([r for r in repo.rows() if r.get("gate") in ("taint", "vouched")], [])
            # The git-layer hook fires on the merge's own commits too; the
            # plugin root points it at this shim, not one on PATH.
            merged = repo.merge(CLAUDE_PLUGIN_ROOT=str(REPO))
            self.assertEqual(merged.returncode, 0, combined(merged))
            self.assertEqual([r for r in repo.rows_at("origin/main")
                              if r.get("gate") == "taint"], [])


if __name__ == "__main__":
    unittest.main()
