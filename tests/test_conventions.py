"""Tests for the conventions generator (`gates conventions sync`).

Stdlib only, per `zero-dep-shim`. Covers the pure, schema-agnostic functions
that turn `docs/conventions.md`-shaped prose into `openspec/config.yaml`'s
`rules:` block (design D4) — the branching Python this change adds, per the
same rationale as `test_manifest.py`: prompts and docs stay untested, but a
defect in text-parsing/text-surgery code corrupts silently for everyone.

`_schema_artifact_ids(_safe)` (the functions that shell out to `openspec`)
are deliberately NOT covered here — thin IO wrappers with nothing to branch
on — and these tests must run with no `openspec` binary on PATH. Precondition
gating (`_conventions_generation_inputs`, `_conventions_drift`) IS covered:
it must resolve to "inactive" without ever reaching that subprocess call.

Run with:  python3 -m unittest discover -s tests
"""

import importlib.machinery
import importlib.util
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

_loader = importlib.machinery.SourceFileLoader("gates_shim_conventions", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)


class TestParseConventionsDoc(unittest.TestCase):
    def test_single_section_with_metadata(self):
        doc = (
            "### my-rule\n"
            "Applies to: proposal\n"
            "Rule: Do the thing.\n"
            "\n"
            "Longer prose explaining why, for the human reader.\n"
        )
        sections = gates.parse_conventions_doc(doc)
        self.assertEqual(
            sections,
            {"my-rule": {"applies_to": ["proposal"], "rule": "Do the thing."}},
        )

    def test_comma_separated_applies_to(self):
        doc = "### r\nApplies to: proposal, tasks\nRule: Do it.\n"
        sections = gates.parse_conventions_doc(doc)
        self.assertEqual(sections["r"]["applies_to"], ["proposal", "tasks"])

    def test_code_only_rule_still_parses(self):
        """`code` is a normal applies-to value here — filtering it out of the
        artifact-keyed emission is `build_rules_by_artifact`'s job, not the
        parser's."""
        doc = "### r\nApplies to: code\nRule: Never do the bad thing.\n"
        sections = gates.parse_conventions_doc(doc)
        self.assertEqual(sections["r"]["applies_to"], ["code"])

    def test_section_missing_rule_line_is_omitted(self):
        doc = "### incomplete\nApplies to: proposal\n\nJust prose, no Rule: line.\n"
        sections = gates.parse_conventions_doc(doc)
        self.assertNotIn("incomplete", sections)

    def test_section_missing_applies_to_is_omitted(self):
        doc = "### incomplete\nRule: Do it.\n"
        sections = gates.parse_conventions_doc(doc)
        self.assertNotIn("incomplete", sections)

    def test_multiple_sections_preserve_order_and_dont_bleed(self):
        doc = (
            "### a\nApplies to: proposal\nRule: A.\n\n"
            "### b\nApplies to: tasks\nRule: B.\n"
        )
        sections = gates.parse_conventions_doc(doc)
        self.assertEqual(list(sections.keys()), ["a", "b"])
        self.assertEqual(sections["a"]["rule"], "A.")
        self.assertEqual(sections["b"]["rule"], "B.")


class TestBuildRulesByArtifact(unittest.TestCase):
    def test_code_only_rules_are_dropped(self):
        sections = {"r": {"applies_to": ["code"], "rule": "X."}}
        by_artifact = gates.build_rules_by_artifact(sections, ["proposal", "tasks"])
        self.assertEqual(by_artifact, {})

    def test_rule_grouped_under_every_named_artifact(self):
        sections = {"r": {"applies_to": ["proposal", "tasks"], "rule": "X."}}
        by_artifact = gates.build_rules_by_artifact(sections, ["proposal", "specs", "tasks"])
        self.assertEqual(by_artifact, {"proposal": ["X."], "tasks": ["X."]})

    def test_id_not_in_active_schema_is_dropped(self):
        """Task 1.4a: a schema switch (e.g. to `minimalist`, which has no
        `proposal`) must silently narrow the emission, not error or leak a
        stale artifact id."""
        sections = {"r": {"applies_to": ["proposal"], "rule": "X."}}
        by_artifact = gates.build_rules_by_artifact(sections, ["specs", "tasks"])
        self.assertEqual(by_artifact, {})

    def test_schema_agnostic_same_source_different_schema(self):
        sections = {
            "a": {"applies_to": ["proposal"], "rule": "A."},
            "b": {"applies_to": ["adr"], "rule": "B."},
        }
        spec_driven = gates.build_rules_by_artifact(sections, ["proposal", "specs", "design", "tasks"])
        self.assertEqual(spec_driven, {"proposal": ["A."]})
        intent_driven = gates.build_rules_by_artifact(sections, ["proposal", "specs", "design", "adr", "tasks"])
        self.assertEqual(intent_driven, {"proposal": ["A."], "adr": ["B."]})


