"""`economics.currency` and `economics.prices` in `.gates.yaml` (openspec
change `token-ledger`, design D4; the token-accounting delta's "Prices are an
adopter binding").

The block is optional. When present, `gates validate` checks its shape only:
a currency string, and per model name the four per-million-token prices
(`input`, `output`, `cache-read`, `cache-write`) as non-negative numbers. It
says nothing about which model names exist. Both YAML readers must hand the
validator the same block: model names are quoted keys and prices are decimals,
neither of which the dependency-free reader handled before.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _usage_fixture import GATES_SHIM, load_shim  # noqa: E402

gates = load_shim("gates_shim_economics_manifest")

BASE = 'gatesVersion: 1\ngates:\n  ci: "true"\n'

PRICED = BASE + (
    "economics:\n"
    "  currency: USD\n"
    "  prices:\n"
    '    "model-alpha": { input: 3, output: 15, cache-read: 0.3, cache-write: 3.75 }\n'
    '    "model-beta.v2": { input: 0.8, output: 4, cache-read: 0.08, cache-write: 1 }\n'
)


def _errors(m):
    with tempfile.TemporaryDirectory() as tmp:
        return gates._errors(m, Path(tmp))


def _economics_errors(m):
    return [e for e in _errors(m) if "economics" in e]


def _with(block):
    m = gates._mini_yaml(BASE)
    m["economics"] = block
    return m


class TestBothReadersAgree(unittest.TestCase):
    def test_the_fallback_reader_parses_quoted_model_names_and_decimals(self):
        parsed = gates._mini_yaml(PRICED)
        self.assertEqual(parsed["economics"], {
            "currency": "USD",
            "prices": {
                "model-alpha": {"input": 3, "output": 15, "cache-read": 0.3, "cache-write": 3.75},
                "model-beta.v2": {"input": 0.8, "output": 4, "cache-read": 0.08, "cache-write": 1},
            },
        })

    def test_a_priced_manifest_validates_through_either_reader(self):
        self.assertEqual(_errors(gates._mini_yaml(PRICED)), [])
        self.assertEqual(_errors(gates._parse_yaml_text(PRICED)), [])


class TestShapeErrors(unittest.TestCase):
    def test_an_absent_block_is_valid(self):
        self.assertEqual(_economics_errors(gates._mini_yaml(BASE)), [])

    def test_each_malformed_shape_is_refused_naming_the_key(self):
        good = {"input": 1, "output": 2, "cache-read": 0, "cache-write": 1}
        cases = {
            "not a mapping": "USD",
            "unknown key": {"currency": "USD", "prices": {}, "discount": 5},
            "no currency with prices": {"prices": {"m": dict(good)}},
            "empty currency": {"currency": " ", "prices": {"m": dict(good)}},
            "prices not a mapping": {"currency": "USD", "prices": ["m"]},
            "a price entry not a mapping": {"currency": "USD", "prices": {"m": 3}},
            "a negative price": {"currency": "USD", "prices": {"m": dict(good, output=-1)}},
            "a non-numeric price": {"currency": "USD", "prices": {"m": dict(good, input="3")}},
            "a boolean price": {"currency": "USD", "prices": {"m": dict(good, input=True)}},
            "a missing price": {"currency": "USD", "prices": {"m": {"input": 1, "output": 2,
                                                                    "cache-read": 0}}},
            "an unknown price key": {"currency": "USD", "prices": {"m": dict(good, batch=1)}},
        }
        for name, block in cases.items():
            with self.subTest(name):
                errs = _economics_errors(_with(block))
                self.assertTrue(errs, f"{name}: no economics error for {block!r}")

    def test_the_cli_exits_1_listing_the_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".gates.yaml").write_text(BASE + "economics:\n  currency: USD\n  prices: 7\n")
            r = subprocess.run([sys.executable, str(GATES_SHIM), "validate"], cwd=root,
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            self.assertIn("economics.prices", r.stderr)


if __name__ == "__main__":
    unittest.main()
