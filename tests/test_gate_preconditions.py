"""gate-preconditions tests for the `gates` shim.

Stdlib only, per `zero-dep-shim`: `bin/gates` has no `.py` suffix, so it is
loaded by path through SourceFileLoader rather than imported (same pattern as
test_manifest.py).

Run with:  python3 -m unittest discover -s tests
"""

import importlib.machinery
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"
SCHEMA = REPO / "schema" / "gates.schema.json"

_loader = importlib.machinery.SourceFileLoader("gates_shim_preconditions", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)


BLOCK_MAPPING_GATE = """\
gatesVersion: 1
gates:
  ci: "true"
  integration:
    run: "just it"
    requires: "just stack-check"
"""

FLOW_MAPPING_GATE = """\
gatesVersion: 1
gates:
  ci: "true"
  integration: {run: "just it", requires: "just stack-check"}
"""

FLOW_MAPPING_WITH_QUOTED_COMMAS_AND_COLONS = """\
gatesVersion: 1
gates:
  ci: "true"
  integration: {run: "echo 'a, b: c'", requires: "test -f flag: ok"}
"""


class TestFlowMappingAgreesWithBlockForm(unittest.TestCase):
    """design D1: the stdlib fallback parses the gate mapping form (block and
    single-level inline flow) to the same structure PyYAML would."""

    def test_block_mapping_form_parses_to_a_dict(self):
        parsed = gates._mini_yaml(BLOCK_MAPPING_GATE)
        gate = parsed["gates"]["integration"]
        self.assertEqual(gate, {"run": "just it", "requires": "just stack-check"})

    def test_inline_flow_mapping_form_parses_to_the_same_dict(self):
        parsed = gates._mini_yaml(FLOW_MAPPING_GATE)
        gate = parsed["gates"]["integration"]
        self.assertEqual(gate, {"run": "just it", "requires": "just stack-check"})

    def test_flow_mapping_with_quoted_commas_and_colons(self):
        parsed = gates._mini_yaml(FLOW_MAPPING_WITH_QUOTED_COMMAS_AND_COLONS)
        gate = parsed["gates"]["integration"]
        self.assertEqual(
            gate, {"run": "echo 'a, b: c'", "requires": "test -f flag: ok"}
        )

    def test_scalar_gate_is_unaffected(self):
        parsed = gates._mini_yaml(BLOCK_MAPPING_GATE)
        self.assertEqual(parsed["gates"]["ci"], "true")

    def test_fallback_agrees_with_pyyaml(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not importable; fallback is the only parser here")
        for name, text in (
            ("block", BLOCK_MAPPING_GATE),
            ("flow", FLOW_MAPPING_GATE),
            ("flow-quoted", FLOW_MAPPING_WITH_QUOTED_COMMAS_AND_COLONS),
        ):
            with self.subTest(form=name):
                self.assertEqual(gates._mini_yaml(text), yaml.safe_load(text))


class TestUnsupportedFlowMappingSubset(unittest.TestCase):
    """design D1: a nested flow structure inside a flow mapping is out of the
    supported subset and must fail loudly — it must never silently degrade
    to a literal string that would then be executed as a shell command."""

    def test_nested_flow_list_value_raises(self):
        with self.assertRaises(ValueError):
            gates._scalar('{run: [a, b], requires: "y"}')

    def test_nested_flow_mapping_value_raises(self):
        with self.assertRaises(ValueError):
            gates._scalar('{run: {a: b}, requires: "y"}')

    def test_result_is_never_a_string(self):
        try:
            result = gates._scalar('{run: [a, b]}')
        except ValueError:
            return
        self.assertNotIsInstance(result, str)


def _validate(text: str) -> list[str]:
    parsed = gates._mini_yaml(text)
    with tempfile.TemporaryDirectory() as tmp:
        return gates._errors(parsed, Path(tmp))


class TestGateMappingFormValidation(unittest.TestCase):
    """design D1/D2, task 2.1: `_errors` accepts the mapping form for gate
    values and rejects a malformed one loudly, naming the gate and defect."""

    def test_mapping_form_with_run_and_requires_validates(self):
        text = (
            "gatesVersion: 1\ngates:\n  ci: \"true\"\n"
            "  integration: {run: \"cmd-a\", requires: \"cmd-b\"}\n"
        )
        self.assertEqual(_validate(text), [])

    def test_mapping_form_with_only_run_validates(self):
        text = 'gatesVersion: 1\ngates:\n  ci: {run: "true"}\n'
        self.assertEqual(_validate(text), [])

    def test_missing_run_is_rejected(self):
        text = 'gatesVersion: 1\ngates:\n  ci: "true"\n  integration: {requires: "cmd-b"}\n'
        errs = _validate(text)
        self.assertTrue(
            any("integration" in e and "run" in e for e in errs), errs
        )

    def test_empty_requires_is_rejected(self):
        text = 'gatesVersion: 1\ngates:\n  ci: "true"\n  integration: {run: "cmd-a", requires: ""}\n'
        errs = _validate(text)
        self.assertTrue(
            any("integration" in e and "requires" in e for e in errs), errs
        )

    def test_unknown_key_is_rejected(self):
        text = (
            "gatesVersion: 1\ngates:\n  ci: \"true\"\n"
            "  integration: {run: \"cmd-a\", timeout: \"5s\"}\n"
        )
        errs = _validate(text)
        self.assertTrue(
            any("integration" in e and "timeout" in e for e in errs), errs
        )

    def test_string_beginning_with_brace_is_rejected(self):
        """Fail-loud backstop (design D1): whatever the parser returns, a
        gate value that is a *string* beginning with `{` must never validate
        as a command — it's an unparsed mapping, not a shell command."""
        m = {
            "gatesVersion": 1,
            "gates": {"ci": "true", "integration": "{run: x, requires: y}"},
        }
        with tempfile.TemporaryDirectory() as tmp:
            errs = gates._errors(m, Path(tmp))
        self.assertTrue(
            any("integration" in e for e in errs), errs
        )


class TestLiveCheckMappingFormValidation(unittest.TestCase):
    """Same validation, applied to a surface's `live-check` value."""

    MANIFEST = """\
gatesVersion: 1
gates:
  ci: "true"
surfaces:
  - name: all
    match: "**"
    live-check: {run: "cmd-a", requires: "cmd-b"}
"""

    def test_valid_live_check_mapping_form_validates(self):
        self.assertEqual(_validate(self.MANIFEST), [])

    def test_live_check_missing_run_is_rejected(self):
        text = self.MANIFEST.replace(
            'live-check: {run: "cmd-a", requires: "cmd-b"}',
            'live-check: {requires: "cmd-b"}',
        )
        errs = _validate(text)
        self.assertTrue(any("live-check" in e and "run" in e for e in errs), errs)

    def test_live_check_unknown_key_is_rejected(self):
        text = self.MANIFEST.replace(
            'live-check: {run: "cmd-a", requires: "cmd-b"}',
            'live-check: {run: "cmd-a", timeout: "5s"}',
        )
        errs = _validate(text)
        self.assertTrue(any("live-check" in e and "timeout" in e for e in errs), errs)


class TestSchemaAcceptsMappingForm(unittest.TestCase):
    """design D6, task 2.2: the JSON schema mirrors the shim's mapping form
    for gate values and `live-check` -- documentation plus editor tooling,
    the shim's own `_errors` stays the runtime authority."""

    def test_schema_is_valid_json(self):
        json.loads(SCHEMA.read_text())

    def test_gate_spec_def_exists_with_run_and_requires(self):
        schema = json.loads(SCHEMA.read_text())
        defs = schema.get("$defs") or schema.get("definitions") or {}
        self.assertIn("gateSpec", defs, "expected a $defs/gateSpec shared shape")
        one_of = defs["gateSpec"].get("oneOf") or []
        mapping_shapes = [s for s in one_of if s.get("type") == "object"]
        self.assertTrue(mapping_shapes, "gateSpec must allow an object (mapping) shape")
        mapping = mapping_shapes[0]
        self.assertIn("run", mapping.get("properties", {}))
        self.assertIn("requires", mapping.get("properties", {}))
        self.assertEqual(mapping.get("required"), ["run"])
        self.assertFalse(mapping.get("additionalProperties", True))

    def test_gates_ci_references_gate_spec(self):
        schema = json.loads(SCHEMA.read_text())
        ci_prop = schema["properties"]["gates"]["properties"]["ci"]
        self.assertEqual(ci_prop.get("$ref"), "#/$defs/gateSpec")

    def test_surfaces_live_check_references_gate_spec(self):
        schema = json.loads(SCHEMA.read_text())
        lc_prop = schema["properties"]["surfaces"]["items"]["properties"]["live-check"]
        self.assertEqual(lc_prop.get("$ref"), "#/$defs/gateSpec")


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _run_gates(root, *args):
    return subprocess.run(
        [sys.executable, str(GATES_SHIM), *args],
        cwd=root, capture_output=True, text=True,
    )


def _new_repo(tmp, manifest_text, *, branch="my-change"):
    root = Path(tmp)
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(manifest_text)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")
    if branch:
        _git(root, "checkout", "-b", branch)
        (root / "openspec" / "changes" / branch).mkdir(parents=True, exist_ok=True)
    return root


class TestGateSpecNormalizer(unittest.TestCase):
    """design D2: `_gate_spec` is the one place scalar-vs-mapping is decided;
    every consumer routes through it."""

    def test_scalar_normalizes_to_run_only(self):
        self.assertEqual(gates._gate_spec("make test"), ("make test", None))

    def test_mapping_normalizes_to_run_and_requires(self):
        self.assertEqual(
            gates._gate_spec({"run": "make test", "requires": "make up"}),
            ("make test", "make up"),
        )

    def test_mapping_without_requires_normalizes_to_none(self):
        self.assertEqual(gates._gate_spec({"run": "make test"}), ("make test", None))


class TestMappingFormGateRuns(unittest.TestCase):
    """design D2: a mapping-form gate with no `requires` runs its `run`
    command exactly like a scalar gate — today's semantics, unchanged."""

    def test_mapping_form_gate_without_requires_runs_and_is_green(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _new_repo(tmp, "gatesVersion: 1\ngates:\n  ci: {run: \"true\"}\n")
            result = _run_gates(root, "run", "ci", "--task", "1.2")
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_mapping_form_gate_body_failure_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _new_repo(tmp, "gatesVersion: 1\ngates:\n  ci: {run: \"false\"}\n")
            result = _run_gates(root, "run", "ci", "--task", "1.2")
            self.assertEqual(result.returncode, 1)


class TestSurfacesDisplayShowsRunCommand(unittest.TestCase):
    """design D2: `cmd_surfaces`' live-check display shows the normalized
    `run` command, not a raw dict repr, for a mapping-form live-check."""

    def test_mapping_form_live_check_prints_run_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = (
                "gatesVersion: 1\n"
                "gates:\n  ci: \"true\"\n"
                "surfaces:\n"
                "  - name: all\n"
                "    match: \"**\"\n"
                "    live-check: {run: \"just smoke\", requires: \"just up\"}\n"
            )
            root = _new_repo(tmp, manifest)
            (root / "a.txt").write_text("x\n")
            result = _run_gates(root, "surfaces", "--changed", "a.txt")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("just smoke", result.stdout)
            self.assertNotIn("requires", result.stdout)


class TestMissingRunFailsLoud(unittest.TestCase):
    """review finding (task 1.2): a mapping-form gate/live-check missing
    `run` must fail loud with an explicit message — never an unhandled
    exception from handing `None` to `_exec`/`subprocess.run`."""

    def test_named_gate_missing_run_fails_loud(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _new_repo(tmp, 'gatesVersion: 1\ngates:\n  ci: {requires: "true"}\n')
            result = _run_gates(root, "run", "ci", "--task", "1.2")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("no 'run' command", result.stderr)

    def test_live_check_missing_run_fails_loud(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = (
                "gatesVersion: 1\n"
                "gates:\n  ci: \"true\"\n"
                "surfaces:\n"
                "  - name: all\n"
                "    match: \"**\"\n"
                "    live-check: {requires: \"true\"}\n"
            )
            root = _new_repo(tmp, manifest)
            (root / "a.txt").write_text("x\n")
            _git(root, "add", "-A")
            result = _run_gates(root, "run", "live-check", "--task", "1.2")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("no 'run' command", result.stderr)

    def test_surfaces_display_never_prints_python_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = (
                "gatesVersion: 1\n"
                "gates:\n  ci: \"true\"\n"
                "surfaces:\n"
                "  - name: all\n"
                "    match: \"**\"\n"
                "    live-check: {requires: \"true\"}\n"
            )
            root = _new_repo(tmp, manifest)
            (root / "a.txt").write_text("x\n")
            result = _run_gates(root, "surfaces", "--changed", "a.txt")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("live-check=None", result.stdout)


PRECONDITION_EXIT = 75


def _read_ledger(root, change):
    p = root / ".gatedloop" / "runs" / f"{change}.jsonl"
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


def _marker_exists(root, gate):
    out = subprocess.run(
        ["git", "rev-parse", "--git-dir"], cwd=root, capture_output=True, text=True,
    ).stdout.strip()
    # Markers are tree-keyed (`worktree-native-loop` D2): `markers/<gate>/<tree>.json`.
    return any((root / out / "gatedloop" / "markers" / gate).glob("*.json"))


class TestNamedGatePreconditionPath(unittest.TestCase):
    """design D3, task 3.1: a declared `requires` runs before the gate body;
    on non-zero it is a distinct outcome (reserved exit 75), never a gate
    failure -- no marker, no ledger row claiming the gate ran."""

    def test_failing_precondition_skips_the_gate_body_and_exits_75(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = 'gatesVersion: 1\ngates:\n  ci: {run: "true", requires: "false"}\n'
            root = _new_repo(tmp, manifest)
            result = _run_gates(root, "run", "ci", "--task", "3.1")
            self.assertEqual(result.returncode, PRECONDITION_EXIT)
            self.assertIn("precondition", result.stderr)
            self.assertIn("false", result.stderr)

    def test_failing_precondition_writes_no_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = 'gatesVersion: 1\ngates:\n  ci: {run: "true", requires: "false"}\n'
            root = _new_repo(tmp, manifest)
            _run_gates(root, "run", "ci", "--task", "3.1")
            self.assertFalse(_marker_exists(root, "ci"))

    def test_failing_precondition_ledger_row_never_reads_green(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = 'gatesVersion: 1\ngates:\n  ci: {run: "true", requires: "false"}\n'
            root = _new_repo(tmp, manifest)
            _run_gates(root, "run", "ci", "--task", "3.1")
            rows = _read_ledger(root, "my-change")
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row["gate"], "ci")
            self.assertEqual(row["exit"], PRECONDITION_EXIT)
            self.assertNotEqual(row["exit"], 0)
            self.assertEqual(row["outcome"], "precondition-failed")
            self.assertEqual(row["precondition"], "false")
            self.assertNotEqual(row["precondition_exit"], 0)
            self.assertIsNone(row["tree"], "a precondition row must never join a real tree")

    def test_passing_precondition_runs_the_gate_body_as_usual(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = 'gatesVersion: 1\ngates:\n  ci: {run: "true", requires: "true"}\n'
            root = _new_repo(tmp, manifest)
            result = _run_gates(root, "run", "ci", "--task", "3.1")
            self.assertEqual(result.returncode, 0)
            self.assertTrue(_marker_exists(root, "ci"))
            rows = _read_ledger(root, "my-change")
            self.assertEqual(rows[-1]["exit"], 0)
            self.assertIsNone(rows[-1].get("outcome"))

    def test_scalar_gate_is_unaffected_by_precondition_handling(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = 'gatesVersion: 1\ngates:\n  ci: "true"\n'
            root = _new_repo(tmp, manifest)
            result = _run_gates(root, "run", "ci", "--task", "3.1")
            self.assertEqual(result.returncode, 0)
            self.assertTrue(_marker_exists(root, "ci"))


def _live_check_manifest(live_check_yaml: str) -> str:
    return (
        "gatesVersion: 1\n"
        "gates:\n  ci: \"true\"\n"
        "surfaces:\n"
        "  - name: all\n"
        "    match: \"**\"\n"
        f"    live-check: {live_check_yaml}\n"
    )


class TestLiveCheckPreconditionPath(unittest.TestCase):
    """design D4, task 3.2: every hot surface's declared `requires` runs
    before any probe body; on any failure no probe runs at all, no marker is
    written, and the run exits 75 with one discriminated ledger row."""

    def test_failing_precondition_skips_the_probe_entirely(self):
        with tempfile.TemporaryDirectory() as tmp:
            probe_marker = Path(tmp) / "probe_ran.txt"
            manifest = _live_check_manifest(
                f'{{run: "touch {probe_marker}", requires: "false"}}'
            )
            root = _new_repo(tmp, manifest)
            (root / "a.txt").write_text("x\n")
            _git(root, "add", "-A")
            result = _run_gates(root, "run", "live-check", "--task", "3.2")
            self.assertEqual(result.returncode, PRECONDITION_EXIT)
            self.assertFalse(probe_marker.exists(), "the probe body must never run")
            self.assertIn("precondition", result.stderr)

    def test_failing_precondition_writes_no_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = _live_check_manifest('{run: "true", requires: "false"}')
            root = _new_repo(tmp, manifest)
            (root / "a.txt").write_text("x\n")
            _git(root, "add", "-A")
            _run_gates(root, "run", "live-check", "--task", "3.2")
            self.assertFalse(_marker_exists(root, "live-check"))

    def test_failing_precondition_ledger_row_is_discriminated(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = _live_check_manifest('{run: "true", requires: "false"}')
            root = _new_repo(tmp, manifest)
            (root / "a.txt").write_text("x\n")
            _git(root, "add", "-A")
            _run_gates(root, "run", "live-check", "--task", "3.2")
            rows = _read_ledger(root, "my-change")
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row["gate"], "live-check")
            self.assertEqual(row["exit"], PRECONDITION_EXIT)
            self.assertEqual(row["outcome"], "precondition-failed")
            self.assertIsNone(row["tree"])

    def test_one_failing_surface_blocks_every_probe(self):
        """When multiple hot surfaces exist, one failing `requires` blocks
        ALL probe bodies — never a partial 'some probes ran' state."""
        with tempfile.TemporaryDirectory() as tmp:
            ok_marker = Path(tmp) / "ok_probe_ran.txt"
            manifest = (
                "gatesVersion: 1\n"
                "gates:\n  ci: \"true\"\n"
                "surfaces:\n"
                "  - name: ok\n"
                "    match: \"a.txt\"\n"
                f"    live-check: {{run: \"touch {ok_marker}\"}}\n"
                "  - name: bad\n"
                "    match: \"b.txt\"\n"
                "    live-check: {run: \"true\", requires: \"false\"}\n"
            )
            root = _new_repo(tmp, manifest)
            (root / "a.txt").write_text("x\n")
            (root / "b.txt").write_text("y\n")
            _git(root, "add", "-A")
            result = _run_gates(root, "run", "live-check", "--task", "3.2")
            self.assertEqual(result.returncode, PRECONDITION_EXIT)
            self.assertFalse(ok_marker.exists(), "no probe body may run when any precondition fails")

    def test_all_passing_preconditions_run_every_probe_as_before(self):
        with tempfile.TemporaryDirectory() as tmp:
            probe_marker = Path(tmp) / "probe_ran.txt"
            manifest = _live_check_manifest(
                f'{{run: "touch {probe_marker}", requires: "true"}}'
            )
            root = _new_repo(tmp, manifest)
            (root / "a.txt").write_text("x\n")
            _git(root, "add", "-A")
            result = _run_gates(root, "run", "live-check", "--task", "3.2")
            self.assertEqual(result.returncode, 0)
            self.assertTrue(probe_marker.exists())
            self.assertTrue(_marker_exists(root, "live-check"))
            rows = _read_ledger(root, "my-change")
            self.assertEqual(rows[-1]["exit"], 0)
            self.assertIsNone(rows[-1].get("outcome"))


if __name__ == "__main__":
    unittest.main()
