"""Tests for `scripts/release`, the maintainer's release procedure.

Stdlib only. `scripts/release` has no `.py` suffix, so it is loaded by path
through SourceFileLoader, the way the shim tests load `bin/gates`; the
subcommands themselves are exercised as a subprocess against throwaway git
repositories, so nothing here touches this repository's remote, tags or
releases.

Run with:  python3 -m unittest discover -s tests
"""

import importlib.machinery
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RELEASE_SCRIPT = REPO / "scripts" / "release"

_loader = importlib.machinery.SourceFileLoader("release_script", str(RELEASE_SCRIPT))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
release = importlib.util.module_from_spec(_spec)
_loader.exec_module(release)

BASELINE = "0.4.0"
PLUGIN = ".claude-plugin/plugin.json"
MARKET = ".claude-plugin/marketplace.json"

# Variables that would point a child git at some other repository.
_GIT_LEAKS = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
              "GIT_COMMON_DIR", "GIT_PREFIX")


# The agent-session variable (`discipline.agent-env`'s default): `publish`
# refuses inside an agent session (release-push D1), so a test sets it
# explicitly rather than inheriting it from whatever ran the suite.
_AGENT_ENV = "CLAUDECODE"


def clean_env(**extra):
    """A copy of the environment for a child process, outside any agent
    session unless `extra` sets one; os.environ is never mutated."""
    env = {k: v for k, v in os.environ.items() if k not in _GIT_LEAKS and k != _AGENT_ENV}
    env.update(extra)
    return env


class ReleaseRepo:
    """A throwaway git repository holding copies of the plugin's two manifests."""

    def __init__(self, root: Path):
        self.root = root
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "Release Test")
        self.git("config", "user.email", "release-test@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        self.git("config", "tag.gpgsign", "false")
        (root / ".claude-plugin").mkdir()
        for rel in (PLUGIN, MARKET):
            shutil.copy(REPO / rel, root / rel)
            # Pin the copies to the fixture's own baseline: the real manifests
            # move with every release, and these tests are written against 0.4.0.
            text = re.sub(r'"version": "\d+\.\d+\.\d+"', f'"version": "{BASELINE}"',
                          (root / rel).read_text())
            (root / rel).write_text(text)
        self.commit_all("initial manifests")

    def git(self, *args, check=True):
        return subprocess.run(["git", *args], cwd=self.root, env=clean_env(),
                              capture_output=True, text=True, check=check)

    def write(self, rel, text):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def read(self, rel):
        return (self.root / rel).read_text()

    def commit_all(self, subject):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", subject)

    def tag(self, name):
        self.git("tag", "-a", name, "-m", name)

    def set_version(self, rel, old, new, occurrence=None):
        """Replace `"version": "old"` in one manifest; `occurrence` picks one of several."""
        text = self.read(rel)
        needle = f'"version": "{old}"'
        if occurrence is None:
            text = text.replace(needle, f'"version": "{new}"')
        else:
            parts = text.split(needle)
            count = len(parts) - 1
            assert occurrence < count, (rel, occurrence, count)
            text = needle.join(parts[: occurrence + 1]) + f'"version": "{new}"' + \
                needle.join(parts[occurrence + 1:])
        self.write(rel, text)

    def set_all_versions(self, old, new):
        self.set_version(PLUGIN, old, new)
        self.set_version(MARKET, old, new)

    def archive_change(self, name, why, capability="x", delta="## ADDED Requirements",
                       date="2026-09-29"):
        """Archive a change the way `/opsx:archive` does, and sync its capability spec."""
        base = f"openspec/changes/archive/{date}-{name}"
        self.write(f"{base}/proposal.md", f"# Proposal: {name}\n\n## Why\n\n{why}\n\n"
                                          "## What Changes\n\n- things\n")
        self.write(f"{base}/specs/{capability}/spec.md",
                   f"# Spec Delta\n\n{delta}\n\n### Requirement: R\n\nIt SHALL.\n")
        self.write(f"openspec/specs/{capability}/spec.md", "# Spec\n\n### Requirement: R\n")
        self.commit_all(f"archive change: {name}")

    def run(self, *args, env=None):
        return subprocess.run([sys.executable, str(RELEASE_SCRIPT), *args], cwd=self.root,
                              env=env if env is not None else clean_env(),
                              capture_output=True, text=True)


class RepoTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name).resolve()
        (self.tmp / "repo").mkdir()
        self.repo = ReleaseRepo(self.tmp / "repo")

    def tearDown(self):
        self._tmp.cleanup()


