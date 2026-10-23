"""A fake forge for the pull-request-mode tests (change `merge-pull-request`).

`gates marker publish`, `marker check-remote`, the pull-request branch of
`gates merge` and `gates record-merged` all reach GitHub through the `gh`
CLI. No test may call the real API, so `Forge.install(bindir)` writes a `gh`
stand-in onto a test's PATH. It is a small stateful forge, not an echo: it
keeps commit statuses, pull requests and merged-PR lookups in a JSON file,
answers the combined-status read from what was posted, and 404s a request
for any repository but its own -- so a test reads the forge's resulting
STATE the way the merge tests read a bare remote's refs.

Only the calls the design names are understood:

- `gh auth status`, `gh repo view --json nameWithOwner`
- `gh api repos/<o>/<r>/statuses/<sha> -X POST -f state=... -f context=...
  -f description=... [-f target_url=...]`
- `gh api repos/<o>/<r>/commits/<sha>/status` (latest status per context)
- `gh api repos/<o>/<r>/commits/<sha>/pulls`
- `gh pr view <number> --json ...` (a pull request by number, in any state,
  with its merge record: what `gates approval attest --merged` reads)
- `gh pr view <head> --json ...`, `gh pr create --head --base --title
  --body|--body-file`, `gh pr edit <head> --body|--body-file`,
  `gh pr merge <head> --squash [--auto]`

and, for `scripts/go-public` (change `go-public-migration`, design D6),
issues across more than one repository (`add_repo` names the others):

- `gh issue list --repo <r> --state all --limit <n> --json ...` (newest first)
- `gh pr list --repo <r> --state all --limit <n> --json number` (newest first)
- `gh issue transfer <n> <dest> --repo <src>` (takes the destination's next
  number, keeps the comments and their ids, prints the new URL)
- `gh api repos/<o>/<r>/issues/<n>` (GET, or `-X PATCH -f body=...`)
- `gh api repos/<o>/<r>/issues/<n>/comments [--paginate --slurp]`
- `gh api -X PATCH repos/<o>/<r>/issues/comments/<id> -f body=...`

Every transfer and every edit is recorded, so a test reads what moved and
what was rewritten, and how many times.

Anything else exits non-zero, so an unexpected call fails loudly rather than
passing as a no-op.

`path_without(...)` builds a PATH holding only named tools, for the "forge
CLI is not installed" cases: a developer machine usually has a real `gh`,
and a PATH prefix cannot hide it.

Stdlib only, per `zero-dep-shim`. Not a test module (no `test` prefix).
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

OWNER_REPO = "acme/widget"

# A CI provider's run variables, unset so a test run inside CI behaves the
# same as one on a laptop (`gates marker publish` reads them for target_url).
NO_CI = {"GITHUB_RUN_ID": None, "GITHUB_SERVER_URL": None, "GITHUB_REPOSITORY": None}

PR_MODE = "integration:\n  mode: pull-request\n"

_FAKE_GH = r'''#!__PYTHON__
import json
import sys

STATE = __STATE__
REPO = __REPO__
BOOLEAN = {"squash", "auto", "merge", "rebase", "delete-branch", "paginate", "slurp", "fill"}


def load():
    try:
        with open(STATE) as f:
            return json.load(f)
    except FileNotFoundError:
        return {"statuses": [], "prs": [], "pulls": [], "unauth": False}


def save(state):
    with open(STATE, "w") as f:
        json.dump(state, f, indent=1)


def die(message, code=1):
    sys.stderr.write(message + "\n")
    sys.exit(code)


def parse(rest):
    opts, fields, pos, i = {}, {}, [], 0
    while i < len(rest):
        a = rest[i]
        if a in ("-f", "-F", "--field", "--raw-field"):
            key, _, value = rest[i + 1].partition("=")
            fields[key] = value
            i += 2
        elif a.startswith("--") and "=" in a:
            key, value = a[2:].split("=", 1)
            opts[key] = value
            i += 1
        elif a.startswith("-"):
            key = a.lstrip("-")
            if key in BOOLEAN or i + 1 >= len(rest):
                opts[key] = True
                i += 1
            else:
                opts[key] = rest[i + 1]
                i += 2
        else:
            pos.append(a)
            i += 1
    return opts, fields, pos


def body_of(opts):
    if "body-file" in opts:
        with open(opts["body-file"]) as f:
            return f.read()
    return opts.get("body", "")


def open_pr(state, head):
    found = [p for p in state["prs"] if p["head"] == head and p["state"] == "OPEN"]
    return found[-1] if found else None


def repos(state):
    return [REPO] + list(state.get("repos", []))


def find_issue(state, repo, number):
    for issue in state.get("issues", []):
        if issue["repo"] == repo and issue["number"] == number:
            return issue
    return None


def issue_json(issue):
    return {"number": issue["number"], "title": issue["title"], "state": issue["state"],
            "createdAt": issue["createdAt"], "body": issue["body"],
            "user": {"login": issue["user"]}}


def comment_json(comment):
    return {"id": comment["id"], "body": comment["body"], "user": {"login": comment["user"]}}


def record_edit(state, kind, repo, ident, body):
    state.setdefault("edits", []).append({"kind": kind, "repo": repo, "id": ident, "body": body})


state = load()
args = sys.argv[1:]
if args[:2] == ["auth", "status"]:
    if state.get("unauth"):
        die("You are not logged into any GitHub hosts. To log in, run: gh auth login")
    print("Logged in to github.com account fake")
    sys.exit(0)
if state.get("unauth"):
    die("To get started with GitHub CLI, please run:  gh auth login", 4)

opts, fields, pos = parse(args[2:] if args[:1] in (["pr"], ["repo"], ["issue"]) else args[1:])

if args[:2] == ["repo", "view"]:
    print(json.dumps({"nameWithOwner": REPO}))
    sys.exit(0)

if args[:2] == ["issue", "list"]:
    repo = opts.get("repo") or REPO
    if repo not in repos(state):
        die("GraphQL: Could not resolve to a Repository with the name '%s'." % repo)
    found = sorted((i for i in state.get("issues", []) if i["repo"] == repo),
                   key=lambda i: i["number"], reverse=True)
    print(json.dumps([issue_json(i) for i in found[:int(opts.get("limit", 30))]]))
    sys.exit(0)

if args[:2] == ["pr", "list"]:
    repo = opts.get("repo") or REPO
    if repo not in repos(state):
        die("GraphQL: Could not resolve to a Repository with the name '%s'." % repo)
    found = sorted(state["prs"], key=lambda p: p["number"], reverse=True) if repo == REPO else []
    print(json.dumps([{"number": p["number"]} for p in found[:int(opts.get("limit", 30))]]))
    sys.exit(0)

if args[:2] == ["issue", "transfer"]:
    source = opts.get("repo") or REPO
    if len(pos) != 2 or not pos[0].isdigit():
        die("fake gh: issue transfer needs <number> <destination>", 2)
    number, dest = int(pos[0]), pos[1]
    if dest not in repos(state):
        die("GraphQL: Could not resolve to a Repository with the name '%s'." % dest)
    if number in state.get("fail_transfer", []):
        die("HTTP 502: Bad Gateway (transfer of #%d)" % number)
    issue = find_issue(state, source, number)
    if issue is None:
        die("GraphQL: Could not resolve to an issue or pull request with the number of %d." % number)
    taken = [i["number"] for i in state.get("issues", []) if i["repo"] == dest]
    if dest == REPO:
        taken += [p["number"] for p in state["prs"]]
    new = max(taken, default=0) + 1
    issue["repo"], issue["number"] = dest, new
    state.setdefault("transfers", []).append({"from": number, "to": new, "source": source,
                                              "dest": dest})
    save(state)
    print("https://github.com/%s/issues/%d" % (dest, new))
    sys.exit(0)

if args[:1] == ["api"]:
    path = (pos[0].lstrip("/") if pos else "").split("?", 1)[0]
    parts = path.split("/")
    if len(parts) < 4 or parts[0] != "repos" or "/".join(parts[1:3]) not in repos(state):
        die("gh: Not Found (HTTP 404)")
    api_repo = "/".join(parts[1:3])
    rest = parts[3:]
    method = opts.get("X") or opts.get("method") or ("POST" if fields else "GET")
    if rest[0] == "issues" and len(rest) == 3 and rest[1] == "comments" and method == "PATCH":
        for issue in state.get("issues", []):
            if issue["repo"] != api_repo:
                continue
            for comment in issue["comments"]:
                if str(comment["id"]) == rest[2]:
                    comment["body"] = fields.get("body", comment["body"])
                    record_edit(state, "comment", api_repo, comment["id"], comment["body"])
                    save(state)
                    print(json.dumps(comment_json(comment)))
                    sys.exit(0)
        die("gh: Not Found (HTTP 404)")
    if rest[0] == "issues" and len(rest) == 2 and rest[1].isdigit():
        issue = find_issue(state, api_repo, int(rest[1]))
        if issue is None:
            die("gh: Not Found (HTTP 404)")
        if method == "PATCH":
            issue["body"] = fields.get("body", issue["body"])
            record_edit(state, "issue", api_repo, issue["number"], issue["body"])
            save(state)
        elif method != "GET":
            die("fake gh: unsupported method %s on an issue" % method, 2)
        print(json.dumps(issue_json(issue)))
        sys.exit(0)
    if rest[0] == "issues" and len(rest) == 3 and rest[2] == "comments" and method == "GET":
        issue = find_issue(state, api_repo, int(rest[1])) if rest[1].isdigit() else None
        if issue is None:
            die("gh: Not Found (HTTP 404)")
        comments = [comment_json(c) for c in issue["comments"]]
        print(json.dumps([comments] if "slurp" in opts else comments))
        sys.exit(0)
    if rest[0] == "statuses" and len(rest) == 2 and method == "POST":
        status = {
            "sha": rest[1], "state": fields.get("state"), "context": fields.get("context"),
            "description": fields.get("description"), "target_url": fields.get("target_url"),
        }
        state["statuses"].append(status)
        save(state)
        print(json.dumps(status))
        sys.exit(0)
    if rest[0] == "commits" and len(rest) == 3 and rest[2] == "status":
        latest = {}
        for s in reversed([s for s in state["statuses"] if s["sha"] == rest[1]]):
            latest.setdefault(s["context"], s)
        statuses = list(latest.values())
        combined = "success" if statuses and all(s["state"] == "success" for s in statuses) else (
            "pending" if not statuses else "failure")
        print(json.dumps({"sha": rest[1], "state": combined, "statuses": statuses}))
        sys.exit(0)
    if rest[0] == "commits" and len(rest) == 3 and rest[2] == "pulls":
        print(json.dumps([p for p in state["pulls"] if p.get("merge_commit_sha") == rest[1]]))
        sys.exit(0)
    die("gh: Not Found (HTTP 404)")

if args[:2] == ["pr", "view"] and pos and pos[0].isdigit():
    found = [p for p in state["prs"] if p["number"] == int(pos[0])]
    if not found:
        die("GraphQL: Could not resolve to a PullRequest with the number of %s." % pos[0])
    pr = found[-1]
    print(json.dumps({
        "number": pr["number"], "url": pr["url"], "state": pr["state"],
        "headRefName": pr["head"], "baseRefName": pr.get("base"),
        "mergedAt": pr.get("merged_at"),
        "mergedBy": {"login": pr["merged_by"]} if pr.get("merged_by") else None,
        "mergeCommit": {"oid": pr["merge_commit"]} if pr.get("merge_commit") else None,
    }))
    sys.exit(0)

if args[:2] == ["pr", "view"]:
    pr = open_pr(state, pos[0] if pos else "")
    if pr is None:
        die('no pull requests found for branch "%s"' % (pos[0] if pos else ""))
    print(json.dumps({"url": pr["url"], "number": pr["number"], "state": pr["state"]}))
    sys.exit(0)

if args[:2] == ["pr", "create"]:
    head = opts.get("head")
    if not head or open_pr(state, head) is not None:
        die("a pull request for branch \"%s\" already exists" % head)
    number = len(state["prs"]) + 1
    pr = {
        "number": number, "head": head, "base": opts.get("base"), "title": opts.get("title"),
        "body": body_of(opts), "state": "OPEN", "auto_merge": None,
        "url": "https://github.com/%s/pull/%d" % (REPO, number),
    }
    state["prs"].append(pr)
    save(state)
    print(pr["url"])
    sys.exit(0)

if args[:2] == ["pr", "edit"]:
    pr = open_pr(state, pos[0] if pos else "")
    if pr is None:
        die("no open pull request for %s" % pos)
    pr["body"] = body_of(opts)
    save(state)
    print(pr["url"])
    sys.exit(0)

if args[:2] == ["pr", "merge"]:
    pr = open_pr(state, pos[0] if pos else "")
    if pr is None:
        die("no open pull request for %s" % pos)
    if "auto" in opts:
        pr["auto_merge"] = "squash" if "squash" in opts else "merge"
    else:
        pr["state"] = "MERGED"
    save(state)
    print("auto-merge enabled" if "auto" in opts else "merged")
    sys.exit(0)

die("fake gh: unsupported invocation: %s" % " ".join(args), 2)
'''


class Forge:
    """The fake forge's state, and the `gh` that serves it."""

    def __init__(self, state_path: Path, repo: str = OWNER_REPO):
        self.state_path = Path(state_path)
        self.repo = repo

    def install(self, bindir: Path) -> "Forge":
        bindir = Path(bindir)
        bindir.mkdir(parents=True, exist_ok=True)
        script = (
            _FAKE_GH.replace("__PYTHON__", sys.executable)
            .replace("__STATE__", repr(str(self.state_path)))
            .replace("__REPO__", repr(self.repo))
        )
        gh = bindir / "gh"
        gh.write_text(script)
        gh.chmod(0o755)
        return self

    # ---- state ------------------------------------------------------------

    def _load(self) -> dict:
        if not self.state_path.exists():
            return {"statuses": [], "prs": [], "pulls": [], "unauth": False}
        return json.loads(self.state_path.read_text())

    def _save(self, state: dict) -> None:
        self.state_path.write_text(json.dumps(state, indent=1))

    def statuses(self, sha: str) -> list:
        return [s for s in self._load()["statuses"] if s["sha"] == sha]

    def latest_status(self, sha: str, context: str) -> dict | None:
        found = [s for s in self.statuses(sha) if s["context"] == context]
        return found[-1] if found else None

    def prs(self) -> list:
        return self._load()["prs"]

    # ---- arranging -------------------------------------------------------

    def add_status(self, sha: str, context: str, state: str, description: str) -> None:
        data = self._load()
        data["statuses"].append({
            "sha": sha, "state": state, "context": context,
            "description": description, "target_url": None,
        })
        self._save(data)

    def add_merged_pull(self, number: int, head_ref: str, merge_sha: str) -> None:
        """What `commits/<sha>/pulls` answers for a squash the forge made."""
        data = self._load()
        data["pulls"].append({
            "number": number, "state": "closed", "merged_at": "2026-10-14T12:00:00Z",
            "merge_commit_sha": merge_sha, "head": {"ref": head_ref},
        })
        self._save(data)

    def add_pr(self, number: int, head: str, base: str = "main", state: str = "MERGED",
               merged_by: str | None = "alice", merged_at: str | None = "2026-10-20T09:30:00Z",
               merge_commit: str | None = None) -> None:
        """A pull request as `gh pr view <number>` reports it. An open PR
        has no merge record, so its merger, time and commit are dropped."""
        if state != "MERGED":
            merged_by = merged_at = merge_commit = None
        data = self._load()
        data["prs"].append({
            "number": number, "head": head, "base": base, "title": head, "body": "",
            "state": state, "auto_merge": None, "merged_by": merged_by,
            "merged_at": merged_at, "merge_commit": merge_commit,
            "url": "https://github.com/%s/pull/%d" % (self.repo, number),
        })
        self._save(data)

    def set_unauthenticated(self) -> None:
        data = self._load()
        data["unauth"] = True
        self._save(data)

    # ---- issues across repositories (go-public-migration) -----------------

    def add_repo(self, repo: str) -> None:
        """Another repository this forge serves, beside its own."""
        data = self._load()
        data.setdefault("repos", []).append(repo)
        self._save(data)

    def add_issue(self, number: int, title: str = "", body: str = "", state: str = "OPEN",
                  comments=(), repo: str | None = None, user: str = "alice") -> None:
        """An issue. `comments` holds (id, body) or (id, body, login) tuples."""
        data = self._load()
        data.setdefault("issues", []).append({
            "repo": repo or self.repo, "number": number, "title": title or f"issue {number}",
            "state": state, "createdAt": "2026-01-01T00:00:%02dZ" % (number % 60),
            "body": body, "user": user,
            "comments": [{"id": c[0], "body": c[1], "user": c[2] if len(c) > 2 else user}
                         for c in comments],
        })
        self._save(data)

    def issues(self, repo: str | None = None) -> list:
        """The issues now in `repo` (this forge's own by default), lowest number first."""
        repo = repo or self.repo
        return sorted((i for i in self._load().get("issues", []) if i["repo"] == repo),
                      key=lambda i: i["number"])

    def issue(self, repo: str, number: int) -> dict | None:
        found = [i for i in self.issues(repo) if i["number"] == number]
        return found[0] if found else None

    def comment(self, repo: str, ident: int) -> dict | None:
        for issue in self.issues(repo):
            for comment in issue["comments"]:
                if comment["id"] == ident:
                    return comment
        return None

    def transfers(self) -> list:
        """Every transfer, in the order it happened: {from, to, source, dest}."""
        return self._load().get("transfers", [])

    def edits(self) -> list:
        """Every body edit, in order: {kind: issue|comment, repo, id, body}."""
        return self._load().get("edits", [])

    def fail_transfer(self, *numbers: int) -> None:
        """Make `gh issue transfer` of these issue numbers fail."""
        data = self._load()
        data["fail_transfer"] = list(numbers)
        self._save(data)

    def clear_transfer_failures(self) -> None:
        self.fail_transfer()


def path_without(tmp: Path, keep=("git",), extra_dirs=()) -> str:
    """A PATH whose only tools are symlinks to `keep` (plus `extra_dirs`,
    e.g. a fake `openspec`), so `gh` is genuinely absent."""
    d = Path(tmp) / "only-bin"
    d.mkdir(parents=True, exist_ok=True)
    for name in keep:
        real = shutil.which(name)
        if real and not (d / name).exists():
            (d / name).symlink_to(real)
    return ":".join([*map(str, extra_dirs), str(d)])
