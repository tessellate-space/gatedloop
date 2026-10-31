"""Tests for the `gates doctor` preflight (streamline-onboarding §4, design D3/D4).

Stdlib only, per `zero-dep-shim`: the shim has no `.py` suffix, so it is loaded
by path through SourceFileLoader rather than imported. PyYAML is optional here
too — the doctor checks are exercised as pure functions on primitives, so they
run identically whether or not PyYAML is installed.

Run with:  python3 -m unittest discover -s tests
"""

import argparse
import contextlib
import importlib.machinery
import importlib.util
import io
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _merge_fixture import clean_env

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

_loader = importlib.machinery.SourceFileLoader("gates_shim", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)


class TestTestedVersionConstant(unittest.TestCase):
    """§4.1: the tested OpenSpec CLI version is a constant the shim can read."""

    def test_constant_is_a_version_string(self):
        v = gates.OPENSPEC_MAX_TESTED
        self.assertIsInstance(v, str)
        self.assertTrue(v.strip(), "OPENSPEC_MAX_TESTED must be non-empty")
        self.assertRegex(v, r"^\d+\.\d+\.\d+", "should look like a semver version")

    def test_expected_gates_version_is_one(self):
        self.assertEqual(gates.EXPECTED_GATES_VERSION, 1)


class TestParseOpenspecVersion(unittest.TestCase):
    """§4.2: `openspec --version` output → a semver string, or None."""

    def test_bare_version(self):
        self.assertEqual(gates._parse_openspec_version("1.8.0"), "1.8.0")

    def test_version_embedded_in_a_line(self):
        self.assertEqual(gates._parse_openspec_version("openspec v1.8.0\n"), "1.8.0")

    def test_prerelease_suffix_kept(self):
        self.assertEqual(gates._parse_openspec_version("2.0.0-rc.1"), "2.0.0-rc.1")

    def test_none_and_empty(self):
        self.assertIsNone(gates._parse_openspec_version(None))
        self.assertIsNone(gates._parse_openspec_version(""))
        self.assertIsNone(gates._parse_openspec_version("no version here"))


def _levels_by_title(checks):
    return {title: level for level, title, _detail in checks}


def _detail_by_title(checks):
    return {title: detail for _level, title, detail in checks}


class TestDoctorChecks(unittest.TestCase):
    """§4.2/§4.4/D3/D4: the pure diagnostic logic, on primitives."""

    def test_all_checks_are_advisory_never_blocking(self):
        # Design D4: doctor warns, never fails. No check is ever a blocking error.
        for installed in (None, gates.OPENSPEC_MAX_TESTED, "9.9.9"):
            for gv in (None, gates.EXPECTED_GATES_VERSION, 99):
                for pr in (None, "/some/plugin/root"):
                    for level, _title, _detail in gates.doctor_checks(installed, gv, pr):
                        self.assertIn(level, ("ok", "warn"))

    def test_matching_openspec_version_is_ok(self):
        checks = gates.doctor_checks(gates.OPENSPEC_MAX_TESTED, 1, "/p")
        self.assertEqual(_levels_by_title(checks)["openspec-version"], "ok")

    def test_mismatched_openspec_version_warns_naming_both(self):
        installed = "9.9.9"
        checks = gates.doctor_checks(installed, 1, "/p")
        levels = _levels_by_title(checks)
        details = _detail_by_title(checks)
        self.assertEqual(levels["openspec-version"], "warn")
        self.assertIn(installed, details["openspec-version"])
        self.assertIn(gates.OPENSPEC_MAX_TESTED, details["openspec-version"])

    def test_missing_openspec_cli_warns(self):
        checks = gates.doctor_checks(None, 1, "/p")
        self.assertEqual(_levels_by_title(checks)["openspec-cli"], "warn")

    def test_no_manifest_is_ok_not_a_warning(self):
        # Doctor runs as gates-init step 0, before any .gates.yaml exists.
        checks = gates.doctor_checks(gates.OPENSPEC_MAX_TESTED, None, "/p")
        self.assertEqual(_levels_by_title(checks)["gates-version"], "ok")

    def test_stale_gates_version_warns(self):
        checks = gates.doctor_checks(gates.OPENSPEC_MAX_TESTED, 99, "/p")
        self.assertEqual(_levels_by_title(checks)["gates-version"], "warn")



