"""A change that rewrites existing tests, end to end (openspec change
`test-rewrites`, task 5.1; design "How it connects end to end").

One fixture change on a real repository with a bare `origin`, implemented in a
linked lane worktree: task 1.1 is a red-first rewrite of an existing test, 1.2
a `characterization` rewrite (it only drops a timing assertion), and 1.3 an
untagged task whose author overwrites an existing test without declaring it.
The brief, the handoff (with its advisory line), each placement, each red or
green step and each commit are driven as the loop drives them, and the lock is
checked at every commit and on the head; then `gates merge` proves the head
(step 1) and integrates. Every step must exit 0.

A characterization test: everything here composes behaviour the earlier tasks
of `test-rewrites` built, so it passes on its first run.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _merge_fixture import CHANGE, MergeRepo, combined, git

MANIFEST = 'gatesVersion: 1\ngates:\n  ci: "true"\n  unit: "sh scripts/unit.sh"\n'

# `unit` is red while any test asks for a token (`WANT:<token>`) the
# implementation does not yet hold.
UNIT_SH = """\
for want in $(grep -ho 'WANT:[a-z]*' tests/*.ts 2>/dev/null | sed 's/WANT://'); do
  grep -q "$want" src/impl.txt 2>/dev/null || exit 1
done
exit 0
"""

TASKS = """\
## 1. Rework the toolbar

- [ ] 1.1 Move the shortcut from E to K [oracle: unit rewrites: tests/toolbar.test.ts]
- [ ] 1.2 Drop the wall-clock assertion from the menu test [oracle: unit characterization rewrites: tests/menu.test.ts]
- [ ] 1.3 Rework the footer
"""

TOOLBAR_BASE = "test('opens')\ntest('key E')\n"
TOOLBAR_NEW = "test('opens')\ntest('key K') // WANT:keyk\n"
MENU_BASE = "test('menu')\nexpect(ms).toBeLessThan(5)\n"
MENU_NEW = "test('menu')\n"
FOOTER_BASE = "test('FOOTER-BASE-CONTENT')\n"
FOOTER_NEW = "test('footer v2') // WANT:footer\n"


class RewriteRepo(MergeRepo):
    def __init__(self, tmp: Path):
        super().__init__(tmp, manifest=MANIFEST)
        p = self.primary
        for rel, text in {
            "scripts/unit.sh": UNIT_SH,
            "src/impl.txt": "base\n",
            "tests/toolbar.test.ts": TOOLBAR_BASE,
            "tests/menu.test.ts": MENU_BASE,
            "tests/footer.test.ts": FOOTER_BASE,
            f"openspec/changes/{CHANGE}/tasks.md": TASKS,
        }.items():
            (p / rel).parent.mkdir(parents=True, exist_ok=True)
            (p / rel).write_text(text)
        self.approve_plan()
        git(p, "add", "-A")
        git(p, "commit", "-q", "-m", "plan: rewrite the toolbar tests")
        git(p, "push", "-q", "origin", "HEAD:main")
        self.push_log.write_text("")

    def must(self, *args):
        r = self.gates(*args, cwd=self.lane)
        if r.returncode != 0:
            raise AssertionError(f"`gates {' '.join(args)}` exited {r.returncode}: {combined(r)}")
        return r

    def write(self, rel, text):
        f = self.lane / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text)

    def commit(self, subject, task=None):
        git(self.lane, "add", "-A")
        self.must("run", "ci", *(["--task", task] if task else []))
        git(self.lane, "add", "-A")
        self.must("tests", "check")
        git(self.lane, "commit", "-q", "-m", subject)
        self.must("tests", "check", "--ref", "HEAD", "--change", CHANGE)

    def tick(self, task):
        rel = f"openspec/changes/{CHANGE}/tasks.md"
        text = (self.lane / rel).read_text()
        (self.lane / rel).write_text(text.replace(f"- [ ] {task} ", f"- [x] {task} "))


class RewriteEndToEnd(unittest.TestCase):
    def test_the_whole_route_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = RewriteRepo(Path(tmp))
            repo.start_change(lane=True)

            brief = repo.must("tests", "brief", CHANGE).stdout
            self.assertIn("## Declared rewrites", brief)
            self.assertIn("test('key E')", brief)
            self.assertIn("expect(ms).toBeLessThan(5)", brief)
            self.assertNotIn("FOOTER-BASE-CONTENT", brief)

            held = f".gatedloop/authored/{CHANGE}"
            repo.write(f"{held}/1.1/tests/toolbar.test.ts.authored", TOOLBAR_NEW)
            repo.write(f"{held}/1.2/tests/menu.test.ts.authored", MENU_NEW)
            repo.write(f"{held}/1.2/CHARACTERIZATION", "drops a wall-clock assertion only\n")
            repo.write(f"{held}/1.3/tests/footer.test.ts.authored", FOOTER_NEW)
            handed = repo.must("tests", "handoff", CHANGE)
            out = combined(handed)
            self.assertIn("1.3", out)
            self.assertIn("tests/footer.test.ts", out)
            self.assertIn("without declaring", out)
            self.assertNotIn("overwrites existing tests/toolbar.test.ts", out)

            diff = repo.must("tests", "show", CHANGE, "--diff").stdout
            self.assertIn("-test('key E')", diff)
            self.assertIn("-expect(ms).toBeLessThan(5)", diff)
            repo.commit(f"author tests: {CHANGE}")

            # 1.1: red first on the rewrite, then green.
            repo.must("task", "start", "1.1")
            repo.must("tests", "place", "1.1")
            self.assertEqual((repo.lane / "tests/toolbar.test.ts").read_text(), TOOLBAR_NEW)
            red = repo.gates("run", "unit", "--task", "1.1", "--attempt", "1", cwd=repo.lane)
            self.assertNotIn(red.returncode, (0, 75), combined(red))
            repo.write("src/impl.txt", "base\nkeyk\n")
            repo.must("run", "unit", "--task", "1.1", "--attempt", "1")
            repo.tick("1.1")
            repo.commit("task 1.1", "1.1")

            # 1.2: a characterization rewrite, green first.
            repo.must("task", "start", "1.2")
            repo.must("tests", "place", "1.2")
            self.assertEqual((repo.lane / "tests/menu.test.ts").read_text(), MENU_NEW)
            repo.must("run", "unit", "--task", "1.2", "--attempt", "1")
            repo.tick("1.2")
            repo.commit("task 1.2", "1.2")

            # 1.3: the undeclared overwrite is placed and locked as before.
            repo.must("task", "start", "1.3")
            repo.must("tests", "place", "1.3")
            red = repo.gates("run", "unit", "--task", "1.3", "--attempt", "1", cwd=repo.lane)
            self.assertNotIn(red.returncode, (0, 75), combined(red))
            repo.write("src/impl.txt", "base\nkeyk\nfooter\n")
            repo.must("run", "unit", "--task", "1.3", "--attempt", "1")
            repo.tick("1.3")
            repo.commit("task 1.3", "1.3")

            repo.prove_head()
            merged = repo.merge()
            self.assertEqual(merged.returncode, 0, combined(merged))
            self.assertEqual(git(repo.primary, "show", "origin/main:tests/toolbar.test.ts") + "\n",
                             TOOLBAR_NEW)


if __name__ == "__main__":
    unittest.main()
