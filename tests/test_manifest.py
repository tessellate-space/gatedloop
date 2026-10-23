"""Manifest-reading correctness tests for the `gates` shim.

Stdlib only, per the `zero-dep-shim` convention: `bin/gates` has no `.py`
suffix, so it is loaded by path through SourceFileLoader rather than imported.

Run with:  python3 -m unittest discover -s tests
"""

import importlib.machinery
import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"
TEMPLATE = REPO / "templates" / "gates.yaml.template"

_loader = importlib.machinery.SourceFileLoader("gates_shim", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)

PROSE = "Prefer composition: avoid deep inheritance"

BLOCK_LIST = f"""\
gatesVersion: 1
gates:
  ci: "true"
surfaces:
  - name: all
    match: "**"
    rules:
      - "{PROSE}"
"""

FLOW_LIST = f"""\
gatesVersion: 1
gates:
  ci: "true"
surfaces:
  - name: all
    match: "**"
    rules: ["{PROSE}"]
"""


class TestProseRulesWithColons(unittest.TestCase):
    """A prose rule containing a colon must stay a string.

    Inline prose is a documented alternative to rule-ids, and prose routinely
    contains colons. The stdlib fallback only runs when PyYAML is absent, so a
    regression here corrupts for adopters while working for the author.
    """

    def test_block_list_prose_rule_is_a_string(self):
        rules = gates._mini_yaml(BLOCK_LIST)["surfaces"][0]["rules"]
        self.assertEqual(rules, [PROSE])
        for item in rules:
            self.assertNotIsInstance(item, dict, "prose rule was reinterpreted as a mapping")

    def test_inline_flow_prose_rule_is_a_string(self):
        rules = gates._mini_yaml(FLOW_LIST)["surfaces"][0]["rules"]
        self.assertEqual(rules, [PROSE])

    def test_fallback_agrees_with_pyyaml(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not importable; fallback is the only parser here")
        for name, text in (("block", BLOCK_LIST), ("flow", FLOW_LIST)):
            with self.subTest(form=name):
                self.assertEqual(gates._mini_yaml(text), yaml.safe_load(text))

    def test_genuine_block_list_mapping_still_parses_as_mapping(self):
        """Guard against the naive fix: `- name: all` must remain a mapping."""
        surfaces = gates._mini_yaml(BLOCK_LIST)["surfaces"]
        self.assertIsInstance(surfaces[0], dict)
        self.assertEqual(surfaces[0]["name"], "all")
        self.assertEqual(surfaces[0]["match"], "**")


class TestShippedTemplate(unittest.TestCase):
    """`gates init` drops this file; `gates validate` must then pass."""

    def test_shipped_template_validates(self):
        parsed = gates._mini_yaml(TEMPLATE.read_text())
        with tempfile.TemporaryDirectory() as tmp:
            errs = gates._errors(parsed, Path(tmp))
        self.assertEqual(errs, [], f"shipped template does not validate: {errs}")


class TestManifestResolutionDropsLegacyNames(unittest.TestCase):
    """`remove-harness-compat`: the one-release `.harness.*` filename fallback
    is retired. `_find_manifest` must resolve only the current names, so a
    project carrying just `.harness.yaml` is treated the same as one with no
    manifest at all — loud, per `fail-loud-gates`, not a special-cased read.
    """

    def test_legacy_filename_alone_is_not_resolved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".harness.yaml").write_text(BLOCK_LIST)
            chosen, ignored = gates._find_manifest(root)
        self.assertIsNone(chosen, "a lone .harness.yaml must no longer resolve as a manifest")
        self.assertIsNone(ignored)

    def test_current_filename_still_resolves(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".gates.yaml").write_text(BLOCK_LIST)
            chosen, ignored = gates._find_manifest(root)
        self.assertEqual(chosen, root / ".gates.yaml")
        self.assertIsNone(ignored)


