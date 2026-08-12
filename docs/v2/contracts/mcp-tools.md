# V2 Private Codex MCP Tool Contract

The initial plugin contains a Codex skill and a thin MCP server. The MCP server delegates to the
authenticated simulator API and contains no simulation mechanics or server OpenAI key.

## Authentication and scopes

Private MCP clients use the exact opaque bearer contract in `http-api.md`: `simv2_` followed by the
unpadded base64url encoding of 32 CSPRNG bytes, sent only in the `Authorization: Bearer` header over
trusted HTTPS. The simulator stores only its SHA-256 digest and persisted client/actor/scope/team
metadata. Every call resolves those values from the credential; a tool argument cannot assert or
override an actor, client, scope, or team grant. The MCP server accepts only a credential whose
persisted client kind is `MCP`; dashboard/API-kind credentials fail closed.

The MCP process receives exactly these two required runtime configuration variables; only the token
is secret:

```text
JIRA_SIMULATOR_BASE_URL=https://simulator.example.test
JIRA_SIMULATOR_API_TOKEN=simv2_<43-base64url-characters>
```

The plugin manifest and checked-in MCP configuration contain only those environment-variable names,
never their values. The server refuses startup/readiness when the base URL is not a canonical HTTPS
origin with no userinfo/query/fragment, when the token is missing, or when the token fails the exact
format/decode/re-encode check. It sends the token only to that configured origin, refuses every HTTP
redirect, and never places it in tool input/output, resource URIs, errors, logs, traces, evidence, or
child-process arguments. It does not use the browser session/cookie flow.

An operator issues, rotates, and revokes the credential with the offline CLI defined in
`http-api.md`. On rotation, the new one-time plaintext is placed in the MCP secret environment and
the MCP process is reloaded/restarted and health-checked before the configured overlap ends; the old
value is then allowed to expire or is explicitly revoked. Revocation or expiry makes subsequent MCP
calls fail closed with the simulator's structured authentication error. Plaintext credentials are
never recoverable through MCP.

Scopes:

- `simulator:read` — teams, state, activity, transcripts, ground truth, operation status.
- `simulator:control` — start, pause, resume, sync freeze, bounded event injection.
- `simulator:provision` — preview and confirm a new team/project.
- `simulator:admin` — confirmed Jira-conflict reconciliation; reset/delete remain future actions.

No initial tool accepts arbitrary URLs, Jira credentials, SQL, file paths, or raw outbox payloads.

## Tool catalogue

### `preview_team`

- Scope: `simulator:provision`
- Input: complete structured `TeamBlueprintDraft`, optional stable request ID and source-prompt hash/
  safe summary. Raw natural-language prompts are rejected by the simulator API.
- Output: validated `TeamBlueprint`, warnings, Jira names/keys, and preview token.
- Side effects: non-provisioning; stores a 24-hour audit/preview record only and creates no team, Jira
  resource, simulation state, content job, or server OpenAI call.
- Confirmation: none.

### `create_team`

- Scope: `simulator:provision`
- Input: preview token, explicit confirmation, idempotency key.
- Output: accepted `ProvisioningOperation` ID and initial state.
- Side effects: asynchronous local/Jira provisioning.
- Confirmation: required; the tool must reject a false or absent confirmation.

### `get_operation`

- Scope: `simulator:read`
- Input: operation ID.
- Output: step/status, retryability, team ID, Jira resources, warnings, and safe error detail. A
  completed ground-truth export additionally returns the bounded export metadata defined below and
  its `simulator-export://` resource URI, never a download token/path.

### `list_teams`

- Scope: `simulator:read`
- Input: optional methodology/runtime/status filters and cursor.
- Output: paginated team summaries.

### `get_team_state`

- Scope: `simulator:read`
- Input: team ID.
- Output: runtime, current Scrum/Kanban policy state, members/availability, current work, risks,
  Jira sync/intervention conflicts, and next wake.

### `get_activity`

- Scope: `simulator:read`
- Input: optional team/run/item/type/time filters and cursor.
- Output: paginated activity envelopes in stable order.

### `get_transcript`

- Scope: `simulator:read`
- Input: team ID and business date or transcript ID.
- Output: internal transcript, source-event references, and provenance. Never publishes to Jira.

### `get_ground_truth`

- Scope: `simulator:read`
- Input: team plus one or more run/sprint/item/visit/event/Jira-key filters and explicit mode `PAGE`
  or `EXPORT`. `PAGE` accepts bounded page size/cursor. `EXPORT` accepts an idempotency key and no
  cursor.
