## 1. Confirm the reproduction is red

- [ ] 1.1 Run report.md's reproduction through `gates run unit` — confirm it fails today, for the reason root cause describes. If it passes, stop: it doesn't reproduce the bug.

## 2. Fix

- [ ] 2.1 <!-- Implement the fix -->

## 3. Confirm green and commit

- [ ] 3.1 Run the same reproduction again — confirm it now passes.
- [ ] 3.2 `gates run ci` green.
- [ ] 3.3 Commit the fix and the reproduction together.
