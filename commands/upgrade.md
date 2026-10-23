---
name: "gatedloop: Upgrade"
description: Walk the settings a new gatedloop version asks this project to decide, one question each, recording every answer as it is given.
category: Workflow
tags: [workflow, setup, upgrade]
---

A gatedloop release can add settings a project should choose deliberately rather than
inherit as defaults. This command walks **only the ones this project hasn't decided
yet**, one question each, and records each answer the moment it is given. It never
commits: the adopter owns their repository's history.

Which items are undecided is computed by the shim, not judged here. Never add, skip
or reorder an item on your own reading of the project.

## Steps

### 1. Ask the shim what is undecided
```bash
gates adoption status --json
```
- **Non-zero exit** → show its error verbatim and stop. It means the catalogue, the
  record (`.gatedloop/adoption.json`) or the manifest could not be read, and nothing
  can be decided until that is fixed.
- **`undecided` is empty** → say "Nothing to decide: every setting this gatedloop
  version introduced is decided, already set, or doesn't apply here." and stop. Ask
  nothing.

### 2. Show the list once
Print each item as `<id> (since <since>): <what>`, in the order the shim returned
them (by `since`, then catalogue order). Say the walk can stop at any point: every
answer already given stays recorded, and the next `/gatedloop:upgrade` resumes from
the first item still undecided.

### 3. One question per item, in that order
Read the item's full entry, with its `question`, `options` and `action`, from the catalogue
shipped with the plugin:
`${CLAUDE_PLUGIN_ROOT}/adoption/catalog.json`.

Ask **one AskUserQuestion** per item:
- the question is the item's `question`;
- the options are the item's `options`, **in catalogue order**: the first is the
  recommended one and its label already says so. Do not reorder or reword them;
- add one more option at the end: **"Decide later"**, which is never in the
  catalogue.

An item whose catalogue entry has `"recurs": true` (such as `git-hook-refresh`) is
an act a release can need again, not a setting chosen once. The shim lists it again
whenever its detector says the act is due, even after an earlier `adopted`, and a
`declined` holds only for the version it was recorded at. When you ask about a
recurring item, say so in one line before the question. If `.gatedloop/adoption.json`
already holds a decision for it, add that this is being asked again because the
installed version or the project changed since that answer.

Then act on the answer:

- **An `adopted` option**: carry out the item's `action` first, then record it.
  - `manifest-key`: set the dotted `key` in `.gates.yaml` to the chosen option's
    `value`, editing only that key and keeping the rest of the file's comments and
    layout. Then run `gates validate`. If it fails, show the errors, undo the
    edit, and record nothing for this item. Ask the question again, or move on if
    the adopter says so. A failing manifest is never left behind.
  - `onboarding-step`: run the named `/gatedloop:gates-init` step. Do **not** carry
    a copy of it here; follow that step as written in the `gates-init` command,
    including its own confirmations. Record `adopted` once the step finishes. If the
    adopter abandons the step partway, record nothing for this item.
  - `confirm`: show the item's `what`, then its `action.detail`, then ask the adopter
    to confirm. Where the detail asks you to name things in the project (for
    example the local schemas under `openspec/schemas/`, or the commands bound to
    the gates it lists), name them from the files, and change nothing.
- **A `declined` option** or **"Decide later"**: carry out nothing.

Record the answer **immediately**, before asking the next question:
```bash
gates adoption record <id> adopted     # or: declined | later
```
If `record` exits non-zero, show its message and stop the walk. An answer that
was not recorded must not be followed by more questions.

### 4. Close
```bash
gates adoption status
```
Show what is left. It should be nothing, apart from any items deferred with "Decide
later", which come back once the plugin version changes, as does a recurring item
declined at this version. Then name the files this
walk may have changed, `.gatedloop/adoption.json` and `.gates.yaml` (plus anything an
onboarding step wrote), and say they are left uncommitted. Committing
`.gatedloop/adoption.json` is how the whole team shares these decisions.

## Guardrails
- Ask only what `gates adoption status` lists. Never ask about an item it didn't list,
  and never decide one on the adopter's behalf.
- Record each answer with `gates adoption record` as soon as it is given, never in a
  batch at the end. Never write `.gatedloop/adoption.json` by hand.
- Every change to the project goes through the adopter's answer. A `declined`
  or "Decide later" changes nothing but the record.
- Never commit, and never run this walk unattended. A headless session gets the
  session brief's one line and is never asked anything.