class TestExtractRulesBlock(unittest.TestCase):
    def test_absent_is_empty_string(self):
        self.assertEqual(gates.extract_rules_block("schema: spec-driven\n"), "")

    def test_extracts_exactly_what_sync_would_have_written(self):
        """Round-trip: whatever `sync_rules_block` writes, `extract_rules_block`
        must read back byte-for-byte — that symmetry is the drift check."""
        original = "schema: spec-driven\n"
        new_block = 'rules:\n  proposal:\n    - "Do X."\n'
        written = gates.sync_rules_block(original, new_block)
        self.assertEqual(gates.extract_rules_block(written), new_block)

    def test_trims_trailing_blank_separator_before_next_key(self):
        text = 'rules:\n  proposal:\n    - "X."\n\nstore: foo\n'
        self.assertEqual(gates.extract_rules_block(text), 'rules:\n  proposal:\n    - "X."\n')

    def test_does_not_pick_up_context_block_scalar(self):
        text = (
            "schema: spec-driven\n\n"
            "context: |\n"
            "  prose mentioning rules: inline, but indented\n"
        )
        self.assertEqual(gates.extract_rules_block(text), "")


class TestConventionsGenerationInputs(unittest.TestCase):
    """Precondition gating for both `cmd_conventions_sync` and the drift
    check — every case here must resolve to `None` (inactive, not an error)
    without shelling out to `openspec`, since these tests run with no
    `openspec` binary guaranteed on PATH."""

    def _manifest(self, rules_doc):
        return {"conventions": {"rules-doc": rules_doc}} if rules_doc else {}

    def test_none_when_no_rules_doc_declared(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(gates._conventions_generation_inputs({}, Path(tmp)))

    def test_none_when_rules_doc_missing_on_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            m = self._manifest("docs/conventions.md")
            self.assertIsNone(gates._conventions_generation_inputs(m, Path(tmp)))

    def test_none_when_openspec_config_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / "docs" / "conventions.md").write_text("# empty\n")
            m = self._manifest("docs/conventions.md")
            self.assertIsNone(gates._conventions_generation_inputs(m, root))

    def test_none_when_config_has_no_schema_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / "docs" / "conventions.md").write_text("# empty\n")
            (root / "openspec").mkdir()
            (root / "openspec" / "config.yaml").write_text("context: hello\n")
            m = self._manifest("docs/conventions.md")
            self.assertIsNone(gates._conventions_generation_inputs(m, root))

    def test_drift_is_none_when_generation_is_inactive(self):
        """`_conventions_drift` must not fail loud for a project that simply
        isn't using OpenSpec-artifact rule generation."""
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(gates._conventions_drift({}, Path(tmp)))

    def test_resolves_when_all_preconditions_met(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / "docs" / "conventions.md").write_text("# empty\n")
            (root / "openspec").mkdir()
            (root / "openspec" / "config.yaml").write_text("schema: spec-driven\n")
            m = self._manifest("docs/conventions.md")
            result = gates._conventions_generation_inputs(m, root)
            self.assertIsNotNone(result)
            rules_doc, doc_path, config_path, schema_name = result
            self.assertEqual(rules_doc, "docs/conventions.md")
            self.assertEqual(schema_name, "spec-driven")


class TestCatalogArtifactSets(unittest.TestCase):
    """Task 1.4a: artifact ids are not a fixed set — they come from the
    active schema, and the shipped catalog's sets genuinely differ (measured
    2026-08-18, recorded in design.md D4/1.4a):

    - `minimalist` has only `specs`/`tasks` — no `proposal` at all.
    - `event-driven` adds `asyncapi`, `event-storming`, `event-modeling`.
    - `intent-driven` and `spec-driven-with-adr` add `adr`.

    A generator that hard-coded `proposal`/`specs`/`design`/`tasks` would
    either drop rules silently for these schemas or emit a key OpenSpec
    would warn about as unknown. These pin the adaptive behaviour instead.
    """

    SOURCE = {
        "rejection-test": {"applies_to": ["proposal"], "rule": "Apply the rejection test."},
        "adr-rationale": {"applies_to": ["adr"], "rule": "Record the rejected alternatives."},
        "event-naming": {"applies_to": ["asyncapi", "event-modeling"], "rule": "Name events past-tense."},
    }

    def test_minimalist_drops_the_proposal_scoped_rule(self):
        minimalist_ids = ["specs", "tasks"]
        by_artifact = gates.build_rules_by_artifact(self.SOURCE, minimalist_ids)
        self.assertEqual(by_artifact, {})

    def test_event_driven_picks_up_event_scoped_rules(self):
        event_driven_ids = ["proposal", "specs", "design", "tasks", "asyncapi", "event-storming", "event-modeling"]
        by_artifact = gates.build_rules_by_artifact(self.SOURCE, event_driven_ids)
        self.assertEqual(
            by_artifact,
            {
                "proposal": ["Apply the rejection test."],
                "asyncapi": ["Name events past-tense."],
                "event-modeling": ["Name events past-tense."],
            },
        )

    def test_intent_driven_picks_up_adr_scoped_rule(self):
        intent_driven_ids = ["proposal", "specs", "design", "adr", "tasks"]
        by_artifact = gates.build_rules_by_artifact(self.SOURCE, intent_driven_ids)
        self.assertEqual(
            by_artifact,
            {"proposal": ["Apply the rejection test."], "adr": ["Record the rejected alternatives."]},
        )

    def test_switching_schema_changes_the_render_with_no_code_change(self):
        spec_driven_block = gates.render_rules_block(
            gates.build_rules_by_artifact(self.SOURCE, ["proposal", "specs", "design", "tasks"]),
            ["proposal", "specs", "design", "tasks"],
        )
        minimalist_block = gates.render_rules_block(
            gates.build_rules_by_artifact(self.SOURCE, ["specs", "tasks"]),
            ["specs", "tasks"],
        )
        self.assertNotEqual(spec_driven_block, minimalist_block)
        self.assertEqual(minimalist_block, "")


