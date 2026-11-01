"""`gates`'s command line, pinned across the parser's move into
`_build_parser()` (stability-contract task 2.1, a characterization guard).

The move must change nothing a user types or reads: no subcommand, flag,
positional, default, choice or help string may differ afterwards. The tree
already has that behaviour, so these tests pass before the move and after
it; a red run here means the refactor changed the interface.

The parser is captured from `main()` itself, the one path that exists both
before and after the move, by stopping `parse_args` the moment `main()`
calls it. Its structure, not `--help`'s rendered text, is compared with
`tests/parser-structure.json`: argparse renders the same parser differently
across the Python versions ci runs (3.9 says "optional arguments:", 3.13
merges a flag's aliases, and 3.9 derives a positional's `required` from its
`nargs` differently), and that difference is not an interface change.

    python3 tests/test_parser_characterization.py --write   # regenerate

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

from __future__ import annotations

import argparse
import importlib.machinery
import importlib.util
import json
import sys
import unittest
import unittest.mock
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"
GOLDEN = Path(__file__).resolve().parent / "parser-structure.json"

_loader = importlib.machinery.SourceFileLoader("gates_shim_parser_char", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)


class _Captured(Exception):
    def __init__(self, parser):
        super().__init__("parser captured")
        self.parser = parser


def captured_parser() -> argparse.ArgumentParser:
    """The top-level parser `main()` builds, taken at its `parse_args` call."""
    def stop(self, *args, **kwargs):
        raise _Captured(self)
    with unittest.mock.patch.object(argparse.ArgumentParser, "parse_args", stop):
        try:
            gates.main()
        except _Captured as captured:
            return captured.parser
    raise AssertionError("main() returned without calling parse_args")


def _plain(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return repr(value)


def _arg(action: argparse.Action) -> dict:
    return {
        "action": type(action).__name__,
        "option_strings": list(action.option_strings),
        "dest": action.dest,
        "nargs": _plain(action.nargs),
        "const": _plain(action.const),
        "default": _plain(action.default),
        "type": getattr(action.type, "__name__", _plain(action.type)),
        "choices": None if isinstance(action, argparse._SubParsersAction)
        else _plain(list(action.choices) if action.choices is not None else None),
        # A positional's `required` is derived from its `nargs` (pinned above),
        # and the derivation differs by Python version: 3.9 marks an
        # `nargs="?"` positional required, 3.13 does not. Only an option's
        # `required` is a choice the shim makes.
        "required": action.required if action.option_strings else None,
        "help": action.help,
        "metavar": _plain(action.metavar),
    }


def structure(parser: argparse.ArgumentParser, path: str = "") -> dict:
    """`{path: {...}}` for `parser` and every subparser beneath it."""
    out = {path or "gates": {
        "prog": parser.prog,
        "description": parser.description,
        "epilog": parser.epilog,
        "formatter_class": parser.formatter_class.__name__,
        "args": [_arg(a) for a in parser._actions],
    }}
    for action in parser._actions:
        if not isinstance(action, argparse._SubParsersAction):
            continue
        helps = {c.dest: c.help for c in action._choices_actions}
        for name, child in action.choices.items():
            child_path = f"{path} {name}".strip()
            out.update(structure(child, child_path))
            out[child_path]["help_in_parent"] = helps.get(name)
    return out


def current() -> dict:
    return structure(captured_parser())


class ParserCharacterizationTest(unittest.TestCase):
    def test_the_golden_file_exists(self):
        self.assertTrue(GOLDEN.is_file(), f"{GOLDEN} is missing; regenerate with --write")

    def test_every_subcommand_flag_and_help_string_is_unchanged(self):
        golden = json.loads(GOLDEN.read_text())
        now = current()
        self.assertEqual(sorted(now), sorted(golden), "the set of subcommands changed")
        for path in sorted(golden):
            self.assertEqual(now[path], golden[path], f"`gates {path}` changed")

    def test_the_capture_sees_the_real_command_line(self):
        now = current()
        for path in ("run", "tests place", "stats", "merge", "discipline check-implement"):
            self.assertIn(path, now)
        run_flags = {o for a in now["run"]["args"] for o in a["option_strings"]}
        self.assertTrue({"--task", "--attempt"} <= run_flags, run_flags)


if __name__ == "__main__":
    if sys.argv[1:] == ["--write"]:
        GOLDEN.write_text(json.dumps(current(), indent=1, sort_keys=True) + "\n")
        print(f"wrote {GOLDEN}")
    else:
        unittest.main()
