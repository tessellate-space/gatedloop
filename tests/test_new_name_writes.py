"""Every write uses the new names, with D2's one exception (change
`rename-to-gatedloop`, design D2; spec "The plugin is named gatedloop").

The regressions caught here:

- `marker publish` posting only `gatedloop/<gate>`, so a project whose branch
  protection still requires `specloop/ci` cannot merge mid-migration; or the
  two contexts saying different things about the same tree;
- a refusal still speaking the earlier name (`specloop: …`, `specloop/ci`),
  which sends an adopter looking for a context that is no longer the one
  being written;
- a re-attest that leaves the `x-specloop-approved-*` spelling beside the new
  one, so the file carries two approvals that can disagree;
- a composed git hook still written with the earlier markers, or a refreshed
  direct copy whose backup keeps the earlier `.specloop-prev` name.

That a `.specloop/`-only project keeps writing its ledger there is asserted
by `test_earlier_name_read.TestStateDirectory`, alongside the read.

Stdlib only, per `zero-dep-shim`. Every repository is a throwaway one; the
forge is the fake in `_forge_fixture`.

Run with:  python3 -m unittest discover -s tests
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _forge_fixture import Forge, NO_CI
from _hook_fixture import TEMPLATE, default_hook, init_repo, write_hook
from _merge_fixture import MergeRepo, combined, git

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

_loader = importlib.machinery.SourceFileLoader("gates_shim_new_name_writes", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)

MANIFEST_SELF = 'gatesVersion: 1\ngates:\n  ci: "true"\napproval:\n  plan: self\n'
PROPOSAL = ("## Why\n\nBecause a reason that is long enough to pass the validator's checks.\n\n"
            "## What Changes\n\n- A thing changes.\n")
EARLIER_KEYS = ("x-specloop-approved-by", "x-specloop-approved-at", "x-specloop-approved-sha")
NEW_KEYS = ("x-gatedloop-approved-by", "x-gatedloop-approved-at", "x-gatedloop-approved-sha")
EARLIER_COPY = ("#!/usr/bin/env bash\n"
                "# specloop git pre-commit hook (enforce-at-the-effect, design D1/D2).\n"
                "echo my-local-edit\nexit 0\n")


def _env() -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["CLAUDECODE"] = "1"
    env["OPEN_SPEC_INTERACTIVE"] = "0"
    return env


def _gates(root, *args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(GATES_SHIM), *args], cwd=root,
                          capture_output=True, text=True, env=_env(), timeout=120)


def _top_keys(text: str) -> list[str]:
    return [line.split(":", 1)[0] for line in text.splitlines()
            if line and not line[0].isspace() and ":" in line]


class TestStatusesUnderBothContexts(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.repo = MergeRepo(self.tmp)
        self.forge = Forge(self.tmp / "forge.json").install(self.repo.bin)
        self.repo.start_change(lane=False)
        self.repo.task_commit("feature.txt", "the thing\n", "add the thing")

    def tearDown(self):
        self._tmp.cleanup()

    def test_a_publish_posts_the_same_verdict_under_both_contexts(self):
        self.repo.prove_head()
        head = git(self.repo.primary, "rev-parse", "HEAD")
        tree = gates._normalize_tree(self.repo.primary, git(self.repo.primary, "rev-parse", "HEAD^{tree}"))

        r = self.repo.gates("marker", "publish", "ci", **NO_CI)

        self.assertEqual(r.returncode, 0, combined(r))
        for context in ("gatedloop/ci", "specloop/ci"):
            with self.subTest(context):
                status = self.forge.latest_status(head, context)
                self.assertIsNotNone(status, f"no {context} status on {head}")
                self.assertEqual(status["state"], "success")
                self.assertEqual(status["description"], f"tree {tree}")
        self.assertTrue(r.stdout.startswith("gatedloop: published gatedloop/ci"), r.stdout)

    def test_a_refusal_names_the_new_context_and_posts_nothing(self):
        # A head no gate ran on: nothing local vouches for its tree.
        (self.repo.primary / "feature.txt").write_text("changed\n")
        git(self.repo.primary, "commit", "-q", "-am", "unproven")
        head = git(self.repo.primary, "rev-parse", "HEAD")

        r = self.repo.gates("marker", "publish", "ci", **NO_CI)

        self.assertEqual(r.returncode, 1, combined(r))
        self.assertTrue(r.stderr.startswith("gatedloop: refusing to publish gatedloop/ci"), r.stderr)
        self.assertEqual(self.forge.statuses(head), [])


class TestApprovalKeysWritten(unittest.TestCase):
    def test_a_reattest_replaces_the_earlier_spelling(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            git(root, "init", "-q", "-b", "main")
            git(root, "config", "user.email", "t@example.com")
            git(root, "config", "user.name", "T")
            (root / ".gates.yaml").write_text(MANIFEST_SELF)
            change = root / "openspec" / "changes" / "my-change"
            change.mkdir(parents=True)
            (change / "proposal.md").write_text(PROPOSAL)
            (change / ".openspec.yaml").write_text(
                "schema: spec-driven\ncreated: 2026-10-22\n"
                + "".join(f'{key}: "Earlier"\n' for key in EARLIER_KEYS))

            r = _gates(root, "approval", "attest", "my-change", "--local")

            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            text = (change / ".openspec.yaml").read_text()
            keys = _top_keys(text)
            self.assertEqual(keys[:2], ["schema", "created"])
            for key in NEW_KEYS:
                self.assertEqual(keys.count(key), 1, text)
            for key in EARLIER_KEYS:
                self.assertNotIn(key, keys, text)
            self.assertNotIn("Earlier", text)


class TestHookWrites(unittest.TestCase):
    def test_a_composed_block_carries_the_new_markers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_repo(root)
            (root / ".husky").mkdir()
            write_hook(root / ".husky" / "pre-commit", "#!/usr/bin/env sh\necho lint\n")

            r = _gates(root, "hook", "install")

            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            body = (root / ".husky" / "pre-commit").read_text()
            self.assertIn("# >>> gatedloop pre-commit (enforce-at-the-effect) >>>", body)
            self.assertIn("# <<< gatedloop pre-commit (enforce-at-the-effect) <<<", body)
            self.assertNotIn("specloop", body)
            self.assertIn("echo lint", body)

    def test_a_refreshed_earlier_copy_is_backed_up_under_the_new_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_repo(root)
            hook = default_hook(root)
            write_hook(hook, EARLIER_COPY)

            r = _gates(root, "hook", "install")

            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(hook.read_bytes(), TEMPLATE.read_bytes())
            self.assertIn("# gatedloop git pre-commit hook", hook.read_text())
            backup = hook.with_name("pre-commit.gatedloop-prev")
            self.assertEqual(backup.read_text(), EARLIER_COPY)
            self.assertFalse(hook.with_name("pre-commit.specloop-prev").exists())


if __name__ == "__main__":
    unittest.main()
