"""Tests for the pure outcomes aggregation behind `gates stats --outcomes`
(escalation-outcomes design D7).

`outcomes_from_rows(rows)` is the per-change reader: parsed ledger rows in,
terminal state / hands-off verdict / breakdowns out -- no I/O, no git, no
clock. `outcomes_aggregate(per_change)` composes the `--all` view. Both are
exercised directly on hand-built rows, the way `test_stats.py` exercises
`stats_from_rows`.

Stdlib only, per `zero-dep-shim`. Run with:  python3 -m unittest discover -s tests
"""

import importlib.machinery
import importlib.util
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

_loader = importlib.machinery.SourceFileLoader("gates_shim_outcomes", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)

CAUSES = ("missing-oracle", "weak-spec", "oracle-conflict", "stalled",
          "environment", "budget", "other")


def row(ts, gate, **extra):
    r = {
        "ts": ts, "gate": gate, "exit": 0, "duration_ms": 0,
        "change": "my-change", "task": None, "tree": None, "attempt": 1,
        "approved_by": None, "sha": None, "session": "agent",
    }
    r.update(extra)
    return r


T = "2026-08-01T00:0{}:00+00:00"


def _clean_merged():
    return [
        row(T.format(0), "task-start", task="1.1"),
        row(T.format(1), "ci"),
        row(T.format(2), "review"),
        row(T.format(3), "merge", sha="abc"),
    ]


class TestTerminalState(unittest.TestCase):
    def test_merged_when_a_merge_row_exists(self):
        out = gates.outcomes_from_rows(_clean_merged())
        self.assertEqual(out["terminal"], "merged")

    def test_merged_wins_over_an_outstanding_halt(self):
        rows = _clean_merged() + [row(T.format(4), "halt", cause="stalled")]
        self.assertEqual(gates.outcomes_from_rows(rows)["terminal"], "merged")

    def test_halted_when_last_halt_is_after_last_task_start(self):
        rows = [
            row(T.format(0), "task-start", task="1.1"),
            row(T.format(1), "halt", cause="stalled", task="1.1"),
        ]
        out = gates.outcomes_from_rows(rows)
        self.assertEqual(out["terminal"], "halted")
        self.assertEqual(out["halt_cause"], "stalled")

    def test_in_progress_after_a_resume(self):
        rows = [
            row(T.format(0), "task-start", task="1.1"),
            row(T.format(1), "halt", cause="stalled", task="1.1"),
            row(T.format(2), "task-start", task="1.1"),
        ]
        out = gates.outcomes_from_rows(rows)
        self.assertEqual(out["terminal"], "in-progress")
        self.assertIsNone(out["halt_cause"])
        self.assertEqual(out["halts"]["stalled"], 1, "the earlier halt still counts")

    def test_order_is_file_order_not_timestamp(self):
        rows = [
            row(T.format(5), "task-start", task="1.1"),
            row(T.format(1), "halt", cause="weak-spec"),  # earlier ts, later in file
        ]
        self.assertEqual(gates.outcomes_from_rows(rows)["terminal"], "halted")

    def test_in_progress_with_only_gate_rows(self):
        rows = [row(T.format(0), "ci")]
        self.assertEqual(gates.outcomes_from_rows(rows)["terminal"], "in-progress")


class TestHandsOff(unittest.TestCase):
    def test_merged_and_clean_is_hands_off(self):
        out = gates.outcomes_from_rows(_clean_merged())
        self.assertTrue(out["hands_off"])
        self.assertEqual(out["verdict"], "hands-off")
        self.assertEqual(out["assisted_by"], [])

    def test_any_halt_intervention_or_taint_makes_it_assisted(self):
        for extra, named in (
            (row(T.format(5), "halt", cause="stalled"), "halt"),
            (row(T.format(5), "intervention", cause="ask"), "intervention"),
            (row(T.format(5), "taint", exit=1, sha="x"), "taint"),
        ):
            out = gates.outcomes_from_rows(_clean_merged() + [extra])
            self.assertFalse(out["hands_off"], named)
            self.assertEqual(out["verdict"], "assisted")
            self.assertEqual(out["assisted_by"], [named])

    def test_not_merged_is_never_hands_off(self):
        rows = [row(T.format(0), "ci")]
        out = gates.outcomes_from_rows(rows)
        self.assertFalse(out["hands_off"])
        self.assertIsNone(out["verdict"])


