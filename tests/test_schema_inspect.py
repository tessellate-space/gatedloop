"""Tests for `gates schema inspect` (design D8: inspect a workflow schema
before trusting it).

Stdlib only, per `zero-dep-shim`. Covers the pure functions that turn an
already-parsed `schema.yaml` (plus already-read template text and this
project's own `.gates.yaml` gate bodies) into a deterministic report:
artifact DAG + cycle/unsatisfiable detection, `apply`-block presence (the
fact `tdd-apply` dispatch refuses on, design D4), and the tool-name-shaped
string scan (spike 1.3: curated list UNION a command-shaped heuristic over
code spans).

The IO orchestrator (`cmd_schema_inspect` — resolves a schema name via
`openspec schema which`, reads `schema.yaml` and template files off disk) is
deliberately NOT covered here, same rationale as `_schema_artifact_ids` vs
its `_safe` wrapper in test_conventions.py: a thin IO wrapper with nothing to
branch on. These tests must run with no `openspec` binary on PATH.

Run with:  python3 -m unittest discover -s tests
"""

import importlib.machinery
import importlib.util
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

_loader = importlib.machinery.SourceFileLoader("gates_shim_schema_inspect", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)


class TestScanToolNames(unittest.TestCase):
    def test_curated_name_matched_whole_word(self):
        self.assertEqual(gates.scan_tool_names("Run the suite with `pytest -q`."), {"pytest"})

    def test_curated_name_not_matched_as_substring(self):
        # "cargo" must not fire on "cargoship" — word-boundary match, not
        # substring (a hyphen, unlike a bare run-on, DOES count as a
        # boundary, which is why "cargo-culting" is a legitimate hit).
        self.assertNotIn("cargo", gates.scan_tool_names("Ship it: `cargoship --now`."))

    # schema-declared-flow D6 (issue #32): product nouns in prose were 100%
    # noise on a real project schema. A curated name counts only in code.
    def test_curated_name_in_prose_is_not_flagged(self):
        text = "The service stores sessions in postgres and signs users in through keycloak; traces go to langfuse."
        self.assertEqual(gates.scan_tool_names(text), set())

    def test_curated_name_in_inline_span_is_flagged(self):
        self.assertEqual(gates.scan_tool_names("Start it with `docker compose up`."), {"docker"})

    def test_curated_name_in_fence_is_flagged(self):
        self.assertIn("keycloak", gates.scan_tool_names("Seed it:\n```\nkeycloak import --dir realms\n```\n"))

    def test_command_shaped_heuristic_in_code_span(self):
        text = "Scaffold the suite: `foo-runner run` once per project."
        self.assertIn("foo-runner", gates.scan_tool_names(text))

    def test_command_shaped_heuristic_ignores_prose_outside_code_span(self):
        text = "Then run the reproduction again until it passes."
        self.assertEqual(gates.scan_tool_names(text), set())

    def test_meta_tools_denylisted_even_command_shaped(self):
        text = "`openspec validate` and `git add` are always available."
        self.assertEqual(gates.scan_tool_names(text), set())

    def test_fenced_code_block_scanned(self):
        text = "```bash\nmy-linter lint src/\n```"
        self.assertIn("my-linter", gates.scan_tool_names(text))

    def test_empty_text(self):
        self.assertEqual(gates.scan_tool_names(""), set())
        self.assertEqual(gates.scan_tool_names(None), set())


class TestSchemaArtifactsFromData(unittest.TestCase):
    def test_normalizes_defaults(self):
        data = {"artifacts": [{"id": "specs", "generates": "specs/**/*.md", "requires": []}]}
        artifacts = gates.schema_artifacts_from_data(data)
        self.assertEqual(artifacts, [{
            "id": "specs", "requires": [], "template": None, "instruction": "",
        }])

    def test_no_artifacts_key(self):
        self.assertEqual(gates.schema_artifacts_from_data({}), [])


