# V2 Stage 0 — Contract and Execution Foundation

> **DETAILED REFERENCE DRAFT — NOT ACTIVE.** See [`README.md`](README.md) for milestone status.
Status: IN PROGRESS

## Tasks
- [x] V2-S0-T01 — Freeze the approved v2 plan — completed 2026-08-10
- [ ] V2-S0-T02 — Checkpoint and isolate the implementation worktree
- [ ] V2-S0-T03 — Verify mandatory skills and reproducible toolchain
- [ ] V2-S0-T04 — Capture baseline and establish evidence harness
- [ ] V2-S0-T05 — Implement blueprint contracts and starter-catalog resolution
- [ ] V2-S0-T06 — Add the additive v2 feature gate and health shell
- [ ] V2-S0-T07 — Restore the SQLite/WAL deployment contract
- [ ] V2-S0-T08 — Preserve or explicitly clear the deployed-data cutover
- [ ] V2-S0-T09 — Prove the target-tenant Jira topology provisioning path

## UAT Results
(pending Gate G0 evidence and Pavel's review)

## Notes
- Task contracts and Gate G0 are in `/docs/v2/implementation-plan.md` and
  `/docs/v2/verification-matrix.md`.
- No implementation code was changed by V2-S0-T01.
- V2-S0-T01 evidence is in `/evidence/v2/V2-S0-T01/README.md`.
- V2-S0-T02 must preserve the existing dirty assessment/planning worktree; no stash/reset/clean.
- V2-S0-T03 must verify the missing mandatory Superpowers TDD skill before code work.
- V2-S0-T08 records a no-op only if the read-only deployed-data inventory proves no prior data needs
  migration; otherwise it preserves source data with count/checksum evidence.
- V2-S0-T09 requires Pavel-authorized disposable Jira mutation and blocks the engine when the public
  API cannot produce/read back the exact canonical topology; it never falls back to private APIs or
  UI automation.
