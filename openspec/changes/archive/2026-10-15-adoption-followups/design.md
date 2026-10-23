# Design

## Context

`adoption-prompts` shipped the catalogue (`adoption/catalog.json`), the closed sets of
detector, predicate and action kinds in `bin/gates`, `.specloop/adoption.json`, and
`/specloop:upgrade`. Two other 0.5.0 changes each left one item for when it landed:

- `lock-and-ledger-hygiene` D-hook: `git-hook-refresh`, whose detector compares the
  installed hook's body against the template, and whose action runs the hook-install
  step;
- `merge-step` D6: `confirm-gate`.

Two facts about today's code shape the first item:

- `_hook_install` returns "already installed — nothing to do" whenever
  `_hook_already_wired(path)` holds. That includes a direct copy of an *older*
  template, so re-running the install step cannot refresh anything.
- Only the `kind == "none"` path writes a copy of the template. The husky path, and
  the snippet printed for a hand wiring, delegate to
  `${CLAUDE_PLUGIN_ROOT}/templates/git-hooks/pre-commit` at run time, so they follow
  the installed plugin.

## Decisions

### D1. A direct copy is recognized by its header, not by where it sits

A file is a **direct copy** when it contains `_HOOK_TEMPLATE_MARK` and does not
contain `SPECLOOP_HOOK_BEGIN`. That matches every file the `none` path has ever
written, wherever `_detect_hook_owner` finds it. A composed file holds the begin
marker and is never a copy.

A copy is **current** when its bytes equal the shipped template's. Comparing bytes
rather than a version line keeps it free of a format that would itself need
migrating. One consequence: an adopter's local edit to a copy reads as stale.
Replacing the copy keeps the edit in a backup file (D3), so nothing is lost and the
installer says where the edit went.

### D2. Two new kinds, each in its own closed set

- **Detector `git-hook-current`** (no fields). The project has acted unless the hook
  path holds a direct copy that is not current. That includes the case where no hook
  is installed: there is nothing to refresh, and whether to install a hook at all is
  `gates-init`'s question, not this item's.
- **Predicate `git-hook-copy`** (no fields). Holds when the hook path holds a direct
  copy, current or not.

Both read one new fact, `facts["hook"]`, gathered once by the same code path
`gates doctor` uses. It is `{"copy": bool, "current": bool}`, and the evaluators
stay pure.

### D3. The installer replaces its own stale copy and nothing else

`gates hook install` gains one case, checked before the "already wired" early
return. If the path holds a direct copy that is not current:

1. it writes the old body to `<hook path>.specloop-prev`, overwriting an earlier
   backup;
2. it writes the shipped template and keeps the executable bit;
3. it prints the hook path and the backup path, and that a local edit to the old copy
   is in the backup;
4. it exits 0.

A current copy keeps today's "nothing to do" message. Everything else is unchanged:
- a composed hook is left alone;
- a foreign bare hook gets the same refusal as today;
- hook-manager config is never touched.

The no-clobber requirement holds because a direct copy is Specloop's own file.

### D4. Recurring items: the detector is the truth

A catalogue item may carry `"recurs": true` (default `false`). For a recurring item,
`_decision_applies` changes:

- `adopted` never applies. Whether the act was done is the detector's call, every
  time.
- `declined` applies only while the installed version equals the version it was
  recorded at, the same rule `later` already follows.
- `later` is unchanged.

The reason: a refresh is an act that each release may require again, not a setting
chosen once. Without this rule, `adopted` recorded at 0.5.0 would hide the 0.6.0
refresh, and `declined` would silence every future template change for good.
`gates adoption record` stores the version on every decision already, so no record
format changes.

`RELEASING.md` says a template change needs **no** new item, because
`git-hook-refresh` recurs.

### D5. `confirm-gate`

| Field | Value |
|---|---|
| detector | `manifest-key gates.confirm` |
| applies when | `surface-key live-check` |
| action | `onboarding-step`, naming `gates-init`'s confirm offer |
| `since` | `0.5.0` |
| recurs | no |

The `merge-step` design wrote `gates.live-check`. The schema has no such key, since
live-checks are bound per surface. `gates-init`'s own offer ("once any `live-check`
is bound") already reads it the right way.

### D6. `git-hook-refresh`

| Field | Value |
|---|---|
| detector | `git-hook-current` |
| applies when | `git-hook-copy` |
| `since` | `0.5.0` |
| recurs | yes |

The action is `onboarding-step`, naming `gates-init`'s hook-install step, which now
refreshes per D3. `/specloop:upgrade` already reports that step's output verbatim.

### D7. `gates doctor`

The hook row gains a `stale-copy` state from `_hook_state`. It warns, naming
`gates hook install` as the fix. The row stays advisory, like every doctor row.

## Risks

- **Byte comparison flags harmless differences**, such as line endings rewritten by
  a git config. The cost is one refresh with a backup, which is acceptable.
- **The backup is overwritten on a second refresh.** It holds only the last body, and
  the one before that is the previous template, so nothing the adopter wrote is lost
  unless they edited two releases in a row without looking. The installer's message
  names the backup each time.
