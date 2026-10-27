# Tasks

## 1. Move the expiry to 0.9.0

- [x] 1.1 Set `EARLIER_EXPIRY` to `0.9.0` in `bin/gates` and update the warning-tail test (`tests/test_earlier_name_read.py`) and any other test pinning `0.8.0` as the expiry. Leave the adoption tests that install a `0.8.0` plugin version alone, because they test versioning, not the expiry. Verify that `./bin/gates run ci` is green and that the warning reads `old names stop working in 0.9.0`
- [ ] 1.2 Name 0.9.0 as the expiry in README.md, SETUP.md (including "Through 0.8.x"), `docs/status.md`, RELEASING.md's expiry rule, CLAUDE.md's in-flight note and the `adoption/catalog.json` migrate-name item. Leave CHANGELOG.md's 0.7.0 section as history. Verify that `grep -rn "0\.8\.0"` outside archived changes and CHANGELOG history finds only the `git-push-hook` item's `since` and the plugin-version test fixtures, and that `scripts/release docs` reports no gap

## Workflow follow-up

- Re-attest `remove-specloop-forwarders` after this plan PR merges, because its artifacts change here.
