#!/usr/bin/env python3
"""Shared command matcher for Bash `PreToolUse` gate hooks (design D1-D3 of
`harden-hook-matching`). One entry point answers "does this hook's command
input contain a guarded invocation, and what are its arguments?" for all of
`hooks/gate-commit.sh`, `hooks/gate-merge.sh`, `hooks/gate-archive.sh`,
`hooks/gate-implement.sh`, and `hooks/gate-scaffold.sh` -- replacing five
ad-hoc `case "$cmd" in *"..."*)` substring patterns with one tested matcher.

The guarded verb is matched as the SUBCOMMAND TOKEN of its program, in
command position, per simple command -- never by raw substring containment.
A hyphenated sibling subcommand (`merge-base`, `merge-tree`, `merge-file`)
does not match; a guarded phrase inside a quoted argument can never sit in
command position after tokenizing. Compound commands (`&&`, `||`, `;`, `|`,
`&`) are split into simple commands and each is examined on its own.

Three classes of token are never arguments (design D1 of `hook-correctness`):
a redirection and its target (`2>&1`, `> out`, `<in`, `&>log`), anything in a
heredoc body (data, not commands -- lines after its terminator are commands
again), and a whole simple command that asks for help (`--help`/`-h`).

If the command string cannot be tokenized (unbalanced quotes), the matcher
falls back to the previous, generous substring behavior -- a parse failure
must never become a silent bypass (design D3): it still fires, and argument
extraction falls back to a best-effort whitespace split.

CLI usage (from a hook script):

    eval "$(printf '%s' "$input" | python3 "${HOOK_DIR}/_gate_match.py" git-merge)"
    # sets: matched=0|1, hook_cwd=<cwd>, and per-kind extras (change=...,
    # branch=..., ref=<merge source ref, git-merge only>)

Kinds: git-commit, git-merge, openspec-archive, implement-branch,
openspec-scaffold.

Stdlib only (`zero-dep-shim`); private, underscore-named helper -- not a
`gates` subcommand (precedent: `hooks/_session_brief.py`).
"""
from __future__ import annotations

import json
import shlex
import sys

OPERATOR_TOKENS = {"&&", "||", ";", "|", "&"}
_HELP_FLAGS = {"--help", "-h"}

# Global git flags that consume a separate following token as their value
# (design D2 item 3).
_GIT_GLOBAL_FLAGS_WITH_VALUE = {
    "-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path",
}
# Global git flags that never take a value.
_GIT_GLOBAL_FLAGS_NO_VALUE = {
    "-p", "--paginate", "--no-pager", "--no-replace-objects", "--bare",
    "--literal-pathspecs",
}
# Wrappers/assignments skipped before locating the program token (design D2
# item 1). `env`'s own leading assignments are skipped too.
_WRAPPERS = {"command", "env", "nohup", "time"}

# The kinds this matcher understands, and what their OLD ad-hoc substring
# pattern fired on -- the conservative fallback floor (design D3), verbatim.
_FALLBACK_SUBSTRINGS = {
    "git-commit": ("git commit",),
    "git-merge": ("git merge",),
    "openspec-archive": ("openspec archive",),
    "implement-branch": ("git checkout -b", "git switch -c"),
    "openspec-scaffold": ("openspec new change",),
}


_HEREDOC_WORD_END = set(" \t\n;&|<>()")


def _heredoc_word(command: str, j: int) -> tuple[str, int]:
    """The delimiter word of a heredoc opener starting at `command[j]` (just
    past `<<`/`<<-` and any blanks), with shell quoting removed, and the
    index just past it."""
    word: list[str] = []
    n = len(command)
    while j < n and command[j] not in _HEREDOC_WORD_END:
        c = command[j]
        if c in ("'", '"'):
            close = command.find(c, j + 1)
            if close == -1:
                return "".join(word) + command[j + 1:], n
            word.append(command[j + 1:close])
            j = close + 1
            continue
        if c == "\\" and j + 1 < n:
            word.append(command[j + 1])
            j += 2
            continue
        word.append(c)
        j += 1
    return "".join(word), j