- Output: `PAGE` returns paginated structured calibration records. `EXPORT` returns stable operation
  and export IDs; after completion, `get_operation` returns deterministic metadata and the MCP
  resource URI described below.

### `start_team`

- Scope: `simulator:control`
- Input: team ID and idempotency key.
- Output: committed running state and next wake.
- Confirmation: the user's clear request is sufficient after the team already exists.

### `pause_team` / `resume_team`

- Scope: `simulator:control`
- Input: team ID, reason, idempotency key.
- Output: committed state/version. Pause returns only after no new tick can commit for the old
  version.

### `freeze_jira_sync` / `unfreeze_jira_sync`

- Scope: `simulator:control`
- Input: team ID, reason, idempotency key.
- Output: committed sync state. This does not pause internal simulation.
- A freeze with an already dispatched Jira request returns `FREEZING` plus an operation ID; no new
  delivery is claimed, and the operation reaches `FROZEN` after the in-flight lease settles.

### `inject_event`

- Scope: `simulator:control`
- Input: team ID, supported event type, constrained target selector, optional effective time/duration,
  reason, and idempotency key.
- Supported MVP causal commands: bounded status-dwell extension, external dependency, cancellation,
  review rejection, and member unavailable. Long stay and carryover remain derived monitors/outcomes;
  commands cannot write either outcome flag directly.
- Bounds/effect rules:
  - dwell extension targets one open ordinary visit/version and adds `0.25–80` remaining business
    dwell hours;
  - dependency targets one active nonterminal item and uses `0.25–240` simulation business hours or
    explicit `OPEN_ENDED`;
  - cancellation targets one active nonterminal item and accepts no duration;
  - review rejection targets the current Code Review/QA/PO Review visit/version, accepts no duration,
    and arms its next attempted normal exit; and
  - member unavailable targets one member for `1–20` whole simulation working days at zero
    availability. Fractional/absolute intervals use `set_member_availability` instead.
- `effective_at` defaults to command acceptance time, cannot be earlier than acceptance, and cannot
  be more than 30 calendar days later. A due durable command persists through restart/pause and
  applies once in the first eligible running transaction after reconciliation/resume, recording
  lateness without backdated work. If its expected
  target/version is no longer eligible, it terminates with a structured stale-target result and no
  partial mechanics or natural RNG consumption.
- Output: persisted command ID and validation result; mechanics occur in the domain transaction.
- Confirmation: the user's clear request is sufficient; bulk/all-team targets are rejected in MVP.

### `update_team_settings`

- Scope: `simulator:control`
- Input: team ID, expected settings version, a typed patch limited to calendar, capacity, backlog,
  and future Scrum cadence fields, reason, and idempotency key.
- Output: validated command/operation ID and new version.
- Active sprint boundaries are immutable through this tool. Calendar/cadence changes take effect at
  the next not-yet-created sprint; Jira topology changes and patches that invalidate current work are
  rejected in MVP. Ordinary future-policy changes use the clear user request.

### `add_work_item` / `update_work_item`

- Scope: `simulator:control`
- Input: team ID, typed work-item fields, expected version for updates, reason, idempotency key.
- Output: committed item/command ID and resulting version.
- Allowed updates: priority/rank, Fibonacci story points, summary, description, acceptance criteria,
  and supported sprint/backlog placement. Status changes use `inject_event` or Jira intervention so
  mechanics cannot be bypassed.

### `set_member_availability`

- Scope: `simulator:control`
- Input: team/member ID, bounded start/end, `availability_fraction`, optional
  `daily_capacity_hours_override`, reason, and idempotency key. This is a restrictive runtime
  overlay: it may overlap another source and composes by the minimum active fraction/cap, but cannot
  increase the confirmed configured availability.
- Output: persisted availability command and resulting team state version.

### `update_content_policy`

- Scope: `simulator:control`
- Input: team ID, expected policy version, typed generation enablement/field selection, approved
  server-side model-profile reference, bounded jobs-per-cycle/timeout/retry/output-token limits,
  reason, and idempotency key.
- Output: new immutable policy version. API keys and resolved secret configuration are never
  returned.
- Enabling content for an active team queues only the safe backfill candidates allowed by
  `R-CONTENT-001`; the user's clear request is sufficient and mechanics never wait for backfill.

### `update_risk_policy`

