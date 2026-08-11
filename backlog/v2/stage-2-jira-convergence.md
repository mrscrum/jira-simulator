# V2 Stage 2 — Outbound Jira Provisioning and Convergence

> **DETAILED REFERENCE DRAFT — NOT ACTIVE.** See [`README.md`](README.md) for milestone status.
Status: IN PROGRESS

## Tasks
- [x] Revision 016 and retryable v2 Jira delivery — completed 2026-08-11
- [ ] V2-S2-T01 — Define typed Jira adapter and capability probe
- [ ] V2-S2-T02 — Implement dependency-aware idempotent outbox writer
- [ ] V2-S2-T03 — Provision and validate the company-managed project
- [ ] V2-S2-T04 — Ensure virtual fields, contexts, and screens
- [ ] V2-S2-T05 — Provision and validate issue types, workflow, and board topology
- [ ] V2-S2-T06 — Project issues, typed fields, relative rank, and transitions
- [ ] V2-S2-T07 — Project dependency-safe sprint lifecycle
- [ ] V2-S2-T08 — Add projection reconciliation, outage recovery, and backpressure
- [ ] V2-S2-T09 — Run disposable Jira two-sprint projection acceptance

## UAT Results
(pending Gate G2 evidence and Pavel's review)

## Notes
- Live mutation requires a designated sandbox/prefix and authorization; unit/fake work proceeds first.
- Stage 2 preserves unexpected Jira differences without overwriting them. Full human-intervention
  ingestion follows the Codex alpha in Stage 4.
- No v2 Jira comments and no simulator-originated changes to actual assignee/reporter.
- The pragmatic outbound foundation now has strict team FIFO/dependencies, retry receipts, semantic
  mappings, provider-visible create preflight, and one post-reconciliation delivery job. Live Jira
  acceptance, inbound reconciliation, and full provisioning breadth remain future work.