def _heredoc_segments(command: str) -> list[str]:
    """`command` with every heredoc BODY removed (hook-correctness D1): the
    lines after a `<<WORD` / `<<-WORD` / `<<'WORD'` opener, up to and
    including the terminator line, are data and never scanned. Returns the
    remaining text split at every unquoted newline -- a newline outside
    quotes ends a command in the shell, a boundary the tokenizer (which
    treats a newline as a blank) would otherwise lose, so a command on the
    line after a heredoc's terminator is matched on its own. Quote-aware: a
    `<<` or a newline inside quotes opens or ends nothing."""
    segments: list[str] = []
    start = 0
    pending: list[tuple[str, bool]] = []
    quote: str | None = None
    i, n = 0, len(command)
    while i < n:
        c = command[i]
        if quote == "'":
            if c == "'":
                quote = None
            i += 1
            continue
        if c == "\\" and i + 1 < n:
            i += 2
            continue
        if quote == '"':
            if c == '"':
                quote = None
            i += 1
            continue
        if c in ("'", '"'):
            quote = c
            i += 1
            continue
        if command.startswith("<<", i) and not command.startswith("<<<", i):
            j = i + 2
            strip_tabs = j < n and command[j] == "-"
            if strip_tabs:
                j += 1
            while j < n and command[j] in " \t":
                j += 1
            word, j = _heredoc_word(command, j)
            if word:
                pending.append((word, strip_tabs))
            i = j
            continue
        if c == "\n":
            segments.append(command[start:i])
            pos = i + 1
            for word, strip_tabs in pending:
                while pos < n:
                    nl = command.find("\n", pos)
                    line = command[pos:] if nl == -1 else command[pos:nl]
                    pos = n if nl == -1 else nl + 1
                    if (line.lstrip("\t") if strip_tabs else line) == word:
                        break
            pending = []
            start = pos
            i = pos
            continue
        i += 1
    segments.append(command[start:])
    return segments


def _split_simple_commands(command: str) -> list[list[str]] | None:
    """Tokenize `command`, splitting into simple commands on the shell
    operator tokens. Heredoc bodies are removed first (hook-correctness D1).
    Returns `None` if the string can't be tokenized (design D3 -- the caller
    falls back to substring matching)."""
    commands: list[list[str]] = []
    for segment in _heredoc_segments(command):
        split = _split_segment(segment)
        if split is None:
            return None
        commands.extend(split)
    return commands


def _split_segment(command: str) -> list[list[str]] | None:
    if not command.strip():
        return []
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return None

    commands: list[list[str]] = []
    current: list[str] = []
    skip_target = False
    for tok in tokens:
        if tok in OPERATOR_TOKENS:
            if current:
                commands.append(current)
            current = []
            skip_target = False
        elif skip_target:
            skip_target = False
        elif _is_redirection_operator(tok):
            # hook-correctness D1: a redirection and its target are never
            # arguments. `shlex` splits `2>&1` into `2`, `>&`, `1` -- a bare
            # fd number immediately before the operator belongs to it.
            if current and current[-1].isdigit():
                current.pop()
            skip_target = True
        else:
            current.append(tok)
    if current:
        commands.append(current)
    return commands


def _is_redirection_operator(tok: str) -> bool:
    """A punctuation token that redirects (`>`, `>>`, `>&`, `<`, `&>`, `>|`,
    `<<`, `<<<`, ...) -- as `shlex`'s `punctuation_chars` splits it off its
    fd and target (design D1's two token patterns, at shlex's granularity)."""
    return bool(tok) and all(c in "<>&|" for c in tok) and any(c in "<>" for c in tok)


def _is_assignment(tok: str) -> bool:
    if "=" not in tok:
        return False
    name = tok.split("=", 1)[0]
    return bool(name) and (name[0].isalpha() or name[0] == "_") and all(
        c.isalnum() or c == "_" for c in name
    )


def _basename(prog: str) -> str:
    return prog.rsplit("/", 1)[-1]


def _prog_and_rest(tokens: list[str]) -> tuple[str | None, list[str]]:
    """Skip leading assignments and wrappers, then return `(basename(prog),
    remaining tokens)` -- or `(None, [])` if nothing is left."""
    i, n = 0, len(tokens)
    while i < n:
        tok = tokens[i]
        if _is_assignment(tok):
            i += 1
            continue
        if tok in _WRAPPERS:
            i += 1
            if tok == "env":
                while i < n and _is_assignment(tokens[i]):
                    i += 1
            continue
        break
    if i >= n:
        return None, []
    return _basename(tokens[i]), tokens[i + 1:]


