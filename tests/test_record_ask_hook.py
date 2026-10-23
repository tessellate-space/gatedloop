"""The `AskUserQuestion` hook records a human turn (escalation-outcomes
design D4).

`hooks/record-ask.sh` is a `PreToolUse` hook on the question tool. It only
records — it never denies — so every case here asserts exit 0, and asserts
what it wrote: one `intervention`/`ask` row on a change branch, nothing on the
merge target, and a stderr line (never a block) when the ledger is
unwritable.

Stdlib only, per `zero-dep-shim`. The hook is driven exactly as Claude Code
drives it: a JSON payload on stdin with `cwd` naming the repository.

Run with:  python3 -m unittest discover -s tests
"""

import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HOOK = REPO / "hooks" / "record-ask.sh"

MANIFEST = 'gatesVersion: 1\ngates:\n  ci: "true"\n'
CHANGE = "my-change"


def _git(cwd, *args):
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
    )


def _repo(tmp, on_change=True):
    root = Path(tmp)
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(MANIFEST)
    tasks = root / "openspec" / "changes" / CHANGE / "tasks.md"
    tasks.parent.mkdir(parents=True)
    tasks.write_text("- [ ] 1.1 a\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")
    if on_change:
        _git(root, "checkout", "-b", CHANGE)
    return root


def _payload(root, question):
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "AskUserQuestion",
        "cwd": str(root),
        "tool_input": {"questions": [
            {"question": question, "header": "Q", "options": []},
            {"question": "second question, never recorded", "options": []},
        ]},
    }


def _run_hook(root, payload):
    env = dict(os.environ)
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    env.pop("CLAUDE_PROJECT_DIR", None)
    return subprocess.run(
        ["bash", str(HOOK)], input=json.dumps(payload), env=env,
        cwd=root, capture_output=True, text=True,
    )


def _rows(root):
    p = root / ".gatedloop" / "runs" / f"{CHANGE}.jsonl"
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


class TestRecordAskHook(unittest.TestCase):
    def test_records_one_ask_row_on_a_change_branch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            r = _run_hook(root, _payload(root, "which port?"))
            self.assertEqual(r.returncode, 0, r.stderr)
            rows = _rows(root)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["gate"], "intervention")
            self.assertEqual(rows[0]["cause"], "ask")
            self.assertEqual(rows[0]["detail"], "which port?")
            self.assertEqual(r.stdout.strip(), "", "the hook never emits a decision")

    def test_detail_is_truncated_to_200_characters(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            long_q = "x" * 250 + "?"
            r = _run_hook(root, _payload(root, long_q))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(_rows(root)[0]["detail"], long_q[:200])

    def test_no_row_on_the_merge_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, on_change=False)
            r = _run_hook(root, _payload(root, "which port?"))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertFalse((root / ".gatedloop" / "runs").exists())
            self.assertEqual(r.stderr.strip(), "", "a silent no-op off a change branch")

    def test_unwritable_ledger_reports_and_still_allows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            runs = root / ".gatedloop" / "runs"
            runs.mkdir(parents=True)
            runs.chmod(stat.S_IRUSR | stat.S_IXUSR)
            try:
                r = _run_hook(root, _payload(root, "which port?"))
            finally:
                runs.chmod(stat.S_IRWXU)
            self.assertEqual(r.returncode, 0, "a recording failure never blocks the human turn")
            self.assertIn("gatedloop", r.stderr)
            self.assertEqual(_rows(root), [])

    def test_registered_under_pretooluse_for_the_question_tool(self):
        hooks = json.loads((REPO / "hooks" / "hooks.json").read_text())["hooks"]
        entries = [e for e in hooks["PreToolUse"] if e.get("matcher") == "AskUserQuestion"]
        self.assertEqual(len(entries), 1)
        cmds = [h["command"] for h in entries[0]["hooks"]]
        self.assertTrue(any("record-ask.sh" in c and "${CLAUDE_PLUGIN_ROOT}" in c for c in cmds))


if __name__ == "__main__":
    unittest.main()
