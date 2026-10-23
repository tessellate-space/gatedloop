"""Shared command matcher for Bash gate hooks (design D1-D3 of
`harden-hook-matching`, task 1.1). `hooks/_gate_match.py` decides whether a
hook's command input contains a guarded invocation IN COMMAND POSITION --
never by raw substring containment -- and extracts per-gate arguments from
the matched simple command.

Two layers: pure-function tests against `match(kind, command)` (loaded
in-process, same by-path technique `test_planning_grade_commit.py` uses for
`bin/gates`), and a handful of CLI-level tests that pipe crafted PreToolUse
JSON through `python3 hooks/_gate_match.py <kind>` and parse the emitted
`eval`-ready assignment lines -- the actual contract every `hooks/gate-*.sh`
relies on.

Stdlib only, per `zero-dep-shim`. Run with:  python3 -m unittest discover -s tests
"""

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MATCHER_PATH = REPO / "hooks" / "_gate_match.py"

_spec = importlib.util.spec_from_file_location("gate_match", str(MATCHER_PATH))
gate_match = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate_match)


def _run_cli(kind: str, command: str, cwd: str = "/repo") -> dict:
    """Pipe a crafted PreToolUse JSON payload through the CLI entry point and
    parse the emitted `name=value` eval lines into a dict."""
    payload = json.dumps({"tool_input": {"command": command}, "cwd": cwd})
    r = subprocess.run(
        [sys.executable, str(MATCHER_PATH), kind],
        input=payload, capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    out = {}
    for line in r.stdout.splitlines():
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        # Each value is shlex-quoted for `eval`; unquote it the same way a
        # shell would so the test asserts on the actual string.
        import shlex as _shlex
        out[key] = _shlex.split(value)[0] if _shlex.split(value) else ""
    return out


class TestGitMergeMatching(unittest.TestCase):
    def test_merge_matches(self):
        self.assertEqual(gate_match.match("git-merge", "git merge some-branch")["matched"], 1)

    def test_merge_base_does_not_match(self):
        self.assertEqual(gate_match.match("git-merge", "git merge-base --is-ancestor A B")["matched"], 0)

    def test_merge_tree_does_not_match(self):
        self.assertEqual(gate_match.match("git-merge", "git merge-tree base a b")["matched"], 0)

    def test_merge_file_does_not_match(self):
        self.assertEqual(gate_match.match("git-merge", "git merge-file a b c")["matched"], 0)

    def test_quoted_prose_mentioning_git_merge_does_not_match(self):
        cmd = 'gh issue create --body "please rerun git merge after review"'
        self.assertEqual(gate_match.match("git-merge", cmd)["matched"], 0)

    def test_dash_capital_c_global_flag_still_matches(self):
        self.assertEqual(
            gate_match.match("git-merge", "git -C /path/to/repo merge some-branch")["matched"], 1
        )

    def test_dash_lower_c_global_flag_still_matches(self):
        self.assertEqual(
            gate_match.match("git-merge", "git -c core.editor=true merge some-branch")["matched"], 1
        )

    def test_compound_command_still_matches(self):
        self.assertEqual(
            gate_match.match("git-merge", "cd /repo && git merge some-branch")["matched"], 1
        )

    def test_leading_env_assignment_is_skipped(self):
        self.assertEqual(gate_match.match("git-merge", "FOO=bar git merge x")["matched"], 1)

    def test_env_wrapper_with_its_own_assignment_is_skipped(self):
        self.assertEqual(gate_match.match("git-merge", "env FOO=bar git merge x")["matched"], 1)

    def test_command_wrapper_is_skipped(self):
        self.assertEqual(gate_match.match("git-merge", "command git merge x")["matched"], 1)

    def test_basename_match_for_absolute_git_path(self):
        self.assertEqual(gate_match.match("git-merge", "/usr/bin/git merge x")["matched"], 1)

    def test_unbalanced_quotes_fall_back_to_substring_and_still_fires(self):
        cmd = 'git merge "unterminated'
        self.assertEqual(gate_match.match("git-merge", cmd)["matched"], 1)

    def test_unbalanced_quotes_without_the_phrase_does_not_fire(self):
        cmd = 'git status "unterminated'
        self.assertEqual(gate_match.match("git-merge", cmd)["matched"], 0)


class TestGitCommitMatching(unittest.TestCase):
    def test_commit_matches(self):
        self.assertEqual(gate_match.match("git-commit", "git commit -m x")["matched"], 1)

    def test_commit_tree_does_not_match(self):
        self.assertEqual(gate_match.match("git-commit", "git commit-tree -m x abc123")["matched"], 0)

    def test_quoted_prose_mentioning_git_commit_does_not_match(self):
        cmd = 'gh pr create --body "run git commit -m done after"'
        self.assertEqual(gate_match.match("git-commit", cmd)["matched"], 0)


class TestOpenspecArchiveMatching(unittest.TestCase):
    def test_extracts_change_name_from_matched_command(self):
        result = gate_match.match("openspec-archive", "openspec archive my-change")
        self.assertEqual(result["matched"], 1)
        self.assertEqual(result["change"], "my-change")

    def test_quoted_prose_mentioning_openspec_archive_does_not_match(self):
        cmd = 'gh issue create --body "remember to run openspec archive later"'
        result = gate_match.match("openspec-archive", cmd)
        self.assertEqual(result["matched"], 0)

    def test_no_positional_name_yields_empty_change(self):
        result = gate_match.match("openspec-archive", "openspec archive --json")
        self.assertEqual(result["matched"], 1)
        self.assertEqual(result["change"], "")


class TestImplementBranchMatching(unittest.TestCase):
    def test_checkout_dash_b_extracts_branch(self):
        result = gate_match.match("implement-branch", "git checkout -b my-change")
        self.assertEqual(result["matched"], 1)
        self.assertEqual(result["branch"], "my-change")

    def test_switch_dash_c_extracts_branch(self):
        result = gate_match.match("implement-branch", "git switch -c my-change")
        self.assertEqual(result["matched"], 1)
        self.assertEqual(result["branch"], "my-change")

    def test_glued_dash_b_extracts_branch(self):
        result = gate_match.match("implement-branch", "git checkout -bmy-change")
        self.assertEqual(result["matched"], 1)
        self.assertEqual(result["branch"], "my-change")

    def test_dash_b_in_a_different_simple_command_does_not_leak(self):
        # The `-b` here belongs to an unrelated `grep` invocation in a
        # different simple command -- it must never be read as the branch
        # for the `git checkout` in the other half of the compound command.
        cmd = "grep -b pattern file.txt && git checkout some-existing-branch"
        result = gate_match.match("implement-branch", cmd)
        self.assertEqual(result["matched"], 0)
        self.assertEqual(result["branch"], "")

    def test_plain_checkout_without_dash_b_does_not_match(self):
        result = gate_match.match("implement-branch", "git checkout some-existing-branch")
        self.assertEqual(result["matched"], 0)


class TestOpenspecScaffoldMatching(unittest.TestCase):
    def test_new_change_matches_as_consecutive_tokens(self):
        self.assertEqual(gate_match.match("openspec-scaffold", "openspec new change")["matched"], 1)

    def test_quoted_prose_does_not_match(self):
        cmd = 'gh issue create --body "run openspec new change soon"'
        self.assertEqual(gate_match.match("openspec-scaffold", cmd)["matched"], 0)

    def test_new_alone_does_not_match(self):
        self.assertEqual(gate_match.match("openspec-scaffold", "openspec new proposal")["matched"], 0)


_REDIRECTIONS = ("2>&1", "> out", "2>/dev/null", "<in", "&>log")

# One plain invocation per kind, and the result it must keep whatever
# redirection is appended to it.
_BASE_INVOCATIONS = {
    "git-commit": ("git commit -m done", {"matched": 1}),
    "git-merge": ("git merge --squash my-change", {"matched": 1, "ref": "my-change"}),
    "openspec-archive": ("openspec archive my-change", {"matched": 1, "change": "my-change"}),
    "implement-branch": ("git checkout -b my-change", {"matched": 1, "branch": "my-change"}),
    "openspec-scaffold": ("openspec new change my-change", {"matched": 1}),
}


class TestRedirectionsAreNeverArguments(unittest.TestCase):
    """hook-correctness D1 (#33 item 1): a trailing `2>&1` made the merge
    matcher see three non-flag tokens (`my-change`, `2`, `1`), give up on the
    ref, and let the hook deny with a misleading "stale marker"; the same
    split made `openspec archive x 2>&1` read as archiving `x` only by luck
    of ordering. A redirection and its target are never arguments."""

    def test_every_kind_keeps_its_arguments_under_every_redirection(self):
        for kind, (base, expected) in _BASE_INVOCATIONS.items():
            for redirection in _REDIRECTIONS:
                command = f"{base} {redirection}"
                with self.subTest(command=command):
                    result = gate_match.match(kind, command)
                    for key, value in expected.items():
                        self.assertEqual(result[key], value, command)

    def test_a_leading_redirection_does_not_hide_the_program(self):
        result = gate_match.match("git-merge", "2>/dev/null git merge --squash my-change")
        self.assertEqual((result["matched"], result["ref"]), (1, "my-change"))


class TestHeredocBodiesAreData(unittest.TestCase):
    """hook-correctness D1 (#33 item 1): a heredoc body is data. A PR body or
    notes file that mentions a guarded command must not trip a hook -- and an
    apostrophe in that prose used to break tokenizing, dropping the whole
    command into the substring fallback, which then fired on the prose."""

    _BODY = "\n".join(base for base, _ in _BASE_INVOCATIONS.values())

    def test_no_kind_matches_a_guarded_invocation_inside_a_heredoc_body(self):
        for opener, terminator in (("<<'EOF'", "EOF"), ("<<EOF", "EOF"), ("<<-EOF", "\tEOF")):
            command = (
                f"cat > notes.md {opener}\nDon't forget:\n{self._BODY}\n{terminator}"
            )
            for kind in _BASE_INVOCATIONS:
                with self.subTest(opener=opener, kind=kind):
                    self.assertEqual(gate_match.match(kind, command)["matched"], 0)

    def test_a_command_after_the_terminator_is_still_matched(self):
        command = (
            "cat > notes.md <<'EOF'\nit's done\nEOF\ngit merge --squash my-change"
        )
        result = gate_match.match("git-merge", command)
        self.assertEqual((result["matched"], result["ref"]), (1, "my-change"))

    def test_the_line_that_opens_the_heredoc_is_still_matched(self):
        command = "git commit -F - <<'EOF'\nsubject\nEOF"
        self.assertEqual(gate_match.match("git-commit", command)["matched"], 1)

    def test_a_quoted_double_angle_is_not_a_heredoc(self):
        command = 'echo "a <<EOF b"\ngit merge --squash my-change\nEOF'
        self.assertEqual(gate_match.match("git-merge", command)["matched"], 1)


class TestHelpIsNotAGuardedInvocation(unittest.TestCase):
    """hook-correctness D1: `openspec archive --help 2>&1` was read as
    archiving a change named `2`; a help request is never the guarded act."""

    def test_archive_help_with_a_redirection_is_unmatched(self):
        self.assertEqual(
            gate_match.match("openspec-archive", "openspec archive --help 2>&1")["matched"], 0
        )

    def test_help_flags_unmatch_every_kind(self):
        for kind, (base, _expected) in _BASE_INVOCATIONS.items():
            for flag in ("--help", "-h"):
                with self.subTest(kind=kind, flag=flag):
                    self.assertEqual(gate_match.match(kind, f"{base} {flag}")["matched"], 0)


class TestCLIEntryPoint(unittest.TestCase):
    """The actual `eval`-line contract every `hooks/gate-*.sh` relies on."""

    def test_git_merge_matched_line(self):
        out = _run_cli("git-merge", "git merge some-branch")
        self.assertEqual(out.get("matched"), "1")
        self.assertEqual(out.get("hook_cwd"), "/repo")

    def test_git_merge_base_unmatched_line(self):
        out = _run_cli("git-merge", "git merge-base --is-ancestor A B")
        self.assertEqual(out.get("matched"), "0")

    def test_openspec_archive_emits_change(self):
        out = _run_cli("openspec-archive", "openspec archive my-change")
        self.assertEqual(out.get("matched"), "1")
        self.assertEqual(out.get("change"), "my-change")

    def test_implement_branch_emits_branch(self):
        out = _run_cli("implement-branch", "git switch -c my-change")
        self.assertEqual(out.get("matched"), "1")
        self.assertEqual(out.get("branch"), "my-change")

    def test_openspec_scaffold_matched_line(self):
        out = _run_cli("openspec-scaffold", "openspec new change")
        self.assertEqual(out.get("matched"), "1")


if __name__ == "__main__":
    unittest.main()
