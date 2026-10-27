"""`gates stats --cost` (openspec change `token-ledger`, design D4; the
token-accounting delta's "Prices are an adopter binding").

The shim ships no price list. With `economics.prices` declared, `--cost`
multiplies each model's recorded counts by its per-million-token prices and
prints a cost per task and per change in the declared currency; a recorded
model with no price is named with its tokens, beside the priced subtotal.
Without prices, `--cost` prints tokens only and says no prices are declared.

JSON shape fixed by these tests, per change under `--cost`:
    "cost": {"prices_declared", "currency", "total", "tasks": {task: amount},
             "unattributed", "unpriced": {model: tokens}}

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _usage_fixture import (  # noqa: E402
    CHANGE, MANIFEST, MODEL_A, MODEL_B, at, change_repo, counts, run_gates, seed,
    task_start, usage_row,
)

PRICES_A = (
    "economics:\n"
    "  currency: EUR\n"
    "  prices:\n"
    f'    "{MODEL_A}": {{ input: 2, output: 10, cache-read: 0.5, cache-write: 4 }}\n'
)
PRICES_AB = PRICES_A + f'    "{MODEL_B}": {{ input: 1, output: 1, cache-read: 1, cache-write: 1 }}\n'

ROWS = [
    task_start(at(0), "1.1"),
    usage_row(at(1), "1.1", {MODEL_A: counts(input=1_000_000, output=500_000,
                                             cache_read=2_000_000, cache_write=250_000)}),
    task_start(at(2), "1.2"),
    usage_row(at(3), "1.2", {MODEL_A: counts(input=500_000), MODEL_B: counts(output=3_000_000)}),
]

# 1.1: 2 + 5 + 1 + 1 = 9.0;  1.2: model-alpha 1.0, model-beta 3.0 when priced.


def _repo(tmp, prices):
    root = change_repo(tmp, manifest=MANIFEST + prices)
    seed(root, *ROWS)
    return root


def _cost(root):
    r = run_gates(root, "stats", "--change", CHANGE, "--cost", "--json")
    assert r.returncode == 0, r.stderr
    (c,) = json.loads(r.stdout)["changes"]
    return c["cost"]


class TestCostWithPrices(unittest.TestCase):
    def test_every_model_priced_gives_a_cost_per_task_and_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, PRICES_AB)
            cost = _cost(root)
            self.assertTrue(cost["prices_declared"])
            self.assertEqual(cost["currency"], "EUR")
            self.assertAlmostEqual(cost["tasks"]["1.1"], 9.0)
            self.assertAlmostEqual(cost["tasks"]["1.2"], 4.0)
            self.assertAlmostEqual(cost["total"], 13.0)
            self.assertEqual(cost["unpriced"], {})
            out = run_gates(root, "stats", "--cost").stdout
            self.assertIn("EUR", out)
            self.assertIn("13.00", out)

    def test_an_unpriced_model_is_named_beside_the_priced_subtotal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, PRICES_A)
            cost = _cost(root)
            self.assertAlmostEqual(cost["total"], 10.0)
            self.assertAlmostEqual(cost["tasks"]["1.2"], 1.0)
            self.assertEqual(cost["unpriced"], {MODEL_B: 3_000_000})
            out = run_gates(root, "stats", "--cost").stdout
            self.assertRegex(out, rf"unpriced.*{MODEL_B}.*3000000")


class TestCostWithoutPrices(unittest.TestCase):
    def test_tokens_only_and_it_says_no_prices_are_declared(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, "")
            cost = _cost(root)
            self.assertFalse(cost["prices_declared"])
            self.assertIsNone(cost["total"])
            out = run_gates(root, "stats", "--cost").stdout
            self.assertIn("no prices declared", out)
            self.assertIn("3750000", out, "the tokens are still printed")


if __name__ == "__main__":
    unittest.main()