class TestVersionKey(unittest.TestCase):
    """`gatesVersion` is the only recognized version key.

    `remove-harness-compat`: the `harnessVersion` compatibility acceptance in
    `_errors` is retired along with the legacy filename fallback (task 2.1) —
    a manifest carrying only the old key is rejected exactly like any other
    manifest missing `gatesVersion`, loud, per `fail-loud-gates`.
    """

    def test_harness_version_key_no_longer_validates(self):
        legacy = BLOCK_LIST.replace("gatesVersion: 1", "harnessVersion: 1")
        parsed = gates._mini_yaml(legacy)
        with tempfile.TemporaryDirectory() as tmp:
            errs = gates._errors(parsed, Path(tmp))
        self.assertIn("gatesVersion must be 1", errs)

    def test_wrong_version_number_still_rejected(self):
        bad = BLOCK_LIST.replace("gatesVersion: 1", "gatesVersion: 2")
        parsed = gates._mini_yaml(bad)
        with tempfile.TemporaryDirectory() as tmp:
            errs = gates._errors(parsed, Path(tmp))
        self.assertIn("gatesVersion must be 1", errs)


class TestRuleIdHeadingResolution(unittest.TestCase):
    """F2 (review 2026-08-18) / design D4: rule-id resolution matches
    `### <id>` headings, not a substring search across the whole doc — a
    dangling id mentioned only in another section's prose must fail loud."""

    def _manifest(self, rule_id):
        return gates._mini_yaml(f"""\
gatesVersion: 1
gates:
  ci: "true"
surfaces:
  - name: all
    match: "**"
    rules:
      - {rule_id}
conventions:
  rules-doc: conventions.md
""")

    def test_dangling_id_mentioned_only_in_prose_fails(self):
        doc = (
            "### real-rule\n"
            "Applies to: proposal\n"
            "Rule: Do the thing.\n"
            "\n"
            "We used to have retired-rule but removed it.\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "conventions.md").write_text(doc)
            m = self._manifest("retired-rule")
            errs = gates._errors(m, root)
        self.assertTrue(
            any("retired-rule" in e and "not found" in e for e in errs),
            f"expected a dangling-id error naming 'retired-rule', got: {errs}",
        )

    def test_heading_without_sync_metadata_resolves(self):
        doc = "### prose-only-rule\nJust prose here, no Applies to:/Rule: lines.\n"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "conventions.md").write_text(doc)
            m = self._manifest("prose-only-rule")
            errs = gates._errors(m, root)
        self.assertEqual(errs, [], f"a heading with no sync metadata should still resolve: {errs}")

    def test_this_repos_own_manifest_still_validates(self):
        """Regression: heading-anchored resolution must not narrow what
        already resolved under the old substring check for the repo's real
        conventions doc."""
        manifest_path = REPO / ".gates.yaml"
        if not manifest_path.exists():
            self.skipTest("no .gates.yaml at repo root")
        m = gates._mini_yaml(manifest_path.read_text())
        errs = gates._errors(m, REPO)
        self.assertEqual(errs, [], f"repo's own manifest failed to validate: {errs}")


class TestIntegrationField(unittest.TestCase):
    """onboarding-asks-first §5: the declared integration process (how a
    change reaches main) is an optional manifest field — absence means
    today's behavior (local squash-merge), and `gates validate` must accept a
    manifest with or without it."""

    def _validate(self, text: str) -> list[str]:
        parsed = gates._mini_yaml(text)
        with tempfile.TemporaryDirectory() as tmp:
            return gates._errors(parsed, Path(tmp))

    def test_absent_integration_still_validates(self):
        self.assertEqual(self._validate(BLOCK_LIST), [])

    def test_local_squash_merge_validates(self):
        text = BLOCK_LIST + "integration:\n  mode: local-squash-merge\n"
        self.assertEqual(self._validate(text), [])

    def test_pull_request_with_required_approval_validates(self):
        text = (
            BLOCK_LIST
            + "integration:\n  mode: pull-request\n  requireApproval: true\n"
        )
        self.assertEqual(self._validate(text), [])

    def test_unknown_mode_is_rejected(self):
        text = BLOCK_LIST + "integration:\n  mode: rebase-and-pray\n"
        errs = self._validate(text)
        self.assertTrue(
            any("integration.mode" in e for e in errs),
            f"expected an integration.mode error, got: {errs}",
        )

    def test_non_boolean_require_approval_is_rejected(self):
        text = (
            BLOCK_LIST
            + 'integration:\n  mode: pull-request\n  requireApproval: "yes"\n'
        )
        errs = self._validate(text)
        self.assertTrue(
            any("integration.requireApproval" in e for e in errs),
            f"expected an integration.requireApproval error, got: {errs}",
        )


