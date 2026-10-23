"""`gates migrate-name` (change `rename-to-gatedloop`, design D3; spec "A
project migrates to the new name by one command").

It moves a project onto the new names in one go, locally: the state
directory, the earlier metadata keys of every active change, and the earlier
markers in a composed hook. It prints each edit it will not make (Claude Code
settings, permission rules, branch-protection contexts) with its exact
replacement. It never commits, leaves archived changes alone, and exits 0
when nothing is left. The regressions caught here:

- a moved directory git sees as a delete plus an untracked add, so the
  ledger's history breaks and a commit can drop it;
- an untracked `.specloop/` left behind because `git mv` refused it;
- a key rewritten with a changed value (an approval sha that no longer
  matches), a non-approval line dropped, or an archived change rewritten;
- a composed hook whose earlier block survives, so the next install appends
  a second one;
- an edit outside the repository made silently, or one it cannot make left
  unsaid;
- a second run that changes something, or a both-directories project merged
  by guesswork.

Every test uses the earlier names on purpose. Stdlib only, per
`zero-dep-shim`. Every repository is a throwaway one.

Run with:  python3 -m unittest discover -s tests
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _hook_fixture import write_hook

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

EARLIER_META = ('schema: spec-driven\n'
                'x-specloop-approved-by: "T <t@example.com>"\n'
                'x-specloop-approved-at: "2026-10-22T09:00:00+00:00"\n'
                f'x-specloop-approved-sha: "{"a" * 64}"\n'
                'x-specloop-epic: big\n')
NEW_META = EARLIER_META.replace("x-specloop-", "x-gatedloop-")
EARLIER_BLOCK = ("# >>> specloop pre-commit (enforce-at-the-effect) >>>\n"
                 'if [ -n "${CLAUDECODE:-}" ]; then :; fi\n'
                 "# <<< specloop pre-commit (enforce-at-the-effect) <<<\n")
NEW_BLOCK = EARLIER_BLOCK.replace(">>> specloop", ">>> gatedloop").replace("<<< specloop", "<<< gatedloop")
SETTINGS = {"enabledPlugins": {"specloop@specloop": True},
            "permissions": {"ask": ["Skill(specloop:merge)"]}}
LEDGER = '{"gate": "unit", "change": "alpha"}\n'


def _env() -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["CLAUDECODE"] = "1"
    return env


def _git(cwd, *args) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                          text=True, env=_env()).stdout


def _migrate(root) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(GATES_SHIM), "migrate-name"], cwd=root,
                          capture_output=True, text=True, env=_env(), timeout=120)


def _project(root: Path, *, state_dir: str = ".specloop", meta: str = EARLIER_META,
             block: str = EARLIER_BLOCK, track_state: bool = True) -> None:
    """A repository on `main` holding one active change (`alpha`), one
    archived change carrying the earlier keys, a composed husky hook, project
    settings naming the earlier plugin, and a ledger under `state_dir`."""
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text('gatesVersion: 1\ngates:\n  ci: "true"\n')
    alpha = root / "openspec" / "changes" / "alpha"
    alpha.mkdir(parents=True)
    (alpha / "proposal.md").write_text("## Why\n\nBecause.\n")
    (alpha / ".openspec.yaml").write_text(meta)
    archived = root / "openspec" / "changes" / "archive" / "2026-01-01-old"
    archived.mkdir(parents=True)
    (archived / ".openspec.yaml").write_text(EARLIER_META)
    write_hook(root / ".husky" / "pre-commit", "#!/usr/bin/env sh\necho lint\n\n" + block)
    (root / ".claude").mkdir()
    (root / ".claude" / "settings.json").write_text(json.dumps(SETTINGS, indent=2) + "\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "project")
    runs = root / state_dir / "runs"
    runs.mkdir(parents=True)
    (runs / "alpha.jsonl").write_text(LEDGER)
    if track_state:
        _git(root, "add", "-A")
        _git(root, "commit", "-q", "-m", "ledger")


def _snapshot(root: Path) -> dict:
    """Every file under `root` but `.git/`, by path, with its bytes."""
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*"))
            if p.is_file() and ".git" not in p.relative_to(root).parts[:1]}


class TestMigratingAProject(unittest.TestCase):
    def test_a_project_moves_to_the_new_names_and_is_told_what_is_left(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _project(root)
            head = _git(root, "rev-parse", "HEAD")
            archived = (root / "openspec/changes/archive/2026-01-01-old/.openspec.yaml").read_bytes()
            settings = (root / ".claude" / "settings.json").read_bytes()

            r = _migrate(root)

            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            # The state directory, moved as a rename git records.
            self.assertFalse((root / ".specloop").exists())
            self.assertEqual((root / ".gatedloop" / "runs" / "alpha.jsonl").read_text(), LEDGER)
            status = _git(root, "status", "--porcelain")
            self.assertIn("R  .specloop/runs/alpha.jsonl -> .gatedloop/runs/alpha.jsonl", status)
            # Active metadata renamed, values and other lines kept; archive untouched.
            self.assertEqual((root / "openspec/changes/alpha/.openspec.yaml").read_text(), NEW_META)
            self.assertEqual(
                (root / "openspec/changes/archive/2026-01-01-old/.openspec.yaml").read_bytes(),
                archived)
            # The composed hook's block, renamed in place.
            self.assertEqual((root / ".husky" / "pre-commit").read_text(),
                             "#!/usr/bin/env sh\necho lint\n\n" + NEW_BLOCK)
            # What it will not do, each with its replacement.
            for old, new in (("specloop/ci", "gatedloop/ci"),
                             ("specloop@specloop", "gatedloop@gatedloop"),
                             ("Skill(specloop:merge)", "Skill(gatedloop:merge)")):
                with self.subTest(old):
                    self.assertIn(old, r.stdout)
                    self.assertIn(new, r.stdout)
            self.assertEqual((root / ".claude" / "settings.json").read_bytes(), settings)
            # Never a commit.
            self.assertEqual(_git(root, "rev-parse", "HEAD"), head)

    def test_an_untracked_state_directory_is_moved_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _project(root, track_state=False)

            r = _migrate(root)

            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertFalse((root / ".specloop").exists())
            self.assertEqual((root / ".gatedloop" / "runs" / "alpha.jsonl").read_text(), LEDGER)


class TestNothingToMigrate(unittest.TestCase):
    def test_a_second_run_changes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _project(root)
            first = _migrate(root)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            before, status = _snapshot(root), _git(root, "status", "--porcelain")

            second = _migrate(root)

            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertEqual(_snapshot(root), before)
            self.assertEqual(_git(root, "status", "--porcelain"), status)

    def test_a_project_on_the_new_names_is_left_as_it_is(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _project(root, state_dir=".gatedloop", meta=NEW_META, block=NEW_BLOCK)
            before = _snapshot(root)

            r = _migrate(root)

            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(_snapshot(root), before)
            self.assertEqual(_git(root, "status", "--porcelain"), "")


class TestBothStateDirectories(unittest.TestCase):
    def test_both_directories_are_refused_and_nothing_moves(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _project(root)
            (root / ".gatedloop" / "runs").mkdir(parents=True)
            (root / ".gatedloop" / "runs" / "beta.jsonl").write_text(LEDGER)
            before = _snapshot(root)

            r = _migrate(root)

            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn(".specloop", r.stderr)
            self.assertIn(".gatedloop", r.stderr)
            self.assertEqual(_snapshot(root), before)


if __name__ == "__main__":
    unittest.main()
