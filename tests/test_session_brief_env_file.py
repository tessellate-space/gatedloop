"""The session brief's fallback PATH entry (openspec change `gates-on-path`,
design D1, issue #40): with `CLAUDE_ENV_FILE` and `CLAUDE_PLUGIN_ROOT` set
and the plugin's `bin/gates` executable, `hooks/session-brief.sh` appends one
line putting `<plugin root>/bin` at the END of PATH -- once, never truncating
the file -- and writes nothing when either variable is absent.

The real hook runs against a throwaway project directory and a fake plugin
root whose `bin/gates` is a stub, so nothing here depends on the host's
plugin install, its PATH, or an OpenSpec CLI.

Stdlib only. Run with:  python3 -m unittest discover -s tests
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _merge_fixture import clean_env

REPO = Path(__file__).resolve().parent.parent
SESSION_BRIEF = REPO / "hooks" / "session-brief.sh"


def _fake_plugin_root(base: Path, executable: bool = True) -> Path:
    root = base / "plugin"
    (root / "bin").mkdir(parents=True)
    stub = root / "bin" / "gates"
    stub.write_text("#!/bin/sh\necho stub-gates\n")
    stub.chmod(0o755 if executable else 0o644)
    return root


def _run_brief(project: Path, plugin_root: Path | None, env_file: Path | None) -> str:
    extra = {
        "CLAUDE_PROJECT_DIR": str(project),
        "CLAUDE_PLUGIN_ROOT": str(plugin_root) if plugin_root else None,
        "CLAUDE_ENV_FILE": str(env_file) if env_file else None,
    }
    proc = subprocess.run(
        ["bash", str(SESSION_BRIEF)], cwd=project, env=clean_env(extra),
        capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def _expected_line(plugin_root: Path) -> str:
    return f'export PATH="$PATH:{plugin_root}/bin"'


class TestEnvFileFallback(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self.project = self.base / "project"
        self.project.mkdir()
        self.plugin = _fake_plugin_root(self.base)
        self.env_file = self.base / "claude-env.sh"

    def tearDown(self):
        self._tmp.cleanup()

    def test_fresh_empty_file_gets_exactly_one_line(self):
        # Regression: the hook never writes the fallback, so `gates` stays
        # unresolvable in a session whose bin/ injection did not happen (#40).
        self.env_file.write_text("")
        _run_brief(self.project, self.plugin, self.env_file)
        self.assertEqual(self.env_file.read_text(), _expected_line(self.plugin) + "\n")

    def test_missing_file_is_created_with_one_line(self):
        _run_brief(self.project, self.plugin, self.env_file)
        self.assertEqual(self.env_file.read_text(), _expected_line(self.plugin) + "\n")

    def test_second_run_does_not_duplicate_the_line(self):
        # Regression: an unconditional append stacks a line per SessionStart
        # (resume, clear, compact) in the same session.
        _run_brief(self.project, self.plugin, self.env_file)
        _run_brief(self.project, self.plugin, self.env_file)
        lines = self.env_file.read_text().splitlines()
        self.assertEqual(lines, [_expected_line(self.plugin)])

    def test_other_writers_lines_are_kept(self):
        # Regression: writing with `>` instead of `>>` truncates another
        # hook's preamble (direnv, another plugin) in the same file.
        self.env_file.write_text("export FOO=bar\n")
        _run_brief(self.project, self.plugin, self.env_file)
        self.assertEqual(
            self.env_file.read_text().splitlines(),
            ["export FOO=bar", _expected_line(self.plugin)],
        )

    def test_the_line_appends_so_an_earlier_gates_still_wins(self):
        # Regression: a prepended entry would shadow the normal bin/ injection
        # or an adopter's own wrapper. Sourcing the written file must leave a
        # `gates` already on PATH first, and add the plugin's as a fallback.
        _run_brief(self.project, self.plugin, self.env_file)
        own = self.base / "own-bin"
        own.mkdir()
        (own / "gates").write_text("#!/bin/sh\necho own-gates\n")
        (own / "gates").chmod(0o755)
        script = f'. "{self.env_file}"; command -v gates'
        first = subprocess.run(
            ["bash", "-c", script], env=clean_env({"PATH": f"{own}:/usr/bin:/bin"}),
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(first.stdout.strip(), str(own / "gates"))
        fallback = subprocess.run(
            ["bash", "-c", script], env=clean_env({"PATH": "/usr/bin:/bin"}),
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(fallback.stdout.strip(), str(self.plugin / "bin" / "gates"))

    def test_no_file_written_without_plugin_root(self):
        # Regression: a fallback built from an empty root would put `/bin`
        # on PATH and claim it as the plugin's.
        _run_brief(self.project, None, self.env_file)
        self.assertFalse(self.env_file.exists())

    def test_no_file_written_when_plugin_gates_is_not_executable(self):
        plugin = _fake_plugin_root(self.base / "other", executable=False)
        _run_brief(self.project, plugin, self.env_file)
        self.assertFalse(self.env_file.exists())

    def test_nothing_written_without_env_file(self):
        before = sorted(p.relative_to(self.base) for p in self.base.rglob("*"))
        _run_brief(self.project, self.plugin, None)
        after = sorted(p.relative_to(self.base) for p in self.base.rglob("*"))
        self.assertEqual(before, after)

    def test_brief_output_is_unchanged_by_the_fallback(self):
        # Regression: the fallback leaks into stdout and corrupts the
        # SessionStart JSON, or changes the brief's text.
        without = _run_brief(self.project, self.plugin, None)
        with_file = _run_brief(self.project, self.plugin, self.env_file)
        self.assertEqual(with_file, without)
        json.loads(with_file)


if __name__ == "__main__":
    sys.exit(unittest.main())
