# Stage 3 — Jira Integration Layer Spec

## Overview

All Jira API interactions encapsulated in a dedicated integration layer. The simulator treats Jira as an eventually-consistent view of internal state — simulation never pauses for Jira. The bootstrapper provisions projects, boards, custom fields, and statuses idempotently. A write queue persists all pending Jira operations and replays them on reconnection.

---

## Architecture

```
backend/app/integrations/
├── jira_client.py          # Raw Jira REST API v3 wrapper
├── jira_bootstrapper.py    # Idempotent project + field + status provisioner
├── jira_write_queue.py     # Persistent write queue, paced delivery, recovery
├── jira_health.py          # Connectivity monitor, failure detection
└── alerting.py             # AWS SES email alerts + daily digest scheduler
```

---

## Core Design Principle — Eventually Consistent

```
Simulation engine  →  internal state DB  (source of truth, always advances)
                            ↓
                     JiraWriteQueue      (persisted, paced, retried)
                            ↓
                       Jira Cloud        (eventually consistent view)
```

- Jira connectivity failures never block or pause the simulation
- All Jira writes are queued in the DB, not fired inline
- Queue processor runs on a separate async loop, paced across the tick interval
- On recovery: latest state per issue is written + a single catch-up comment
- Dashboard shows Jira sync status independently of simulation status

---

## JiraClient

Low-level wrapper around Jira REST API v3. No business logic — pure API surface.

### Authentication
- Single shared service account for all teams
- Credentials: `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN` from environment
- Basic auth: base64(`email:api_token`) in `Authorization` header
- All requests include `Content-Type: application/json`, `Accept: application/json`

### Methods

**Projects:**
```python
get_project(project_key: str) -> dict | None
create_project(key: str, name: str, board_type: Literal["scrum","kanban"]) -> dict
```

**Boards & Sprints:**
```python
get_board(project_key: str) -> dict | None
create_board(project_key: str, board_type: str) -> dict
get_active_sprint(board_id: int) -> dict | None
create_sprint(board_id: int, name: str, start_date: datetime, end_date: datetime) -> dict
start_sprint(sprint_id: int) -> dict
complete_sprint(sprint_id: int) -> dict
add_issues_to_sprint(sprint_id: int, issue_keys: list[str]) -> None
```

**Custom Fields:**
```python
get_custom_fields() -> list[dict]
create_custom_field(name: str, field_type: str) -> dict
get_field_id_by_name(name: str) -> str | None
```

**Statuses & Transitions:**
```python
get_project_statuses(project_key: str) -> list[dict]
get_issue_transitions(issue_key: str) -> list[dict]
transition_issue(issue_key: str, transition_id: str) -> None
```

**Issues:**
```python
create_issue(project_key: str, issue_type: str, summary: str, description: str,
             story_points: int, custom_fields: dict) -> dict
update_issue(issue_key: str, fields: dict) -> None
get_issue(issue_key: str) -> dict
add_comment(issue_key: str, body: str) -> dict
add_to_sprint(issue_key: str, sprint_id: int) -> None
```

**Issue Links:**
```python
create_issue_link(link_type: str, inward_key: str, outward_key: str) -> None
get_issue_link_types() -> list[dict]
```

**Health:**
```python
ping() -> bool   # GET /rest/api/3/myself — fast connectivity check
```

### Error Handling
- All methods raise typed exceptions: `JiraAuthError`, `JiraNotFoundError`, `JiraRateLimitError`, `JiraConnectionError`
- `JiraRateLimitError` includes `retry_after` seconds from the 429 response header
- `JiraConnectionError` triggers the write queue's offline mode

---

## JiraBootstrapper

Idempotent provisioner. Safe to run multiple times — checks before creating.

### Trigger conditions
1. `POST /jira/bootstrap/{team_id}` — manual trigger via API
2. Auto-run on first simulation start if project not yet bootstrapped (checked via DB flag `team.jira_bootstrapped`)

### Per-team bootstrap sequence

```
1. Check project exists (get_project)
   → exists: log "project found, skipping creation"
   → not found: create_project(key, name, board_type)

2. Check board exists (get_board)
   → exists: store board_id in DB
   → not found: create_board(project_key, board_type)

3. Custom fields (run once globally, not per team)
   → get all existing custom fields
   → for each required field (sim_assignee, sim_reporter):
       → exists by name: store field_id in DB
       → not found: create_custom_field, store field_id

4. Workflow statuses
   → fetch existing project statuses
   → for each step in team's configured workflow:
       → status name matches existing: store status_id, store transition_id
       → not found: cannot create statuses via Jira REST API v3 directly
         → log warning: "Status '{name}' not found in Jira project {key}.
            Please create it manually or via Jira admin, then re-run bootstrap."
         → mark team as bootstrap_incomplete in DB
         → continue (do not abort entire bootstrap)

5. Mark team.jira_bootstrapped = true in DB (even if some statuses missing)
   Store bootstrap_warnings[] for dashboard display
```

### Bootstrap status API
```
GET /jira/bootstrap/{team_id}/status
→ {
    bootstrapped: bool,
    warnings: list[str],        # e.g. missing statuses
    board_id: int,
    custom_field_ids: dict,
    last_run: datetime
  }
```