class TestDetectRequiresIssues(unittest.TestCase):
    def test_clean_dag(self):
        artifacts = [
            {"id": "proposal", "requires": []},
            {"id": "specs", "requires": ["proposal"]},
            {"id": "tasks", "requires": ["specs"]},
        ]
        issues = gates.detect_requires_issues(artifacts)
        self.assertEqual(issues, {"unsatisfiable": [], "cycles": []})

    def test_unsatisfiable_requires(self):
        artifacts = [{"id": "tasks", "requires": ["nonexistent"]}]
        issues = gates.detect_requires_issues(artifacts)
        self.assertEqual(issues["unsatisfiable"], ["tasks requires undefined 'nonexistent'"])
        self.assertEqual(issues["cycles"], [])

    def test_direct_cycle(self):
        artifacts = [
            {"id": "a", "requires": ["b"]},
            {"id": "b", "requires": ["a"]},
        ]
        issues = gates.detect_requires_issues(artifacts)
        self.assertEqual(issues["unsatisfiable"], [])
        self.assertEqual(len(issues["cycles"]), 1)

    def test_self_cycle(self):
        artifacts = [{"id": "a", "requires": ["a"]}]
        issues = gates.detect_requires_issues(artifacts)
        self.assertEqual(len(issues["cycles"]), 1)


class TestSchemaApplyInfo(unittest.TestCase):
    def test_no_apply_block(self):
        info = gates.schema_apply_info({"name": "architecture"})
        self.assertEqual(info, {
            "has_apply": False, "implementable": False,
            "tracks": None, "requires": None, "instruction": "",
        })

    def test_apply_block_present(self):
        data = {"apply": {"requires": ["tasks"], "tracks": "tasks.md", "instruction": "go"}}
        info = gates.schema_apply_info(data)
        self.assertTrue(info["has_apply"])
        self.assertEqual(info["tracks"], "tasks.md")
        self.assertEqual(info["requires"], ["tasks"])
        self.assertEqual(info["instruction"], "go")

    # Design D2 (issue #32): an `apply:` key alone is not an implementation
    # phase. The adopter's `epic` schema had `apply:` with no `tracks` and was
    # routed to the per-task loop, where only prose stood between the agent
    # and an invented task list.
    def test_apply_without_tracks_is_not_implementable(self):
        data = {"apply": {"requires": ["epic"], "instruction": "an epic is never implemented"}}
        info = gates.schema_apply_info(data)
        self.assertTrue(info["has_apply"], "has_apply keeps its meaning: the key exists")
        self.assertFalse(info["implementable"])

    def test_apply_with_empty_tracks_is_not_implementable(self):
        for tracks in ("", "   ", None):
            with self.subTest(tracks=tracks):
                info = gates.schema_apply_info({"apply": {"tracks": tracks, "requires": ["x"]}})
                self.assertFalse(info["implementable"])

    def test_apply_with_tracks_is_implementable(self):
        info = gates.schema_apply_info({"apply": {"tracks": "tasks.md", "requires": ["tasks"]}})
        self.assertTrue(info["implementable"])

    def test_no_apply_is_not_implementable(self):
        self.assertFalse(gates.schema_apply_info({})["implementable"])


class TestCrossCheckGateBinding(unittest.TestCase):
    def test_bound_vs_unbound(self):
        gates_dict = {"ci": "npm test", "unit": "npm run unit"}
        result = gates.cross_check_gate_binding({"npm", "cucumber"}, gates_dict)
        self.assertEqual(result["bound"], ["npm"])
        self.assertEqual(result["unbound"], ["cucumber"])

    def test_no_gates_declared(self):
        result = gates.cross_check_gate_binding({"pytest"}, {})
        self.assertEqual(result, {"bound": [], "unbound": ["pytest"]})


