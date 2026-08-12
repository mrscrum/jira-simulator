# V2 Calibration Ground-Truth Contract

Ground truth explains why each simulated outcome occurred and correlates it with Jira. It is
append-only and distinct from user-facing activity copy.

## Required common fields

- `ground_truth_id`, globally increasing `append_sequence`, zero-based `transaction_sequence`,
  `schema_version`, `algorithm_version`
- `team_id`, `run_id`, optional `sprint_id`, `work_item_id`, `status_visit_id`, `member_id`
- known Jira project, board, sprint, issue, and status identifiers
- `decision_type`, `decision_sequence`, `occurred_at`, `recorded_at`
- root-seed reference and deterministic substream key (never a secret)
- structured inputs, output, and units
- causation/correlation IDs and originating actor/source
- baseline/profile IDs and versions

## Status-visit records

Append-only visit evidence is split so later duration facts never rewrite an entry record:

### Sample/open

- canonical status and Jira status mapping
- issue type and story points at sampling time
- minimum, p25, p50, p99, maximum anchors
- uniform draw and sampled dwell business hours
- touch distribution/version, draw, and sampled touch hours
- active multipliers and their bounded result
- business/calendar entry instant

### Progress credit

- credited interval and interval idempotency key
- business/calendar/queue/blocked/unavailable increments
- member labor consumed, responsibility proficiency, and effective touch credit
- remaining dwell/touch values after the credit

### Close

- business/calendar exit instant and total duration components
- exit reason: normal, manual move, rework, cancellation, quarantine, or run end
- link to the sample/open record and all progress-credit records by `status_visit_id`

## Risk decision record

- risk type and policy version
- base probability
- normalized factor values and coefficient values
- unclamped and clamped final probability
- deterministic draw and selected outcome
- resulting duration/capacity/route/dependency effect
- whether forced by an authenticated agent command

## Planning and lifecycle record

- backlog ordering and candidate IDs
- carryover ordering
- sampled capacity target and exclusions
- planned fixed start/end and observed start/end
- manual lifecycle override actor/source if any
- scope additions/removals and forecast changes
- final completed/carryover/cancelled totals

## Jira intervention record

- webhook/changelog/poll identity
- Jira actor account ID/display name when available
- observed and ingested timestamps
- field/lifecycle operation and before/after values
- echo-detection evidence
- policy ownership class: human-writable, protected, or unsupported
- decision: accepted, rejected, quarantined, or corrective projection
- resulting internal version and generated outbox IDs

## Content provenance record

- content type and source event IDs
- prompt-template, output-schema, model, and generator versions
- server job ID, attempt count, token usage when returned, and fallback reason
- content hash and internal document ID
- mechanical quality/complexity inputs supplied to the generator

## API/export behavior

- Authenticated reads support filtering by team, run, sprint, item, visit, event, risk, and Jira key.
- An export operation snapshots its maximum `append_sequence`, then writes a deterministic
  `application/zip` archive containing exactly `manifest.json` then `ground-truth.ndjson` in that
  fixed entry order. Each NDJSON line and the manifest use RFC 8785 canonical JSON encoded as UTF-8 and
  terminated by LF. Records are ordered by `append_sequence`. ZIP entries use `STORE`, fixed
  `1980-01-01T00:00:00` timestamps, fixed Unix file mode `0644`, no extra fields, and no archive/
  entry comments. The manifest contains contract/schema/algorithm versions, normalized filters,
  team/run semantic IDs, row count, first/last sequence, and the NDJSON SHA-256. Persistent export
  metadata stores the manifest SHA-256 and whole-archive SHA-256 outside the archive, avoiding a
  self-referential checksum.
- Pagination/export order is the unique monotonically increasing `append_sequence` assigned when a
  ledger row is inserted; it is never derived from a timestamp or UUID. `transaction_sequence`
  preserves the producer's order among rows emitted by one transaction/correlation. The opaque
  cursor carries the last append sequence, while `occurred_at` and `recorded_at` remain separately
  filterable. Gaps from rolled-back or reserved values are valid. Late Jira observations with an old
  observed time therefore append after, and cannot fall behind, an already-issued cursor.
- Correction is represented by a new record referencing the corrected record; rows are not edited
  to hide prior evidence.
- Export archives are private files under `/data/exports/<team-id>/<export-id>.zip`; no response or
  MCP result exposes this raw path. A scoped client creates an export, polls authenticated metadata,
  and streams it through the authenticated download route or
  `simulator-export://ground-truth/<team-id>/<export-id>` MCP resource. The default archive lifetime
  is 24 hours. Expiry may remove only the derived ZIP;
  operation metadata/checksums remain and the source ground-truth ledger is never deleted.
- MVP retains all source records for the life of the run and performs no automatic source-ledger
  deletion.
