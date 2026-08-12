# V2 Stage 4 — Jira Intervention, Causal Risks, Internal Content, and Transcripts

> **DETAILED REFERENCE DRAFT — NOT ACTIVE.** See [`README.md`](README.md) for milestone status.
Status: NOT STARTED

## Tasks
- [x] First realism behaviors and fake-Jira vertical acceptance — completed 2026-08-11; intrinsic-pause correction verified
- [x] First realism and vertical acceptance review fix round 1 — completed 2026-08-11
- [x] First realism continuation-evidence review fix round 2 — completed 2026-08-11
- [ ] V2-S4-T01 — Add durable verified Jira webhook intake
- [ ] V2-S4-T02 — Register webhooks and normalize/deduplicate Jira interventions
- [ ] V2-S4-T03 — Adopt manual sprint topology and scope membership
- [ ] V2-S4-T04 — Import unknown Jira cards with explicit defaults
- [ ] V2-S4-T05 — Adopt manual estimate, priority, relative rank, and content changes
- [ ] V2-S4-T06 — Adopt manual status, terminal, blocking, deletion, and archive changes
- [ ] V2-S4-T07 — Detect protected-field and protected-topology conflicts
- [ ] V2-S4-T08 — Complete poll snapshots, startup intervention drain, and stale supersession
- [ ] V2-S4-T09 — Implement confirmed Jira-conflict resolution
- [ ] V2-S4-T10 — Persist versioned risk policies and evaluation triggers
- [ ] V2-S4-T11 — Implement versioned causal probability engine
- [ ] V2-S4-T12 — Implement status-aging and carryover monitors
- [ ] V2-S4-T13 — Implement synthetic external dependency episodes
- [ ] V2-S4-T14 — Implement cancellation and review/QA/PO rejection
- [ ] V2-S4-T15 — Implement member unavailability
- [ ] V2-S4-T16 — Add risk-policy and causal-event APIs
- [ ] V2-S4-T17 — Implement structured OpenAI content jobs, safe backfill, and fallback
- [ ] V2-S4-T18 — Implement internal daily transcript documents
- [ ] V2-S4-T19 — Add deferred MCP content, risk, transcript, and Jira-conflict tools
- [ ] V2-S4-T20 — Prove manual-intervention and named-risk scenarios

## UAT Results
(pending Gate G4 evidence and Pavel's review)

## Notes
- LLM output narrates committed mechanics and never decides risk outcomes.
- Transcripts remain internal and produce no Jira comments.
- Full manual Jira intervention support is deliberately after Gate G3 so basic Codex/statistical
  Scrum arrives first, but it remains mandatory for the Scrum MVP release at Gate G5.
- The first pragmatic risk policy evaluates versioned blueprint rules at persisted triggers for
  sampled long stay, configured review return, cancellation, external dependency, and member
  unavailability. It records causal factors/draw/deltas/intents and uses deterministic fallback
  text without calling a language model.
- The remaining detailed Stage 4 task list is still non-active reference scope; inbound Jira,
  generated content, transcripts, APIs, and named scenario breadth remain later slices.
- Review fix round 1 records due false outcomes, makes dependency entry decisions one-shot with
  state-only continuation, uses business-service long-stay aging, and enforces terminal precedence
  when multiple configured risks share a tick.
- Review fix round 2 gives every committed dependency continuation wait delta a ground-truth-only
  record while preserving no-redraw, no-repeat-start, no-projection, and terminal precedence.
- Final review correction prevents external-dependency entry or continuation on workflow statuses
  whose configured semantics already pause the service clock.