class TestInspectSchemaData(unittest.TestCase):
    def test_apply_less_two_artifact_schema(self):
        # The exact shape design D4 verifies: explore -> adr, no apply block.
        data = {
            "name": "architecture",
            "artifacts": [
                {"id": "explore", "requires": []},
                {"id": "adr", "requires": ["explore"]},
            ],
        }
        report = gates.inspect_schema_data(data, {}, {})
        self.assertEqual(report["artifacts"], ["explore", "adr"])
        self.assertFalse(report["apply"]["has_apply"])
        self.assertEqual(report["requires_issues"], {"unsatisfiable": [], "cycles": []})
        self.assertEqual(report["flagged_tool_names"], {})

    def test_flags_coupling_and_reports_it_against_this_projects_gates(self):
        data = {
            "name": "behaviour-driven-like",
            "artifacts": [
                {"id": "specs", "requires": [], "instruction": "Run `cucumber run` over the specs."},
            ],
            "apply": {"tracks": "tasks.md", "requires": ["specs"]},
        }
        report = gates.inspect_schema_data(data, {}, {"ci": "npm test"})
        self.assertEqual(report["flagged_tool_names"], {"specs": ["cucumber"]})
        self.assertEqual(report["coupling"], {"bound": [], "unbound": ["cucumber"]})

    # schema-declared-flow D2 / 1.4: inspection must surface the #32 `epic`
    # shape before dispatch silently treats it as decision-terminal.
    def test_reports_implementable_and_flow(self):
        data = {"name": "acme-bugfix", "artifacts": [],
                "apply": {"tracks": "tasks.md", "requires": []},
                "gatedloop": {"flow": "regression-first"}}
        report = gates.inspect_schema_data(data, {}, {})
        self.assertTrue(report["apply"]["implementable"])
        self.assertEqual(report["flow"], "regression-first")
        self.assertEqual(report["warnings"], [])

    def test_undeclared_flow_reported_as_default(self):
        report = gates.inspect_schema_data({"name": "s", "apply": {"tracks": "t.md"}}, {}, {})
        self.assertEqual(report["flow"], "per-task")

    def test_warns_when_apply_has_no_tracks_and_says_omit_apply(self):
        data = {"name": "epic", "apply": {"requires": ["epic"], "instruction": "never implemented"}}
        report = gates.inspect_schema_data(data, {}, {})
        self.assertFalse(report["apply"]["implementable"])
        self.assertEqual(len(report["warnings"]), 1)
        self.assertIn("tracks", report["warnings"][0])
        self.assertIn("omit", report["warnings"][0].lower())

    def test_warns_on_flow_declared_on_non_implementable_schema(self):
        data = {"name": "odd", "gatedloop": {"flow": "regression-first"}}
        report = gates.inspect_schema_data(data, {}, {})
        self.assertTrue(any("regression-first" in w for w in report["warnings"]))

    def test_unknown_flow_is_a_warning_not_a_crash(self):
        # Inspection reports rather than blocks (workflow-packs D8); dispatch
        # is where an unknown flow fails loud.
        data = {"name": "x", "apply": {"tracks": "t.md"}, "gatedloop": {"flow": "yolo"}}
        report = gates.inspect_schema_data(data, {}, {})
        self.assertEqual(report["flow"], "yolo")
        self.assertTrue(any("yolo" in w for w in report["warnings"]))

    def test_human_output_prints_implementable_flow_and_omit_apply_rule(self):
        data = {"name": "epic", "artifacts": [{"id": "epic", "requires": []}],
                "apply": {"requires": ["epic"]}}
        text = "\n".join(gates.format_inspect_report(gates.inspect_schema_data(data, {}, {}), "epic"))
        self.assertIn("implementable: no", text)
        self.assertIn("flow: per-task", text)
        self.assertIn("omit", text.lower())

    def test_template_text_is_scanned_too(self):
        data = {"name": "s", "artifacts": [{"id": "tasks", "requires": [], "instruction": ""}]}
        report = gates.inspect_schema_data(data, {"tasks": "Use `pytest run` here."}, {})
        self.assertEqual(report["flagged_tool_names"], {"tasks": ["pytest"]})


if __name__ == "__main__":
    unittest.main()