class TestCheck(RepoTestCase):
    """`check`: one value across every manifest field, never behind the latest tag."""

    def test_agreeing_fields_and_matching_tag_pass(self):
        self.repo.tag("v0.4.0")
        result = self.repo.run("check")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_one_marketplace_field_differing_fails_and_lists_all_three(self):
        self.repo.tag("v0.4.0")
        self.repo.set_version(PLUGIN, "0.4.0", "0.5.0")
        self.repo.set_version(MARKET, "0.4.0", "0.5.0", occurrence=0)
        result = self.repo.run("check")
        self.assertNotEqual(result.returncode, 0)
        err = result.stderr
        self.assertIn("plugin.json version: 0.5.0", err)
        self.assertIn("marketplace.json metadata.version: 0.5.0", err)
        self.assertIn("marketplace.json plugins[gatedloop].version: 0.4.0", err)

    def test_version_behind_latest_tag_fails_naming_both(self):
        self.repo.tag("v0.4.0")
        self.repo.set_all_versions("0.4.0", "0.3.0")
        self.repo.commit_all("go backwards")
        result = self.repo.run("check")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("0.3.0", result.stderr)
        self.assertIn("v0.4.0", result.stderr)

    def test_no_tags_checks_agreement_only(self):
        self.repo.set_all_versions("0.4.0", "0.1.0")
        self.assertEqual(self.repo.run("check").returncode, 0)
        self.repo.set_version(PLUGIN, "0.1.0", "0.2.0")
        self.assertNotEqual(self.repo.run("check").returncode, 0)

    def test_non_semver_value_fails(self):
        self.repo.set_all_versions("0.4.0", "0.4")
        result = self.repo.run("check")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("0.4", result.stderr)
        self.assertIn("MAJOR.MINOR.PATCH", result.stderr)

    def test_latest_tag_is_the_highest_semver_reachable(self):
        self.repo.tag("v0.2.0")
        self.repo.tag("v0.10.0")
        self.repo.tag("not-a-release")
        self.assertEqual(release.latest_tag(self.repo.root), ("v0.10.0", (0, 10, 0)))


class TestStatus(RepoTestCase):
    """`status`: what shipped since the latest tag, and a suggested level."""

    def setUp(self):
        super().setUp()
        self.repo.tag("v0.4.0")

    def test_planning_only_commits_are_current(self):
        self.repo.write("openspec/changes/next/proposal.md", "# Proposal\n")
        self.repo.commit_all("propose: next")
        self.repo.write("docs/notes.md", "notes\n")
        self.repo.commit_all("docs: notes")
        result = self.repo.run("status")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("current", result.stdout)

    def test_shipped_fix_suggests_patch_and_exits_one(self):
        self.repo.write("hooks/brief.sh", "echo fixed\n")
        self.repo.commit_all("Fix the session brief")
        result = self.repo.run("status")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("patch", result.stdout)
        self.assertIn("Fix the session brief", result.stdout)

    def test_built_in_rule_edit_is_shipped(self):
        # The shim reads rules/loop-rules.md at runtime (test-quality-rule
        # D1), so editing it changes every adopter's review: a release is due.
        self.repo.write("rules/loop-rules.md", "### gatedloop.test-quality\n")
        self.repo.commit_all("Tighten the test-quality rule")
        result = self.repo.run("status")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("Tighten the test-quality rule", result.stdout)

    def test_adoption_catalogue_edit_is_shipped(self):
        # The shim reads adoption/catalog.json at runtime (adoption-prompts D1),
        # so a new item reaches adopters only in a release.
        self.repo.write("adoption/catalog.json", '{"items": []}\n')
        self.repo.commit_all("Add an adoption item")
        result = self.repo.run("status")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("Add an adoption item", result.stdout)

    def test_archived_change_with_added_requirement_suggests_minor(self):
        self.repo.write("skills/new/SKILL.md", "# New\n")
        self.repo.commit_all("New skill: a thing")
        self.repo.archive_change("new-thing", "Adopters lack a thing. It hurts.")
        result = self.repo.run("status")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("minor", result.stdout)
        self.assertIn("new-thing", result.stdout)

    def test_new_capability_without_added_section_suggests_minor(self):
        self.repo.write("bin/tool", "#!/bin/sh\n")
        self.repo.commit_all("Tool")
        self.repo.archive_change("fresh-cap", "Why.", capability="fresh",
                                 delta="## MODIFIED Requirements")
        doc = release.status_report(self.repo.root)
        self.assertEqual(doc["suggested"], "minor")

    def test_modified_existing_capability_suggests_patch(self):
        self.repo.write("openspec/specs/old/spec.md", "# Spec\n")
        self.repo.commit_all("seed capability")
        self.repo.git("tag", "-d", "v0.4.0")
        self.repo.tag("v0.4.0")
        self.repo.write("bin/tool", "#!/bin/sh\n")
        self.repo.commit_all("Tool fix")
        self.repo.archive_change("fix-old", "Why.", capability="old",
                                 delta="## MODIFIED Requirements")
        doc = release.status_report(self.repo.root)
        self.assertEqual(doc["suggested"], "patch")
        self.assertEqual([c["name"] for c in doc["archived_changes"]], ["fix-old"])

    def test_json_prints_one_document(self):
        self.repo.write("commands/start.md", "start\n")
        self.repo.commit_all("Start command")
        self.repo.archive_change("start-cmd", "Why.")
        result = self.repo.run("status", "--json")
        self.assertEqual(result.returncode, 1, result.stderr)
        doc = json.loads(result.stdout)
        for key in ("tag", "shipped_commits", "archived_changes", "suggested"):
            self.assertIn(key, doc)
        self.assertEqual(doc["tag"], "v0.4.0")
        self.assertEqual([c["subject"] for c in doc["shipped_commits"]], ["Start command"])
        self.assertEqual([c["name"] for c in doc["archived_changes"]], ["start-cmd"])
        self.assertEqual(doc["suggested"], "minor")

    def test_json_when_current(self):
        doc = json.loads(self.repo.run("status", "--json").stdout)
        self.assertEqual(doc["shipped_commits"], [])
        self.assertIsNone(doc["suggested"])