class TestAcceptanceMatchBlock(unittest.TestCase):
    """acceptance-gate design D5: an optional top-level `acceptance` block
    whose one key, `match`, is a glob naming where the project's acceptance
    scenarios live -- the only thing the shim knows about them."""

    def _validate(self, text: str) -> list[str]:
        parsed = gates._mini_yaml(text)
        with tempfile.TemporaryDirectory() as tmp:
            return gates._errors(parsed, Path(tmp))

    def test_declared_match_glob_validates(self):
        text = BLOCK_LIST + 'acceptance:\n  match: "features/**/*.feature"\n'
        self.assertEqual(self._validate(text), [])

    def test_block_without_match_fails_naming_match(self):
        text = BLOCK_LIST + 'acceptance:\n  dir: "features"\n'
        errs = self._validate(text)
        self.assertTrue(
            any("acceptance" in e and "match" in e for e in errs),
            f"expected an error naming acceptance.match, got: {errs}",
        )

    def test_extra_key_fails(self):
        text = (
            BLOCK_LIST
            + 'acceptance:\n  match: "features/**/*.feature"\n  format: gherkin\n'
        )
        errs = self._validate(text)
        self.assertTrue(
            any("acceptance" in e and "format" in e for e in errs),
            f"expected an error naming the unknown key, got: {errs}",
        )


class TestBraceGlobValidation(unittest.TestCase):
    """expand-brace-globs design D3: `gates validate` runs the same
    expander (`_expand_braces`) over every surface's `match`, collecting
    every failure — naming surface + pattern — rather than stopping at the
    first, matching this file's existing all-errors-at-once style."""

    MANIFEST = """\
gatesVersion: 1
gates:
  ci: "true"
surfaces:
  - name: good
    match: "{bin,tests}/**"
  - name: bad-one
    match: "{bin,tests/**"
  - name: bad-two
    match: "{}/**"
"""

    def _validate(self, text: str) -> list[str]:
        parsed = gates._mini_yaml(text)
        with tempfile.TemporaryDirectory() as tmp:
            return gates._errors(parsed, Path(tmp))

    def test_valid_brace_pattern_validates(self):
        errs = self._validate(
            "gatesVersion: 1\ngates:\n  ci: \"true\"\nsurfaces:\n"
            "  - name: good\n    match: \"{bin,tests}/**\"\n"
        )
        self.assertEqual(errs, [])

    def test_every_unexpandable_surface_is_reported_at_once(self):
        errs = self._validate(self.MANIFEST)
        self.assertTrue(
            any("bad-one" in e and "{bin,tests/**" in e for e in errs),
            f"expected an error naming surface 'bad-one' and its pattern, got: {errs}",
        )
        self.assertTrue(
            any("bad-two" in e and "{}/**" in e for e in errs),
            f"expected an error naming surface 'bad-two' and its pattern, got: {errs}",
        )
        self.assertFalse(
            any("good" in e for e in errs),
            f"the valid surface 'good' should not have been reported, got: {errs}",
        )


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _scratch_git_repo(tmp):
    """A throwaway git repo with locally-scoped identity (matches the fixture
    already used by `tests/test_scaffold_gate.py` / `tests/test_session_brief.py`)."""
    root = Path(tmp)
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")
    return root


class TestLoadManifestDropsLegacyWarnings(unittest.TestCase):
    """`remove-harness-compat` task 2.3: `load_manifest` no longer has a
    "both exist" branch (there is nothing left for the current filename to
    be preferred over) or a legacy-filename/legacy-key deprecation warning —
    a legacy-only project now gets the same "no manifest found" / invalid-
    manifest failure as any other malformed setup, not a special warning.
    """

    def test_lone_legacy_filename_reports_no_manifest_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _scratch_git_repo(tmp)
            (root / ".harness.yaml").write_text(BLOCK_LIST)
            r = subprocess.run(
                [str(GATES_SHIM), "validate"], cwd=root, capture_output=True, text=True,
            )
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("no manifest found", r.stderr)
        self.assertNotIn("is deprecated", r.stderr)

    def test_harness_version_key_gets_no_special_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _scratch_git_repo(tmp)
            legacy = BLOCK_LIST.replace("gatesVersion: 1", "harnessVersion: 1")
            (root / ".gates.yaml").write_text(legacy)
            r = subprocess.run(
                [str(GATES_SHIM), "validate"], cwd=root, capture_output=True, text=True,
            )
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("gatesVersion must be 1", r.stdout + r.stderr)
        self.assertNotIn("is deprecated", r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