def _skip_git_global_flags(tokens: list[str]) -> list[str]:
    """Skip git global flags before the subcommand token (design D2 item 3).
    An unrecognized `-x` flag is skipped on its own -- conservatively never
    consuming a following token as its value (design Risks) -- so the next
    token is always the next subcommand candidate."""
    i, n = 0, len(tokens)
    while i < n:
        tok = tokens[i]
        if not tok.startswith("-"):
            break
        if tok.startswith("--") and "=" in tok:
            i += 1
            continue
        if tok in _GIT_GLOBAL_FLAGS_WITH_VALUE:
            i += 2
            continue
        if tok in _GIT_GLOBAL_FLAGS_NO_VALUE:
            i += 1
            continue
        i += 1  # unrecognized flag: skip only itself
    return tokens[i:]


def _match_git_subcommand(tokens: list[str], want: str) -> list[str] | None:
    """If this simple command invokes `git` (by basename) with subcommand
    token `want` (after skipping global flags), return the remaining tokens;
    else `None`."""
    prog, rest = _prog_and_rest(tokens)
    if prog != "git":
        return None
    rest = _skip_git_global_flags(rest)
    if not rest or rest[0] != want:
        return None
    return rest[1:]


def _match_openspec_tokens(tokens: list[str], want: list[str]) -> list[str] | None:
    """If this simple command invokes `openspec` (by basename) followed
    immediately by the consecutive tokens in `want`, return the remaining
    tokens; else `None`."""
    prog, rest = _prog_and_rest(tokens)
    if prog != "openspec":
        return None
    if rest[:len(want)] != want:
        return None
    return rest[len(want):]


def _first_non_flag(tokens: list[str]) -> str:
    for t in tokens:
        if not t.startswith("-"):
            return t
    return ""


# `git merge` flags that consume a following token as their value (so that
# token is never mistaken for the source ref).
_MERGE_SEQUENCER_FLAGS = {"--continue", "--abort", "--quit"}

_MERGE_FLAGS_WITH_VALUE = {
    "-m", "--message", "-s", "--strategy", "-X", "--strategy-option",
    "--into-name",
}


def _merge_source_ref(tokens: list[str]) -> str:
    """The trailing non-flag argument of a `git merge` invocation (design
    D4) -- the merge source ref, e.g. `my-change` in `git merge --squash
    my-change`. Ambiguous shapes resolve to "" (no ref): zero non-flag
    arguments (`git merge --continue`) or more than one (an octopus merge --
    there is no single "the" source, and guessing one would validate against
    the wrong tree). `match` reports the latter as `ref_parse=failed`, which
    `gate-merge.sh` denies by name; a sequencer step keeps the HEAD-tree
    fallback (hook-correctness D1).
    """
    non_flags: list[str] = []
    i, n = 0, len(tokens)
    while i < n:
        tok = tokens[i]
        if tok.startswith("-"):
            if tok in _MERGE_FLAGS_WITH_VALUE:
                i += 2
                continue
            if tok.startswith("--") and "=" in tok:
                i += 1
                continue
            i += 1
            continue
        non_flags.append(tok)
        i += 1
    return non_flags[0] if len(non_flags) == 1 else ""


def _flag_value(tokens: list[str], flag: str) -> str:
    """The value of `flag` (e.g. `-b`) within this simple command's
    remaining tokens: a following token, or a glued `-bvalue` form."""
    for i, t in enumerate(tokens):
        if t == flag:
            return tokens[i + 1] if i + 1 < len(tokens) else ""
        if t.startswith(flag) and len(t) > len(flag):
            return t[len(flag):]
    return ""


def _naive_arg_after(command: str, token: str) -> str:
    """Best-effort argument extraction when tokenization has already failed
    (design D3): a plain whitespace split, no quote awareness."""
    parts = command.split()
    for i, t in enumerate(parts):
        if t == token and i + 1 < len(parts):
            return parts[i + 1].strip("'\"")
    return ""


