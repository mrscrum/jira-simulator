# V2 Jira Projection and Intervention Contract

## Outbox command envelope

Every command stores:

- stable `command_id` and `idempotency_key`;
- `team_id`, aggregate type/ID/version, correlation and causation IDs;
- typed operation and versioned validated payload containing local IDs;
- prerequisite command IDs;
- attempt/status/next-attempt fields and bounded retry policy;
- a random attempt lease token, lease expiry, and team delivery epoch used for compare-and-swap
  completion;
- expected Jira postcondition and read-back strategy;
- response fingerprint and created Jira resource IDs; and
- terminal failure/conflict detail safe for the dashboard.

The domain transaction inserts commands. A separate writer resolves local IDs from
`JiraResourceMap`, performs network calls, and records results. No engine module calls Jira.

### Command state machine

- `PENDING` is a newly committed command. Dependency resolution moves it to `READY` when it has no
  outstanding prerequisite or to `BLOCKED` while one remains; all succeeded moves `BLOCKED` to
  `READY`.
- `READY → IN_FLIGHT` atomically writes a fresh 128-bit random lease token, expiry, and current team
  delivery epoch. A delivery result may change command state only when status remains `IN_FLIGHT`
  and both token and epoch match. Lease expiry or process loss becomes `UNKNOWN_OUTCOME`, never a
  blind retry. A late response appends a delivery observation but cannot overwrite reconciler state;
  it triggers postcondition reconciliation.
- Successful postcondition/read-back becomes `SUCCEEDED`. A timeout/ambiguous response enters
  `UNKNOWN_OUTCOME`; discovery/read-back then chooses `SUCCEEDED`, `READY`, or a conflict.
- Jira 429 enters `RETRY_WAIT` until `Retry-After` and does not consume the transient-exhaustion
  counter. Transport/5xx failures use bounded backoff and consume one of eight default transient
  failures; exhaustion becomes `FAILED_TERMINAL`. Contract-invalid 400/422 is terminal immediately.
  Authentication/authorization, missing protected resources, and irreconcilable 409 responses also
  become terminal with the smallest-scope projection conflict.
- A succeeded prerequisite makes a blocked child eligible. A superseded prerequisite deterministically
  supersedes or rebases each child. A terminal prerequisite propagates `BLOCKED_TERMINAL` to every
  descendant; no descendant remains permanently runnable-blocked.
- Confirmed conflict resolution offers only server-generated `RETRY`, `SUPERSEDE`, or `REBASE`
  choices. Retry creates a new auditable attempt/command linked to the terminal row after the cause
  is corrected; it never edits history or accepts a caller-supplied Jira payload.

High-water depth counts `PENDING`, `BLOCKED`, `READY`, `IN_FLIGHT`, `RETRY_WAIT`, and
`UNKNOWN_OUTCOME`. It excludes `SUCCEEDED`, `SUPERSEDED`, `FAILED_TERMINAL`, and
`BLOCKED_TERMINAL` while their visible conflict/history remains retained.

## Required command types and ordering

