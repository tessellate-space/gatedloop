# Proposal: batch-approval-check

## Why

A console that shows whether each change is approved has to call `gates approval check <change>` once per change. tessellate's delivery console makes about 54 such calls per page load, at 0.33–0.42 s each, which is about 17.5 s of a 38 s load (#182). Almost all of that cost repeats across calls rather than varying per change:

- an interpreter start for each call;
- about 17 git calls per check. They resolve the same merge target and the same local counterpart. `_approval_sha_ref` also runs one `git show` per plan file.

To work around this, the console runs 8 checks at a time and caches the results under a key it has to guess. That copies gatedloop's invalidation logic outside gatedloop, and a wrong guess shows a stale approval as valid.

Rejection test: this makes an existing guarantee, that the plan is approved on the target, cheap enough to check where a team looks at it. It authors no artifact and names no stack command.

## What Changes

- **`gates approval check --json [<change> ...]`.** It resolves the merge target and the policy once, reads every plan file the named changes need in one batched git read, and prints one JSON document. Each change gets the same verdict and the same reason text that the single-change form gives it. Exit 0 when every check passes, 1 otherwise. With no names, it checks every change under `openspec/changes/` (not `archive/`) on the resolved ref.
- **A fingerprint of the inputs.** The document carries a `fingerprint` computed from everything a verdict reads: the policy, the target ref and its commit, and the local counterpart and its commit when one is consulted. A caller can cache the whole document under it. There is no `--since`, because the fingerprint is cheap to recompute and a caller-supplied SHA would be one more input to trust.
- The single-change form `gates approval check <change>` keeps its arguments, its output and its exit code. Internally it uses the same code path.
- The new document's top-level keys join `tests/contract.json`, beside `handoff` and `stats`.

## Capabilities

### Modified Capabilities

- `approval-policy`: the batched check.
- `public-contract`: the snapshot records the batched check's document keys.

## Impact

- `bin/gates`: `_approval_check_at` is split into a resolved context (the target, its local counterpart, the policy) and a per-change verdict. A batched blob reader (`git ls-tree` plus `git cat-file --batch`) feeds `_approval_sha_ref`'s hash. The argparse entry for `approval check` gains `--json`, and its positional becomes `nargs="*"` when `--json` is passed.
- `tests/`: a new `tests/test_approval_check_batch.py`, plus `tests/test_contract.py` and `tests/contract.json`.
- `SETUP.md` (the command reference) and `docs/stability.md` (the list of covered documents).
