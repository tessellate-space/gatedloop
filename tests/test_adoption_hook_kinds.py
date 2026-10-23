"""The `git-hook-current` detector and the `git-hook-copy` predicate
(openspec change `adoption-followups`, design D2).

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
from _hook_fixture import (GATES_SHIM, OLDER_COPY, TEMPLATE, composed_husky_hook,  # noqa: E402
                           default_hook, init_repo, write_hook)

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


def facts(copy_=False, current=False):
    return {"manifest": {}, "rules_doc": None, "schemas": [], "existing_globs": set(),
            "hook": {"copy": copy_, "current": current}}


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
        )
        for f, acted in cases:
            with self.subTest(hook=f["hook"]):
                self.assertIs(gates.adoption_detector_acted({"kind": "git-hook-current"}, f), acted)


class TestPredicateGitHookCopy(unittest.TestCase):
    """D2: holds exactly when the hook path holds a direct copy, current or not."""

    def test_holds_only_for_a_copy(self):
        cases = (
            (facts(copy_=True, current=False), True),
            (facts(copy_=True, current=True), True),
            (facts(copy_=False), False),
        )
        for f, holds in cases:
            with self.subTest(hook=f["hook"]):
                self.assertIs(gates.adoption_applies({"kind": "git-hook-copy"}, f), holds)


class TestLoaderAcceptsTheNewKinds(unittest.TestCase):
    """The closed sets grow by one kind each; anything else still fails loud."""

    def test_item_with_both_kinds_loads(self):
        items = gates.load_adoption_catalog({"items": [copy.deepcopy(ITEM)]})
        self.assertEqual([i["id"] for i in items], ["git-hook-refresh"])

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

    def hook_fact(self, setup):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_repo(root)
            setup(root)
            return gates._adoption_project_facts(root, {}, [])["hook"]

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


if __name__ == "__main__":
    unittest.main()