| Command | Required predecessor/postcondition |
|---|---|
| `ENSURE_PROJECT` | Company-managed project exists with expected key/type. |
| `ENSURE_ISSUE_TYPES` | Project exists; dedicated standard Story/Bug/Task/Spike/Enabler types exist in a dedicated issue-type scheme associated only with the managed project. |
| `ENSURE_WORKFLOW_CONFIGURATION` | Project and issue types exist; canonical status categories, workflow/transitions, and workflow scheme exist and the scheme is associated with the managed project. |
| `ENSURE_BOARD` | Workflow association succeeded; matching Scrum/Kanban board/filter exists and complete configuration read-back has the expected project location and 1:1 category-column mapping. |
| `ENSURE_VIRTUAL_FIELDS` | Global `sim_assignee` and `sim_reporter` fields exist on required screens/contexts. |
| `CREATE_ISSUE` | Project, issue types, workflow, and fields exist; initial payload atomically sets protected issue property `jira-simulator.item-id`; returns/stores Jira issue ID/key. |
| `UPDATE_VIRTUAL_FIELDS` | Issue mapping exists; payload contains no real assignee/reporter. |
| `SET_ESTIMATE` | Issue mapping exists; only supported Fibonacci story points are written/read back. |
| `UPDATE_CONTENT_FIELDS` | Issue mapping exists; only summary, description, and acceptance criteria are allowed. |
| `RANK_ISSUE` | Issue/board mapping exists; postcondition is relative order among managed items, never a raw LexoRank value. |
| `TRANSITION_ISSUE` | Issue/status mapping exists; read-back reaches expected status. |
| `CREATE_SPRINT` | Scrum board exists; use the deterministic discovery identity below; returns/stores Jira sprint ID. |
| `ADD_ISSUES_TO_SPRINT` | Sprint and issue mappings exist. |
| `START_SPRINT` | Sprint membership projection succeeded; for a successor, the predecessor `COMPLETE_SPRINT` also succeeded. |
| `COMPLETE_SPRINT` | Carryover/successor membership commands completed first. |
| `MOVE_ISSUES_TO_BACKLOG` | Issue mappings exist; read-back confirms no active sprint membership. |

V2 does not emit `ADD_COMMENT`. It never uses `UPDATE_ISSUE` to change actual Jira assignee or
reporter. A contract test must fail if those keys occur in any v2 update payload.

The topology predecessor chain is `ENSURE_PROJECT → ENSURE_ISSUE_TYPES →
ENSURE_WORKFLOW_CONFIGURATION → ENSURE_BOARD`. `ENSURE_VIRTUAL_FIELDS` follows the project and must
succeed before issue creation. `OFFICIAL_PROJECT_SCOPED_V1` uses documented public Jira Cloud APIs
only. Its board configuration read-back must map To Do to the To Do column; Analysis, Development,
Code Review, QA, PO Review, and Blocked External to In Progress; and Done and Cancelled to Done,
with every status present exactly once. Public API inability to produce that mapping is a terminal
capability conflict, not permission to call a private endpoint or automate Jira's UI.

All issue-field commands use explicit allowlists and reject actual assignee/reporter, arbitrary
field maps, and unknown custom fields. Unknown-outcome creation scans the fully paginated managed
project candidate window and reconciles by `jira-simulator.item-id` before a retry. Transition
commands form a causal predecessor chain; when a parent is superseded by an
accepted human observation, descendants are explicitly superseded or deterministically rebased,
never left blocked forever or collapsed into one transition.

Initial sprint ordering is the explicit predecessor chain `CREATE_SPRINT → ADD_ISSUES_TO_SPRINT →
START_SPRINT`. Before a boundary transaction emits Jira commands, deterministic replenishment and
planning commit the successor's complete scope: unchanged carryover plus newly selected backlog.
The command graph is `CREATE_SUCCESSOR → ADD_CARRYOVER_TO_SUCCESSOR`, `CREATE_SUCCESSOR →
ADD_NEW_SCOPE_TO_SUCCESSOR`, `ADD_CARRYOVER_TO_SUCCESSOR → COMPLETE_OLD`, and
`COMPLETE_OLD + ADD_NEW_SCOPE_TO_SUCCESSOR → START_SUCCESSOR`; no writer inference may omit an edge.
Autonomous, manual-boundary, and restart-created successors all use the same full-scope rule.

`CREATE_SPRINT` uses name `SIM-<PROJECT_KEY>-<first-12-lowercase-hex-digits-of-sprint-semantic-UUID>`
and sends planned start/end as UTC instants normalized to milliseconds. After an ambiguous outcome,
enter `UNKNOWN_OUTCOME` and begin a settlement window of at least two minutes with at least three
complete, paced, fully paginated scans of every sprint state for that board. Match the exact tuple
`(board_id, name, normalized_start, normalized_end)`: one match is claimed and then stamped with
protected property `jira-simulator.sprint-id`; multiple matches create a protected conflict. Zero
matches after the full window becomes `FAILED_TERMINAL` with visible conflict code
`SPRINT_CREATE_UNCERTAIN`; it never
automatically retries. Server-provided resolution choices may adopt a later discovered candidate or
offer an explicitly confirmed retry that states the duplicate risk. The property improves later
reconciliation but is not relied on for the first unknown outcome because setting it is a separate
Jira call and the tuple is not a Jira uniqueness constraint.