---

## JiraWriteQueue

Persistent queue of all pending Jira operations. Survives restarts.

### DB model: `jira_write_queue`
```
id              UUID primary key
team_id         FK → teams
issue_id        FK → issues (nullable — some ops are not issue-specific)
operation_type  enum: CREATE_ISSUE | UPDATE_ISSUE | TRANSITION_ISSUE |
                      ADD_COMMENT | CREATE_LINK | ADD_TO_SPRINT |
                      UPDATE_SPRINT | COMPLETE_SPRINT
payload         JSON — full API call parameters
status          enum: PENDING | IN_FLIGHT | DONE | FAILED | SKIPPED
created_at      datetime
processed_at    datetime (nullable)
attempts        int default 0
last_error      text (nullable)
priority        int default 5 (lower = higher priority, range 1–10)
```

### Pacing
- Queue processor runs as async background task, separate from tick engine
- Target: spread all PENDING writes across 80% of the tick interval
  (e.g. 30 min tick → process queue over 24 min, leaving 6 min buffer)
- Minimum delay between writes: 200ms
- On `JiraRateLimitError`: pause entire queue for `retry_after` seconds

### Write priority order
```
1. CREATE_ISSUE          (issues must exist before they can be linked/transitioned)
2. ADD_TO_SPRINT         (must be in sprint before transition)
3. TRANSITION_ISSUE      (status changes)
4. ADD_COMMENT           (narrative, lowest impact if delayed)
5. CREATE_LINK           (cross-team links)
6. UPDATE_ISSUE          (field updates — SP changes, custom field updates)
7. UPDATE_SPRINT / COMPLETE_SPRINT
```

### Offline mode
- `JiraConnectionError` → queue processor enters OFFLINE mode
- Simulation continues advancing internally
- All new writes queued as PENDING, no attempts made
- Health monitor polls `ping()` every 60 seconds
- On reconnection → enter RECOVERY mode

### Recovery mode
- For each issue with PENDING writes:
  - Collapse all pending operations into current state (latest transition + field values)
  - Write single UPDATE_ISSUE with current state
  - Write single ADD_COMMENT: `"[Simulator] Sync resumed after outage. State fast-forwarded from {gap_start} to {gap_end} ({n} ticks). Internal simulation continued uninterrupted."`
  - Mark all intermediate PENDING writes as SKIPPED
- Resume normal paced processing after recovery writes complete

---

## JiraHealth Monitor

```python
class JiraHealthMonitor:
    status: Literal["ONLINE", "OFFLINE", "RECOVERING"]
    last_checked: datetime
    last_online: datetime
    consecutive_failures: int
    outage_start: datetime | None
```

- Polls `ping()` every 60 seconds in a background async task
- `ONLINE → OFFLINE`: 2 consecutive failures (2 minutes to detect)
- `OFFLINE → RECOVERING`: first successful ping after outage
- `RECOVERING → ONLINE`: all recovery writes processed
- Publishes status changes to: alerting system + dashboard state endpoint

---

## Alerting — AWS SES

### Configuration
```bash
ALERT_EMAIL_FROM=simulator@yourdomain.com   # SES-verified sender
ALERT_EMAIL_TO=you@email.com                # recipient
AWS_SES_REGION=us-east-1                    # can differ from main region
```

Terraform addition (Stage 0 infra update):
- `aws_ses_email_identity` for sender address
- IAM policy on EC2 instance profile: `ses:SendEmail` permission
- SES sandbox note: recipient must also be verified unless SES production access requested

### Alert events and templates

| Event | Subject | Trigger |
|---|---|---|
| Jira offline | `[Simulator] Jira connection lost` | `ONLINE → OFFLINE` |
| Jira recovered | `[Simulator] Jira connection restored` | `RECOVERING → ONLINE` |
| Simulation engine crash | `[Simulator] Engine error — simulation paused` | Unhandled exception in tick engine |
| Bootstrap incomplete | `[Simulator] Bootstrap warnings for {team}` | Bootstrap completes with warnings |
| Daily digest | `[Simulator] Daily activity digest` | 08:00 UTC daily |

### Daily digest content
```
Simulation status: Running / Paused
Active teams: N
Current sprint: N (day X of Y)

Per-team summary:
  Alpha Squad: 12 issues in flight, 3 completed, 2 dysfunctions triggered
  Beta Core:   8 issues in flight, 1 completed, 0 dysfunctions triggered

Jira sync:
  Writes completed today: 847
  Writes failed/skipped: 3
  Current queue depth: 12

Last 24h dysfunctions:
  Low quality story ×3, Bug injection ×5, Re-estimation ×1
```

### Alerting module API
```python
async def send_alert(event: AlertEvent, context: dict) -> None
async def send_daily_digest() -> None
```

Daily digest scheduled via APScheduler at 08:00 UTC — separate job from tick engine.

---

## New API Endpoints

