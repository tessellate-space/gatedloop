## 1. Precondition

- [ ] 1.1 Run `gates migrate-name` on this repository and commit the result, per design D4

## 2. Removal

- [ ] 2.1 Remove read-both and the earlier-name warning from `bin/gates`; a `.specloop/`-only project is refused naming `gates migrate-name` (design D1, D2). Tests
- [ ] 2.2 `gates marker publish` posts only `gatedloop/<gate>`. Tests
- [ ] 2.3 Remove the forwarder plugin, its marketplace entry and its release-script field (design D1). Tests

## 3. Close

- [ ] 3.1 Shrink the allow-list test and the migration notes (design D3); `gates run ci` green