## Delivery behavior

- Delivery is at-least-once with effective idempotency from discovery-before-create, stable resource
  mapping, expected postconditions, and reconciliation.
- The writer claims/leases a command in one short transaction, closes the database session before
  the Jira network call, then records result/read-back in a separate short transaction.
- HTTP 429 obeys `Retry-After`; transient failures use bounded exponential backoff with jitter.
- An unknown outcome after timeout is reconciled under its command-specific settlement policy;
  no create is retried merely because one read found no match.
- Before an update/transition derived from an older aggregate version is delivered, compare the
  latest known Jira changelog/resource version. A newer conflicting human observation is ingested
  first and the stale command becomes `SUPERSEDED`; it is never delivered merely because it was
  queued earlier.
- A prerequisite failure blocks descendants without discarding them.
- Pausing a team prevents new commands; already committed commands may drain.
- Sync freeze atomically increments the team's delivery epoch and enters `FREEZING`, which prevents
  every new claim. An already dispatched call is not cancelled: its matching lease may append and
  reconcile its result, but it cannot trigger another claim. When no command remains actively
  leased, state becomes `FROZEN`; callers poll the returned operation when this is not immediate.
  Unfreeze is allowed only from `FROZEN` and preserves queue order.
- Recovery is paced and alternates delivery with read-back to avoid propagating stale assumptions.

## Manual Jira intervention inbox

Signed admin webhooks are registered through Jira's webhook administration API with a rotated secret
stored outside the repository. The public callback requires trusted HTTPS, verifies the raw UTF-8
body against `X-Hub-Signature`, stores a raw hash, and acknowledges quickly. Sprint events are
filtered locally to managed board/sprint IDs because Jira does not apply JQL filtering to them.
Registration/rotation/read-back are observable capability-checked operations; periodic polling is
mandatory even when registration succeeds.

