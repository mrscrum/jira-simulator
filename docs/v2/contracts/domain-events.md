# V2 Domain and Activity Event Contract

## Envelope

Every committed event uses this versioned envelope:

```json
{
  "event_id": "uuid",
  "append_sequence": 12345,
  "transaction_sequence": 2,
  "semantic_deduplication_key": "stable nullable key",
  "schema_version": 1,
  "event_type": "WORK_ITEM_STATUS_ENTERED",
  "occurred_at": "UTC instant represented by the simulation",
  "recorded_at": "UTC database commit instant",
  "team_id": "nullable local stable id",
  "run_id": "nullable local stable id",
  "aggregate_type": "WORK_ITEM",
  "aggregate_id": "local stable id",
  "aggregate_version": 12,
  "actor_type": "SIMULATOR | CODEX_USER | JIRA_USER | SYSTEM",
  "actor_id": "nullable stable actor/Jira account id",
  "correlation_id": "command/tick/provisioning id",
  "causation_id": "nullable event/command id",
  "source": "LIVE_TICK | AGENT_COMMAND | PROVISIONING_WORKER | OUTBOX_WORKER | JIRA_WEBHOOK | JIRA_POLL | JIRA_RECONCILIATION | CONTENT_WORKER | RESTART_RECONCILIATION | SYSTEM",
  "payload": {},
  "ground_truth_ref": "nullable ground-truth event id"
}
```

`event_id` is unique. `append_sequence` provides insertion-order pagination; one transaction may
emit multiple same-type events for one aggregate version and orders them by `transaction_sequence`.
Commands or provider observations that need replay protection supply a unique
`semantic_deduplication_key`; the aggregate/version/type tuple is not itself unique. Payloads are
validated by `event_type` and version. An incompatible payload is rejected before the state
transaction commits.

`team_id` is null only before a team reservation exists, such as `TEAM_BLUEPRINT_PREVIEWED`; its
preview/reservation ID is the aggregate ID. `run_id` is null for preview/provisioning/team-control
events before a run exists. All team/runtime work events require both IDs.

## Required Event Catalogue

### Provisioning and control

- `TEAM_BLUEPRINT_PREVIEWED`
- `TEAM_PROVISIONING_CONFIRMED`
- `TEAM_PROVISIONING_STEP_COMPLETED`
- `TEAM_READY`
- `TEAM_PROVISIONING_FAILED`
- `TEAM_STARTED`
- `TEAM_PAUSED`
- `TEAM_RESUMED`
- `TEAM_SYNC_FROZEN`
- `TEAM_SYNC_UNFROZEN`
- `TEAM_RECONCILIATION_PENDING`
- `TEAM_RECONCILIATION_CLEARED`

### Work and flow

- `WORK_ITEM_CREATED`
- `WORK_ITEM_IMPORTED_FROM_JIRA`
- `WORK_ITEM_STATUS_ENTERED`
- `WORK_ITEM_STATUS_EXITED`
- `WORK_ITEM_ASSIGNED_INTERNAL`
- `WORK_ITEM_RELEASED_INTERNAL`
- `WORK_CREDITED`
- `WORK_ITEM_COMPLETED`
- `WORK_ITEM_CANCELLED`
- `WORK_ITEM_DELETED_EXTERNALLY`
- `WORK_ITEM_QUARANTINED`
- `WORK_ITEM_RECONCILED`
- `PROJECTION_BACKPRESSURE_STARTED`
- `PROJECTION_BACKPRESSURE_CLEARED`

### Scrum

- `SPRINT_PLANNED`
- `SPRINT_STARTED`
- `SPRINT_SCOPE_ADDED`
- `SPRINT_SCOPE_REMOVED`
- `SPRINT_COMPLETED`
- `WORK_ITEM_CARRIED_OVER`
- `SPRINT_BOUNDARY_RECONCILED`
- `SPRINT_MANUAL_BOUNDARY_OVERRIDE`

### Kanban

- `KANBAN_ITEM_ARRIVED`
- `KANBAN_ITEM_PULLED`
- `KANBAN_WIP_LIMIT_REACHED`
- `SERVICE_CLOCK_STARTED`
- `SERVICE_CLOCK_PAUSED`
- `SERVICE_CLOCK_RESUMED`
- `SERVICE_LEVEL_WARNING`
- `SERVICE_LEVEL_BREACHED`
- `SERVICE_CLOCK_STOPPED`

### Risk and availability

- `RISK_EVALUATED`
- `STATUS_STAY_WARNING`
- `LONG_STAY_DETECTED`
- `EXTERNAL_DEPENDENCY_STARTED`
- `EXTERNAL_DEPENDENCY_RESOLVED`
- `REVIEW_REJECTED`
- `REWORK_ADDED`
- `MEMBER_BECAME_UNAVAILABLE`
- `MEMBER_BECAME_AVAILABLE`
- `STORY_POINTS_CHANGED`

### Jira projection and intervention

- `JIRA_OUTBOX_COMMAND_CREATED`
- `JIRA_OUTBOX_COMMAND_DELIVERED`
- `JIRA_OUTBOX_COMMAND_RETRY_SCHEDULED`
- `JIRA_OUTBOX_COMMAND_FAILED`
- `JIRA_OUTBOX_COMMAND_SUPERSEDED`
- `JIRA_RECONCILIATION_MATCHED`
- `JIRA_RECONCILIATION_DIVERGED`
- `JIRA_INTERVENTION_OBSERVED`
- `JIRA_INTERVENTION_ACCEPTED`
- `JIRA_INTERVENTION_REJECTED`
- `JIRA_INTERVENTION_ECHO_SUPPRESSED`
- `JIRA_FIELD_CONFLICT_DETECTED`
- `JIRA_TOPOLOGY_CONFLICT_DETECTED`

### Content

- `CONTENT_JOB_CREATED`
- `CONTENT_GENERATED`
- `CONTENT_FALLBACK_USED`
- `DAILY_TRANSCRIPT_CREATED`

## State-change payload minimum

Every state-changing event payload includes:

- `before`: only the relevant versioned fields before mutation;
- `after`: only the relevant versioned fields after mutation;
- `reason_code`: stable machine-readable reason;
- `policy_version`: applicable policy/algorithm version; and
- Jira/local resource identifiers when already known.

Events never contain secrets or raw OpenAI/Jira authorization material. Human-readable activity
copy is a projection of these records and may be regenerated; the event envelope is the durable
contract.