- Scope: `simulator:control`
- Input: team ID, expected policy version, typed bounded coefficients/bases/caps, reason, idempotency.
- Output: new immutable policy version. Existing decisions retain their original version.
- Confirmation: required when applied to an already active team.

### `reconcile_jira_conflict`

- Scope: `simulator:admin`
- Input: conflict ID, one of the server-provided resolution options, explicit confirmation, and
  idempotency key.
- Output: accepted command ID and audit record.
- Confirmation: required.

## Ground-truth export metadata and resource retrieval

For a ready export, `get_operation` returns this bounded metadata object from the authenticated HTTP
metadata route:

```json
{
  "export_id": "uuid",
  "team_id": "uuid",
  "status": "READY",
  "query_hash": "64-lowercase-hex",
  "snapshot_append_sequence": 123,
  "record_count": 123,
  "media_type": "application/zip",
  "byte_length": 12345,
  "artifact_sha256": "64-lowercase-hex",
  "manifest_sha256": "64-lowercase-hex",
  "ready_at": "RFC-3339 UTC",
  "expires_at": "RFC-3339 UTC",
  "resource_uri": "simulator-export://ground-truth/<team_id>/<export_id>"
}
```

It omits HTTP download hrefs, storage paths/keys, cookies, bearer credentials, and signed query
tokens. The resource URI contains only the team/export UUIDs and is an identifier, not authority.
The MCP server accepts only the exact URI grammar
`simulator-export://ground-truth/{team_uuid}/{export_uuid}`; it never dereferences an arbitrary URI or
caller-supplied HTTP location.

At G5 the MCP server exposes a resource template for that URI and supports `resources/read`. A read:

1. parses and validates both UUIDs without network discovery;
2. calls the configured simulator origin's authenticated export metadata route;
3. verifies `READY`, team authorization, media type, byte length, expiry, and checksum formats;
4. fetches the authenticated download route without following a cross-origin redirect;
5. verifies the downloaded byte length and artifact SHA-256, then parses the two-entry ZIP and
   verifies the manifest SHA-256 plus its NDJSON length/checksum/count; and
6. returns one MCP blob resource with the same URI, `mimeType: application/zip`, base64-encoded ZIP
   bytes in `blob`, and the bounded metadata above under `_meta.simulator_export`.

The ZIP bytes and manifest follow the deterministic package contract in `http-api.md`. An expired
artifact returns structured `EXPORT_EXPIRED`; not-ready returns `EXPORT_NOT_READY` plus the operation
ID; unknown, unauthorized, or cross-team identifiers use the same not-found shape. The MCP server
does not cache artifacts beyond one call or persist them to a caller-visible path. Resource retrieval
is the transport counterpart of `get_ground_truth`, not a generic URL/file tool, and it is not
registered before G5.

## Mutation guarantees

- Every mutation has an idempotency key with a minimum 24-hour retention window and stable result.
- Provisioning preview/creation keys are retained for the operation/team lifetime. Reusing any
  retained key with a different validated input hash returns `IDEMPOTENCY_KEY_REUSED`.
- The API persists actor, client, scopes, validated input hash, confirmation, result, and correlation
  IDs.
- A tool timeout does not imply failure; callers use `get_operation` or repeat the same key.
- Validation errors are structured and do not partially mutate state.
- Destructive reset/delete tools are not part of the initial contract.
- Every supported v2 operator endpoint must map to one of these typed tools or an explicitly
  documented composition; no generic `call_api`, raw Jira payload, SQL, or arbitrary patch tool is
  permitted.
- Offline credential administration, same-origin dashboard sessions/CSRF, and authenticated export
  byte transport are security/transport helpers rather than operator actions. They do not add raw
  mutation capability and therefore do not require separate MCP tools; export retrieval is available
  only through the constrained `simulator-export://` resource above.

## Delivery stages

- Gate G3 exposes `get_operation`, `list_teams`, `get_team_state`, `get_activity`, preview/create,
  start/pause/resume, sync controls, settings, work-item, and availability tools.
- Gate G4 adds content/risk policy control, risk injection, Jira-conflict reconciliation, and
  transcript reads after their backing services exist.
- Gate G5 adds full ground-truth query/export tools after the authenticated export service exists.
- Gate G6 activates Kanban-specific creation, state, SLA/SLE, and emerging-item behavior.

The catalogue describes the eventual typed surface; a tool must not be registered before its named
delivery gate and backing API are complete.