Provider references: Atlassian's official [Jira Software webhook guide](https://developer.atlassian.com/cloud/jira/software/webhooks/)
defines signed admin webhooks, `X-Hub-Signature`, and unfiltered sprint events; its official
[secure-URL notice](https://developer.atlassian.com/cloud/jira/platform/deprecation-notice-registering-webhooks-with-non-secure-urls/)
requires a globally trusted HTTPS callback for new registrations. The official
[create-issue contract](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issues/)
supports setting issue properties in the initial create request. Atlassian's official
[sprint API](https://developer.atlassian.com/cloud/jira/software/rest/api-group-sprint/) shows that
create accepts board/name/start/end while sprint properties are separate calls, which is why the
unknown-outcome predicate cannot depend on the property already existing.

Topology provisioning uses Atlassian's official [project API](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-projects/),
[issue-type API](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-types/),
[issue-type-scheme API](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-type-schemes/),
[workflow API](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-workflows/),
[workflow-scheme API](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-workflow-schemes/),
and [board API](https://developer.atlassian.com/cloud/jira/software/rest/api-group-board/). The board
API's supported configuration operation is read-back; the target-tenant Gate G0 proof therefore
must demonstrate category-derived column mapping after workflow association.

Webhooks and periodic poll observations normalize into one envelope containing Jira tenant/resource,
delivery and changelog/change-item IDs, actor, observed/ingested time, fields changed, before/after
values, source, and raw hash. Delivery deduplication uses tenant plus webhook delivery identity;
semantic deduplication uses changelog/change-item identity or a poll-derived resource snapshot delta.
Repeated delivery is a no-op.

Processing order for one aggregate is Jira observed time, Jira changelog sequence when available,
then stable inbox ID. Simulator echo detection requires the service actor, matching changed fields,
delivered outbox command ID/trace when present, expected postcondition, and resource version. A
bounded correlation window may support the decision but cannot suppress an observation by itself.

### Field/lifecycle policy

| Change | Policy |
|---|---|
| Manual sprint start/complete/restart | Adopt once when reconcilable; otherwise pause lifecycle with a visible conflict. |
| Card add/remove from sprint | Adopt scope change; recalculate forecast; stop/release work when removed. |
| Story points | Adopt supported Fibonacci value; scale remaining current touch work, resample future visits. If the old value is absent/zero, preserve current work and record `NO_RATIO_BASELINE`. |
| Mapped ordinary/terminal status | Adopt. Outside a block, close the current visit and enter the observed route status. From `Blocked External`, first resolve the block; moving to the suspended status resumes the same visit/sample/progress, while moving elsewhere closes the suspended visit as a manual transition and samples only the new target visit. |
| `Blocked External` | Enter an open-ended manual dependency episode, suspend the ordinary visit and all ordinary dwell/aging/touch clocks, and release capacity; do not create/resample a normal visit. Moving back to the suspended status resolves and resumes it. A different mapped target resolves the block then follows the manual-transition rule. The workflow exposes Blocked External to every ordinary mapped target plus Done and Cancelled; either terminal transition closes both the episode and suspended visit exactly once. |
| Unmapped status/unsupported points | Quarantine affected item; show conflict; do not crash or overwrite. |
| Priority/rank/summary/description/acceptance criteria | Adopt and record before/after. Rank is relative managed-item order; Jira LexoRank rebalance alone is not a semantic intervention. Content edits do not resample quality/complexity. |
| Card deleted/archived | Retain tombstone/history, stop work/release capacity, never silently recreate. |
| Project/board/workflow/status scheme/virtual field topology | Protected team sync conflict; never auto-recreate/remap. |
| `sim_assignee`, `sim_reporter`, `jira-simulator.*` properties, internal/provenance fields | Protected conflict; require explicit reconciliation. |
| Actual Jira assignee/reporter | Preserve a human Jira value; no simulator-originated update changes it after creation. |

Manual sprint completion/start uses the original local cadence anchor. The successor starts at the
accepted observed instant and ends at the first original boundary strictly after it; later sprints
return to that anchor. A candidate successor must belong to the managed board, be the sole active
non-completed sprint, have reconcilable membership/status mappings, and have no protected topology
conflict. A completed predecessor may reopen only before its successor has any committed positive
labor, positive ordinary-dwell credit, or autonomous status transition; otherwise lifecycle is
isolated as a conflict. All adopted/overridden planned and observed instants remain in history.

An unknown Jira issue entering a managed sprint is imported with `origin=JIRA_MANUAL`. Required
missing simulation metadata uses the team's versioned explicit defaults and is recorded in ground
truth; inability to map type/status/points quarantines only that issue. If its observed status is
`Blocked External`, a mapped prior status from Jira changelog becomes the suspended visit before the
open-ended block is applied. Without such a prior status, quarantine the item and offer only
server-generated choices for the underlying ordinary status; never invent or sample a blocker visit.

## Reconciliation states

- `MATCHED` — Jira satisfies expected projection.
- `PENDING_DELIVERY` — queued intent explains the difference.
- `HUMAN_INTERVENTION` — supported Jira change should be ingested.
- `PROTECTED_CONFLICT` — protected simulator field changed.
- `UNSUPPORTED_CONFLICT` — change cannot be represented safely.
- `DELIVERY_DIVERGENCE` — Jira did not reach a command's expected postcondition.

Every non-matched state produces an activity and ground-truth record. Only the smallest affected
team lifecycle or item is paused/quarantined.

Every accepted/rejected observation records delivery/changelog identity, actor, observed and
ingested timestamps, before/after, ownership/policy decision, resulting aggregate version, generated
or superseded outbox IDs, and correction lineage. Confirmed conflict resolution follows
detect → enumerate server choices → confirm → restore/adopt → Jira read-back → idempotent repeat.