class TestBreakdowns(unittest.TestCase):
    def test_halts_by_cause_lists_every_cause_with_zeros(self):
        rows = [
            row(T.format(0), "halt", cause="weak-spec"),
            row(T.format(1), "halt", cause="weak-spec"),
            row(T.format(2), "halt", cause="missing-oracle"),
        ]
        out = gates.outcomes_from_rows(rows)
        self.assertEqual(set(out["halts"]), set(CAUSES))
        self.assertEqual(out["halts"]["weak-spec"], 2)
        self.assertEqual(out["halts"]["missing-oracle"], 1)
        self.assertEqual(out["halts"]["stalled"], 0)

    def test_unknown_or_missing_cause_is_a_malformed_halt(self):
        rows = [
            row(T.format(0), "halt", cause="flaky"),
            row(T.format(1), "halt"),  # no cause at all
            row(T.format(2), "halt", cause="stalled"),
        ]
        out = gates.outcomes_from_rows(rows)
        self.assertEqual(sum(out["halts"].values()), 1)
        self.assertEqual(out["data_quality"]["malformed_halts"], 2)

    def test_interventions_by_kind(self):
        rows = [
            row(T.format(0), "intervention", cause="ask"),
            row(T.format(1), "intervention", cause="ask"),
            row(T.format(2), "intervention", cause="human-commit", sha="s"),
        ]
        out = gates.outcomes_from_rows(rows)
        self.assertEqual(out["interventions"], {"ask": 2, "human-commit": 1})

    def test_taints_counted(self):
        rows = [row(T.format(0), "taint", exit=1), row(T.format(1), "taint-clear")]
        self.assertEqual(gates.outcomes_from_rows(rows)["taints"], 1)

    def test_first_ts_is_the_earliest_usable_timestamp(self):
        rows = [
            row("2026-08-03T00:00:00+00:00", "ci"),
            row("garbage", "ci"),
            row("2026-08-01T00:00:00+00:00", "ci"),
        ]
        out = gates.outcomes_from_rows(rows)
        self.assertEqual(out["first_ts"], "2026-08-01T00:00:00+00:00")
        self.assertEqual(out["data_quality"]["rows_without_ts"], 1)

    def test_rows_without_session_are_counted(self):
        rows = [row(T.format(0), "ci"), row(T.format(1), "ci")]
        del rows[0]["session"]
        rows[1]["session"] = None
        out = gates.outcomes_from_rows(rows + [row(T.format(2), "ci")])
        self.assertEqual(out["data_quality"]["rows_without_session"], 2)

    def test_unclassified_commits_are_counted(self):
        rows = [row(T.format(0), "unclassified-commit", sha="s")]
        out = gates.outcomes_from_rows(rows)
        self.assertEqual(out["data_quality"]["unclassified_commits"], 1)

    def test_empty_ledger_does_not_crash(self):
        out = gates.outcomes_from_rows([])
        self.assertEqual(out["terminal"], "in-progress")
        self.assertIsNone(out["first_ts"])


class TestAggregate(unittest.TestCase):
    def _change(self, name, rows):
        out = gates.outcomes_from_rows(rows)
        out["change"] = name
        return out

    def test_hands_off_share_three_of_four(self):
        dirty = _clean_merged() + [row(T.format(5), "intervention", cause="ask")]
        per = [self._change(f"c{i}", _clean_merged()) for i in range(3)]
        per.append(self._change("c3", dirty))
        agg = gates.outcomes_aggregate(per)
        self.assertEqual(agg["hands_off_share"],
                         {"numerator": 3, "denominator": 4, "value": 0.75})
        self.assertEqual(agg["by_terminal"], {"merged": 4, "halted": 0, "in-progress": 0})
        self.assertEqual(agg["interventions_by_kind"], {"ask": 1, "human-commit": 0})

    def test_nothing_merged_is_not_computable(self):
        per = [
            self._change("a", [row(T.format(0), "halt", cause="stalled")]),
            self._change("b", [row(T.format(0), "ci")]),
        ]
        agg = gates.outcomes_aggregate(per)
        self.assertEqual(agg["hands_off_share"],
                         {"numerator": 0, "denominator": 0, "value": None})
        self.assertEqual(agg["by_terminal"], {"merged": 0, "halted": 1, "in-progress": 1})

    def test_halts_by_cause_sums_with_zeros(self):
        per = [
            self._change("a", [row(T.format(0), "halt", cause="weak-spec"),
                               row(T.format(1), "halt", cause="missing-oracle")]),
            self._change("b", [row(T.format(0), "halt", cause="weak-spec")]),
        ]
        agg = gates.outcomes_aggregate(per)
        self.assertEqual(agg["halts_by_cause"]["weak-spec"], 2)
        self.assertEqual(agg["halts_by_cause"]["missing-oracle"], 1)
        self.assertEqual(agg["halts_by_cause"]["other"], 0)

    def test_trend_is_by_month_of_first_activity(self):
        aug = [row("2026-08-10T00:00:00+00:00", "ci"),
               row("2026-09-02T00:00:00+00:00", "merge")]
        sep = [row("2026-09-05T00:00:00+00:00", "ci")]
        agg = gates.outcomes_aggregate([self._change("a", aug), self._change("b", sep)])
        self.assertEqual(agg["trend"], {
            "2026-08": {"changes": 1, "merged": 1, "hands_off": 1},
            "2026-09": {"changes": 1, "merged": 0, "hands_off": 0},
        })

    def test_taints_total(self):
        per = [self._change("a", [row(T.format(0), "taint", exit=1)]),
               self._change("b", [row(T.format(0), "taint", exit=1)])]
        self.assertEqual(gates.outcomes_aggregate(per)["taints"], 2)


