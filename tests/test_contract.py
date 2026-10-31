"""The public surface, regenerated from the code and compared with the
checked-in `tests/contract.json` (stability-contract D3, D4).

Any difference fails `ci`: a removal, and an addition too, so no surface
enters the contract unreviewed. The failure prints the diff and the command
that rewrites the snapshot; rewriting it is the deliberate step, and the PR
shows the change in `tests/contract.json`.

    python3 tests/test_contract.py --write [--out PATH]

What the snapshot records:
- every `gates` subcommand, from `_build_parser()`, with its flags and
  positionals, marked `public` or `internal` (D4: `internal` only when
  listed in CONTRACT_INTERNAL with its reason);
- the exit codes, the `gatedloop/<gate>` status contexts and the manifest's
  top-level keys;
- the top-level keys of `gates handoff --json` and `gates stats --json`,
  each from a real run in a fixture repository;
- the ledger row fields and the row version.

`scripts/release status` diffs this file at the latest tag against `HEAD`
and reports public removals as breaking (D5).

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

from __future__ import annotations

import argparse
import copy
import difflib
import functools
import importlib.machinery
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
REPO = TESTS.parent
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

from _plan_fixture import PLAN, PlanRepo  # noqa: E402

GATES_SHIM = REPO / "bin" / "gates"
SCHEMA = REPO / "schema" / "gates.schema.json"
CONTRACT_PATH = TESTS / "contract.json"
REWRITE = "python3 tests/test_contract.py --write"

# D4: a subcommand is `internal` only when it is listed here, with the
# reason; every subcommand beneath a listed one is internal too. Adding an
# entry is a reviewed edit, the same as `DOCS_EXEMPT` in `scripts/release`.
CONTRACT_INTERNAL = {
    "discipline": "called only by the bundled hooks (hooks/*.sh, templates/git-hooks/*)",
    "gate-marker": "called only by the bundled commit hooks, which check the ci marker",
    "hook git-cwd": "called only by the bundled hooks, to resolve a guarded command's directory",
    "taint": "called only by the bundled commit hooks and the merge",
    "audit": "called only by the bundled Stop hook (hooks/continue-loop.sh)",
    "ledger record-merge": "called only by the bundled merge (gates merge step 4)",
}

# Exit codes every subcommand shares; PRECONDITION_EXIT_CODE is read from the
# shim. `gates merge`'s per-step codes are its own documented table (SETUP.md).
SHARED_EXIT_CODES = {
    "0": "success",
    "1": "failure, refusal or a red gate",
    "2": "usage error (the command line did not parse)",
}
MERGE_EXIT_CODES = {
    "1": "step 0 or 1 refused (75 when the merge lock is busy)",
    "2": "step 2, integrate",
    "3": "step 3, prove the merged tree",
    "4": "step 4, record",
    "5": "step 5, confirm",
    "6": "step 6, archive and publish",
}


@functools.lru_cache(maxsize=None)
def _shim():
    loader = importlib.machinery.SourceFileLoader("gates_shim_contract", str(GATES_SHIM))
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
    loader.exec_module(module)
    return module


def _internal_reason(path: str) -> str | None:
    words = path.split()
    for n in range(len(words), 0, -1):
        reason = CONTRACT_INTERNAL.get(" ".join(words[:n]))
        if reason:
            return reason
    return None


def _subcommands(parser: argparse.ArgumentParser, path: str = "") -> dict:
    out = {}
    for action in parser._actions:
        if not isinstance(action, argparse._SubParsersAction):
            continue
        for name, child in action.choices.items():
            child_path = f"{path} {name}".strip()
            options = sorted(o for a in child._actions for o in a.option_strings
                             if not isinstance(a, argparse._HelpAction))
            positionals = [a.dest for a in child._actions
                           if not a.option_strings and not isinstance(a, argparse._SubParsersAction)]
            entry = {"options": options, "positionals": positionals}
            reason = _internal_reason(child_path)
            entry["visibility"] = "internal" if reason else "public"
            if reason:
                entry["reason"] = reason
            out[child_path] = entry
            out.update(_subcommands(child, child_path))
    return out


def _document_keys() -> dict:
    """The top-level keys of `gates handoff --json` and `gates stats --json`,
    from real runs: a plan approved on `main` through `_plan_fixture`, whose
    attestation leaves a ledger for `stats` to read."""
    with tempfile.TemporaryDirectory() as tmp:
        plan = PlanRepo(Path(tmp))
        plan.merge_plan_pr(42, merger="alice")
        attest = plan.gates("approval", "attest", PLAN, "--merged", "42")
        if attest.returncode != 0:
            raise AssertionError(f"fixture attest failed: {attest.stdout}{attest.stderr}")
        plan.commit_on_main(f"attest approval: {PLAN} (merged #42)")
        plan.push_main()
        docs = {}
        for name, args in (("handoff", ("handoff", PLAN, "--json")),
                           ("stats", ("stats", "--all", "--json"))):
            r = plan.gates(*args)
            if r.returncode != 0:
                raise AssertionError(f"`gates {' '.join(args)}` failed: {r.stdout}{r.stderr}")
            docs[name] = sorted(json.loads(r.stdout))
        return docs


@functools.lru_cache(maxsize=None)
def _generate() -> str:
    shim = _shim()
    snapshot = {
        "subcommands": _subcommands(shim._build_parser()),
        "exit_codes": {**SHARED_EXIT_CODES,
                       str(shim.PRECONDITION_EXIT_CODE): "a precondition failed; the gate did not run"},
        "merge_exit_codes": MERGE_EXIT_CODES,
        "status_contexts": sorted(f"{shim.STATUS_CONTEXT_PREFIX}{g}"
                                  for g in (*shim.PUBLISHED_STATUS_GATES, "tests")),
        "manifest_keys": sorted(json.loads(SCHEMA.read_text())["properties"]),
        "documents": _document_keys(),
        "ledger_fields": list(shim.LEDGER_ROW_FIELDS),
        "ledger_row_version": shim.LEDGER_ROW_VERSION,
    }
    return _dumps(snapshot)


def generate() -> dict:
    """The snapshot of the code as it is."""
    return json.loads(_generate())


def _dumps(snapshot: dict) -> str:
    return json.dumps(snapshot, indent=1, sort_keys=True) + "\n"


def compare(snapshot: dict, actual: dict) -> str | None:
    """`None` when the two agree; otherwise the failure message, carrying a
    unified diff (`-` the snapshot, `+` the code) and the rewrite command."""
    if snapshot == actual:
        return None
    diff = "".join(difflib.unified_diff(
        _dumps(snapshot).splitlines(keepends=True), _dumps(actual).splitlines(keepends=True),
        fromfile="tests/contract.json", tofile="the code",
    ))
    return (
        "The public surface differs from tests/contract.json (`-` is the snapshot, "
        "`+` is the code).\n\n" + diff +
        f"\nIf the change is intended, rewrite the snapshot with `{REWRITE}` and "
        "commit it, so the PR shows the change to the contract. A removed public "
        "entry is breaking (docs/stability.md).\n"
    )


def write(path: Path = CONTRACT_PATH, snapshot: dict | None = None) -> None:
    Path(path).write_text(_dumps(generate() if snapshot is None else snapshot))


class ContractTest(unittest.TestCase):
    def test_the_snapshot_matches_the_code(self):
        self.assertTrue(CONTRACT_PATH.is_file(), f"{CONTRACT_PATH} is missing; run `{REWRITE}`")
        message = compare(json.loads(CONTRACT_PATH.read_text()), copy.deepcopy(generate()))
        if message:
            self.fail(message)


if __name__ == "__main__":
    if sys.argv[1:2] == ["--write"]:
        ap = argparse.ArgumentParser(description="rewrite the contract snapshot")
        ap.add_argument("--write", action="store_true")
        ap.add_argument("--out", type=Path, default=CONTRACT_PATH)
        args = ap.parse_args()
        write(args.out)
        print(f"wrote {args.out}")
    else:
        unittest.main()
