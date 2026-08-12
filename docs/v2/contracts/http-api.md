# V2 HTTP API Surface Contract

All routes are under `/api/v2` and require TLS. The liveness probe is anonymous, the Jira callback
uses its verified provider signature, session establishment uses the bearer credential below, and
all remaining routes require scoped bearer/session authentication. Every response returns a
correlation ID. Control/query responses use JSON; the ground-truth download route is the only initial
binary response. Mutations accept `Idempotency-Key`; versioned updates also require an expected
aggregate version. Long operations return `202 Accepted` plus an operation resource.

## Authentication and dashboard session

### Opaque bearer credentials

An API credential is the literal ASCII prefix `simv2_` followed by the unpadded base64url encoding of
exactly 32 bytes from the operating-system CSPRNG. The encoded suffix is therefore exactly 43
characters, and the complete credential is exactly 49 characters. It carries no claims and is sent
only as:

```text
Authorization: Bearer simv2_<43-base64url-characters>
```

The lexical check is `^simv2_[A-Za-z0-9_-]{43}$`; validation must then decode exactly 32 bytes and
re-encode to the identical suffix so noncanonical base64url values are rejected.

Query parameters, cookies, request bodies, tool arguments, and URLs must never carry this
credential. The database stores only
`SHA-256(credential ASCII bytes)` plus a credential UUID, client ID, actor ID, exact scopes, optional
team allowlist (`null` means all teams in this private deployment), client kind (`API`, `MCP`, or
`DASHBOARD`), issued/expiry/revocation times, and rotation lineage. The 256-bit random value makes an
indexed SHA-256 digest suitable for lookup;
the presented digest is still compared in constant time. A request cannot override the persisted
client, actor, scopes, or team access.

Credential lifecycle is an offline operator surface, never an HTTP or MCP tool. The required CLI is:

```text
python -m app.v2.auth_cli issue  --client-id ID --actor-id ID \
  --client-kind API|MCP|DASHBOARD --scopes SCOPE[,SCOPE...] \
  (--team-id UUID ... | --all-teams) [--expires-in-days 90]
python -m app.v2.auth_cli rotate --credential-id UUID [--overlap-minutes 1440]
python -m app.v2.auth_cli revoke --credential-id UUID
```

Issuance defaults to 90 days and rejects a lifetime above 365 days. It writes
`JIRA_SIMULATOR_API_TOKEN=<credential>` exactly once to the invoking TTY after committing the digest;
it refuses a non-TTY output and never writes the plaintext to application logs, audit rows, evidence,
or the database. Rotation creates a new credential and digest, never elevates scopes/team access,
shows the replacement once with a new 90-day lifetime, and expires the old credential after a default
24-hour overlap; the explicit overlap range is `0–1,440` minutes. Revocation is immediate and
invalidates every dashboard session derived from that credential. A lost plaintext credential cannot
be recovered and must be rotated or revoked.

Missing, malformed, unknown, expired, or revoked credentials return `401` with
`WWW-Authenticate: Bearer`; insufficient scope returns `403`. A resource outside the credential's
team allowlist uses the same `404` shape as an unknown resource. Authentication failures are safely
audited by correlation/client digest prefix only, never by credential value.

### Same-origin dashboard session and CSRF

The React dashboard never embeds a bearer credential in its bundle and never stores one in
`localStorage`, `sessionStorage`, IndexedDB, a cookie, or a URL. An operator uses a separately issued
browser credential long enough to establish a same-origin server session:

```text
POST   /session    bearer credential required; establishes a browser session
GET    /session    session cookie required; returns actor/scopes/team access and CSRF token
DELETE /session    session cookie plus CSRF required; revokes the session
```

`POST /session` has an empty body, requires the bearer header and an exact same-origin `Origin`, and
rejects every credential whose persisted client kind is not `DASHBOARD`, then returns
`204 No Content`. It sets only
`__Host-simv2_session=simv2s_<43-base64url-characters>` with
`Secure; HttpOnly; SameSite=Strict; Path=/; Max-Age=86400` and no `Domain`. The suffix is another
independent 32-byte CSPRNG value; only its SHA-256 digest, credential link, created/last-used time,
and absolute expiry are stored. Sessions expire after eight hours idle, after 24 hours absolute,
or sooner when the source credential expires/revokes.

