"""A declared `loop.plan-preflight.classifier` command (openspec change
`plan-preflight`, design D3 "Layer 2"; task 5.4).

`gates plan tier` runs it with `{digest, dimensions}` on stdin, in the
repository root, under `classifier-timeout`, with the shim's environment
passed through; its stderr goes to `.gatedloop/out/plan-classifier-<ts>.log`
only. A valid verdict is provider `external`; anything else falls back to
the built-in lens with a visible cause. The effective tier is the higher of
the floor and the verdict.

Stdlib only, per `zero-dep-shim`. Real git repositories, fixture classifier
commands, the shim driven as a subprocess. Run with:
python3 -m unittest discover -s tests
"""

from __future__ import annotations

import json
import shlex
import sys
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

from _preflight_fixture import CHANGE, MANIFEST, PreflightRepo, write  # noqa: E402

CLASSIFIER = """\
import os, sys
data = sys.stdin.buffer.read()
open(os.environ["PF_STDIN_FILE"], "wb").write(data)
open(os.environ["PF_ENV_FILE"], "w").write(os.environ.get("PF_SECRETLESS_MARK", "<unset>"))
sys.stderr.write("classifier diagnostics: STDERR-MARK\\n")
mode = sys.argv[1]
if mode == "sleep":
    import time; time.sleep(30)
elif mode == "fail":
    sys.exit(3)
elif mode == "garbage":
    print("not json at all")
elif mode == "badtier":
    print('{"tier": "medium", "confidence": null, "evidence": []}')
else:
    print('{"tier": "%s", "confidence": 0.7, "evidence": [], "reason": "fixture"}' % mode)
"""

MODIFIED_SPEC = "# Spec Delta\n\n## MODIFIED Requirements\n\n### Requirement: X\n\nY.\n"


class ClassifierCommandTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.script = write(self.tmp, "fixture/classify.py", CLASSIFIER)

    def tearDown(self):
        self._tmp.cleanup()

    def repo_manifest(self, mode: str | None, timeout: int | None = None) -> str:
        block = ""
        if mode is not None:
            cmd = f"{shlex.quote(sys.executable)} {shlex.quote(str(self.script))} {mode}"
            block = "loop:\n  plan-preflight:\n    classifier: " + json.dumps(cmd) + "\n"
            if timeout:
                block += f"    classifier-timeout: {timeout}\n"
        return MANIFEST + block

    def repo(self, mode: str | None, timeout: int | None = None, **kw) -> PreflightRepo:
        return PreflightRepo(self.tmp / "work", manifest=self.repo_manifest(mode, timeout), **kw)

    def tier(self, r: PreflightRepo, **env) -> tuple[dict, str]:
        env.setdefault("PF_STDIN_FILE", str(self.tmp / "stdin.bin"))
        env.setdefault("PF_ENV_FILE", str(self.tmp / "env.txt"))
        out = r.gates("plan", "tier", CHANGE, "--json", **env)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        return json.loads(out.stdout), out.stdout + out.stderr

    def test_a_full_verdict_raises_a_light_floor(self):
        doc, _ = self.tier(self.repo("full"))
        self.assertEqual((doc["floor"], doc["tier"]), ("light", "full"))
        c = doc["classifier"]
        self.assertEqual((c["provider"], c["cause"], c["tier"], c["confidence"]),
                         ("external", None, "full", 0.7))

    def test_a_light_verdict_on_a_full_floor_leaves_it_full(self):
        doc, _ = self.tier(self.repo("light", specs={"widget": MODIFIED_SPEC}))
        self.assertEqual((doc["floor"], doc["classifier"]["tier"], doc["tier"]),
                         ("full", "light", "full"))

    def test_invalid_output_falls_back(self):
        for mode, cause in (("garbage", "invalid: not JSON"),
                            ("badtier", "invalid: tier must be 'light' or 'full' (got 'medium')")):
            with self.subTest(mode):
                r = PreflightRepo(self.tmp / f"work-{mode}", manifest=self.repo_manifest(mode))
                doc, _ = self.tier(r)
                self.assertEqual((doc["classifier"]["provider"], doc["classifier"]["cause"]),
                                 ("builtin", cause))
                self.assertEqual(doc["tier"], "light")

    def test_a_non_zero_exit_and_a_missing_command(self):
        doc, _ = self.tier(self.repo("fail"))
        self.assertEqual(doc["classifier"]["cause"], "exit 3")
        r = PreflightRepo(self.tmp / "work2", manifest=MANIFEST + (
            "loop:\n  plan-preflight:\n    classifier: no-such-classifier-command\n"))
        doc, _ = self.tier(r)
        self.assertEqual((doc["classifier"]["provider"], doc["classifier"]["cause"]),
                         ("builtin", "exit 127"))

    def test_a_timeout_kills_the_command_and_falls_back(self):
        r = self.repo("sleep", timeout=1)
        doc, _ = self.tier(r)
        self.assertEqual((doc["classifier"]["provider"], doc["classifier"]["cause"]),
                         ("builtin", "timeout 1s"))
        out = r.gates("plan", "tier", CHANGE, PF_STDIN_FILE=str(self.tmp / "s2"),
                      PF_ENV_FILE=str(self.tmp / "e2"))
        self.assertIn("classifier: builtin, cause: timeout 1s", out.stdout)

    def test_none_declared(self):
        doc, _ = self.tier(self.repo(None))
        self.assertEqual((doc["classifier"]["provider"], doc["classifier"]["cause"]),
                         ("builtin", "none-declared"))

    def test_the_command_gets_the_digest_and_the_shims_environment(self):
        r = self.repo("light")
        self.tier(r, PF_SECRETLESS_MARK="reached")
        self.assertEqual((self.tmp / "env.txt").read_text(), "reached")
        stdin = (self.tmp / "stdin.bin").read_bytes()
        printed = r.gates("plan", "digest", CHANGE, "--json", "--limit", "48000").stdout
        self.assertTrue(stdin.startswith(b'{"digest":' + printed.rstrip("\n").encode()
                                         + b',"dimensions":'))
        self.assertEqual([d["id"] for d in json.loads(stdin)["dimensions"]],
                         ["security-path", "persisted-data", "public-interface", "irreversible",
                          "overall-tier"])

    def test_stderr_goes_to_the_log_only(self):
        r = self.repo("full")
        _doc, text = self.tier(r)
        logs = list((r.root / ".gatedloop" / "out").glob("plan-classifier-*.log"))
        self.assertEqual(len(logs), 1)
        self.assertIn("STDERR-MARK", logs[0].read_text())
        self.assertNotIn("STDERR-MARK", text)
        self.assertNotIn("STDERR-MARK", "".join(p.read_text() for p in (r.root / ".gatedloop").rglob("*.jsonl")))
        self.assertEqual(r.status(), "")


if __name__ == "__main__":
    unittest.main()
