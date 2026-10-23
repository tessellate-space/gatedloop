---
name: feedback
description: "File a structured, privacy-bounded report against gatedloop's own repository — a bug/friction report or a positive \"worked in stack X\" field report. Context is gathered from a fixed whitelist only; the complete literal issue body is shown and explicitly approved before anything is posted; a missing `gh` degrades loud, never silent."
argument-hint: "[bug|friction|field-report]"
---

# Feedback

Turn a running gatedloop into a structured channel back to its own repository. This
skill files a GitHub issue — either a **bug/friction** report or a positive
**field report** ("it worked in stack X") — under one hard rule: **nothing leaves
the machine that you have not read and approved.**

People run gatedloop inside real projects, some of them client work. A leaked
snippet of project code or a proprietary gate command in a public issue is a
trust incident, not a bug report. So collection is a **positive whitelist** (a
source not on the list is excluded by default, never stripped by exception), and
the **complete literal issue body** is shown for explicit approval before any send.

**Not a stack binding.** This skill names `gh` and posts to gatedloop's *own*
repository — the one in `plugin.json`'s `repository` field — never the adopter's
project repo, and never the adopter's test/build/probe commands. `gh` here is
gatedloop talking to its own home, the same way the loop's approval-attestation
already shells out to `gh`. The repository slug has a single source of truth
(step 2); it is never hard-coded in this prose.

---

## Steps

### 1. Choose the report kind

Ask the reporter (or read it from the invocation argument) which kind of report this
is. Both kinds run the **identical** whitelist, approval, and degradation path — the
only difference is the label applied at creation:

| Kind | When | Label |
|---|---|---|
| Bug / friction | Something broke, was confusing, or fought you | `friction` |
| Field report | gatedloop worked in a stack we may not have anticipated | `field-report` |

A positive confirmation is field evidence too — the cheap half to collect — so it is
a first-class path, not an afterthought.

### 2. Resolve the target repository from plugin metadata

Read `${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json` and take its `repository`
field. Normalise it to an `owner/repo` slug (strip the `https://github.com/` prefix
and any trailing `.git`). This is the **only** source of the slug — never type the
owner/name into the issue body, the `gh` command, or a template by hand. A fork or
rename then retargets reports automatically instead of filing them into the wrong
tracker.

Derive two values and keep them for later:
- **slug** — `owner/repo`, for `gh issue create -R <slug>`.
- **issues URL** — `<repository>/issues/new` (the `repository` value with `/issues/new`
  appended), for the manual-filing fallback in step 6.

If `plugin.json` has no `repository` field, stop and say so plainly — the skill
cannot guess a destination, and guessing is exactly the drift this step prevents.

### 3. Gather context — from the whitelist ONLY

Collect **only** the items below, deterministically, and **nothing else**. This is
an allowlist: if a datum is not named here, it is not collected.

| Whitelisted item | How it is obtained |
|---|---|
| Plugin version | the `version` field of the same `plugin.json` read in step 2 |
| OpenSpec CLI version | `openspec --version` |
| `gates` diagnostics | `gates validate` output; also `gates doctor` **if the installed `gates` provides it** — tolerate its absence, do not treat a missing `doctor` as an error |
| The command or gate the report concerns | ask the reporter; record the `/gatedloop:*` or `/opsx:*` command name, or the abstract gate **name** (`ci`, `unit`, …) |
| `.gates.yaml` **shape** | the gate **names** (the keys under `gates:`) and each surface's `name` + `match` glob — see the carve-out below |
| OS / platform | `uname -sm` (or the platform equivalent) |

**The `.gates.yaml` carve-out is the subtle one — get it exactly right.** Record the
gate **names** (`ci`, `unit`, `verify`, …) and the surface **globs** (`backend/app/**`).
These are gatedloop's own vocabulary and are safe. **Never** read or record the command
**body** a gate name maps to (the value of a `gates:` entry, or any `live-check:`
value) — a deploy command with an embedded token is the adopter's, not ours, and it
never leaves the machine. If a report genuinely needs a gate body to make sense, that is a string
the reporter pastes in **by hand**, having seen it — the skill does not read it for them.

