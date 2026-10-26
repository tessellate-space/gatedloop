"""The `git-hook-current` detector and the `git-hook-copy` predicate
(openspec change `adoption-followups`, design D2), both covering the push hook
too, and the `git-push-hook-installed` detector and `git-commit-hook-wired`
predicate (`git-layer-enforcement`, design D4).

Stdlib only, per `zero-dep-shim`. The evaluators are pure and are tested on
facts; the one gathered fact, `facts["hook"]`, is tested in throwaway git
repos. Nothing here touches this repository's own `.git/hooks`.

Run with:  python3 -m unittest discover -s tests
"""

import copy
import importlib.machinery
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _hook_fixture import (GATES_SHIM, OLDER_COPY, OLDER_PUSH_COPY, PUSH_TEMPLATE,  # noqa: E402
                           TEMPLATE, composed_husky_hook, default_hook, init_repo,
                           write_hook)

_loader = importlib.machinery.SourceFileLoader("gates_shim_adoption_hook_kinds", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)

ITEM = {
    "id": "git-hook-refresh",
    "since": "0.5.0",
    "what": "Refresh the installed copy of the git hook.",
    "question": "Refresh it?",
    "options": [
        {"answer": "adopted", "label": "Refresh it (Recommended)"},
        {"answer": "declined", "label": "No"},
    ],
    "detector": {"kind": "git-hook-current"},
    "applies_when": {"kind": "git-hook-copy"},
    "action": {"kind": "onboarding-step", "step": "gates-init hook step"},
}


def facts(copy_=False, current=False, push_copy=False, push_current=False,
          commit_state="absent", push_state="absent"):
    return {"manifest": {}, "rules_doc": None, "schemas": [], "existing_globs": set(),
            "hook": {"copy": copy_, "current": current},
            "push_hook": {"copy": push_copy, "current": push_current},
            "hook_states": {"pre-commit": commit_state, "pre-push": push_state}}


class TestDetectorGitHookCurrent(unittest.TestCase):
    """D2: acted unless the hook path holds a direct copy that is not current."""

    def test_acted_unless_a_stale_copy(self):
        # Fails if a stale copy counted as acted (the refresh is never
        # offered), or if no copy at all counted as not acted (a project with
        # a composed hook, or none, would be nagged to refresh nothing).
        cases = (
            (facts(copy_=True, current=False), False),
            (facts(copy_=True, current=True), True),
            (facts(copy_=False), True),
            # git-layer-enforcement D4: either hook's stale copy needs the
            # refresh. Fails if the detector still read the commit hook alone.
            (facts(copy_=True, current=True, push_copy=True, push_current=False), False),
            (facts(push_copy=True, push_current=False), False),
            (facts(copy_=True, current=True, push_copy=True, push_current=True), True),
        )
        for f, acted in cases:
            with self.subTest(hook=f["hook"], push_hook=f["push_hook"]):
                self.assertIs(gates.adoption_detector_acted({"kind": "git-hook-current"}, f), acted)

    def test_facts_without_a_push_hook_entry_read_as_no_copy(self):
        # Facts gathered by an older caller carry no `push_hook`; the
        # detector must not fail on them.
        f = facts(copy_=True, current=True)
        del f["push_hook"]
        self.assertIs(gates.adoption_detector_acted({"kind": "git-hook-current"}, f), True)


class TestPredicateGitHookCopy(unittest.TestCase):
    """D2: holds exactly when the hook path holds a direct copy, current or not."""

    def test_holds_only_for_a_copy(self):
        cases = (
            (facts(copy_=True, current=False), True),
            (facts(copy_=True, current=True), True),
            (facts(copy_=False), False),
            (facts(push_copy=True), True),
        )
        for f, holds in cases:
            with self.subTest(hook=f["hook"], push_hook=f["push_hook"]):
                self.assertIs(gates.adoption_applies({"kind": "git-hook-copy"}, f), holds)


