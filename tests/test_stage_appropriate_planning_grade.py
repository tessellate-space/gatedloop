"""Stage-appropriate planning-grade validation (design D4 of
`worktree-native-loop`, tasks 4.1-4.2). A deliberately proposal-only backlog
entry -- no `specs/` content yet, no `skip_specs: true` -- is a legitimate
stage, not a change refused for lacking artifacts it never claimed to have.
`gates discipline check-commit` now classifies each staged change directory:

- delta content (any file under `specs/`, or `skip_specs: true`) -> full
  `openspec validate <change> --type change`, exactly as before this design.
- proposal-only -> `openspec status --change <name> --json` must succeed;
  the allow message names the stage.
- status unreadable -> denied, naming the failed read.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

MANIFEST = 'gatesVersion: 1\ngates:\n  ci: "true"\n'

FAKE_OPENSPEC_STATUS_OK = """\
#!/usr/bin/env bash
if [ "$1" = "status" ]; then
  echo '{"changeName":"'"$3"'","isComplete":false}'
  exit 0
fi
if [ "$1" = "validate" ]; then
  echo '{"items":[{"id":"'"$2"'","type":"change","valid":true,"issues":[]}]}'
  exit 0
fi
exit 1
"""

FAKE_OPENSPEC_STATUS_FAILS = """\
#!/usr/bin/env bash
if [ "$1" = "status" ]; then
  echo "openspec: unreadable status" >&2
  exit 1
fi
if [ "$1" = "validate" ]; then
  echo '{"items":[{"id":"'"$2"'","type":"change","valid":true,"issues":[]}]}'
  exit 0
fi
exit 1
"""

FAKE_OPENSPEC_VALIDATE_FAILS = """\
#!/usr/bin/env bash
if [ "$1" = "validate" ]; then
  echo "validation failed: missing tasks.md" >&2
  exit 1
fi
if [ "$1" = "status" ]; then
  echo '{"changeName":"'"$3"'","isComplete":false}'
  exit 0
fi
exit 1
"""

# Fails loud if `validate` is ever called for a change name it doesn't
# expect (used to prove proposal-only changes never hit `validate`, and
# fully-delta changes never hit `status`).
FAKE_OPENSPEC_FAILS_ON_WRONG_CALL = """\
#!/usr/bin/env bash
if [ "$1" = "validate" ]; then
  case "$3" in
    proposal-only-change) echo "validate must never run for a proposal-only change" >&2; exit 1 ;;
  esac
  echo '{"items":[{"id":"'"$2"'","type":"change","valid":true,"issues":[]}]}'
  exit 0
fi
if [ "$1" = "status" ]; then
  case "$3" in
    with-delta) echo "status must never run for a change with delta content" >&2; exit 1 ;;
  esac
  echo '{"changeName":"'"$3"'","isComplete":false}'
  exit 0