CHANGELOG_SEED = """\
# Changelog

Every release of the plugin, newest first.

## 0.4.0 — 2026-09-29

- workflow packs
"""

RELEASE_DATE = "2026-10-01"


class CutFixture(RepoTestCase):
    """Tagged 0.4.0 with a changelog, then one archived change and one fix shipped."""

    def setUp(self):
        super().setUp()
        self.repo.write("CHANGELOG.md", CHANGELOG_SEED)
        self.repo.commit_all("changelog")
        self.repo.tag("v0.4.0")
        # The squash commit of `new-thing`: it carries the change's tasks.md.
        self.repo.write("skills/new/SKILL.md", "# New\n")
        self.repo.write("openspec/changes/new-thing/tasks.md", "- [x] 1.1\n")
        self.repo.commit_all("New thing: a skill that does it (#9)")
        self.repo.archive_change("new-thing", "Adopters lack a thing.\nIt hurts. A lot.")
        self.repo.write("hooks/brief.sh", "echo fixed\n")
        self.repo.commit_all("Fix the session brief")
        # README.md names the one shipped skill, so the docs check `cut` runs is clean.
        self.repo.write("README.md", "readme: the new skill\n")
        self.repo.commit_all("propose: other-thing")
        self.env = clean_env(GATEDLOOP_RELEASE_DATE=RELEASE_DATE)

    def snapshot(self):
        files = {rel: self.repo.read(rel) for rel in (PLUGIN, MARKET, "CHANGELOG.md")}
        return (files, self.repo.git("rev-parse", "HEAD").stdout,
                self.repo.git("status", "--porcelain").stdout)