def _merged_at(tree):
    return [
        row(T.format(0), "task-start", task="1.1"),
        row(T.format(1), "ci"),
        row(T.format(3), "merge", sha="abc", tree=tree),
    ]


def _acc(minute, verdict, tree, **extra):
    return row(T.format(minute), "acceptance", exit=None, verdict=verdict,
               tree=tree, accepted_by="po", **extra)


class TestAcceptanceTerminal(unittest.TestCase):
    """acceptance-gate design D7: under a declared acceptance policy the
    terminal event is acceptance of the tree that shipped."""

    def test_accept_of_the_merged_tree_is_accepted_and_hands_off(self):
        rows = _merged_at("T1") + [_acc(2, "accept", "T1")]
        out = gates.outcomes_from_rows(rows, acceptance_policy="self")
        self.assertEqual(out["terminal"], "accepted")
        self.assertTrue(out["hands_off"])
        self.assertEqual(out["verdict"], "hands-off")

    def test_merge_without_acceptance_is_merged_and_names_it(self):
        out = gates.outcomes_from_rows(_merged_at("T1"), acceptance_policy="self")
        self.assertEqual(out["terminal"], "merged")
        self.assertFalse(out["hands_off"])
        self.assertEqual(out["verdict"], "assisted")
        self.assertIn("missing acceptance", out["assisted_by"])

    def test_accept_of_a_different_tree_is_merged(self):
        rows = _merged_at("T1") + [_acc(2, "accept", "T0")]
        out = gates.outcomes_from_rows(rows, acceptance_policy="self")
        self.assertEqual(out["terminal"], "merged")
        self.assertFalse(out["hands_off"])

    def test_reject_counts_under_halts_by_cause(self):
        rows = [row(T.format(0), "task-start", task="1.1"),
                _acc(1, "reject", "T1", cause="missing-oracle", detail="nothing checked it")]
        out = gates.outcomes_from_rows(rows, acceptance_policy="self")
        self.assertEqual(out["halts"]["missing-oracle"], 1)
        per = dict(out, change="a")
        agg = gates.outcomes_aggregate([per], acceptance_policy="self")
        self.assertEqual(agg["halts_by_cause"]["missing-oracle"], 1)

    def test_share_is_accepted_over_merged_plus_accepted(self):
        accepted = dict(gates.outcomes_from_rows(
            _merged_at("T1") + [_acc(2, "accept", "T1")], acceptance_policy="self"),
            change="a")
        merged = dict(gates.outcomes_from_rows(_merged_at("T2"), acceptance_policy="self"),
                      change="b")
        agg = gates.outcomes_aggregate([accepted, merged], acceptance_policy="self")
        self.assertEqual(agg["hands_off_share"],
                         {"numerator": 1, "denominator": 2, "value": 0.5})
        self.assertEqual(agg["by_terminal"]["accepted"], 1)
        self.assertEqual(agg["by_terminal"]["merged"], 1)

    def test_undeclared_policy_is_unchanged(self):
        fixtures = [
            _clean_merged(),
            _merged_at("T1") + [_acc(2, "accept", "T1")],
            [row(T.format(0), "task-start", task="1.1"),
             _acc(1, "reject", "T1", cause="weak-spec", detail="d")],
        ]
        for rows in fixtures:
            without = [r for r in rows if r["gate"] != "acceptance"]
            with self.subTest(rows=len(rows)):
                self.assertEqual(gates.outcomes_from_rows(rows),
                                 gates.outcomes_from_rows(without))
                self.assertEqual(gates.outcomes_from_rows(rows, acceptance_policy=None),
                                 gates.outcomes_from_rows(without))
        per = [dict(gates.outcomes_from_rows(_clean_merged()), change="a")]
        self.assertEqual(gates.outcomes_aggregate(per)["by_terminal"],
                         {"merged": 1, "halted": 0, "in-progress": 0})


class TestAuthorshipAndTestDefects(unittest.TestCase):
    """split-test-author design D11. Regression guarded: the outcomes view
    misreporting who authored a change's tests, or losing its defect count."""

    def _handoff(self, author, task=None):
        return row(T.format(0), "tests-handoff", author=author, task=task)

    def test_authorship_from_the_handoff_authors(self):
        cases = {
            "separate": [self._handoff("separate"), self._handoff("separate", "1.2")],
            "inline": [self._handoff("inline")],
            "mixed": [self._handoff("separate"), self._handoff("inline", "1.2")],
            "none": _clean_merged(),
        }
        for expected, rows in cases.items():
            with self.subTest(expected=expected):
                self.assertEqual(gates.outcomes_from_rows(rows)["authorship"], expected)

    def test_defects_are_counted(self):
        rows = [self._handoff("separate"),
                row(T.format(1), "test-defect", task="1.1", detail="x"),
                row(T.format(2), "test-defect", task="1.2", detail="y")]
        self.assertEqual(gates.outcomes_from_rows(rows)["test_defects"], 2)
        self.assertEqual(gates.outcomes_from_rows(_clean_merged())["test_defects"], 0)


if __name__ == "__main__":
    unittest.main()
