# Tasks

## 1. The declared range (D1, D3)

- [x] 1.1 Set `OPENSPEC_MAX_TESTED = "1.16.0"` in `bin/gates` and the highest tested value in `docs/stability.md` to `1.16.0`, leaving `OPENSPEC_MIN` at `1.14.3`. (`tests/contract.json` does not snapshot the constants; no regeneration needed.) Verify with the existing range tests that 1.15.0 and 1.16.0 are inside the range, 1.16.1 above it, and that the constants match `docs/stability.md` [oracle: unit]
- [x] 1.2 State the range as 1.14.3 to 1.16.0 in `README.md` (status line, install prerequisites, OpenSpec prerequisite), `SETUP.md` prerequisite 1 (plus: OpenSpec 1.16's npm install needs Node.js 22.12+; the standalone binary doesn't) and `docs/status.md` (header and Upstream coupling, plus one sentence that 1.16's `validate --strict` fails a scenario with no WHEN/GIVEN or THEN step). Verify `grep -rn "1.14.3 to 1.14.3\|\`1.14.3\` to \`1.14.3\`\|\*\*1.14.3\*\* to \*\*1.14.3\*\*" README.md SETUP.md docs` finds nothing [oracle: none]

## 2. The ci matrix (D2)

- [x] 2.1 Add `include: [{os: ubuntu-24.04, python: '3.13', openspec: '1.16.0'}]` to the `ci` matrix in `.github/workflows/gatedloop.yml`, leaving `PRIMARY` on 1.14.3 and the `record` job untouched. Verify on the implementation PR that five legs run, the 1.16.0 leg runs `gates run ci`, and only the 1.14.3 ubuntu/3.13 leg posts `gatedloop/ci` and `gatedloop/tests` [oracle: none]