**Everything off this list is excluded by default.** In particular the skill does
**NOT** read or attach: diff content, the adopter's project file contents, gate
command bodies, environment variables, or credentials. If the fullest context for a
failure would be a project file or a diff, do **not** read it — instead tell the
reporter they may paste, by hand, only what they choose to disclose, and that whatever
they paste will appear verbatim in the body they approve in step 5.

### 4. Assemble the complete literal issue body

Build the exact markdown that will be posted — title and body — from the report kind,
the reporter's description, and the whitelisted context from step 3. Anything the reporter
chose to paste by hand (step 3) goes in verbatim. This assembled text is what step 5
shows; there is no second, richer version assembled elsewhere.

Use a stable structure mirroring the issue templates in `.github/ISSUE_TEMPLATE/`:
what happened / expected vs actual (or, for a field report, what worked), the command
or gate involved, the environment block (plugin version, OpenSpec version, OS/platform,
`gates` diagnostics, `.gates.yaml` shape), and anything pasted by hand.

### 5. Show the literal body and get explicit approval

Show the reporter the **complete, literal issue body** — the exact text, byte for byte,
that step 6 will post. A summary ("I'll include your versions and platform") does
**not** substitute: the whole failure mode this guards against is a field the reporter
did not realise was being sent, and only the literal payload surfaces it.

Then ask for explicit approval to post.

- **Approved** → proceed to step 6.
- **Declined / edits requested** → post **nothing**. Apply any edits to the body and
  show the revised literal body again for approval. The report is never sent by any
  other path on a decline.

Up to this point **no network call that could publish the report has been made.** The
only commands run so far read local state (`plugin.json`, `openspec --version`,
`gates validate`, `uname`) — none of them post.

### 6. Post — or degrade loud

Only after explicit approval, attempt the post. `gh issue create` is the **first and
only** call that can publish:

```bash
gh issue create -R <slug> --title "<title>" --label <label> --body-file <approved-body>
```

where `<label>` is `friction` or `field-report` per step 1. (Pass the approved body via
a file or here-doc so it is posted verbatim, unaltered from what was shown.)

**If `gh` is missing, unauthenticated, or offline** — detected before or when the post
is attempted (`command -v gh`, a failing `gh auth status`, or a network error from
`gh issue create`) — **degrade loud, never silent:**

1. Print the **complete issue body** again (the approved text), so the reporter has it in
   full to file by hand.
2. Print the issues URL from step 2 (`<repository>/issues/new`) and name the label to
   apply.
3. State plainly that **nothing was posted automatically** and that this is the manual
   path, not a failure the reporter has to decode.

Never drop the report on a failed post, never report success over an unsent report, and
never fall back to broader/unbounded collection to "make up for" the missing CLI. The
whole point of this channel is not losing signal.

### 7. Confirm

On a successful post, print the issue URL `gh` returns and the label applied. On the
degraded path, confirm the reporter has the full body and the manual-filing URL. Either
way, the reporter knows exactly where the report is (or that it is theirs to file).

---

## Guardrails

- **Whitelist only.** Collect exactly the step-3 items and nothing else. A source not on
  the list is not collected — never denylisted-then-stripped. No diffs, no project file
  contents, no gate command bodies, no env/credentials.
- **Gate names and globs, never bodies.** The `.gates.yaml` shape is names + surface
  globs. The command a name maps to is the adopter's and is never read.
- **Literal body before send.** The exact text is shown and explicitly approved before
  the first publish-capable call. A summary never substitutes; a decline posts nothing.
- **Slug from metadata.** The repository is resolved from `plugin.json`'s `repository`
  via `${CLAUDE_PLUGIN_ROOT}` — never hard-coded in prose, so a fork or rename cannot
  leave a stale target.
- **Fail loud, never silent.** No `gh` → print the full body and the manual-filing URL
  and say nothing was posted. Never a silent drop, never a success message over an
  unsent report.
- **Both kinds, one contract.** Bug/friction and field report differ only by label;
  whitelist, approval, and degradation are identical for both.
