# Jira Team Simulator v2 Backlog

Product authority is [`/docs/v2/high-level-plan.md`](/docs/v2/high-level-plan.md). Pavel asked that
implementation detail be left to the capable implementing model, so this backlog tracks outcomes,
not a fixed microtask sequence.

The approved execution design is
[`2026-08-11-pragmatic-v2-live-simulator-design.md`](../../docs/superpowers/specs/2026-08-11-pragmatic-v2-live-simulator-design.md).
Accepted Tasks 1–6 remain frozen and usable. The capacity-credit Tasks 7/8 are superseded,
non-binding planning history and must not be resumed. Team count is configuration; five teams are a
UAT/load fixture only.

## Milestones

- [x] M0 — Agree requirements, architecture, and delivery order — completed 2026-08-10
- [ ] M1 — Deliver the persisted Scrum simulation core — **IN PROGRESS**; the reviewed
  persistence-spine and deterministic-kernel plans are complete, Task 5 has added authoritative
  state at revision 015 and is technically accepted after Ultra review of round-5 commit `0782070`
  reported CLEAN with no Critical or Important findings; Task 6 commit chain `4cfaa65` → `6bac956`
  → `47f9e55` is also technically accepted after independent Ultra review reported CLEAN with no
  Critical or Important findings in the completed [`m1-scrum-state.md`](m1-scrum-state.md) plan.
  The coherent bootstrap/read and incremental atomic Scrum-tick slices are complete with
  first-boundary, DST cadence, ranked capacity/WIP allocation, direct zero-touch transitions, and
  exactly one stale-runtime retry. Review fix round 1 preserves minimum-fraction availability,
  pre-fraction capacity, earliest shared completion, residual tick time, and causal evidence. The
  fixed lifecycle/scheduler/restart slice is complete with unchanged carryover, persisted due-team
  authority, exclusive paging beyond 100, sequential failure isolation, and evidence-first
  zero-work restart boundaries. Revision 016 and retryable Jira delivery are complete with strict
  per-team FIFO/dependencies, cross-team continuation, provider-visible create preflight, persisted
  pacing, and one post-reconciliation delivery job. Review fix round 1 keeps incomplete scope
  retryable/blocking and exhausts public Jira sprint pages before create. The first causal-risk and
  fake-Jira vertical now proves two sprint boundaries, restart without catch-up, outage recovery,
  retained intent drain, and provider-success/local-receipt replay without duplicate resources;
  review fix round 1 moves provisioning behind production bootstrap and corrects false-decision
  evidence, dependency one-shot continuation, business-time aging, and terminal precedence; next
  work is a focused inbound-observation, content, transcript, or API slice
- [ ] M2 — Deliver the first live Jira and Codex vertical slice
- [ ] M3 — Add manual Jira reconciliation, risks, content, transcripts, and ground truth
- [ ] M4 — Release the dashboard-backed Scrum MVP and run configured-load UAT
- [ ] M5 — Add and accept the Kanban vertical slice
- [ ] M6 — Measure higher configured loads and harden operations where evidence requires it

For each milestone, the implementing model should create only the reviewable, context-sized tasks
needed at that time, following `/AGENTS.md`, and update the relevant stage file before code changes.

The existing stage files contain a detailed planning draft created before Pavel asked for a
high-level plan. They are reference material only; their task IDs and sequencing are not binding.

The reviewed persistence spine is complete through revision 016. The
[`m1-deterministic-kernel.md`](m1-deterministic-kernel.md) plan is also complete: Task 3 provides
review-hardened slotted/reconstruction-resistant HMAC-U53 provenance, scoped safe-integer
coordinates, and formula-bound dwell/touch samples; Task 4 provides pure dual-clock/DST-safe
business-calendar, fixed-cadence, and review-hardened `US_FEDERAL_V1` horizon primitives. The
starter year is team-zone-derived, only available IANA keys are accepted, canonical horizons are
authenticated before use, stale extensions catch up idempotently in ten-year blocks, and extreme
timezone/local-boundary conversions expose a stable domain range error. M1 remains in progress. The
completed [`m1-scrum-state.md`](m1-scrum-state.md) plan contains exactly two context-sized slices:
Task 5 is complete with review-hardened revision-015 authoritative state persistence, sealed and
blueprint-authenticated timing provenance, typed semantic-owner constraints, exact zero-touch
null-activity visits, sample-complete snapshots, and sparse touched-row after-images resolved
against persisted owners before DML. Both mapper entry points require a clean caller ORM unit of
work, empty write sets reject before SQL, every nested draw is exactly typed and fully
HMAC-authenticated, and retained sample units are exact finite built-in floats. Matching clean ORM
identities are refreshed for every authority/state read, so committed updates, corruption, and
deletion cannot be masked by caller cache state; deleted cached visits can be restored from complete
after-images. Round-5 commit `0782070` narrowly detaches the confirmed-missing same-key visit and
sample identities during cascade restoration while preserving unrelated caller cache entries. Its
isolated and full verification is GREEN, and independent Ultra technical review reported CLEAN
with no Critical or Important findings. Task 6 now adds the exact immutable authoritative command,
one-session runtime/state/counter/natural/evidence transaction, sparse existing-row updates, exact
new-allocation ranges, work-item child-counter seeds, monotonic replay, typed stale/conflict rollback,
restart continuation, and unchanged post-commit adapter boundary. Review-fix round 1 freezes every
ownership/history coordinate, rejects missing established blueprint members, requires whole-slice
exactness for advanced replay, deeply validates committed results, and binds visible natural owners
before a session. Round 2 immutably rebuilds the nested committed runtime and ledger records so all
aware result instants retain exact UTC while naive instants still reject. Deleted established
counters remain stale; Task 6 itself added no external call or revision 016. Verification is 252
focused, 1037 all-v2 with one baseline warning, and 1555 full-backend
with 43 skipped and 15 baseline warnings; Ruff, static, Alembic, and no-migration checks are clean.
Original commit `4cfaa65`, round-1 commit `6bac956`, and round-2 commit `47f9e55` are verified; the
independent Ultra technical review reported CLEAN with no Critical or Important findings. Task 6 and
the Scrum-state plan are complete. The pragmatic Jira-delivery slice subsequently added reversible
revision 016 receipts/mappings and fake-provider retry/idempotency coverage without changing Task 6
authority or projection rows. M1 remains in progress. The former
[`m1-capacity-credit.md`](m1-capacity-credit.md) Tasks 7/8 are preserved as superseded planning
history and are not implementation or acceptance authority. The next task is the approved
focused inbound-observation/content/transcript/API slice rather than the superseded capacity-credit
matrix. The completed first realism vertical uses versioned deterministic rules for sampled long
stay, review return, cancellation, dependency pause, and member unavailability; it adds no schema
above sole head revision 016.

Before each M1 slice, preserve unrelated work and verify the mandatory Superpowers TDD skill required
by `/AGENTS.md`. Live Jira mutation always requires a designated disposable project/tenant and
explicit authorization.
