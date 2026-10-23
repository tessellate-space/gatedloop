# Proposal

## Why

The maintainer chose to publish gatedloop as a **fresh public repository**, `tessellate-space/gatedloop`, rather than renaming this private one. A rename would expose the full history. Of 703 commits, 599 carry the maintainer's personal email, as do 68 tracked files (approval keys and ledger rows). Rewriting history in place would still leave the old commits reachable on GitHub through every closed PR's `refs/pull/*`, and only GitHub Support can purge those.

So the old repository stays private as the archive. The specs and archived changes carry the project's history into the new one, and **all 45 issues move**, with their comments, and are remapped.

GitHub's issue transfer keeps every comment but assigns new numbers, and PRs (96) can't be transferred at all. So every `#NN` reference needs remapping:
- in the clean tree: specs, archived plans, CHANGELOG, docs;
- in the moved issues' bodies and comments.

## What Changes

- **`scripts/go-public`**, repo-local maintainer tooling, never shipped (like `scripts/release`). Its subcommands, each with `--dry-run`:
  - `plan`: lists every issue (open and closed) and every PR, and writes the old→new number map for an oldest-first transfer, printing what each later step would do;
  - `tree <dir>`: exports the current tree with no history into `<dir>`, replaces the personal email with the GitHub noreply address in every text file, and remaps references (D3);
  - `transfer`: moves every issue, oldest first, with `gh issue transfer`, recording the real new numbers, then remaps references in each moved issue's body and in comments, which needs repository admin rights;
  - `push`: creates the initial commit with the noreply identity, pushes to the new repository, and tags the first public release.
- **The outward steps are separate commands** the maintainer runs: creating the repository, `transfer` and `push`. Nothing outward runs from `plan` or `tree`.
- **A pointer in the archive.** The archive's README gains one line pointing at the public repository. The public README says that numbers before 0.7.0 were remapped from the private archive, and that PR links name it.

## Capabilities

### New Capabilities

None. This is repo-local tooling, no plugin behaviour.

### Modified Capabilities

None.

## Impact

- `scripts/go-public` (new) and its tests.
- `RELEASING.md` gains a "Publishing the public repository" section.
- `rename-to-gatedloop` D5 now points here instead of `gh repo rename`.
