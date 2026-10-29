"""Tasks are listed in natural order (openspec change `friction-fixes`, design
D2; the test-discipline delta's "Tasks are listed in natural order"
requirement; issue #46).

`gates tests show` sorted task ids by a key mixing `int` and `str`, so a
lettered id (`1.2a`) crashed it. The other listings sorted ids as strings, so
`1.10` came before `1.2`. Every listing now shares one key: `1.2`, `1.2a`,
`1.9`, `1.10`, and an id outside the grammar sorts last instead of raising.

Stdlib only, per `zero-dep-shim`. The key and the formatters are tested
directly; `tests show` and `usage show` through the shim, in a throwaway git
repository.

Run with:  python3 -m unittest discover -s tests
"""

import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"
CHANGE = "ordered"
CDIR = f"openspec/changes/{CHANGE}"
ORDER = ["1.2", "1.2a", "1.9", "1.10"]
SHUFFLED = ["1.10", "1.2a", "1.2", "1.9"]
MODEL = "model-alpha"

_loader = importlib.machinery.SourceFileLoader("gates_shim_task_sort", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)


def _env():
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.pop("CLAUDE_PROJECT_DIR", None)
    env["CLAUDECODE"] = "1"
    return env


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
                   env=_env())


def _write(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def _gates(root, *args):
    return subprocess.run([sys.executable, str(GATES_SHIM), *args], cwd=root,
                          capture_output=True, text=True, env=_env(), timeout=60)


def _usage_row(task, n):
    return {"gate": "usage", "change": CHANGE, "task": task, "exit": 0,
            "ts": f"2026-10-01T00:00:{n:02d}+00:00", "source": "transcript", "messages": 1,
            "tokens": {MODEL: {"input": n, "output": 0, "cache_read": 0, "cache_write": 0}}}


def _handed_off(tmp):
    """A change on its branch whose four tasks, in shuffled file order, are
    each handed off behaviour-free."""
    root = Path(tmp)
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    _write(root, ".gates.yaml", 'gatesVersion: 1\ngates:\n  ci: "true"\n  unit: "true"\n')
    _write(root, f"{CDIR}/.openspec.yaml", "schema: spec-driven\n")
    _write(root, f"{CDIR}/tasks.md",
           "## 1. Work\n\n" + "".join(f"- [ ] {t} task {t}\n" for t in SHUFFLED))
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "plan")
    _git(root, "checkout", "-b", CHANGE)
    for t in SHUFFLED:
        _write(root, f".gatedloop/authored/{CHANGE}/{t}/NO-TESTS", "docs only\n")
    r = _gates(root, "tests", "handoff", CHANGE)
    assert r.returncode == 0, r.stderr
    return root


def _positions(text, ids):
    """Where each id first appears as a listed row in `text`, in `ids` order."""
    out = []
    for tid in ids:
        rows = [i for i, line in enumerate(text.splitlines())
                if line.split() and line.split()[0] == tid]
        assert rows, f"{tid} not listed in:\n{text}"
        out.append(rows[0])
    return out


class TestTheSortKey(unittest.TestCase):
    """Regressions guarded: `int` compared with `str` for a lettered id, and
    `1.10` sorted before `1.2`."""

    def test_natural_order(self):
        self.assertEqual(sorted(SHUFFLED, key=gates._task_sort_key), ORDER)

    def test_a_letter_sorts_after_its_bare_id_and_before_the_next(self):
        self.assertEqual(sorted(["1.3", "1.2b", "1.2", "1.2a"], key=gates._task_sort_key),
                         ["1.2", "1.2a", "1.2b", "1.3"])

    def test_an_id_outside_the_grammar_sorts_last_and_never_raises(self):
        got = sorted(["legacy", "1.2", "1.x", "1.10"], key=gates._task_sort_key)
        self.assertEqual(got[:2], ["1.2", "1.10"])
        self.assertEqual(set(got[2:]), {"legacy", "1.x"})


class TestTestsShow(unittest.TestCase):
    """Regression guarded: #46's crash -- `gates tests show` raising a
    `TypeError` on a change holding `1.2a`."""

    def test_human_output_exits_zero_in_natural_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _handed_off(tmp)
            r = _gates(root, "tests", "show", CHANGE)
            self.assertEqual(r.returncode, 0, r.stderr)
            pos = _positions(r.stdout, ORDER)
            self.assertEqual(pos, sorted(pos), r.stdout)

    def test_json_exits_zero_holding_every_task(self):
        # `--json` prints a sorted-keys object, whose key order carries no
        # meaning; what #46 broke there was the exit.
        with tempfile.TemporaryDirectory() as tmp:
            root = _handed_off(tmp)
            r = _gates(root, "tests", "show", CHANGE, "--json")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(set(json.loads(r.stdout)["tasks"]), set(ORDER))


class TestTheUsageAndCostListings(unittest.TestCase):
    """Regression guarded: the usage table and the cost lines listing `1.10`
    before `1.2`, out of step with `tests show`."""

    ROWS = [_usage_row(t, n) for n, t in enumerate(SHUFFLED, start=1)]

    def test_the_tokens_section(self):
        lines = gates._tokens_format_human(gates.tokens_from_rows(self.ROWS))
        pos = _positions("\n".join(lines), ORDER)
        self.assertEqual(pos, sorted(pos), lines)

    def test_the_cost_lines(self):
        m = {"economics": {"currency": "USD",
                           "prices": {MODEL: {"input": 1, "output": 1,
                                              "cache-read": 1, "cache-write": 1}}}}
        cost = gates.cost_from_tokens(gates.tokens_from_rows(self.ROWS), m)
        lines = gates._cost_format_human(cost)
        pos = _positions("\n".join(lines), ORDER)
        self.assertEqual(pos, sorted(pos), lines)

    def test_usage_show(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _handed_off(tmp)
            with open(root / f".gatedloop/runs/{CHANGE}.jsonl", "a") as f:
                for row in self.ROWS:
                    f.write(json.dumps(row) + "\n")
            r = _gates(root, "usage", "show", "--change", CHANGE)
            self.assertEqual(r.returncode, 0, r.stderr)
            summary = r.stdout.split("\n\n", 1)[1]
            pos = _positions(summary, ORDER)
            self.assertEqual(pos, sorted(pos), r.stdout)


if __name__ == "__main__":
    unittest.main()