`GET /session` returns a `simv2c_`-prefixed CSRF token derived as
`base64url(HMAC-SHA256(server CSRF key, raw session cookie))`; the key is supplied only through server
secret configuration as `JIRA_SIMULATOR_CSRF_KEY`, whose value is the unpadded base64url encoding of
exactly 32 CSPRNG bytes. Rotating that key invalidates existing dashboard sessions. Every
session-cookie request using `POST`, `PUT`,
`PATCH`, or `DELETE` must present that value in `X-CSRF-Token` and an exact same-origin `Origin`.
Bearer-authenticated nonbrowser clients do not use cookies or CSRF. Credentialed cross-origin CORS
is disabled. Session routes are authentication transport helpers, are exempt from domain-command
idempotency keys, and do not require MCP tool parity.

The `GET /session` JSON contains only `client_id`, `actor_id`, sorted `scopes`, team access (`ALL` or
sorted IDs), idle/absolute expiry instants, and `csrf_token`. `DELETE /session` returns `204`, marks
the server session revoked, and clears the cookie with the same attributes and `Max-Age=0`. Every
session response uses `Cache-Control: no-store`.

## Health and operations

```text
GET  /health/live
GET  /health/ready                         simulator:read
GET  /operations/{operation_id}            simulator:read
```

Liveness proves only that the process responds. Readiness reports database/migration/scheduler/Jira
discovery state without exposing secrets. Stage 0 exposes liveness and builds the readiness evaluator
internally; `/health/ready` is not externally mounted until scoped authentication exists at G3.

## Team preview, provisioning, and state

```text
POST /team-previews                         simulator:provision
POST /teams                                 simulator:provision + confirmed preview
GET  /teams                                 simulator:read
GET  /teams/{team_id}                       simulator:read
GET  /teams/{team_id}/state                 simulator:read
PATCH /teams/{team_id}/settings             simulator:control
POST /teams/{team_id}/start                 simulator:control
POST /teams/{team_id}/pause                 simulator:control
POST /teams/{team_id}/resume                simulator:control
POST /teams/{team_id}/jira-sync/freeze      simulator:control
POST /teams/{team_id}/jira-sync/unfreeze    simulator:control
```

`POST /teams` accepts only a valid unexpired preview token, explicit confirmation, and idempotency
key. `POST /team-previews` accepts a complete structured `TeamBlueprintDraft` and optional source
hash/safe summary; neither route accepts a raw natural-language prompt or arbitrary Jira payload.

## Work, people, content, and risk controls

```text
POST  /teams/{team_id}/work-items                         simulator:control
PATCH /teams/{team_id}/work-items/{work_item_id}          simulator:control
POST  /teams/{team_id}/members/{member_id}/availability   simulator:control
PUT   /teams/{team_id}/content-policy                     simulator:control
PUT   /teams/{team_id}/risk-policy                        simulator:control
POST  /teams/{team_id}/event-injections                   simulator:control
POST  /teams/{team_id}/jira-conflicts/{conflict_id}/resolve simulator:admin + confirmation
```

Each route accepts a typed bounded schema. There is no generic command, arbitrary patch, SQL, or raw
Jira payload endpoint.

## Activity, transcripts, and ground truth

```text
GET  /activity                              simulator:read
GET  /teams/{team_id}/activity              simulator:read
GET  /teams/{team_id}/transcripts           simulator:read
GET  /teams/{team_id}/transcripts/{id}      simulator:read
GET  /teams/{team_id}/ground-truth          simulator:read
POST /teams/{team_id}/ground-truth/exports  simulator:read
GET  /teams/{team_id}/ground-truth/exports/{export_id}          simulator:read
GET  /teams/{team_id}/ground-truth/exports/{export_id}/download simulator:read
```

List routes use stable opaque cursors. Export creation accepts the same typed filters as the query,
requires `Idempotency-Key`, atomically captures the current maximum `append_sequence` as its snapshot,
and returns `202` with stable `operation_id` and `export_id`. The canonical query hash is lowercase
hex SHA-256 over RFC-8785 JSON containing team ID, normalized filters, snapshot append sequence, and
export format version. Repeating the same retained idempotency key returns the same operation/export;
reusing it with different normalized input conflicts.