class TestThePushHookItemKinds(unittest.TestCase):
    """D4: the `git-push-hook` item applies when the commit hook is wired, and
    is acted on once the push hook is anything but absent."""

    def test_detector_acted_unless_the_push_hook_is_absent(self):
        for state in ("wired", "stale-copy", "manager-uncomposed", "unmanaged-hook", "absent"):
            with self.subTest(push_state=state):
                self.assertIs(
                    gates.adoption_detector_acted({"kind": "git-push-hook-installed"},
                                                  facts(push_state=state)),
                    state != "absent")

    def test_predicate_holds_only_for_a_wired_commit_hook(self):
        # Fails if a project with no commit hook (or one it cannot run) were
        # asked about the push hook alone.
        for state in ("wired", "stale-copy", "manager-uncomposed", "unmanaged-hook", "absent"):
            with self.subTest(commit_state=state):
                self.assertIs(
                    gates.adoption_applies({"kind": "git-commit-hook-wired"},
                                           facts(commit_state=state)),
                    state == "wired")


class TestLoaderAcceptsTheNewKinds(unittest.TestCase):
    """The closed sets grow by one kind each; anything else still fails loud."""

    def test_item_with_both_kinds_loads(self):
        items = gates.load_adoption_catalog({"items": [copy.deepcopy(ITEM)]})
        self.assertEqual([i["id"] for i in items], ["git-hook-refresh"])

    def test_the_push_hook_kinds_load(self):
        item = copy.deepcopy(ITEM)
        item.update(id="git-push-hook", detector={"kind": "git-push-hook-installed"},
                    applies_when={"kind": "git-commit-hook-wired"})
        items = gates.load_adoption_catalog({"items": [item]})
        self.assertEqual([i["id"] for i in items], ["git-push-hook"])

    def test_unknown_kind_still_refused(self):
        for field in ("detector", "applies_when"):
            with self.subTest(field=field):
                item = copy.deepcopy(ITEM)
                item[field] = {"kind": "git-hook-telepathy"}
                with self.assertRaises(gates.AdoptionError) as ctx:
                    gates.load_adoption_catalog({"items": [item]})
                self.assertIn("git-hook-refresh", str(ctx.exception))
                self.assertIn("git-hook-telepathy", str(ctx.exception))


class TestHookFactIsGathered(unittest.TestCase):
    """D2: `facts["hook"]` is gathered once, by the code path `gates doctor`
    reads, so the upgrade walk and the doctor never disagree about a hook."""

    def hook_fact(self, setup, key="hook"):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_repo(root)
            setup(root)
            return gates._adoption_project_facts(root, {}, [])[key]

    def test_each_hook_shape(self):
        cases = (
            ("stale copy", lambda r: write_hook(default_hook(r), OLDER_COPY),
             {"copy": True, "current": False}),
            ("current copy", lambda r: write_hook(default_hook(r), TEMPLATE.read_bytes()),
             {"copy": True, "current": True}),
            ("composed", lambda r: composed_husky_hook(r, gates._composed_hook_snippet()),
             {"copy": False}),
            ("no hook", lambda r: None, {"copy": False}),
        )
        for name, setup, expected in cases:
            with self.subTest(hook=name):
                fact = self.hook_fact(setup)
                self.assertEqual({k: fact[k] for k in expected}, expected)

    def test_each_push_hook_shape(self):
        cases = (
            ("stale copy", lambda r: write_hook(default_hook(r, "pre-push"), OLDER_PUSH_COPY),
             {"copy": True, "current": False}),
            ("current copy", lambda r: write_hook(default_hook(r, "pre-push"),
                                                  PUSH_TEMPLATE.read_bytes()),
             {"copy": True, "current": True}),
            ("no hook", lambda r: None, {"copy": False}),
        )
        for name, setup, expected in cases:
            with self.subTest(hook=name):
                fact = self.hook_fact(setup, "push_hook")
                self.assertEqual({k: fact[k] for k in expected}, expected)

    def test_both_hook_states_are_gathered(self):
        # The same states `gates doctor` reports, so the walk and the doctor
        # agree on what is installed.
        states = self.hook_fact(
            lambda r: write_hook(default_hook(r), TEMPLATE.read_bytes()), "hook_states")
        self.assertEqual(states, {"pre-commit": "wired", "pre-push": "absent"})


if __name__ == "__main__":
    unittest.main()
