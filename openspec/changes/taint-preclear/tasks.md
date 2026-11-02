## 1. The audit vouches by the head

- [ ] 1.1 In `cmd_audit`, record a `vouched` row instead of a taint for a commit with no green `ci` row of its own when it is an ancestor of the audited head and a green unscoped `ci` row names the head's tree, compared ledger-blind; a scoped head `ci` or none taints as before; `vouched` rows count as already classified (design D1, D2) [oracle: unit]
- [ ] 1.2 A rebased change whose head passed a full `ci` goes through `gates merge` step 1 with no taint, and one whose head `ci` was scoped is still refused (design D1, D3) [oracle: unit]

## 2. Docs

- [ ] 2.1 Describe vouching by the head in AUTOMATION.md's enforcement layer 3 and SETUP.md's taint section (design D1–D3) [oracle: none]