fi
exit 1
"""


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _run_gates(root, *args, path=None):
    env = dict(os.environ)
    if path is not None:
        env["PATH"] = path
    return subprocess.run(
        [sys.executable, str(GATES_SHIM), *args], cwd=root, capture_output=True, text=True, env=env,
    )


def _install_fake_openspec(bindir: Path, script: str) -> str:
    bindir.mkdir(parents=True, exist_ok=True)
    exe = bindir / "openspec"
    exe.write_text(script)
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}"


def _init_repo(root: Path) -> None:
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(MANIFEST)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")


def _write_tree(root: Path) -> str:
    return subprocess.run(
        ["git", "write-tree"], cwd=root, capture_output=True, text=True,
    ).stdout.strip()


def _proposal_only_change(root: Path, name: str) -> Path:
    d = root / "openspec" / "changes" / name
    d.mkdir(parents=True)
    (d / "proposal.md").write_text("plan\n")
    (d / ".openspec.yaml").write_text("schema: spec-driven\ncreated: 2026-08-19\n")
    return d


def _change_with_delta(root: Path, name: str) -> Path:
    d = root / "openspec" / "changes" / name
    d.mkdir(parents=True)
    (d / "proposal.md").write_text("plan\n")
    (d / "specs").mkdir()
    (d / "specs" / "spec.md").write_text("### Requirement\ndelta\n")
    return d


def _skip_specs_change(root: Path, name: str) -> Path:
    d = root / "openspec" / "changes" / name
    d.mkdir(parents=True)
    (d / "proposal.md").write_text("plan\n")
    (d / ".openspec.yaml").write_text("schema: spec-driven\nskip_specs: true\n")
    return d


class TestProposalOnlyClass(unittest.TestCase):
    def test_proposal_only_change_committed_alone_is_allowed_via_status(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as bin_tmp:
            root = Path(tmp)
            _init_repo(root)
            _proposal_only_change(root, "backlog-idea")
            _git(root, "add", "-A")
            path = _install_fake_openspec(Path(bin_tmp), FAKE_OPENSPEC_STATUS_OK)

            r = _run_gates(root, "discipline", "check-commit", _write_tree(root), path=path)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("proposal-only", r.stdout + r.stderr)
            self.assertIn("backlog-idea", r.stdout + r.stderr)

    def test_proposal_only_change_never_calls_validate(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as bin_tmp:
            root = Path(tmp)
            _init_repo(root)
            _proposal_only_change(root, "proposal-only-change")
            _git(root, "add", "-A")
            path = _install_fake_openspec(Path(bin_tmp), FAKE_OPENSPEC_FAILS_ON_WRONG_CALL)

            r = _run_gates(root, "discipline", "check-commit", _write_tree(root), path=path)
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_status_unreadable_denies_naming_the_failed_read(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as bin_tmp:
            root = Path(tmp)
            _init_repo(root)
            _proposal_only_change(root, "backlog-idea")
            _git(root, "add", "-A")
            path = _install_fake_openspec(Path(bin_tmp), FAKE_OPENSPEC_STATUS_FAILS)

            r = _run_gates(root, "discipline", "check-commit", _write_tree(root), path=path)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("status", r.stderr)
            self.assertIn("backlog-idea", r.stderr)


class TestDeltaContentClass(unittest.TestCase):
    def test_specs_content_triggers_full_validation(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as bin_tmp:
            root = Path(tmp)
            _init_repo(root)
            _change_with_delta(root, "with-delta")
            _git(root, "add", "-A")
            path = _install_fake_openspec(Path(bin_tmp), FAKE_OPENSPEC_FAILS_ON_WRONG_CALL)

            r = _run_gates(root, "discipline", "check-commit", _write_tree(root), path=path)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("with-delta", r.stdout + r.stderr)

    def test_skip_specs_true_also_triggers_full_validation(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as bin_tmp:
            root = Path(tmp)
            _init_repo(root)
            _skip_specs_change(root, "with-delta")
            _git(root, "add", "-A")
            path = _install_fake_openspec(Path(bin_tmp), FAKE_OPENSPEC_FAILS_ON_WRONG_CALL)

            r = _run_gates(root, "discipline", "check-commit", _write_tree(root), path=path)
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_full_validation_failure_denies_naming_the_failure(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as bin_tmp:
            root = Path(tmp)
            _init_repo(root)
            _change_with_delta(root, "with-delta")
            _git(root, "add", "-A")
            path = _install_fake_openspec(Path(bin_tmp), FAKE_OPENSPEC_VALIDATE_FAILS)

            r = _run_gates(root, "discipline", "check-commit", _write_tree(root), path=path)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("openspec validate", r.stderr)


class TestMalformedOpenspecYamlIsUnreadable(unittest.TestCase):
    """A `.openspec.yaml` that exists but fails to parse is missing evidence
    about `skip_specs`, never inferred as absent (fail-loud-gates) -- the
    commit is denied naming the parse failure, the same "never a silent
    pass on missing evidence" the status-unreadable case already applies."""

    def test_malformed_yaml_denies_naming_the_change(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as bin_tmp:
            root = Path(tmp)
            _init_repo(root)
            d = root / "openspec" / "changes" / "broken-yaml"
            d.mkdir(parents=True)
            (d / "proposal.md").write_text("plan\n")
            # A DIRECTORY at the `.openspec.yaml` path: `Path.exists()`
            # reports it present, but reading it raises `IsADirectoryError`
            # -- a parse failure `_mini_yaml`'s permissive line-based parser
            # can't paper over the way it would a merely-odd YAML string.
            (d / ".openspec.yaml").mkdir()
            _git(root, "add", "-A")
            path = _install_fake_openspec(Path(bin_tmp), FAKE_OPENSPEC_FAILS_ON_WRONG_CALL)

            r = _run_gates(root, "discipline", "check-commit", _write_tree(root), path=path)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("broken-yaml", r.stderr)
            self.assertIn("could not be determined", r.stderr)


class TestMixedMultiChangeStaging(unittest.TestCase):
    def test_one_proposal_only_and_one_with_delta_both_validate_at_their_own_stage(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as bin_tmp:
            root = Path(tmp)
            _init_repo(root)
            _proposal_only_change(root, "proposal-only-change")
            _change_with_delta(root, "with-delta")
            _git(root, "add", "-A")
            path = _install_fake_openspec(Path(bin_tmp), FAKE_OPENSPEC_FAILS_ON_WRONG_CALL)

            r = _run_gates(root, "discipline", "check-commit", _write_tree(root), path=path)
            self.assertEqual(r.returncode, 0, r.stderr)
            out = r.stdout + r.stderr
            self.assertIn("proposal-only-change", out)
            self.assertIn("with-delta", out)


class TestProposalGrowsIntoADelta(unittest.TestCase):
    """End-to-end (task 4.2): the same change committed twice as it grows.
    First as a deliberately proposal-only backlog entry -- committed alone
    with no filler delta spec -- then again once real delta content is
    added, exercising full validation the second time."""

    def test_committed_proposal_only_then_committed_again_with_delta(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as bin_tmp:
            root = Path(tmp)
            _init_repo(root)
            path = _install_fake_openspec(Path(bin_tmp), FAKE_OPENSPEC_FAILS_ON_WRONG_CALL)

            # Scaffold, as `openspec new change` would: proposal.md + a
            # scaffold check first (design D4 of unblock-parallel-planning),
            # both on the merge target.
            scaffold = _run_gates(root, "discipline", "check-propose", "--scaffold")
            self.assertEqual(scaffold.returncode, 0, scaffold.stderr)
            change_dir = _proposal_only_change(root, "grows-up")
            _git(root, "add", "-A")

            r1 = _run_gates(root, "discipline", "check-commit", _write_tree(root), path=path)
            self.assertEqual(r1.returncode, 0, r1.stderr)
            self.assertIn("proposal-only", r1.stdout + r1.stderr)
            _git(root, "commit", "-m", "propose grows-up (backlog, no deltas yet)")

            # No filler delta spec was ever required to get here. Now the
            # change grows a real delta -- the SAME change re-commits at
            # full-validation grade, no longer proposal-only.
            (change_dir / "specs").mkdir()
            (change_dir / "specs" / "spec.md").write_text("### Requirement\ndelta\n")
            _git(root, "add", "-A")

            r2 = _run_gates(root, "discipline", "check-commit", _write_tree(root), path=path)
            self.assertEqual(r2.returncode, 0, r2.stderr)
            self.assertIn("grows-up", r2.stdout + r2.stderr)
            self.assertNotIn("proposal-only", r2.stdout + r2.stderr)


if __name__ == "__main__":
    unittest.main()
