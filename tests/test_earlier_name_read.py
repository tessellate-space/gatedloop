"""Read-both, loud, for one release (change `rename-to-gatedloop`, design D2;
spec "The earlier name is read loudly for one release").

Through 0.7.x the shim reads every renamed identifier under its new spelling
and, where that is absent, under the earlier `specloop` one, and the first
earlier spelling a command reads prints one stderr line naming `gates
migrate-name`. The regressions caught here, one per identifier:

- the state directory: an unmigrated project's ledger not found (every gate
  then reads as never run), a second directory written beside it (a split
  ledger), a fresh project still given `.specloop/`, or both directories
  silently accepted;
- the approval and epic keys: an unmigrated plan reading as unapproved, or an
  epic as having no children;
- the status contexts: a commit vouched for under `specloop/ci` refused by
  `marker check-remote`, or an earlier context outranking a newer verdict;
- the rule ids: a surface naming `specloop.test-quality` refused by
  `gates validate`, or listed under the earlier id;
- the hook markers: a composed hook or direct copy written by an earlier
  release read as a foreign hook;
- the schema flow block: a bugfix-style schema declaring `specloop:` routed
  to the default loop;
- a ledger committed under `.specloop/runs/`: missed by the readers that take
  it from a ref or a tree, or hashed into a normalized tree.

The record-branch matcher has no earlier spelling to read: `gates
record-merged` skips every head branch containing `/`, whatever its prefix.

Each test uses the old name on purpose. Stdlib only, per `zero-dep-shim`.
Every repository is a throwaway one; the forge is the fake in
`_forge_fixture`.

Run with:  python3 -m unittest discover -s tests
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _forge_fixture import Forge, NO_CI
from _hook_fixture import default_hook, init_repo, write_hook
from _merge_fixture import MergeRepo, combined, git

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

_loader = importlib.machinery.SourceFileLoader("gates_shim_earlier_name", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)

CHANGE = "add-thing"
WARNING_TAIL = "run gates migrate-name (old names stop working in 0.8.0)"
MANIFEST = 'gatesVersion: 1\ngates:\n  ci: "true"\napproval:\n  plan: self\n'
PROPOSAL = ("## Why\n\nBecause a reason that is long enough to pass the validator's checks.\n\n"
            "## What Changes\n\n- A thing changes.\n")

# The blocks and headers an earlier release wrote into a git hook.
EARLIER_BLOCK = ("# >>> specloop pre-commit (enforce-at-the-effect) >>>\n"
                 'if [ -n "${CLAUDECODE:-}" ]; then :; fi\n'
                 "# <<< specloop pre-commit (enforce-at-the-effect) <<<\n")
EARLIER_COPY = ("#!/usr/bin/env bash\n"
                "# specloop git pre-commit hook (enforce-at-the-effect, design D1/D2).\n"
                "exit 0\n")


def _env() -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["CLAUDECODE"] = "1"
    env["OPEN_SPEC_INTERACTIVE"] = "0"
    return env


def _git(cwd, *args) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                          text=True, env=_env()).stdout.strip()


def _gates(root, *args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(GATES_SHIM), *args], cwd=root,
                          capture_output=True, text=True, env=_env(), timeout=120)


def _warnings(stderr: str) -> list[str]:
    return [line for line in stderr.splitlines() if WARNING_TAIL in line]


def _project(root: Path, *, state_dirs=(), metadata: str = "") -> Path:
    """A repository on branch `add-thing`, the change planned on `main`, with
    the named state directories present (each holding a ledger row) and
    `metadata` appended to the change's `.openspec.yaml`."""
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(MANIFEST)
    change = root / "openspec" / "changes" / CHANGE
    change.mkdir(parents=True)
    (change / "proposal.md").write_text(PROPOSAL)
    (change / "tasks.md").write_text("## 1. Do it\n\n- [ ] 1.1 Add the thing\n")
    (change / ".openspec.yaml").write_text("schema: spec-driven\n" + metadata)
    for name in state_dirs:
        runs = root / name / "runs"
        runs.mkdir(parents=True)
        (runs / f"{CHANGE}.jsonl").write_text(json.dumps({"gate": "unit", "change": CHANGE}) + "\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "plan")
    _git(root, "checkout", "-q", "-b", CHANGE)
    return change


def _rows(path: Path) -> int:
    return len(path.read_text().splitlines()) if path.exists() else 0


class TestStateDirectory(unittest.TestCase):
    def test_a_project_not_yet_migrated_keeps_working_and_warns_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            change = _project(root, state_dirs=(".specloop",))
            sha = _gates(root, "approval", "sha", CHANGE).stdout.strip()
            (change / ".openspec.yaml").write_text(
                "schema: spec-driven\n"
                'x-specloop-approved-by: "T <t@example.com>"\n'
                'x-specloop-approved-at: "2026-10-22T09:00:00+00:00"\n'
                f'x-specloop-approved-sha: "{sha}"\n')
            _git(root, "commit", "-q", "-am", "approved")
            _git(root, "checkout", "-q", "main")
            _git(root, "merge", "-q", "--ff-only", CHANGE)
            _git(root, "checkout", "-q", CHANGE)

            for args in (("run", "ci"), ("approval", "check", CHANGE)):
                with self.subTest(args):
                    r = _gates(root, *args)

                    self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                    warnings = _warnings(r.stderr)
                    self.assertEqual(len(warnings), 1, r.stderr)
                    self.assertTrue(warnings[0].startswith("gatedloop: read the earlier name '"),
                                    warnings[0])
            self.assertEqual(_rows(root / ".specloop" / "runs" / f"{CHANGE}.jsonl"), 2)
            self.assertFalse((root / ".gatedloop").exists())

    def test_a_fresh_project_writes_the_new_directory_without_a_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _project(root)

            r = _gates(root, "run", "ci")

            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(_warnings(r.stderr), [])
            self.assertEqual(_rows(root / ".gatedloop" / "runs" / f"{CHANGE}.jsonl"), 1)
            self.assertFalse((root / ".specloop").exists())

    def test_a_migrated_project_reads_the_new_directory_without_a_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _project(root, state_dirs=(".gatedloop",))

            r = _gates(root, "run", "ci")

            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(_warnings(r.stderr), [])
            self.assertEqual(_rows(root / ".gatedloop" / "runs" / f"{CHANGE}.jsonl"), 2)

    def test_both_state_directories_are_refused_naming_the_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _project(root, state_dirs=(".specloop", ".gatedloop"))

            r = _gates(root, "run", "ci")

            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("gates migrate-name", r.stderr)
            self.assertIn(".specloop", r.stderr)
            self.assertIn(".gatedloop", r.stderr)
            for name in (".specloop", ".gatedloop"):
                self.assertEqual(_rows(root / name / "runs" / f"{CHANGE}.jsonl"), 1, name)


class TestChangeMetadata(unittest.TestCase):
    def test_approval_keys_are_read_under_either_spelling_the_new_one_first(self):
        new = {"x-gatedloop-approved-by": "New", "x-gatedloop-approved-at": "now",
               "x-gatedloop-approved-sha": "abc"}
        earlier = {"x-specloop-approved-by": "Earlier", "x-specloop-approved-at": "then",
                   "x-specloop-approved-sha": "def"}
        cases = (
            ("new", new, ("New", "now", "abc")),
            ("earlier", earlier, ("Earlier", "then", "def")),
            ("both", {**earlier, **new}, ("New", "now", "abc")),
            ("field by field", {**earlier, "x-gatedloop-approved-by": "New"},
             ("New", "then", "def")),
        )
        for name, data, expected in cases:
            with self.subTest(name):
                self.assertEqual(gates._approval_meta(data), expected)

    def test_the_epic_key_is_read_under_either_spelling_the_new_one_first(self):
        cases = (
            ("new", "x-gatedloop-epic: big\n", "big"),
            ("earlier", "x-specloop-epic: big\n", "big"),
            ("both", "x-specloop-epic: old\nx-gatedloop-epic: big\n", "big"),
        )
        for name, text, expected in cases:
            with self.subTest(name), tempfile.TemporaryDirectory() as tmp:
                change = Path(tmp)
                (change / ".openspec.yaml").write_text("schema: spec-driven\n" + text)
                self.assertEqual(gates._read_epic(change), expected)


class TestStatusContexts(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.repo = MergeRepo(self.tmp)
        self.repo.start_change(lane=False)
        self.repo.task_commit("feature.txt", "the thing\n", "add the thing")
        self.head = git(self.repo.primary, "rev-parse", "HEAD")
        self.tree = gates._normalize_tree(
            self.repo.primary, git(self.repo.primary, "rev-parse", "HEAD^{tree}"))

    def tearDown(self):
        self._tmp.cleanup()

    def _check(self, statuses):
        with tempfile.TemporaryDirectory() as state:
            forge = Forge(Path(state) / "forge.json").install(self.repo.bin)
            for context, state_name in statuses:
                forge.add_status(self.head, context, state_name, f"tree {self.tree}")
            return self.repo.gates("marker", "check-remote", "ci", self.head, **NO_CI)

    def test_a_status_under_either_context_verifies_and_only_the_earlier_warns(self):
        for context, warned in (("gatedloop/ci", 0), ("specloop/ci", 1)):
            with self.subTest(context):
                r = self._check([(context, "success")])

                self.assertEqual(r.returncode, 0, combined(r))
                self.assertEqual(len(_warnings(r.stderr)), warned, r.stderr)

    def test_the_new_context_outranks_the_earlier_one(self):
        r = self._check([("specloop/ci", "success"), ("gatedloop/ci", "failure")])

        self.assertEqual(r.returncode, 1, combined(r))
        self.assertIn("gatedloop/ci", combined(r))


class TestRuleIds(unittest.TestCase):
    def _repo(self, root: Path, rule: str) -> None:
        init_repo(root)
        (root / "rules.md").write_text("### house-style\nApplies to: code\nRule: Be tidy.\n")
        (root / ".gates.yaml").write_text(
            'gatesVersion: 1\ngates:\n  ci: "true"\nconventions:\n  rules-doc: rules.md\n'
            f'surfaces:\n  - name: all\n    match: "**"\n    rules:\n      - house-style\n'
            f"      - {rule}\n")

    def test_a_surface_naming_the_built_in_rule_resolves_under_either_id(self):
        for rule, warned in (("gatedloop.test-quality", 0), ("specloop.test-quality", 1)):
            with self.subTest(rule), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self._repo(root, rule)

                validated = _gates(root, "validate")
                listed = _gates(root, "rules", "--changed", "a.txt")

                self.assertEqual(validated.returncode, 0, validated.stdout + validated.stderr)
                self.assertEqual(listed.returncode, 0, listed.stdout + listed.stderr)
                self.assertEqual(listed.stdout.count("gatedloop.test-quality"), 1, listed.stdout)
                self.assertNotIn("specloop.test-quality", listed.stdout)
                self.assertIn("house-style", listed.stdout)
                self.assertEqual(len(_warnings(listed.stderr)), warned, listed.stderr)


class TestHookMarkers(unittest.TestCase):
    def test_hooks_an_earlier_release_wrote_are_still_ours(self):
        cases = (
            ("composed, earlier markers", "#!/bin/sh\necho lint\n" + EARLIER_BLOCK, "wired"),
            ("composed, new markers",
             "#!/bin/sh\necho lint\n" + gates._composed_hook_snippet(), "wired"),
            ("direct copy, earlier header", EARLIER_COPY, "stale-copy"),
        )
        for name, body, expected in cases:
            with self.subTest(name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                init_repo(root)
                write_hook(default_hook(root), body)

                self.assertEqual(gates._hook_state(root), expected)


class TestSchemaFlow(unittest.TestCase):
    def test_the_flow_block_is_read_under_either_name_the_new_one_first(self):
        cases = (
            ("new", "gatedloop:\n  flow: regression-first\n", "regression-first"),
            ("earlier", "specloop:\n  flow: regression-first\n", "regression-first"),
            ("both", "specloop:\n  flow: regression-first\ngatedloop:\n  flow: per-task\n",
             "per-task"),
        )
        for name, text, expected in cases:
            with self.subTest(name):
                # The dependency-free reader dispatch uses, and a full parse
                # of the same text, must agree.
                self.assertEqual(gates.schema_flow(gates.read_dispatch_blocks(text)), expected)
                self.assertEqual(gates.schema_flow(gates._parse_yaml_text(text)), expected)

    def test_the_schema_flow_adoption_item_sees_a_schema_declaring_the_earlier_block(self):
        facts = {"schemas": ["name: a\nspecloop:\n  flow: regression-first\n"]}
        detector = {"kind": "schema-key", "key": "gatedloop"}

        self.assertTrue(gates.adoption_detector_acted(detector, facts))


class TestCommittedLedger(unittest.TestCase):
    def _commit_ledger(self, root: Path, state_dir: str, row: dict) -> str:
        runs = root / state_dir / "runs"
        runs.mkdir(parents=True, exist_ok=True)
        (runs / f"{CHANGE}.jsonl").write_text(json.dumps(row) + "\n")
        _git(root, "add", "-A")
        _git(root, "commit", "-q", "-m", f"ledger under {state_dir}")
        return _git(root, "rev-parse", "HEAD^{tree}")

    def test_a_ledger_committed_under_either_directory_is_read_from_a_ref_and_a_tree(self):
        row = {"gate": gates.ACCEPTANCE_EVENT, "change": CHANGE, "tree": "t"}
        for state_dir in (".gatedloop", ".specloop"):
            with self.subTest(state_dir), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                init_repo(root)
                (root / "a.txt").write_text("a\n")
                _git(root, "add", "-A")
                _git(root, "commit", "-q", "-m", "base")
                _git(root, "checkout", "-q", "-b", "other")
                tree = self._commit_ledger(root, state_dir, row)
                _git(root, "checkout", "-q", "main")

                self.assertEqual(gates._change_ledger_rows(root, CHANGE, "refs/heads/other"), [row])
                self.assertEqual(gates._acceptance_rows_for(root, tree, CHANGE), [row])

    def test_a_normalized_tree_ignores_a_ledger_under_either_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_repo(root)
            (root / "a.txt").write_text("a\n")
            _git(root, "add", "-A")
            _git(root, "commit", "-q", "-m", "base")
            bare = _git(root, "rev-parse", "HEAD^{tree}")
            trees = [self._commit_ledger(root, d, {"gate": "unit"}) for d in (".gatedloop", ".specloop")]

            normalized = {gates._normalize_tree(root, t) for t in [bare, *trees]}

            self.assertEqual(len(normalized), 1, normalized)


if __name__ == "__main__":
    unittest.main()
