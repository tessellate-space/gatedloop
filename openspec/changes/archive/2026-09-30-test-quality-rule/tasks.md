## 1. The built-in rule and its resolution

- [x] 1.1 Add `rules/loop-rules.md` with a short header (what the file is, that its ids are `specloop.`-prefixed, and that `gates rules` always lists them) and the `### specloop.test-quality` section, with the design D3 text verbatim
- [x] 1.2 A test runs the shipped-pack stack-name audit over `rules/loop-rules.md` and asserts no project-specific tool, framework or library name appears
- [x] 1.3 `cmd_rules` prints the "Built-in loop rules (always apply)" block and the resolved plugin-relative path after the surface rules, for every diff including one with no hot surface (design D1)
- [x] 1.4 Add `rules/` to `SHIPPED_PATHS` in `scripts/release` (and wherever `RELEASING.md` lists the shipped set), so a change to the rule counts as shipped
- [x] 1.5 `cmd_rules` exits non-zero with an explicit message when the built-in file or a listed section is missing; tests cover present, missing file and missing section

## 2. The loop's prompts

- [x] 2.1 `skills/tdd-apply/SKILL.md` 5c: replace the one-line RED step with the design D4 four-question checklist, including the `weak-spec` halt for an extraction outside the task
- [x] 2.2 `skills/tdd-apply/SKILL.md` 5c and `agents/tdd-implementer.md`: step 0 of the RED order (`gates rules --changed <task paths>` plus `design.md`, read before the questions), classification and seams from the project's rules, project-rule precedence, and the "no seam defined" `weak-spec` halt (design D4a)
- [x] 2.3 `skills/tdd-apply/SKILL.md` 5d/5h: add the scaffolding-test deletion (D4) and the `Covered-by:` trailer for a task that adds no test (D5); 5f passes the commit message draft to the review with the diff
- [x] 2.4 `skills/tdd-apply/SKILL.md` steps 6 and 7 per design D6; the 5-bugfix route gains its one line (D4)
- [x] 2.5 `agents/tdd-implementer.md`: a short "Before any test" section carrying the four questions and the `Covered-by:` rule, pointing at the skill for detail; the halt-cause table gains the "needs a domain seam" row under `weak-spec`
- [x] 2.6 `agents/convention-review.md`: step 3 resolves built-in rules from the path `gates rules` prints and applies `specloop.test-quality` to test code in the diff, citing `specloop.test-quality #<n>` (design D8)

## 3. Adopter-facing docs

- [x] 3.1 SETUP.md: the "a blocking gate's runner must" list (design D7), and a short note in the conventions section that `specloop.test-quality` is built in and always reviewed, and one sentence naming layering rules as the ones the loop consults before writing code (design D4a)
- [x] 3.2 `commands/gates-init.md`: the one-line runner requirement when binding `verify` or `live-check`
- [x] 3.3 README's component table or "how to read it" notes mention the built-in rule in one line

## 4. Close

- [x] 4.1 `gates run ci` green on the final tree; `openspec validate test-quality-rule --strict` passes