class TestRenderRulesBlock(unittest.TestCase):
    def test_empty_when_nothing_to_emit(self):
        self.assertEqual(gates.render_rules_block({}, ["proposal", "tasks"]), "")

    def test_canonical_shape(self):
        by_artifact = {"proposal": ["Do X."], "tasks": ["Do Y.", "Do Z."]}
        block = gates.render_rules_block(by_artifact, ["proposal", "specs", "tasks"])
        self.assertEqual(
            block,
            'rules:\n  proposal:\n    - "Do X."\n  tasks:\n    - "Do Y."\n    - "Do Z."\n',
        )

    def test_artifact_order_follows_schema_not_dict_order(self):
        by_artifact = {"tasks": ["Y."], "proposal": ["X."]}
        block = gates.render_rules_block(by_artifact, ["proposal", "tasks"])
        self.assertLess(block.index("proposal"), block.index("tasks"))

    def test_quotes_embedded_double_quotes(self):
        block = gates.render_rules_block({"proposal": ['Say "hi".']}, ["proposal"])
        self.assertIn('"Say \\"hi\\"."', block)


class TestSyncRulesBlock(unittest.TestCase):
    def test_appends_when_absent(self):
        original = "schema: spec-driven\n"
        new_block = 'rules:\n  proposal:\n    - "Do X."\n'
        updated = gates.sync_rules_block(original, new_block)
        self.assertEqual(updated, "schema: spec-driven\n\nrules:\n  proposal:\n    - \"Do X.\"\n")

    def test_append_is_noop_when_nothing_to_add_and_none_present(self):
        original = "schema: spec-driven\n"
        self.assertEqual(gates.sync_rules_block(original, ""), original)

    def test_replaces_existing_block(self):
        original = 'schema: spec-driven\n\nrules:\n  proposal:\n    - "Old."\n'
        new_block = 'rules:\n  proposal:\n    - "New."\n'
        updated = gates.sync_rules_block(original, new_block)
        self.assertEqual(updated, 'schema: spec-driven\n\nrules:\n  proposal:\n    - "New."\n')

    def test_removes_block_when_new_is_empty(self):
        original = 'schema: spec-driven\n\nrules:\n  proposal:\n    - "Old."\n'
        updated = gates.sync_rules_block(original, "")
        self.assertEqual(updated, "schema: spec-driven\n")

    def test_never_touches_context_block_scalar(self):
        """The `context: |` block-scalar body is indented, exactly like a
        `rules:` block would be — this guards against the naive fix that
        matches on indentation alone rather than tracking the owning key."""
        original = (
            "schema: spec-driven\n\n"
            "context: |\n"
            "  Some prose.\n\n"
            "  More prose, including a line that happens to start with rules:\n"
            "  not a real key, just prose.\n"
        )
        new_block = 'rules:\n  proposal:\n    - "New."\n'
        updated = gates.sync_rules_block(original, new_block)
        self.assertIn("Some prose.", updated)
        self.assertIn("More prose, including a line that happens to start with rules:", updated)
        self.assertTrue(updated.rstrip("\n").endswith('- "New."'))

    def test_replacing_is_idempotent(self):
        original = "schema: spec-driven\n"
        new_block = 'rules:\n  proposal:\n    - "X."\n'
        once = gates.sync_rules_block(original, new_block)
        twice = gates.sync_rules_block(once, new_block)
        self.assertEqual(once, twice)


if __name__ == "__main__":
    unittest.main()
