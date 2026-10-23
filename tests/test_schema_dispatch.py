"""Tests for schema dispatch (schema-declared-flow, issue #32).

The route `tdd-apply` takes for a change is decided from the schema's declared
flow (`gatedloop.flow`) and from whether its `apply` block tracks anything —
never from the schema's name (design D1/D2). Stdlib only, per `zero-dep-shim`.

Run with:  python3 -m unittest discover -s tests
"""

import importlib.machinery
import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

_loader = importlib.machinery.SourceFileLoader("gates_shim_schema_dispatch", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)


class TestSchemaFlow(unittest.TestCase):
    """Design D1: the flow is a declared property, closed list, fail loud."""

    def test_undeclared_flow_defaults_to_per_task(self):
        self.assertEqual(gates.schema_flow({"name": "spec-driven"}), "per-task")
        self.assertEqual(gates.schema_flow({"gatedloop": {}}), "per-task")

    def test_declared_regression_first_is_read(self):
        data = {"name": "acme-bugfix", "gatedloop": {"flow": "regression-first"}}
        self.assertEqual(gates.schema_flow(data), "regression-first")

    def test_unknown_flow_fails_loud_naming_value_and_known_flows(self):
        # The silent fall-through #32 reported must not come back as a
        # silent fallback to per-task on a typo.
        with self.assertRaises(gates.SchemaDispatchError) as cm:
            gates.schema_flow({"gatedloop": {"flow": "regresion-first"}})
        msg = str(cm.exception)
        self.assertIn("regresion-first", msg)
        for known in ("per-task", "regression-first"):
            self.assertIn(known, msg)

    def test_non_mapping_gatedloop_block_fails_loud(self):
        with self.assertRaises(gates.SchemaDispatchError):
            gates.schema_flow({"gatedloop": "regression-first"})


TRACKED_APPLY = {"requires": ["tasks"], "tracks": "tasks.md", "instruction": "go"}
# Issue #32's `epic`: an apply block with requires and prose, no tracks.
EPIC_APPLY = {"requires": ["epic"], "instruction": "An epic is never implemented.\n"}


class TestDispatchRoute(unittest.TestCase):
    """Design D2's table, and the name-blindness #32 asked for."""

    def test_no_apply_refuses(self):
        r = gates.dispatch_route({"name": "architecture"})
        self.assertEqual(r["route"], "refuse")
        self.assertFalse(r["has_apply"])
        self.assertFalse(r["implementable"])

    def test_apply_without_tracks_refuses_like_no_apply(self):
        r = gates.dispatch_route({"name": "epic", "apply": EPIC_APPLY})
        self.assertEqual(r["route"], "refuse")
        self.assertTrue(r["has_apply"])
        self.assertFalse(r["implementable"])
        self.assertIn("tracks", r["reason"])

    def test_tracked_apply_without_flow_runs_per_task(self):
        r = gates.dispatch_route({"name": "spec-driven", "apply": TRACKED_APPLY})
        self.assertEqual(r["route"], "per-task")
        self.assertEqual(r["flow"], "per-task")
        self.assertTrue(r["implementable"])

    def test_fork_under_another_name_keeps_regression_first(self):
        data = {"name": "acme-bugfix", "apply": TRACKED_APPLY,
                "gatedloop": {"flow": "regression-first"}}
        self.assertEqual(gates.dispatch_route(data)["route"], "regression-first")

    def test_schema_named_bugfix_without_flow_is_routed_by_structure(self):
        r = gates.dispatch_route({"name": "bugfix", "apply": TRACKED_APPLY})
        self.assertEqual(r["route"], "per-task")

    def test_flow_on_non_implementable_schema_refuses_naming_contradiction(self):
        data = {"name": "odd", "apply": EPIC_APPLY, "gatedloop": {"flow": "regression-first"}}
        r = gates.dispatch_route(data)
        self.assertEqual(r["route"], "refuse")
        self.assertIn("regression-first", r["reason"])

    def test_unknown_flow_raises_rather_than_routing(self):
        data = {"name": "x", "apply": TRACKED_APPLY, "gatedloop": {"flow": "yolo"}}
        with self.assertRaises(gates.SchemaDispatchError):
            gates.dispatch_route(data)