The metadata route never returns a filesystem/object-store path or a bearer/download token. Its
stable shape is:

```json
{
  "export_id": "uuid",
  "operation_id": "uuid",
  "team_id": "uuid",
  "status": "QUEUED | RUNNING | READY | FAILED | EXPIRED",
  "query_hash": "64-lowercase-hex",
  "filters": {},
  "snapshot_append_sequence": 123,
  "record_count": 123,
  "media_type": "application/zip",
  "byte_length": 12345,
  "artifact_sha256": "64-lowercase-hex",
  "manifest_sha256": "64-lowercase-hex",
  "created_at": "RFC-3339 UTC",
  "ready_at": "RFC-3339 UTC or null",
  "expires_at": "RFC-3339 UTC or null",
  "metadata_href": "/api/v2/teams/.../ground-truth/exports/...",
  "download_href": "/api/v2/teams/.../ground-truth/exports/.../download",
  "resource_uri": "simulator-export://ground-truth/<team_id>/<export_id>",
  "error": null
}
```

Count, lengths, hashes, ready/expiry fields, links, and resource URI are `null` until applicable.
`expires_at` is exactly 24 hours after `ready_at`. Expiry disables retrieval but never deletes or
changes source ground-truth rows; the metadata/audit remains readable. A caller creates a new export
with a new idempotency key when an artifact has expired.

### Deterministic export package

The artifact is a ZIP with exactly two regular files in this order:

1. `manifest.json` — RFC-8785 canonical JSON followed by one LF;
2. `ground-truth.ndjson` — records ordered by `append_sequence`, each encoded as RFC-8785 canonical
   JSON followed by one LF; an empty export is a zero-byte file.

The manifest contains export format version, team ID, normalized filters, query hash, snapshot
append sequence, record count, nullable first/last append sequence, sorted schema/algorithm versions,
and the NDJSON filename/byte length/lowercase SHA-256. It deliberately omits operation/export IDs and
creation timestamps so the same logical snapshot produces identical file bytes. Metadata carries
the SHA-256 of the manifest bytes and complete ZIP bytes.

ZIP entries use `STORE` (no compression), fixed timestamp `1980-01-01 00:00:00`, Unix create-system
value `3`, create/extract version `20`, regular-file external attributes `0100644 << 16`, zero
internal attributes, general-purpose flag `0x0800`, UTF-8 names, known sizes in local headers with no
data descriptors/ZIP64, no extra fields, and no archive/file comments. These rules plus the fixed
entry order make the complete artifact byte-deterministic and must have a checked-in golden-byte
fixture. The download response is
`application/zip`, uses attachment filename `ground-truth-<team_id>-<export_id>.zip` after strict ID
validation, `ETag` equal to the quoted artifact SHA-256, and `Cache-Control: private, no-store`.

The download route always revalidates bearer/session scope and team access; the relative href is not
authorization. Before `READY` it returns `409 EXPORT_NOT_READY` with the operation ID, after expiry it
returns `410 EXPORT_EXPIRED`, and another team's or an unknown export returns the same `404` shape.
No response exposes the server storage key/path. The `simulator-export://` URI is an MCP resource
identifier defined in `mcp-tools.md`, not an HTTP URL or secret.

## Jira integration

```text
POST /jira/webhooks                         verified Jira webhook identity/signature
GET  /teams/{team_id}/jira-sync             simulator:read
GET  /teams/{team_id}/jira-conflicts        simulator:read
```

The webhook route stores and acknowledges a valid observation quickly; it does not apply simulation
mechanics inline. Poll reconciliation uses the same normalized inbox contract.

## Error contract

```json
{
  "error": {
    "code": "STABLE_MACHINE_CODE",
    "message": "safe human-readable summary",
    "field_errors": [{"path": "workflow.routes[0]", "code": "UNKNOWN_STATUS"}],
    "retryable": false,
    "operation_id": null,
    "correlation_id": "uuid"
  }
}
```

Never return secrets, authorization headers, raw provider exceptions, SQL, or unredacted OpenAI
prompts containing credentials.
