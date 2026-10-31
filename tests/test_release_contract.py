"""`scripts/release` reports contract removals as breaking (stability-contract D5).

`status` compares `tests/contract.json` at the latest tag with the one at
`HEAD`; `cut` drafts a `### Breaking` entry per removal with a `TODO`
migration; `publish` refuses while a `TODO` remains. The regressions:
- a removed public flag shipping without a breaking entry;
- additions, or a removed `internal` subcommand, reported as breaking, so
  the report stops being read;
- a tag that predates the snapshot crashing `status` or being reported as
  "everything removed";
- a raised ledger row version passing as an ordinary release;
- `status` starting to suggest `major` on its own (the level stays the
  maintainer's);
- `publish` writing anything before it refuses a `TODO`.

Throwaway repositories through `test_release`'s fixtures; nothing touches
this repository's remote, tags or releases. Stdlib only. Run with:
    python3 -m unittest discover -s tests
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import unittest

import test_release as release_tests

CONTRACT = "tests/contract.json"
RUN_TASK = "--task"

SNAPSHOT = {
    "subcommands": {
        "run": {"visibility": "public", "options": ["--attempt", "--task"], "positionals": ["gate"]},
        "stats": {"visibility": "public", "options": ["--json"], "positionals": []},
        "discipline": {"visibility": "internal", "reason": "only the bundled hooks call it",
                       "options": [], "positionals": []},
    },
    "exit_codes": {"0": "success", "1": "failure", "2": "usage error", "75": "precondition failed"},
    "status_contexts": ["gatedloop/ci", "gatedloop/live-check", "gatedloop/tests"],
    "manifest_keys": ["gates", "gatesVersion", "surfaces"],
    "documents": {"handoff": ["change", "verify"], "stats": ["changes", "totals"]},
    "ledger_fields": ["exit", "gate", "ts", "v"],
    "ledger_row_version": 1,
}


def _dump(snapshot) -> str:
    return json.dumps(snapshot, indent=1, sort_keys=True) + "\n"


def _without_run_task(snapshot):
    s = copy.deepcopy(snapshot)
    s["subcommands"]["run"]["options"].remove(RUN_TASK)
    return s


class _ContractRepo(release_tests.RepoTestCase):
    """Tagged 0.4.0 holding `tests/contract.json` (unless told not to), then
    `HEAD`'s snapshot and one shipped fix, so a release is due."""

    def build(self, at_head, at_tag=SNAPSHOT):
        self.repo.write("CHANGELOG.md", release_tests.CHANGELOG_SEED)
        if at_tag is not None:
            self.repo.write(CONTRACT, _dump(at_tag))
        self.repo.commit_all("changelog and contract")
        self.repo.tag("v0.4.0")
        self.repo.write(CONTRACT, _dump(at_head))
        self.repo.write("hooks/brief.sh", "echo fixed\n")
        self.repo.commit_all("Fix the session brief")

    def status_json(self) -> dict:
        r = self.repo.run("status", "--json")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        return json.loads(r.stdout)

    def breaking(self, doc: dict) -> list:
        self.assertIn("breaking", doc, f"status --json carries no breaking list: {doc}")
        return doc["breaking"]

    def status_text(self) -> str:
        r = self.repo.run("status")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        return r.stdout


class StatusBreakingTest(_ContractRepo):
    def test_a_removed_public_flag_is_reported_as_breaking(self):
        self.build(_without_run_task(SNAPSHOT))
        doc = self.status_json()
        hits = [e for e in self.breaking(doc) if RUN_TASK in e and "run" in e]
        self.assertEqual(len(hits), 1, self.breaking(doc))
        self.assertEqual(len(self.breaking(doc)), 1, self.breaking(doc))
        text = self.status_text()
        self.assertRegex(text, r"(?i)breaking")
        self.assertIn(RUN_TASK, text)

    def test_the_level_stays_the_maintainers(self):
        self.build(_without_run_task(SNAPSHOT))
        doc = self.status_json()
        self.assertTrue(self.breaking(doc))
        self.assertEqual(doc["suggested"], "patch")

    def test_additions_only_are_not_breaking(self):
        head = copy.deepcopy(SNAPSHOT)
        head["subcommands"]["run"]["options"].append("--scope")
        head["subcommands"]["frobnicate"] = {"visibility": "public", "options": [], "positionals": []}
        head["ledger_fields"].append("newfield")
        self.build(head)
        self.assertEqual(self.breaking(self.status_json()), [])
        self.assertNotRegex(self.status_text(), r"(?i)breaking")

    def test_a_removed_internal_subcommand_is_not_breaking(self):
        head = copy.deepcopy(SNAPSHOT)
        del head["subcommands"]["discipline"]
        self.build(head)
        self.assertEqual(self.breaking(self.status_json()), [])

    def test_other_removals_are_breaking_too(self):
        head = copy.deepcopy(SNAPSHOT)
        head["status_contexts"].remove("gatedloop/tests")
        head["ledger_fields"].remove("gate")
        del head["exit_codes"]["75"]
        self.build(head)
        breaking = " | ".join(self.breaking(self.status_json()))
        for name in ("gatedloop/tests", "gate", "75"):
            self.assertIn(name, breaking)

    def test_a_raised_row_version_is_breaking(self):
        head = copy.deepcopy(SNAPSHOT)
        head["ledger_row_version"] = 2
        self.build(head)
        breaking = self.breaking(self.status_json())
        self.assertEqual(len(breaking), 1, breaking)
        self.assertIn("1", breaking[0])
        self.assertIn("2", breaking[0])

    def test_a_tag_without_a_snapshot_skips_the_comparison_and_says_so(self):
        self.build(_without_run_task(SNAPSHOT), at_tag=None)
        self.assertEqual(self.breaking(self.status_json()), [])
        self.assertIn("contract comparison skipped: the tag has no snapshot", self.status_text())