def _exe(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\nexit 0\n")
    path.chmod(0o755)
    return path


class TestShimLocationRow(unittest.TestCase):
    """gates-on-path D3 (issue #40): `plugin-registered` decided on
    CLAUDE_PLUGIN_ROOT, which the Bash tool's environment never carries, so it
    warned in every working session. The row is now `shim-location`: where
    the running shim lives, worked out from its own path, and never a warning.
    The third positional primitive is that path; None omits the row."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name).resolve()

    def tearDown(self):
        self._tmp.cleanup()

    def row(self, shim_path):
        checks = gates.doctor_checks(gates.OPENSPEC_MAX_TESTED, 1, str(shim_path))
        self.assertNotIn("plugin-registered", _levels_by_title(checks))
        return _levels_by_title(checks)["shim-location"], _detail_by_title(checks)["shim-location"]

    def test_installed_plugin_copy_names_the_version(self):
        # Regression: the installed copy is reported as "elsewhere", losing
        # the one fact (which version runs) a bug report needs.
        shim = _exe(self.base / "cfg" / "plugins" / "cache" / "gatedloop" / "gatedloop"
                    / "0.5.1" / "bin" / "gates")
        level, detail = self.row(shim)
        self.assertEqual(level, "ok")
        self.assertIn("installed plugin", detail)
        self.assertIn("0.5.1", detail)

    def test_checkout_is_named_as_a_checkout(self):
        # Regression: a shim run from a working copy is mistaken for the
        # installed plugin, hiding why a fix "isn't picked up".
        root = self.base / "gatedloop"
        (root / ".git").mkdir(parents=True)
        (root / ".claude-plugin").mkdir()
        (root / ".claude-plugin" / "plugin.json").write_text("{}\n")
        shim = _exe(root / "bin" / "gates")
        level, detail = self.row(shim)
        self.assertEqual(level, "ok")
        self.assertIn("checkout", detail)
        self.assertNotIn("installed plugin", detail)

    @unittest.skipUnless((REPO / ".git").exists(),
                         "the tree is an export with no .git (go-public tree), not a checkout")
    def test_this_repository_is_a_checkout(self):
        # A linked worktree's `.git` is a file, not a directory.
        level, detail = self.row(REPO / "bin" / "gates")
        self.assertEqual(level, "ok")
        self.assertIn("checkout", detail)

    def test_another_path_is_named(self):
        shim = _exe(self.base / "somewhere" / "bin" / "gates")
        level, detail = self.row(shim)
        self.assertEqual(level, "ok")
        self.assertIn(str(shim), detail)
        self.assertNotIn("installed plugin", detail)
        self.assertNotIn("checkout", detail)

    def test_keeps_the_config_dir_pointer_without_a_warning(self):
        shim = _exe(self.base / "somewhere" / "bin" / "gates")
        level, detail = self.row(shim)
        self.assertEqual(level, "ok")
        self.assertIn("CLAUDE_CONFIG_DIR", detail)
        self.assertIn("Bash tool", detail)

    def test_omitted_when_not_given(self):
        checks = gates.doctor_checks(gates.OPENSPEC_MAX_TESTED, 1, None)
        self.assertNotIn("shim-location", _levels_by_title(checks))
        self.assertNotIn("plugin-registered", _levels_by_title(checks))


class TestDoctorWithoutPluginRoot(unittest.TestCase):
    """The scenario "run from the Bash tool of a working session": `gates`
    resolves and CLAUDE_PLUGIN_ROOT is unset. The real shim runs with PATH set
    explicitly (this shim symlinked onto it), never inherited."""

    def test_no_registration_warning_and_shim_location_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "gates").symlink_to(GATES_SHIM)
            proc = subprocess.run(
                [sys.executable, str(GATES_SHIM), "doctor"], cwd=REPO,
                env=clean_env({"PATH": f"{tmp}:/usr/bin:/bin", "CLAUDE_PLUGIN_ROOT": None}),
                capture_output=True, text=True, timeout=120,
            )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = proc.stdout
        self.assertNotIn("plugin-registered", out)
        self.assertIn("[ok  ] shim-location:", out)
        for line in out.splitlines():
            if "[WARN]" in line:
                self.assertNotIn("CLAUDE_PLUGIN_ROOT", line)
                self.assertNotIn("registered", line)


class TestDoctorPyYAMLRow(unittest.TestCase):
    """schema-declared-flow D5 (issue #32): PyYAML was an undeclared,
    unchecked dependency -- doctor reported all green on a machine where
    schema inspection could not run, and the only hint was a plain pip install
    that a PEP 668 Python refuses."""

    def test_importable_is_ok(self):
        checks = gates.doctor_checks(gates.OPENSPEC_MAX_TESTED, 1, "/p", yaml_importable=True)
        self.assertEqual(_levels_by_title(checks)["pyyaml"], "ok")

    def test_absent_warns_naming_what_needs_it_and_a_pep668_hint(self):
        checks = gates.doctor_checks(gates.OPENSPEC_MAX_TESTED, 1, "/p", yaml_importable=False)
        self.assertEqual(_levels_by_title(checks)["pyyaml"], "warn")
        detail = _detail_by_title(checks)["pyyaml"]
        self.assertIn("gates schema inspect", detail)
        self.assertIn("gates schema dispatch", detail)
        self.assertIn("--user", detail)
        self.assertIn("PEP 668", detail)

    def test_doctor_exits_zero_and_warns_with_pyyaml_hidden(self):
        buf = io.StringIO()
        with mock.patch.dict(sys.modules, {"yaml": None}), contextlib.redirect_stdout(buf):
            rc = gates.cmd_doctor(argparse.Namespace())
        self.assertEqual(rc, 0)
        self.assertRegex(buf.getvalue(), r"\[WARN\] pyyaml:")


class TestDoctorCommandExitCode(unittest.TestCase):
    """§4.5 (scripted check of the shim's exit code): a version mismatch must
    warn and still exit 0 — it never blocks onboarding or fails validation."""

    def test_mismatch_exits_zero_and_warns(self):
        original = gates.OPENSPEC_MAX_TESTED
        gates.OPENSPEC_MAX_TESTED = "0.0.1-test-sentinel"  # force a mismatch
        try:
            buf = io.StringIO()
            # The installed CLI is faked: the real `openspec --version` is a
            # host fact, and on a loaded machine it can outrun its timeout and
            # read as "not found" -- never the mismatch this test is about.
            with mock.patch.object(gates, "_installed_openspec_version", return_value="1.0.0"), \
                    contextlib.redirect_stdout(buf):
                rc = gates.cmd_doctor(argparse.Namespace())
            out = buf.getvalue()
        finally:
            gates.OPENSPEC_MAX_TESTED = original
        self.assertEqual(rc, 0, "doctor must not block/fail on a version mismatch")
        self.assertIn("0.0.1-test-sentinel", out)


class TestTestedVersionIsPinned(unittest.TestCase):
    """openspec-1-14-compat D6: gatedloop is verified against OpenSpec 1.14.3,
    and this repository's CI installs exactly the version doctor names --
    otherwise CI would prove the suite on a CLI the constant does not claim."""

    def test_openspec_1_14_3_is_the_tested_contract(self):
        # 0.5.0 warned every adopter on 1.14.3 that it was untested.
        checks = gates.doctor_checks("1.14.3", 1, "/p")
        self.assertEqual(_levels_by_title(checks)["openspec-version"], "ok")

    def test_every_workflow_pin_matches_the_tested_version(self):
        workflow = (REPO / ".github" / "workflows" / "gatedloop.yml").read_text()
        pins = re.findall(r"@fission-ai/openspec@([0-9][0-9A-Za-z.+-]*)", workflow)
        self.assertTrue(pins, "the workflow must pin the OpenSpec CLI version")
        self.assertEqual(set(pins), {gates.OPENSPEC_MAX_TESTED}, pins)


if __name__ == "__main__":
    unittest.main()