class TestCut(CutFixture):
    def test_cut_minor_bumps_fields_and_writes_section(self):
        before = {rel: self.repo.read(rel) for rel in (PLUGIN, MARKET)}
        head = self.repo.git("rev-parse", "HEAD").stdout
        result = self.repo.run("cut", "minor", env=self.env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for rel, text in before.items():
            self.assertEqual(self.repo.read(rel),
                             text.replace('"version": "0.4.0"', '"version": "0.5.0"'))
        self.assertEqual(self.repo.run("check").returncode, 0)
        expected = CHANGELOG_SEED.replace(
            "## 0.4.0",
            f"## 0.5.0 — {RELEASE_DATE}\n\n"
            "- **new-thing**: Adopters lack a thing.\n\n"
            "### Other changes\n\n"
            "- Fix the session brief\n\n"
            "## 0.4.0", 1)
        self.assertEqual(self.repo.read("CHANGELOG.md"), expected)
        self.assertEqual(self.repo.git("rev-parse", "HEAD").stdout, head, "cut must not commit")
        self.assertIn("scripts/release publish", result.stdout)

    def test_refuses_undocumented_command_before_any_write(self):
        # Guards shipping a command the docs never mention: `cut` is the last
        # automated stop before an adopter gets it.
        self.repo.write("commands/merge.md", "merge\n")
        self.repo.commit_all("Merge command")
        before = self.snapshot()
        result = self.repo.run("cut", "minor", env=self.env)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("commands/merge.md:1: undocumented command 'merge'", result.stderr)
        self.assertIn("/release-docs", result.stderr)
        self.assertEqual(self.snapshot(), before)

    def test_docs_check_runs_before_every_other_check(self):
        # Off main and with a gap, the docs gap is what `cut` reports.
        self.repo.write("commands/merge.md", "merge\n")
        self.repo.commit_all("Merge command")
        self.repo.git("checkout", "-q", "-b", "feature")
        result = self.repo.run("cut", "minor", env=self.env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("undocumented command 'merge'", result.stderr)
        self.assertNotIn("releases are cut on", result.stderr)

    def test_schema_change_without_an_adoption_item_warns_and_cuts(self):
        # adoption-prompts D7: a new manifest key is probably a decision for
        # adopters; the cut says so and still completes.
        self.repo.write("schema/gates.schema.json", '{"properties": {}}\n')
        self.repo.commit_all("Add a manifest key")
        result = self.repo.run("cut", "minor", env=self.env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("schema/gates.schema.json", result.stderr)
        self.assertIn("adoption/catalog.json", result.stderr)
        self.assertIn('"version": "0.5.0"', self.repo.read(PLUGIN))

    def test_schema_change_with_an_item_for_the_new_version_does_not_warn(self):
        self.repo.write("schema/gates.schema.json", '{"properties": {}}\n')
        self.repo.write("adoption/catalog.json",
                        json.dumps({"items": [{"id": "new-key", "since": "0.5.0"}]}))
        self.repo.commit_all("Add a manifest key and its adoption item")
        result = self.repo.run("cut", "minor", env=self.env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("adoption", result.stderr)

    def test_cut_patch_and_major(self):
        self.assertEqual(release.next_version("0.4.0", "patch"), "0.4.1")
        self.assertEqual(release.next_version("0.4.7", "minor"), "0.5.0")
        self.assertEqual(release.next_version("0.4.7", "major"), "1.0.0")

    def test_refuses_dirty_tree(self):
        self.repo.write("hooks/brief.sh", "echo uncommitted\n")
        before = self.snapshot()
        result = self.repo.run("cut", "minor", env=self.env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("hooks/brief.sh", result.stderr)
        self.assertEqual(self.snapshot(), before)

    def test_refuses_off_main(self):
        self.repo.git("checkout", "-q", "-b", "feature")
        before = self.snapshot()
        result = self.repo.run("cut", "minor", env=self.env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("main", result.stderr)
        self.assertEqual(self.snapshot(), before)

    def test_refuses_when_nothing_to_release(self):
        self.repo.set_all_versions("0.4.0", "0.4.1")
        self.repo.commit_all("Release 0.4.1")
        self.repo.tag("v0.4.1")
        before = self.snapshot()
        result = self.repo.run("cut", "minor", env=self.env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("nothing", result.stderr)
        self.assertEqual(self.snapshot(), before)

    def test_refuses_existing_section(self):
        self.repo.write("CHANGELOG.md", CHANGELOG_SEED.replace(
            "## 0.4.0", "## 0.5.0 — 2026-09-30\n\n- drafted\n\n## 0.4.0"))
        self.repo.commit_all("changelog draft")
        before = self.snapshot()
        result = self.repo.run("cut", "minor", env=self.env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("0.5.0", result.stderr)
        self.assertEqual(self.snapshot(), before)


GH_STUB = """\
#!{python}
# A `gh` stand-in: logs each call (and the notes file's content) and never
# talks to a forge.
import json, os, sys
args = sys.argv[1:]
entry = {{"args": args}}
if "--notes-file" in args:
    with open(args[args.index("--notes-file") + 1]) as fh:
        entry["notes"] = fh.read()
with open(os.environ["GH_STUB_LOG"], "a") as fh:
    fh.write(json.dumps(entry) + "\\n")
if args[:2] == ["auth", "status"]:
    sys.exit(int(os.environ.get("GH_STUB_AUTH_EXIT", "0")))
"""


class TestPublish(CutFixture):
    """`publish`, against a bare repo as `origin` and a `gh` stub on PATH."""

    def setUp(self):
        super().setUp()
        self.origin = self.tmp / "origin.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(self.origin)],
                       check=True, env=clean_env(), capture_output=True)
        self.repo.git("remote", "add", "origin", str(self.origin))
        self.repo.git("push", "-q", "origin", "main", "--tags")
        stub_dir = self.tmp / "stub-bin"
        stub_dir.mkdir()
        stub = stub_dir / "gh"
        stub.write_text(GH_STUB.format(python=sys.executable))
        stub.chmod(0o755)
        self.gh_log = self.tmp / "gh.log"
        self.env = clean_env(PATH=f"{stub_dir}{os.pathsep}{os.environ.get('PATH', '')}",
                             GH_STUB_LOG=str(self.gh_log),
                             GATEDLOOP_RELEASE_DATE=RELEASE_DATE)
        cut = self.repo.run("cut", "minor", env=self.env)
        self.assertEqual(cut.returncode, 0, cut.stdout + cut.stderr)
        self.head = self.repo.git("rev-parse", "HEAD").stdout.strip()

    def gh_calls(self):
        if not self.gh_log.exists():
            return []
        return [json.loads(line) for line in self.gh_log.read_text().splitlines()]

    def origin_git(self, *args):
        return subprocess.run(["git", *args], cwd=self.origin, env=clean_env(),
                              capture_output=True, text=True)

    def expected_notes(self):
        text = self.repo.read("CHANGELOG.md")
        start = text.index("## 0.5.0")
        end = text.index("## 0.4.0")
        return text[start:end].rstrip() + "\n"

    def assert_nothing_written(self, result):
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.repo.git("rev-parse", "HEAD").stdout.strip(), self.head)
        self.assertEqual(self.repo.git("tag", "--list", "v0.5.0").stdout.strip(), "")
        self.assertNotIn("release", [c["args"][0] for c in self.gh_calls()])

    def test_full_publish(self):
        notes = self.expected_notes()
        result = self.repo.run("publish", env=self.env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        log = self.origin_git("log", "--format=%s", f"{self.head}..main").stdout.splitlines()
        self.assertEqual(log, ["Release 0.5.0"])
        self.assertEqual(self.origin_git("cat-file", "-t", "v0.5.0").stdout.strip(), "tag")
        self.assertEqual(self.origin_git("rev-parse", "v0.5.0^{commit}").stdout,
                         self.origin_git("rev-parse", "main").stdout)
        creates = [c for c in self.gh_calls() if c["args"][:2] == ["release", "create"]]
        self.assertEqual(len(creates), 1)
        args = creates[0]["args"]
        self.assertEqual(args[:5], ["release", "create", "v0.5.0", "--title", "gatedloop 0.5.0"])
        self.assertEqual(args[5], "--notes-file")
        self.assertEqual(creates[0]["notes"], notes)
        self.assertEqual(self.repo.git("status", "--porcelain").stdout, "")

    def test_gh_not_authenticated_writes_nothing(self):
        env = dict(self.env, GH_STUB_AUTH_EXIT="1")
        status = self.repo.git("status", "--porcelain").stdout
        result = self.repo.run("publish", env=env)
        self.assert_nothing_written(result)
        self.assertIn("gh auth", result.stderr)
        self.assertEqual(self.repo.git("status", "--porcelain").stdout, status)

    def test_existing_local_tag_refuses(self):
        self.repo.tag("v0.5.0")
        result = self.repo.run("publish", env=self.env)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.repo.git("rev-parse", "HEAD").stdout.strip(), self.head)
        self.assertIn("v0.5.0", result.stderr)

    def test_existing_remote_tag_refuses(self):
        self.repo.tag("v0.5.0")
        self.repo.git("push", "-q", "origin", "v0.5.0")
        self.repo.git("tag", "-d", "v0.5.0")
        result = self.repo.run("publish", env=self.env)
        self.assert_nothing_written(result)
        self.assertIn("v0.5.0", result.stderr)

    def test_unexpected_changed_path_refuses(self):
        self.repo.write("hooks/brief.sh", "echo sneaked in\n")
        result = self.repo.run("publish", env=self.env)
        self.assert_nothing_written(result)
        self.assertIn("hooks/brief.sh", result.stderr)

    def test_adoption_item_for_a_later_release_refuses_naming_it(self):
        # adoption-prompts D1 "Unreleased items": after `cut`, every item for
        # this release carries exactly its version; one tagged later must not
        # ship to adopters as if it were released.
        catalog = {"items": [{"id": "this-release", "since": "0.5.0"},
                             {"id": "next-release", "since": "0.6.0"}]}
        self.repo.write("adoption/catalog.json", json.dumps(catalog))
        self.repo.git("add", "adoption/catalog.json")
        self.repo.git("commit", "-q", "-m", "adoption items")
        self.repo.git("push", "-q", "origin", "main")
        self.head = self.repo.git("rev-parse", "HEAD").stdout.strip()
        result = self.repo.run("publish", env=self.env)
        self.assert_nothing_written(result)
        self.assertIn("next-release", result.stderr)
        self.assertNotIn("this-release", result.stderr)

    def test_push_failure_after_commit_leaves_no_tag_and_prints_resume(self):
        hook = self.origin / "hooks" / "pre-receive"
        hook.write_text("#!/bin/sh\necho rejected by test >&2\nexit 1\n")
        hook.chmod(0o755)
        result = self.repo.run("publish", env=self.env)
        self.assertNotEqual(result.returncode, 0)
        out = result.stdout + result.stderr
        self.assertEqual(self.repo.git("log", "-1", "--format=%s").stdout.strip(), "Release 0.5.0")
        self.assertEqual(self.repo.git("tag", "--list", "v0.5.0").stdout.strip(), "")
        self.assertEqual(self.origin_git("tag", "--list", "v0.5.0").stdout.strip(), "")
        self.assertIn("exists locally", out)
        self.assertIn("no tag", out)
        self.assertIn("git push origin main", out)
        self.assertNotIn("release", [c["args"][0] for c in self.gh_calls()])


    # release-push D1: `publish` refuses inside an agent session, before any
    # write, and hands the maintainer the notes file and the exact commands.
    NOTES = ".gatedloop/out/release-notes-v0.5.0.md"

    def test_publish_from_an_agent_session_writes_nothing_but_the_notes(self):
        # Scenario "Publish from an agent session".
        notes = self.expected_notes()
        result = self.repo.run("publish", env=dict(self.env, CLAUDECODE="1"))
        self.assert_nothing_written(result)
        self.assertEqual(self.origin_git("log", "--format=%s", f"{self.head}..main").stdout, "")
        self.assertIn("agent session", result.stderr)
        self.assertEqual(self.repo.read(self.NOTES), notes)
        lines = [ln.strip() for ln in result.stderr.splitlines() if ln.strip()]
        sequence = next(ln for ln in lines if ln.startswith("git add"))
        self.assertIn("git commit -q -m 'Release 0.5.0'", sequence)
        self.assertLess(sequence.index("git push origin main"),
                        sequence.index("git tag -a v0.5.0"))
        self.assertTrue(sequence.endswith(f"--notes-file {self.NOTES}"), sequence)
        self.assertNotIn("env -u", result.stderr)

    def test_publish_outside_an_agent_session_still_publishes(self):
        # Scenario "Publish outside an agent session": the fixture's env
        # carries no agent-env variable.
        self.assertNotIn("CLAUDECODE", self.env)
        result = self.repo.run("publish", env=self.env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.origin_git("cat-file", "-t", "v0.5.0").stdout.strip(), "tag")

class TestReminderHook(RepoTestCase):
    """`status --hook`: one line of SessionStart context, or nothing, never a block."""

    def setUp(self):
        super().setUp()
        self.repo.tag("v0.4.0")

    def test_unreleased_work_injects_one_line(self):
        self.repo.write("skills/new/SKILL.md", "# New\n")
        self.repo.commit_all("New skill")
        self.repo.archive_change("new-thing", "Why.")
        result = self.repo.run("status", "--hook")
        self.assertEqual(result.returncode, 0, result.stderr)
        doc = json.loads(result.stdout)
        out = doc["hookSpecificOutput"]
        self.assertEqual(out["hookEventName"], "SessionStart")
        line = out["additionalContext"]
        self.assertNotIn("\n", line)
        self.assertIn("v0.4.0", line)
        self.assertIn("1 archived change", line)
        self.assertIn("1 shipped commit", line)
        self.assertIn("minor", line)
        self.assertIn("scripts/release cut minor", line)
        self.assertLess(line.index("/release-docs"), line.index("scripts/release cut minor"),
                        "the reminder names the docs pass before cut")

    def test_current_release_prints_nothing(self):
        result = self.repo.run("status", "--hook")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_outside_a_git_repo_prints_nothing(self):
        outside = self.tmp / "not-a-repo"
        outside.mkdir()
        result = subprocess.run([sys.executable, str(RELEASE_SCRIPT), "status", "--hook"],
                                cwd=outside, env=clean_env(GIT_CEILING_DIRECTORIES=str(self.tmp)),
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_a_status_error_prints_nothing(self):
        self.repo.write("hooks/x.sh", "x\n")
        self.repo.commit_all("x")
        self.repo.git("tag", "-d", "v0.4.0")
        result = self.repo.run("status", "--hook")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")


class TestChangelog(CutFixture):
    """The backfilled CHANGELOG.md, and `cut` inserting above it."""

    HEADING = r"^## (\d+\.\d+\.\d+) — (\d{4}-\d{2}-\d{2})$"

    def test_backfilled_sections_newest_first(self):
        text = (REPO / "CHANGELOG.md").read_text()
        headings = re.findall(r"^## .*$", text, re.MULTILINE)
        for heading in headings:
            self.assertRegex(heading, self.HEADING)
        versions = [re.match(self.HEADING, h).group(1) for h in headings]
        self.assertEqual(versions[-3:], ["0.4.0", "0.3.0", "0.2.0"])

    def test_cut_inserts_above_the_real_changelog(self):
        real = (REPO / "CHANGELOG.md").read_text()
        # The real changelog as of the fixture's baseline: sections for
        # releases after it are dropped, so `cut minor` from 0.4.0 has a place
        # to insert 0.5.0 whatever the repository has released since.
        real = real[: real.index("\n## ") + 1] + real[real.index(f"\n## {BASELINE} ") + 1:]
        self.repo.write("CHANGELOG.md", real)
        self.repo.commit_all("changelog: real copy")
        result = self.repo.run("cut", "minor", env=self.env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        text = self.repo.read("CHANGELOG.md")
        top = real.index("\n## ") + 1
        self.assertTrue(text.startswith(real[:top] + f"## 0.5.0 — {RELEASE_DATE}\n"))
        self.assertTrue(text.endswith("\n" + real[top:]))


class TestReminderPlacement(unittest.TestCase):
    """The reminder lives in this repo's project settings, never in the plugin's hooks."""

    def test_project_settings_run_the_reminder(self):
        settings = json.loads((REPO / ".claude" / "settings.json").read_text())
        commands = [h["command"] for group in settings["hooks"]["SessionStart"]
                    for h in group["hooks"]]
        self.assertIn('python3 "$CLAUDE_PROJECT_DIR/scripts/release" status --hook', commands)

    def test_plugin_hooks_carry_no_release_reminder(self):
        self.assertNotIn("scripts/release", (REPO / "hooks" / "hooks.json").read_text())


SHIM_STUB = """\
#!/usr/bin/env python3
# A `bin/gates` stand-in: only its --help choice list matters to the inventory.
print("usage: gates [-h]\\n             {init,run,gate-marker} ...")
"""

SCHEMA_STUB = {"properties": {"gatesVersion": {}, "surfaces": {},
                              "gates": {"properties": {"ci": {}, "unit": {}}}}}

README_CLEAN = """\
# Plugin

Run `/gatedloop:start`, or `/gatedloop:tdd-apply` for the loop. The
convention-review agent and the verify skill review each task.

```bash
gates init
gates run ci
```

Set `gatesVersion`, declare `surfaces`, and map the `ci` and `unit` gates
under `gates`. The gates are cheap.
"""


class DocsFixture(RepoTestCase):
    """A plugin tree whose README.md mentions every inventory item."""

    def setUp(self):
        super().setUp()
        self.repo.write("commands/start.md", "start\n")
        self.repo.write("agents/convention-review.md", "agent\n")
        self.repo.write("skills/tdd-apply/SKILL.md", "skill\n")
        self.repo.write("skills/verify/SKILL.md", "skill\n")
        self.repo.write("bin/gates", SHIM_STUB)
        self.repo.write("schema/gates.schema.json", json.dumps(SCHEMA_STUB))
        self.repo.write("README.md", README_CLEAN)
        self.repo.write("SETUP.md", "# Setup\n")


class TestDocs(DocsFixture):
    """`docs`: README.md and SETUP.md against the inventory, both directions."""

    def test_complete_docs_pass(self):
        # Guards a false alarm: prose "gates are", an exempt subcommand and a
        # /gatedloop:<skill> reference must not be reported, or `cut` never runs.
        result = self.repo.run("docs")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.count("\n"), 1, result.stdout)

    def test_undocumented_command_is_reported_with_its_file(self):
        # Guards the drift this check exists for: a command ships, no doc names it.
        self.repo.write("commands/merge.md", "merge\n")
        result = self.repo.run("docs")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(result.stdout.splitlines(),
                         ["commands/merge.md:1: undocumented command 'merge': "
                          "neither README.md nor SETUP.md mentions it"])

    def test_undocumented_manifest_key_and_gate_are_reported(self):
        self.repo.write("README.md", README_CLEAN.replace("declare `surfaces`, ", "")
                        .replace("the `ci` and `unit` gates", "the `ci` gate"))
        result = self.repo.run("docs")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        out = result.stdout
        self.assertIn("undocumented manifest key 'surfaces'", out)
        self.assertIn("undocumented gate 'unit'", out)
        self.assertIn("schema/gates.schema.json:", out)

    def test_stale_gates_subcommand_is_reported_with_file_and_line(self):
        # Guards a removed or renamed subcommand the docs still teach.
        self.repo.write("SETUP.md", "# Setup\n\nThe gates are fine.\n\n```bash\n"
                                    "gates frobnicate --all\n```\n")
        result = self.repo.run("docs")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(result.stdout.splitlines(),
                         ["SETUP.md:6: stale mention 'gates frobnicate': "
                          "bin/gates has no such subcommand"])

    def test_stale_gatedloop_command_is_reported(self):
        self.repo.write("SETUP.md", "# Setup\n\nRun `/gatedloop:frobnicate`.\n")
        result = self.repo.run("docs")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("SETUP.md:3: stale mention '/gatedloop:frobnicate'", result.stdout)

    def test_exempt_subcommand_is_skipped_but_others_are_not(self):
        # Guards the exemption from swallowing its neighbours: `gate-marker` is
        # exempt, `run` is not.
        self.assertIn(("gates subcommand", "gate-marker"), release.DOCS_EXEMPT)
        self.repo.write("README.md", README_CLEAN.replace("gates run ci\n", ""))
        result = self.repo.run("docs")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("undocumented gates subcommand 'run'", result.stdout)
        self.assertNotIn("gate-marker", result.stdout)

    def test_missing_schema_fails_loud(self):
        # Guards a moved schema silently dropping every gate and manifest-key check.
        (self.repo.root / "schema/gates.schema.json").unlink()
        result = self.repo.run("docs")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("schema/gates.schema.json", result.stderr)

    def test_exempt_retired_name_may_stay_in_a_migration_table(self):
        # Guards the migration tables: a retired name listed in DOCS_EXEMPT is
        # not stale, while an unlisted one still is.
        self.repo.write("SETUP.md", "| Was | Now |\n|---|---|\n"
                                    "| `/gatedloop:old-init` | `/gatedloop:start` |\n"
                                    "| `/gatedloop:gone` | nothing |\n")
        exempt = {("command", "old-init"): "retired; kept in the migration table"}
        with unittest.mock.patch.dict(release.DOCS_EXEMPT, exempt):
            gaps = release.docs_gaps(self.repo.root)
        self.assertEqual(gaps, ["SETUP.md:4: stale mention '/gatedloop:gone': "
                                "no such command or skill"])


class TestFirstSentence(unittest.TestCase):
    def test_joins_lines_and_cuts_at_first_sentence(self):
        text = "# P\n\n## Why\n\nClaude Code uses a\nversion field. More here.\n\n## What\n"
        self.assertEqual(release.first_why_sentence(text), "Claude Code uses a version field.")

    def test_cuts_at_200_characters(self):
        text = "## Why\n\n" + "word " * 100 + "\n"
        sentence = release.first_why_sentence(text)
        self.assertLessEqual(len(sentence), 201)
        self.assertTrue(sentence.endswith("…"))

    def test_missing_why(self):
        self.assertIsNone(release.first_why_sentence("# P\n\n## What Changes\n\n- x\n"))


if __name__ == "__main__":
    unittest.main()
