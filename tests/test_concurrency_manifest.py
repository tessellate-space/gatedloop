"""`concurrency.serialize` manifest validation (design D6 of
`worktree-native-loop`, task 6.1). Names must be declared gates (or
`live-check`, a declarable gate in the contract table though not a `gates:`
entry); absent -> no locking, today's exact behavior.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

import importlib.machinery
import importlib.util
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

_loader = importlib.machinery.SourceFileLoader("gates_shim_concurrency", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)

BASE_MANIFEST = 'gatesVersion: 1\ngates:\n  ci: "true"\n  unit: "true"\n'


class TestConcurrencyValidation(unittest.TestCase):
    def _validate(self, text: str) -> list[str]:
        parsed = gates._mini_yaml(text)
        with tempfile.TemporaryDirectory() as tmp:
            return gates._errors(parsed, Path(tmp))

    def test_absent_block_still_validates(self):
        self.assertEqual(self._validate(BASE_MANIFEST), [])

    def test_declared_gate_name_validates(self):
        text = BASE_MANIFEST + "concurrency:\n  serialize:\n    - ci\n"
        self.assertEqual(self._validate(text), [])

    def test_live_check_is_a_valid_name_though_not_a_declared_gate(self):
        text = BASE_MANIFEST + "concurrency:\n  serialize:\n    - live-check\n"
        self.assertEqual(self._validate(text), [])

    def test_undeclared_gate_name_is_rejected(self):
        text = BASE_MANIFEST + "concurrency:\n  serialize:\n    - verify\n"
        errs = self._validate(text)
        self.assertTrue(
            any("verify" in e and "concurrency.serialize" in e for e in errs),
            f"expected a concurrency.serialize error, got: {errs}",
        )

    def test_non_list_is_rejected(self):
        text = BASE_MANIFEST + "concurrency:\n  serialize: ci\n"
        errs = self._validate(text)
        self.assertTrue(
            any("concurrency.serialize" in e for e in errs), f"expected an error, got: {errs}",
        )

    def test_concurrency_not_a_mapping_is_rejected(self):
        text = BASE_MANIFEST + "concurrency: \"oops\"\n"
        errs = self._validate(text)
        self.assertTrue(
            any("concurrency" in e for e in errs), f"expected an error, got: {errs}",
        )

    def test_max_wait_seconds_must_be_a_positive_integer(self):
        """lock-and-ledger-hygiene D2: the wait bound is validated by both
        parsers' output -- a zero, negative, fractional, boolean or string
        bound would disable or nonsense the bound the loop relies on."""
        parsers = [("mini_yaml", gates._mini_yaml)]
        try:
            import yaml
            parsers.append(("pyyaml", yaml.safe_load))
        except ImportError:
            pass
        cases = (("480", True), ("0", False), ("1.5", False), ("true", False),
                 ('"480"', False))
        for parser_name, parse in parsers:
            for value, valid in cases:
                with self.subTest(parser=parser_name, value=value):
                    text = BASE_MANIFEST + f"concurrency:\n  max-wait-seconds: {value}\n"
                    with tempfile.TemporaryDirectory() as tmp:
                        errs = gates._errors(parse(text), Path(tmp))
                    named = [e for e in errs if "concurrency.max-wait-seconds" in e]
                    if valid:
                        self.assertEqual(errs, [])
                    else:
                        self.assertTrue(named, f"expected a max-wait-seconds error, got: {errs}")

    def test_empty_string_entry_is_rejected(self):
        text = BASE_MANIFEST + "concurrency:\n  serialize:\n    - \"\"\n"
        errs = self._validate(text)
        self.assertTrue(
            any("concurrency.serialize" in e for e in errs), f"expected an error, got: {errs}",
        )


if __name__ == "__main__":
    unittest.main()
