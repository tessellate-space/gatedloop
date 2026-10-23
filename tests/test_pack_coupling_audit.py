"""The shipped-pack coupling audit (stack-agnostic-prompts, workflow-packs 7.2).

No file gatedloop ships under `packs/` may name a curated project-specific tool
anywhere -- prose included. `gates schema inspect` stopped flagging curated
names in prose (schema-declared-flow D6: product nouns were noise on adopters'
own schemas), which is right for a third-party schema but would let one slip
into a pack we ship. This grep is the audit D6's tradeoff relies on; until now
it was a manual step, not a test.

Stdlib only. Run with:  python3 -m unittest discover -s tests
"""

import importlib.machinery
import importlib.util
import re
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

_loader = importlib.machinery.SourceFileLoader("gates_shim_pack_audit", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)


def audit(packs_dir: Path) -> dict:
    """{relative path: sorted curated names} for every pack file naming one."""
    hits = {}
    for f in sorted(packs_dir.rglob("*")):
        # Pack content only: an OS artifact such as `.DS_Store` is binary and
        # is never shipped, so it is not what this audit is about.
        if not f.is_file() or f.name.startswith("."):
            continue
        text = f.read_text().lower()
        names = sorted(n for n in gates.TOOL_NAME_CURATED
                       if re.search(r"\b" + re.escape(n) + r"\b", text))
        if names:
            hits[str(f.relative_to(packs_dir))] = names
    return hits


class TestShippedPackCouplingAudit(unittest.TestCase):
    def test_audit_catches_a_curated_name_in_prose(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "p" / "templates").mkdir(parents=True)
            (Path(d) / "p" / "templates" / "report.md").write_text("Run the suite with pytest first.\n")
            self.assertEqual(audit(Path(d)), {"p/templates/report.md": ["pytest"]})

    def test_shipped_packs_name_no_curated_tool(self):
        self.assertEqual(audit(REPO / "packs"), {})


if __name__ == "__main__":
    unittest.main()