class CutDraftsBreakingTest(_ContractRepo):
    def test_cut_drafts_a_breaking_entry_with_a_todo_migration(self):
        self.build(_without_run_task(SNAPSHOT))
        env = release_tests.clean_env(GATEDLOOP_RELEASE_DATE=release_tests.RELEASE_DATE)
        r = self.repo.run("cut", "minor", env=env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        section = self.repo.read("CHANGELOG.md").split("## 0.4.0")[0]
        self.assertIn("### Breaking", section)
        (entry,) = [line for line in section.splitlines()
                    if line.startswith("- ") and RUN_TASK in line]
        self.assertIn("TODO", entry)

    def test_cut_without_removals_drafts_no_breaking_section(self):
        head = copy.deepcopy(SNAPSHOT)
        head["subcommands"]["run"]["options"].append("--scope")
        self.build(head)
        env = release_tests.clean_env(GATEDLOOP_RELEASE_DATE=release_tests.RELEASE_DATE)
        r = self.repo.run("cut", "minor", env=env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("### Breaking", self.repo.read("CHANGELOG.md"))


class PublishRefusesTodoTest(release_tests.CutFixture):
    """`publish` against a bare `origin` and a `gh` stub, as `test_release`'s
    own publish tests run it."""

    def setUp(self):
        super().setUp()
        self.origin = self.tmp / "origin.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(self.origin)],
                       check=True, env=release_tests.clean_env(), capture_output=True)
        self.repo.git("remote", "add", "origin", str(self.origin))
        self.repo.git("push", "-q", "origin", "main", "--tags")
        stub_dir = self.tmp / "stub-bin"
        stub_dir.mkdir()
        stub = stub_dir / "gh"
        stub.write_text(release_tests.GH_STUB.format(python=sys.executable))
        stub.chmod(0o755)
        self.gh_log = self.tmp / "gh.log"
        self.env = release_tests.clean_env(
            PATH=f"{stub_dir}{os.pathsep}{os.environ.get('PATH', '')}",
            GH_STUB_LOG=str(self.gh_log),
            GATEDLOOP_RELEASE_DATE=release_tests.RELEASE_DATE)
        cut = self.repo.run("cut", "minor", env=self.env)
        self.assertEqual(cut.returncode, 0, cut.stdout + cut.stderr)
        self.head = self.repo.git("rev-parse", "HEAD").stdout.strip()

    def _gh_calls(self):
        if not self.gh_log.exists():
            return []
        return [json.loads(line) for line in self.gh_log.read_text().splitlines()]

    def _add_breaking(self, migration: str) -> None:
        text = self.repo.read("CHANGELOG.md")
        marker = "## 0.4.0"
        entry = f"### Breaking\n\n- flag `run --task` removed: {migration}\n\n"
        self.repo.write("CHANGELOG.md", text.replace(marker, entry + marker, 1))

    def test_a_todo_migration_refuses_before_the_first_write_naming_the_entry(self):
        self._add_breaking("TODO")
        r = self.repo.run("publish", env=self.env)
        out = r.stdout + r.stderr
        self.assertNotEqual(r.returncode, 0, out)
        self.assertIn("run --task", out)
        self.assertIn("TODO", out)
        self.assertEqual(self.repo.git("rev-parse", "HEAD").stdout.strip(), self.head)
        self.assertEqual(self.repo.git("tag", "--list", "v0.5.0").stdout.strip(), "")
        self.assertNotIn("release", [c["args"][0] for c in self._gh_calls()])

    def test_a_written_migration_publishes(self):
        self._add_breaking("pass the task id as `--work-item` instead")
        r = self.repo.run("publish", env=self.env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