```
POST   /jira/bootstrap/{team_id}          # Manual bootstrap trigger
GET    /jira/bootstrap/{team_id}/status   # Bootstrap status + warnings
GET    /jira/health                       # Current Jira connectivity status
GET    /jira/queue/status                 # Queue depth, in-flight, failed counts
POST   /jira/queue/retry-failed           # Manually retry FAILED items
GET    /jira/projects/{project_key}/statuses  # Proxied status list (for StatusPicker)
```

---

## DB Schema Additions

```sql
-- Bootstrap tracking
ALTER TABLE teams ADD COLUMN jira_bootstrapped BOOLEAN DEFAULT FALSE;
ALTER TABLE teams ADD COLUMN jira_board_id INTEGER;
ALTER TABLE teams ADD COLUMN jira_bootstrap_warnings JSON;
ALTER TABLE teams ADD COLUMN jira_bootstrapped_at TIMESTAMP;

-- Custom field IDs (global, stored once)
CREATE TABLE jira_config (
    key   TEXT PRIMARY KEY,   -- e.g. 'field_id_sim_assignee'
    value TEXT NOT NULL
);

-- Write queue
CREATE TABLE jira_write_queue (
    id              TEXT PRIMARY KEY,
    team_id         TEXT REFERENCES teams(id),
    issue_id        TEXT REFERENCES issues(id),
    operation_type  TEXT NOT NULL,
    payload         JSON NOT NULL,
    status          TEXT NOT NULL DEFAULT 'PENDING',
    priority        INTEGER NOT NULL DEFAULT 5,
    created_at      TIMESTAMP NOT NULL,
    processed_at    TIMESTAMP,
    attempts        INTEGER NOT NULL DEFAULT 0,
    last_error      TEXT
);

-- Jira key mapping (internal issue ID ↔ Jira issue key)
CREATE TABLE jira_issue_map (
    issue_id        TEXT PRIMARY KEY REFERENCES issues(id),
    jira_key        TEXT NOT NULL UNIQUE,   -- e.g. ALPHA-42
    jira_id         TEXT NOT NULL,          -- Jira internal ID
    created_at      TIMESTAMP NOT NULL
);

-- Cross-team link tracking
CREATE TABLE jira_issue_links (
    id              TEXT PRIMARY KEY,
    from_issue_id   TEXT REFERENCES issues(id),
    to_issue_id     TEXT REFERENCES issues(id),
    link_type       TEXT NOT NULL,          -- e.g. 'blocks'
    jira_link_id    TEXT,                   -- Jira link ID once created
    status          TEXT NOT NULL DEFAULT 'PENDING'
);
```

---

## Test Coverage

### Unit tests (mock JiraClient)
| Module | What to test |
|---|---|
| `JiraBootstrapper` | Skips creation when project exists, creates when not found, handles missing statuses gracefully, marks bootstrap_incomplete correctly, idempotent on re-run |
| `JiraWriteQueue` | Enqueue adds with correct priority, pacing respects tick interval, rate limit response pauses queue, FAILED items not retried automatically |
| `JiraHealth` | ONLINE→OFFLINE after 2 failures, OFFLINE→RECOVERING on ping success, outage_start recorded correctly |
| `alerting` | SES send called with correct template per event type, daily digest includes all teams |

### Integration tests (real Jira sandbox, gated behind `INTEGRATION_TESTS=true`)
| Scenario | What to verify |
|---|---|
| Bootstrap fresh project | Project, board, custom fields created; status warnings logged for missing statuses |
| Bootstrap existing project | No duplicate resources created |
| Create issue | Appears in Jira with correct fields, sim_assignee populated |
| Transition issue | Status changes in Jira, transition history visible |
| Cross-project link | Link visible in both issues in Jira |
| Recovery replay | After simulated outage: latest state written, catch-up comment present, intermediate ops skipped |

---

## Alembic Migrations

One migration file per logical change:
- `add_jira_bootstrap_fields_to_teams`
- `create_jira_config_table`
- `create_jira_write_queue_table`
- `create_jira_issue_map_table`
- `create_jira_issue_links_table`

---

## UAT Criteria

Claude Code considers Stage 3 done when:

- [ ] `POST /jira/bootstrap/{team_id}` runs on a fresh Jira project → project, board, and custom fields created; missing statuses logged as warnings
- [ ] Bootstrap is idempotent — running twice produces no duplicates, no errors
- [ ] `sim_assignee` and `sim_reporter` custom fields visible on issues in Jira
- [ ] Issue created via queue → appears in Jira with correct summary, type, story points, custom fields
- [ ] Issue transitioned → status change visible in Jira history
- [ ] Cross-project link created → visible in both issues in Jira, stored in `jira_issue_links`
- [ ] Simulate Jira outage (bad API token) → simulation continues, queue accumulates, dashboard shows OFFLINE
- [ ] Restore connection → recovery write + catch-up comment appear in Jira, queue clears
- [ ] Alert email sent on outage and recovery (check inbox)
- [ ] Daily digest email arrives at 08:00 UTC (or force-trigger via test endpoint)
- [ ] `GET /jira/queue/status` shows accurate queue depth
- [ ] All unit tests green with mocked Jira client
- [ ] Integration tests green against real Jira sandbox
- [ ] Ruff clean, all migrations apply cleanly on fresh DB