def _fallback_match(kind: str, command: str) -> dict:
    matched = any(s in command for s in _FALLBACK_SUBSTRINGS[kind])
    result: dict = {"matched": 1 if matched else 0}
    if kind == "openspec-archive":
        result["change"] = _naive_arg_after(command, "archive") if matched else ""
    if kind == "implement-branch":
        result["branch"] = (
            (_naive_arg_after(command, "-b") or _naive_arg_after(command, "-c"))
            if matched else ""
        )
    if kind == "git-merge":
        # No quote-safe way to find "the trailing non-flag argument" once
        # tokenization has already failed -- conservatively report no ref,
        # same as an unresolvable/ambiguous ref: the caller falls back to
        # the current HEAD tree (design D3: never fail open).
        result["ref"] = ""
        result["ref_parse"] = "none"
        # Unparsable, so whether a switch precedes the merge is unknown:
        # assume one, keeping the merge gated (design D3: never fail open).
        result["switch_before"] = "1"
    return result


def match(kind: str, command: str) -> dict:
    """Does `command` contain a `kind` invocation in command position, and
    what are its arguments? Returns a dict with at least `matched` (0 or 1)
    plus any kind-specific extras (`change`, `branch`)."""
    commands = _split_simple_commands(command)
    if commands is None:
        # The heredoc bodies are data even here: only the command text
        # around them is substring-scanned (hook-correctness D1).
        return _fallback_match(kind, "\n".join(_heredoc_segments(command)))
    # hook-correctness D1: a help request (`--help`/`-h`) is never the
    # guarded act -- drop those simple commands before matching.
    commands = [c for c in commands if not _HELP_FLAGS.intersection(c)]

    if kind == "git-commit":
        matched = any(_match_git_subcommand(c, "commit") is not None for c in commands)
        return {"matched": 1 if matched else 0}

    if kind == "git-merge":
        ref = ""
        matched = False
        needs_ref = False
        switched = False
        switch_before = False
        for c in commands:
            if (
                _match_git_subcommand(c, "checkout") is not None
                or _match_git_subcommand(c, "switch") is not None
            ):
                switched = True
            rest = _match_git_subcommand(c, "merge")
            if rest is None:
                continue
            # The checkout the hook sees is not the one the merge runs in
            # when the same command switches branches first -- the hook must
            # not judge the merge's scope from it (hook-correctness D2).
            switch_before = switch_before or switched
            matched = True
            if not ref:
                ref = _merge_source_ref(rest)
            # A sequencer step (`--continue`, `--abort`, `--quit`) carries no
            # incoming ref by design and keeps checking HEAD's tree; any other
            # merge must name exactly one (hook-correctness D1).
            if not _MERGE_SEQUENCER_FLAGS.intersection(rest):
                needs_ref = True
        ref_parse = "failed" if matched and needs_ref and not ref else ("ok" if ref else "none")
        return {
            "matched": 1 if matched else 0, "ref": ref, "ref_parse": ref_parse,
            "switch_before": "1" if switch_before else "0",
        }

    if kind == "openspec-archive":
        for c in commands:
            rest = _match_openspec_tokens(c, ["archive"])
            if rest is not None:
                return {"matched": 1, "change": _first_non_flag(rest)}
        return {"matched": 0, "change": ""}

    if kind == "implement-branch":
        for c in commands:
            rest = _match_git_subcommand(c, "checkout")
            if rest is not None:
                branch = _flag_value(rest, "-b")
                if branch:
                    return {"matched": 1, "branch": branch}
            rest = _match_git_subcommand(c, "switch")
            if rest is not None:
                branch = _flag_value(rest, "-c")
                if branch:
                    return {"matched": 1, "branch": branch}
        return {"matched": 0, "branch": ""}

    if kind == "openspec-scaffold":
        matched = any(
            _match_openspec_tokens(c, ["new", "change"]) is not None for c in commands
        )
        return {"matched": 1 if matched else 0}

    raise ValueError(f"unknown gate-match kind '{kind}'")


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in _FALLBACK_SUBSTRINGS:
        kinds = ", ".join(sorted(_FALLBACK_SUBSTRINGS))
        print(
            f"gatedloop: _gate_match.py requires exactly one kind argument ({kinds})",
            file=sys.stderr,
        )
        return 2

    kind = argv[1]
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except Exception:
        data = {}
    command = ((data.get("tool_input") or {}).get("command")) or ""
    hook_cwd = data.get("cwd") or ""

    result = match(kind, command)

    lines = [f"matched={shlex.quote(str(result['matched']))}"]
    lines.append(f"hook_cwd={shlex.quote(hook_cwd)}")
    for key in ("change", "branch", "ref", "ref_parse", "switch_before"):
        if key in result:
            lines.append(f"{key}={shlex.quote(result[key])}")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