class TestReadDispatchBlocks(unittest.TestCase):
    """Design D4: the scoped reader dispatch uses when PyYAML is absent. It
    reads two scalars out of two top-level blocks and nothing else."""

    def test_reads_tracks_and_flow(self):
        text = (
            "name: acme-bugfix\n"
            "apply:\n"
            "  requires:\n"
            "    - tasks\n"
            "  tracks: tasks.md\n"
            "  instruction: |\n"
            "    tracks: not-this.md\n"
            "    flow: not-this-either\n"
            "gatedloop:\n"
            "  flow: regression-first\n"
        )
        data = gates.read_dispatch_blocks(text)
        self.assertEqual(data["apply"]["tracks"], "tasks.md")
        self.assertEqual(data["gatedloop"]["flow"], "regression-first")

    def test_absent_blocks_are_absent(self):
        data = gates.read_dispatch_blocks("name: architecture\nartifacts:\n  - id: adr\n")
        self.assertNotIn("apply", data)
        self.assertNotIn("gatedloop", data)

    def test_apply_without_tracks_is_present_but_tracks_nothing(self):
        # Issue #32's `epic`: nested `requires` and a multi-line instruction
        # are passed over, never read as an absent block.
        text = (
            "apply:\n"
            "  requires: [epic]\n"
            "  instruction: >\n"
            "    An epic is never implemented.\n"
            "\n"
            "    Its children are.\n"
        )
        data = gates.read_dispatch_blocks(text)
        self.assertIn("apply", data)
        self.assertTrue(data["apply"], "a present apply block must read as truthy")
        self.assertIsNone(data["apply"].get("tracks"))

    def test_block_ends_at_next_column_zero_key(self):
        text = "apply:\n  requires: [tasks]\nartifacts:\n  tracks: decoy.md\n"
        self.assertIsNone(gates.read_dispatch_blocks(text)["apply"].get("tracks"))

    def test_first_child_indent_other_than_two(self):
        text = "gatedloop:\n    flow: regression-first\n"
        self.assertEqual(gates.read_dispatch_blocks(text)["gatedloop"]["flow"], "regression-first")

    def test_quoted_scalars_and_trailing_comments(self):
        cases = {
            'apply:\n  tracks: "tasks.md"\n': "tasks.md",
            "apply:\n  tracks: 'tasks.md'  # the checklist\n": "tasks.md",
            "apply:  # impl phase\n  tracks: tasks.md # checklist\n": "tasks.md",
            'apply:\n  tracks: "a #b.md"\n': "a #b.md",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(gates.read_dispatch_blocks(text)["apply"]["tracks"], expected)

    def test_null_scalar_reads_as_none(self):
        for v in ("", " ~", " null"):
            with self.subTest(v=v):
                self.assertIsNone(gates.read_dispatch_blocks(f"apply:\n  tracks:{v}\n")["apply"]["tracks"])

    def test_comment_lines_do_not_end_a_block(self):
        text = "apply:\n# a column-0 comment\n  tracks: tasks.md\n"
        self.assertEqual(gates.read_dispatch_blocks(text)["apply"]["tracks"], "tasks.md")


class TestReadDispatchBlocksRefuses(unittest.TestCase):
    """Design D4: every shape the reader does not recognise fails loud naming
    the line -- it must never under-read a block as absent or empty."""

    CASES = {
        "flow mapping": ("name: x\napply: {tracks: tasks.md}\n", 2),
        "anchor on the block": ("apply: &impl\n  tracks: tasks.md\n", 1),
        "alias on the read key": ("apply:\n  tracks: *checklist\n", 2),
        "anchor on the read key": ("gatedloop:\n  flow: &f regression-first\n", 2),
        "anchor on an unread child": ("apply:\n  requires: &r [tasks]\n  tracks: t.md\n", 2),
        "merge key inside a block": ("apply:\n  <<: *base\n", 2),
        "top-level merge key": ("<<: *base\nname: x\n", 1),
        "literal indicator on tracks": ("apply:\n  tracks: |\n    tasks.md\n", 2),
        "folded indicator on flow": ("gatedloop:\n  flow: >-\n    regression-first\n", 2),
        "tab indent": ("apply:\n\ttracks: tasks.md\n", 2),
        "repeated top-level key": ("apply:\n  tracks: a.md\nname: x\napply:\n  requires: [a]\n", 4),
        "repeated read key": ("apply:\n  tracks: a.md\n  tracks: b.md\n", 3),
    }

    def test_each_unrecognised_shape_fails_naming_the_line(self):
        for label, (text, line) in self.CASES.items():
            with self.subTest(shape=label):
                with self.assertRaises(gates.SchemaDispatchError) as cm:
                    gates.read_dispatch_blocks(text)
                msg = str(cm.exception)
                self.assertIn(f"line {line}", msg)
                self.assertIn("PyYAML", msg)


SPEC_DRIVEN_SHAPED = """\
name: spec-driven
version: 1
description: Default OpenSpec workflow - proposal → specs → design → tasks
artifacts:
  - id: proposal
    generates: proposal.md
    template: proposal.md
    instruction: |
      Create the proposal document.

      apply:
        tracks: not-a-real-block.md
    requires: []
  - id: tasks
    generates: tasks.md
    requires:
      - proposal

apply:
  requires: [tasks]
  tracks: tasks.md
  instruction: |
    Read context files, work through pending tasks, mark complete as you go.
    Pause if you hit blockers or need clarification.
"""

# Issue #32's `epic`: an apply block with requires and a multi-line
# instruction, but no tracks.
EPIC_SHAPED = """\
name: epic
version: 1
description: An epic groups changes; it is never implemented itself.
artifacts:
  - id: epic
    generates: epic.md
    requires: []
apply:
  requires:
    - epic
  instruction: >
    An epic is never implemented. Its children are.

    Archive it once every child change has shipped.
"""


def _hidden_pyyaml():
    """Make `import yaml` raise ImportError, as on a machine without it."""
    return mock.patch.dict(sys.modules, {"yaml": None})


class TestScopedReaderParity(unittest.TestCase):
    """Design D4: with PyYAML hidden, the scoped reader must decide the same
    route the PyYAML path does, on every shape we ship or were shown."""

    FIXTURES = {
        "packs/bugfix": (REPO / "packs" / "bugfix" / "schema.yaml").read_text(),
        "packs/architecture": (REPO / "packs" / "architecture" / "schema.yaml").read_text(),
        "spec-driven-shaped": SPEC_DRIVEN_SHAPED,
        "#32 epic": EPIC_SHAPED,
    }

    def test_hidden_pyyaml_uses_the_scoped_reader(self):
        # A shape only the scoped reader refuses proves which path ran.
        with _hidden_pyyaml():
            with self.assertRaises(gates.SchemaDispatchError):
                gates.dispatch_data_from_text("apply:\n  tracks: &a tasks.md\n")

    def test_scoped_route_equals_pyyaml_route(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not importable; no reference parse to compare against")
        for label, text in self.FIXTURES.items():
            with self.subTest(schema=label):
                with _hidden_pyyaml():
                    scoped = gates.dispatch_route(gates.dispatch_data_from_text(text))
                reference = gates.dispatch_route(yaml.safe_load(text))
                self.assertEqual(scoped, reference)

    def test_known_routes(self):
        with _hidden_pyyaml():
            routes = {label: gates.dispatch_route(gates.dispatch_data_from_text(text))["route"]
                      for label, text in self.FIXTURES.items()}
        self.assertEqual(routes["packs/architecture"], "refuse")
        self.assertEqual(routes["spec-driven-shaped"], "per-task")
        self.assertEqual(routes["#32 epic"], "refuse")


class TestShippedBugfixPackDeclaresItsFlow(unittest.TestCase):
    """Task 4.1: the shipped bugfix pack opts into regression-first by
    declaration, so dispatch no longer needs its name -- and the namespaced
    key must not cost the pack its OpenSpec validity (design Risks)."""

    PACK = REPO / "packs" / "bugfix"

    def test_bugfix_pack_routes_regression_first_on_both_readers(self):
        text = (self.PACK / "schema.yaml").read_text()
        with _hidden_pyyaml():
            self.assertEqual(gates.dispatch_route(gates.dispatch_data_from_text(text))["route"],
                             "regression-first")
        self.assertEqual(gates.dispatch_route(gates.dispatch_data_from_text(text))["route"],
                         "regression-first")

    def test_bugfix_pack_still_passes_openspec_schema_validate(self):
        import shutil, subprocess, tempfile
        if shutil.which("openspec") is None:
            self.skipTest("OpenSpec CLI not on PATH; cannot run `openspec schema validate`")
        with tempfile.TemporaryDirectory() as d:
            shutil.copytree(self.PACK, Path(d) / "openspec" / "schemas" / "bugfix")
            r = subprocess.run(["openspec", "schema", "validate", "bugfix"],
                               cwd=d, capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class TestResolveSchemaDir(unittest.TestCase):
    """Task 3.1: inspect and dispatch resolve a schema name the same way, so
    they can never disagree about which schema.yaml they read."""

    def test_relative_path_resolves_against_root(self):
        root = Path("/proj")
        self.assertEqual(gates.resolve_schema_dir(root, None, "packs/bugfix"), root / "packs" / "bugfix")

    def test_name_resolved_through_openspec_schema_which(self):
        fake = mock.Mock(stdout='{"name": "acme-bugfix", "path": "/proj/openspec/schemas/acme-bugfix"}')
        with mock.patch.object(gates.subprocess, "run", return_value=fake) as run:
            got = gates.resolve_schema_dir(Path("/proj"), "acme-bugfix", None)
        self.assertEqual(got, Path("/proj/openspec/schemas/acme-bugfix"))
        self.assertEqual(run.call_args.args[0], ["openspec", "schema", "which", "acme-bugfix", "--json"])

    def test_unresolvable_name_fails_loud(self):
        with mock.patch.object(gates.subprocess, "run", side_effect=OSError("no openspec")):
            with self.assertRaises(SystemExit) as cm:
                gates.resolve_schema_dir(Path("/proj"), "ghost", None)
        self.assertIn("ghost", str(cm.exception.code))

    def test_neither_name_nor_path_fails_loud(self):
        with self.assertRaises(SystemExit):
            gates.resolve_schema_dir(Path("/proj"), None, None)


class TestCmdSchemaDispatch(unittest.TestCase):
    """Task 3.2 / design D3: the route is data -- exit 0 for every decided
    route, `refuse` included; non-zero only when no route can be decided."""

    def _run(self, schema_text, as_json=True):
        import argparse, contextlib, io, tempfile
        with tempfile.TemporaryDirectory() as d:
            if schema_text is not None:
                (Path(d) / "schema.yaml").write_text(schema_text)
            args = argparse.Namespace(name="whatever", path=d, json=as_json)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = gates.cmd_schema_dispatch({}, Path(d), args)
            return rc, buf.getvalue()

    def test_json_object_for_regression_first_fork(self):
        import json
        text = "name: acme-bugfix\napply:\n  tracks: tasks.md\ngatedloop:\n  flow: regression-first\n"
        rc, out = self._run(text)
        self.assertEqual(rc, 0)
        obj = json.loads(out)
        self.assertEqual(obj["schema"], "whatever")
        self.assertEqual(obj["route"], "regression-first")
        self.assertEqual(set(obj), {"schema", "route", "reason", "has_apply", "implementable", "flow"})

    def test_refuse_is_a_decision_and_exits_zero(self):
        import json
        rc, out = self._run("name: architecture\nartifacts: []\n")
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out)["route"], "refuse")

    def test_unknown_flow_exits_non_zero(self):
        with self.assertRaises(SystemExit) as cm:
            self._run("apply:\n  tracks: t.md\ngatedloop:\n  flow: yolo\n")
        self.assertNotIn(cm.exception.code, (0, None))
        self.assertIn("yolo", str(cm.exception.code))

    def test_missing_schema_file_exits_non_zero(self):
        with self.assertRaises(SystemExit) as cm:
            self._run(None)
        self.assertNotIn(cm.exception.code, (0, None))

    def test_human_output_names_the_route(self):
        rc, out = self._run("apply:\n  tracks: t.md\n", as_json=False)
        self.assertEqual(rc, 0)
        self.assertIn("per-task", out)


if __name__ == "__main__":
    unittest.main()
