# Design

## Decisions

### D1. The order of operations

1. `rename-to-gatedloop`, `public-status` and `role-commands` merge in this private repository.
2. The maintainer creates an empty public `tessellate-space/gatedloop`.
3. Run `go-public plan` and review its map.
4. Run `go-public transfer`. Issues move oldest first, and the real new numbers are recorded, overriding the predicted map wherever they differ.
5. Run `go-public tree <dir>` with the recorded map.
6. Run `go-public push`, which pushes and tags `v0.7.0`, the first public release.
7. Add the archive pointer in the private repository.

The transfer comes before the tree, because the tree's remapping needs the **real** numbers.

### D2. The map

`map.json` holds:
- `{"issues": {old: new}}`, from the transfer;
- `{"prs": [old…]}`, from `gh pr list --state all`.

Old issue and PR numbers share one sequence, so a number belongs to at most one list. A `#NN` that is neither is left alone, and the script reports it.

### D3. Reference rewriting

It applies to text files in the exported tree and to moved issues' bodies and comments:
- **Issues.** `#NN` and `tessellate-space/specloop#NN`, where NN is an issue, become `#<new>`.
- **PRs.** `#NN`, where NN is a PR, becomes `specloop PR NN` (the private archive), and a full PR URL keeps its URL.
- **Repository links.** `github.com/tessellate-space/specloop/issues/NN` and the like become the new repository's URL with the new number. A `/pull/NN` link stays pointing at the archive.
- **Where it doesn't touch.** Code blocks, and anything that isn't a reference (hex colours, `#` headings, shell comments). A reference is `#` followed by digits, at a word boundary, not inside a fenced or inline code span.
- **Output.** A report lists every rewrite, file:line old → new, so it can be reviewed in the dry run.

### D4. The email

In the tree, every occurrence of the personal email in a text file becomes the GitHub noreply address, `64685892+radub21@users.noreply.github.com`, the address already used on some commits. The archive's own files are never edited. The initial public commit and every later commit use the noreply identity, which is set in the new clone's git config by `push`.

### D5. What must hold before `push`

The script refuses to push unless all of these hold:
- the personal email appears nowhere in the tree;
- every rewrite report line has been produced;
- `python3 -m unittest discover -s tests` passes in the exported tree.

### D6. Tests

The script's text functions (the map, the rewriter, the email scrub) are tested on fixtures. The outward calls are tested against the fake `gh` in `tests/_forge_fixture.py`, extended for `issue transfer`, `issue edit` and comment edits. The real GitHub API is never called from tests.

## Risks

- **A transfer fails midway.** `transfer` is resumable: it skips issues already moved, using the recorded map, and continues.
- **Comments by other people.** Editing them needs repository admin rights, which the maintainer has. The edits are logged.
