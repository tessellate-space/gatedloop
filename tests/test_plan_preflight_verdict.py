"""The plan-tier verdict's contract and the shipped dimensions (openspec
change `plan-preflight`, design D3; task 5.1).

`schema/plan-tier.schema.json` is the published contract; `bin/gates`
checks it with a stdlib validator, `_plan_tier_errors`. One fixture set runs
through both: the schema (by a small evaluator for the keywords the schema
uses, which fails on any other keyword) and the validator, pinning which
fixtures are accepted, so the two cannot drift apart. The dimensions file
loads, fails loud when missing or malformed, and names no vendor or model.

Stdlib only, per `zero-dep-shim`. Run with:
python3 -m unittest discover -s tests
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

from _preflight_fixture import GATES_SHIM, REPO  # noqa: E402

_loader = importlib.machinery.SourceFileLoader("gates_shim_pf_verdict", str(GATES_SHIM))
gates = importlib.util.module_from_spec(importlib.util.spec_from_loader(_loader.name, _loader))
_loader.exec_module(gates)

SCHEMA = json.loads((REPO / "schema" / "plan-tier.schema.json").read_text())
DIMENSIONS = REPO / "rules" / "plan-tier-dimensions.json"

VALID = {"tier": "light", "confidence": 0.8,
         "evidence": [{"dimension": "persisted-data", "value": 0.1, "confidence": 0.9},
                      {"dimension": "overall-tier", "value": "light", "confidence": None}],
         "reason": "adds one helper"}

# name -> (raw text, accepted?)
FIXTURES = {
    "valid": (json.dumps(VALID), True),
    "reason null": (json.dumps({**VALID, "reason": None}), True),
    "reason absent": (json.dumps({k: v for k, v in VALID.items() if k != "reason"}), True),
    "confidence null, boolean value": (json.dumps({"tier": "full", "confidence": None, "evidence": [
        {"dimension": "irreversible", "value": True}]}), True),
    "bad tier": (json.dumps({**VALID, "tier": "medium"}), False),
    "confidence 1.5": (json.dumps({**VALID, "confidence": 1.5}), False),
    "evidence item with no dimension": (json.dumps({**VALID, "evidence": [{"value": 0.2}]}), False),
    "extra key": (json.dumps({**VALID, "model": "x"}), False),
    "non-JSON": ("tier: full", False),
}

_TYPES = {"object": dict, "array": list, "string": str, "null": type(None), "boolean": bool}
_KNOWN = {"$schema", "title", "description", "type", "additionalProperties", "required",
          "properties", "enum", "minimum", "maximum", "items", "minLength"}


def _type_ok(v, t: str) -> bool:
    if t == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    return isinstance(v, _TYPES[t])


def schema_accepts(node: dict, v) -> bool:
    """A JSON Schema evaluator for exactly the keywords this schema uses; an
    unknown keyword fails the test rather than being ignored."""
    unknown = set(node) - _KNOWN
    assert not unknown, f"the evaluator does not know {unknown}; extend it"
    types = node.get("type")
    if types is not None:
        types = [types] if isinstance(types, str) else types
        if not any(_type_ok(v, t) for t in types):
            return False
    if "enum" in node and v not in node["enum"]:
        return False
    num = isinstance(v, (int, float)) and not isinstance(v, bool)
    if num and "minimum" in node and v < node["minimum"]:
        return False
    if num and "maximum" in node and v > node["maximum"]:
        return False
    if isinstance(v, str) and len(v) < node.get("minLength", 0):
        return False
    if isinstance(v, dict):
        props = node.get("properties", {})
        if any(k not in v for k in node.get("required", [])):
            return False
        if node.get("additionalProperties") is False and set(v) - set(props):
            return False
        if not all(schema_accepts(props[k], x) for k, x in v.items() if k in props):
            return False
    if isinstance(v, list) and "items" in node:
        return all(schema_accepts(node["items"], x) for x in v)
    return True


def by_schema(text: str) -> bool:
    try:
        obj = json.loads(text)
    except ValueError:
        return False
    return schema_accepts(SCHEMA, obj)


def by_shim(text: str) -> bool:
    obj, errs = gates._plan_tier_parse(text)
    return not errs


class VerdictContractTest(unittest.TestCase):
    def test_schema_and_validator_accept_the_same_fixtures(self):
        for name, (text, accepted) in FIXTURES.items():
            with self.subTest(name):
                self.assertEqual(by_schema(text), accepted, "schema")
                self.assertEqual(by_shim(text), accepted, "validator")

    def test_the_validator_returns_every_error(self):
        bad = {"tier": "medium", "confidence": 2, "evidence": [{"value": 0.2}], "extra": 1}
        self.assertEqual(len(gates._plan_tier_errors(bad)), 4, gates._plan_tier_errors(bad))
        self.assertEqual(gates._plan_tier_parse("not json")[1], ["not JSON"])


class DimensionsFileTest(unittest.TestCase):
    def test_the_shipped_dimensions_load(self):
        dims = gates._plan_tier_dimensions()
        self.assertEqual([d["id"] for d in dims],
                         ["security-path", "persisted-data", "public-interface", "irreversible",
                          "overall-tier"])
        for d in dims[:4]:
            self.assertEqual((d["kind"], d["threshold"]), ("probability", 0.5))
        self.assertEqual((dims[4]["kind"], dims[4]["options"], dims[4]["raises"]),
                         ("choice", ["light", "full"], "full"))

    def test_the_file_names_no_vendor_or_model(self):
        text = DIMENSIONS.read_text().lower()
        for word in ("anthropic", "claude", "openai", "gpt", "gemini", "llama", "mistral",
                     "cohere", "opus", "sonnet", "haiku", "model"):
            self.assertIsNone(re.search(rf"\b{word}\b", text), word)

    def run_with(self, content: str | None):
        """The validate path with a plugin copy whose dimensions file is
        `content` (absent when None)."""
        with tempfile.TemporaryDirectory() as tmp:
            plugin = Path(tmp) / "plugin"
            (plugin / "bin").mkdir(parents=True)
            (plugin / "rules").mkdir()
            (plugin / "bin" / "gates").write_text(GATES_SHIM.read_text())
            for f in (REPO / "rules").iterdir():
                if f.name != DIMENSIONS.name:
                    (plugin / "rules" / f.name).write_text(f.read_text())
            if content is not None:
                (plugin / "rules" / DIMENSIONS.name).write_text(content)
            proj = Path(tmp) / "proj"
            proj.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=proj, check=True)
            (proj / ".gates.yaml").write_text(
                'gatesVersion: 1\ngates:\n  ci: "true"\nloop:\n  plan-preflight:\n'
                "    dimensions:\n      persisted-data: 0.3\n")
            return subprocess.run([sys.executable, str(plugin / "bin" / "gates"), "validate"],
                                  cwd=proj, capture_output=True, text=True, timeout=60)

    def test_a_missing_or_malformed_file_fails_loud(self):
        for content in (None, "{not json", json.dumps({"dimensions": [{"id": "x", "kind": "vibes"}]})):
            with self.subTest(content=content):
                out = self.run_with(content)
                self.assertNotEqual(out.returncode, 0)
                self.assertIn("plan-tier-dimensions.json", out.stderr)
        self.assertEqual(self.run_with(DIMENSIONS.read_text()).returncode, 0)


if __name__ == "__main__":
    unittest.main()
