## 1. README

- [x] 1.1 Add the status paragraph (design D1) and reorder the README with the quickstart before the vocabulary (design D2)

## 2. Status and topology

- [x] 2.1 Write `docs/status.md` from the field guide per design D3, and make `docs/field-guide.md` a one-line redirect
- [x] 2.2 Write `docs/topology.md` per design D4

## 3. Wording

- [x] 3.1 Remove the tester and trial wording from the feedback skill (design D5), and check `AGENT_INSTALL.md` for private-repository assumptions

## 4. Close

- [x] 4.1 `python3 scripts/release docs` exits 0; `gates run ci` green; `openspec validate public-status --strict` passes
