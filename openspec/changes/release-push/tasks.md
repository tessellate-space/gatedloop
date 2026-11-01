## 1. The push gate

- [x] 1.1 `_push_changes` leaves out a change branch whose tip is an ancestor of the merge target's remote-tracking ref, and the `check-push` refusal for a commit that carries no change says it belongs to no change in flight instead of naming one (design D2, D3) [oracle: unit]

## 2. Release tooling

- [ ] 2.1 `scripts/release publish` refuses, before its first write, inside an agent session (`gates discipline agent-session` exits 0), writing the notes to `.gatedloop/out/release-notes-vX.Y.Z.md` and printing the full command sequence; RELEASING.md's `publish` section says it runs outside an agent session (design D1) [oracle: unit]
