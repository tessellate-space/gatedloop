# Design: batch-approval-check

## Context

`_approval_check_at(root, change, m)` resolves the merge target, falls back to the local counterpart under `approval.plan: self`, reads `.openspec.yaml` on the chosen ref, and compares `approved_sha` with `_approval_sha_ref(root, change, ref)`. That function runs one `git ls-tree` and then one `git show` per plan artifact file, plus the `tasks.md` read for the oracle tags. Every part except the last three steps is the same for every change.

## Decisions

### D1. One resolved context, many verdicts

`_approval_context(root, m)` resolves, once:
- the policy;
- the target, or the refusal reason when no target resolves;
- under `self`, the local counterpart branch, if it exists.

`_approval_verdict(ctx, change, reader)` returns `(ok, ref, reason, meta)`, where `meta` is `approved_by`, `approved_at` and `approved_sha`. It applies today's rules in today's order, with the same reason strings, including the unpushed-merge advisory. `_approval_check_at` becomes a thin wrapper that builds a context and a single-change reader. Its callers (`handoff`, `check-implement`, `_plan_approval_refusal`) and their outputs are unchanged.

### D2. A batched reader that hashes the same bytes

For each ref the batch consults (the target and, if needed, the counterpart), the reader runs:
- one `git ls-tree -r <ref> -- openspec/changes/`;
- one `git cat-file --batch` for every blob the named changes need (artifacts, `.openspec.yaml`, `tasks.md`).

So the number of git calls doesn't depend on how many changes are named.

The approval hash must be identical to `_approval_sha_ref`'s. Today each file is read with `text=True`, which decodes UTF-8 with universal newlines, so `\r\n` and `\r` become `\n`. The reader decodes each blob the same way before hashing. A test compares the batched sha with `_approval_sha_ref` for a change whose files include a CRLF file and a non-ASCII one. Presence on the ref (`_change_present_on_ref`) is answered from the same `ls-tree` listing.

### D3. The document

```json
{"policy": "self", "target": "origin/main", "fingerprint": "<sha256 hex>",
 "results": [{"change": "...", "ok": true, "ref": "origin/main", "unpushed": false,
              "approved_by": "...", "approved_at": "...", "approved_sha": "...",
              "reason": "..."}]}
```

- `results` keeps the order of the names given, or sorted name order when none are given.
- A refused change has `ok: false` and `ref: null`. Its `approved_*` fields are whatever its `.openspec.yaml` on the consulted ref holds, or `null`.
- `unpushed` is true where the local counterpart answered.
- A context failure, meaning no target resolves, is still a document: every result is refused with the context's reason, and the command exits 1.
- A name that has no change on the ref gets today's "not present" reason.
- An empty `openspec/changes/` gives `results: []` and exit 0.

### D4. The fingerprint

The fingerprint is the SHA-256 of these fields, newline-joined:
- the document version `1`;
- the policy;
- the target name and the commit it resolves to;
- under `self`, the counterpart's name and commit, or `-` when there is none.

Those are every input a verdict reads, because each verdict reads only blobs at those commits. A caller that keys its cache on the fingerprint is correct by construction. Recomputing it costs the same few `rev-parse` calls the batch runs anyway. So there is no `--since` and no "unchanged" short-circuit.

### D5. The argument surface

`approval check` takes `--json`. Without it, exactly one change is required, as now; zero or several names exit 2, naming `--json`. With it, zero or more names are allowed. The single-change form's text output is unchanged.

## Risks

- D2's newline rule copies today's behaviour, including its quirk. Fixing the quirk would invalidate every recorded approval, so it is out of scope.
- A large repository's `ls-tree` over `openspec/changes/` stays one call. Its output grows with the number of changes, not with the number of git calls.
