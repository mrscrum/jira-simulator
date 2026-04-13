# Stage 4 — Simulation Engine Spec

## Overview

The core simulation engine. Manages sprint lifecycle, issue state machines, agent capacity, backlog generation, and all 14 simulation events. Jira writes are handed off to the Stage 3 write queue — the engine never calls Jira directly. Internal state is the single source of truth.

---

## Architecture

```
backend/app/engine/
├── simulation.py           # Master tick orchestrator
├── sprint_lifecycle.py     # Planning → Active → Review → Retro phases
├── issue_state_machine.py  # Per-issue state transitions, move left, descope
├── capacity.py             # Per-person capacity, WIP, timezone-aware working hours
├── backlog.py              # Backlog management + AI content generation
├── events/
│   ├── base.py             # BaseEvent interface
│   ├── move_left.py
│   ├── descope.py
│   ├── velocity_drift.py
│   ├── carry_over.py
│   ├── sprint_goal_risk.py
│   ├── unplanned_absence.py
│   ├── stale_issue.py
│   ├── priority_change.py
│   ├── split_story.py
│   ├── external_block.py
│   ├── uneven_load.py
│   ├── review_bottleneck.py
│   ├── onboarding_tax.py
│   ├── late_planning.py
│   ├── skipped_retro.py
│   └── scope_commitment_miss.py
└── calendar.py             # Business day + holiday + timezone calculations
```

---

## Core Design — Tick Engine

### Tick sequence (every N minutes, real time)

```
1. Calendar check
   → Is current real time within any team's working hours?
   → Skip capacity advancement for teams outside working hours
   → Still process queued events and state checks regardless

2. Per-team loop (parallel, order randomised each tick):
   a. Capacity reset for new business day if applicable
   b. Sprint phase check (advance phase if conditions met)
   c. Issue state machine advancement
   d. Event rolls (dysfunction + simulation events)
   e. Stale issue detection
   f. Sprint goal risk evaluation
   g. Uneven load / review bottleneck detection

3. Backlog maintenance (top up if below configured depth)

4. Jira write queue population (hand off all state changes)

5. Persist internal state snapshot to DB

6. Alert checks (engine errors, sprint goal risk threshold breached)
```

### Tick safety
- Each tick is wrapped in a DB transaction — partial ticks do not corrupt state
- If a tick fails mid-way: roll back, log error, send alert, retry next tick
- Tick engine records `last_successful_tick` — used for catch-up detection on restart

---

## Calendar & Working Hours Model

### Per-team configuration
```python
class TeamCalendar:
    timezone: str               # e.g. "America/New_York", "Europe/London"
    working_hours_start: int    # e.g. 9
    working_hours_end: int      # e.g. 17
    working_days: list[int]     # e.g. [0,1,2,3,4] (Mon–Fri)
    holidays: list[date]        # configurable per team
```

### Multi-timezone team modeling
- Each member has their own timezone (inherits team default, can override)
- Member is "working" only when current real time falls within their working hours
- Cross-timezone teams: overlap window calculated — only overlap hours count for synchronous handoffs
- Async handoffs (e.g. BA in London hands off to Dev in New York): handoff lag = time until receiving member's working hours begin

### Business day calculations
```python
def is_working_time(member: Member, at: datetime) -> bool
def next_working_moment(member: Member, after: datetime) -> datetime
def working_hours_remaining_today(member: Member, at: datetime) -> float
def working_days_in_sprint(team: Team, sprint: Sprint) -> int
```

### Holiday handling
- Public holidays configured per team (list of dates)
- On a holiday: member capacity = 0, same as weekend
- Holiday list seeded with common defaults (US/UK/EU), fully editable in config UI

---

## Sprint Lifecycle

### Phases and transitions

```
BACKLOG_PREP
  → auto-advance when: backlog depth ≥ sprint_capacity × 1.5
  → or: manual trigger via API

PLANNING
  → duration: configurable (default 4 hours, deducted from sprint day 1 capacity)
  → late_planning event may extend this
  → issue selection: capacity-fitted / point-target / priority-ordered (per team config)
  → scope_commitment_miss check runs here
  → auto-advance when: planning duration elapsed

ACTIVE (sprint running)
  → duration: team.sprint_length_days business days
  → all simulation events fire during this phase
  → sprint_goal_risk evaluated every tick
  → pause point: configurable — engine pauses here and waits for resume signal

REVIEW
  → duration: configurable (default 2 hours)
  → carry-over issues identified
  → velocity calculated: completed_points / committed_points
  → velocity_drift updated

RETROSPECTIVE
  → skipped_retro event may skip this phase
  → if not skipped: dysfunction probabilities adjusted based on sprint outcome
    (e.g. high bug rate → bug_injection probability nudged down slightly, modeling team learning)
  → auto-advance to BACKLOG_PREP for next sprint
```

### Sprint DB model
```sql
CREATE TABLE sprints (
    id                  TEXT PRIMARY KEY,
    team_id             TEXT REFERENCES teams(id),
    sprint_number       INTEGER NOT NULL,
    phase               TEXT NOT NULL,  -- BACKLOG_PREP|PLANNING|ACTIVE|REVIEW|RETRO
    start_date          DATE,
    end_date            DATE,
    committed_points    INTEGER,
    completed_points    INTEGER,
    carried_over_points INTEGER DEFAULT 0,
    velocity            FLOAT,
    goal_at_risk        BOOLEAN DEFAULT FALSE,
    pause_before_planning BOOLEAN DEFAULT FALSE,
    created_at          TIMESTAMP NOT NULL
);
```

---

## Issue State Machine

### Internal states (not directly visible in Jira)

```
BACKLOG
  → [Sprint Planning] → SPRINT_COMMITTED

SPRINT_COMMITTED
  → [Working hours + role free] → QUEUED_FOR_ROLE

QUEUED_FOR_ROLE          ← wait_time accumulates here
  → [Role/person has capacity] → IN_PROGRESS
  → [Stale threshold] → fires stale_issue event

IN_PROGRESS              ← touch_time burns down here
  → [Touch time exhausted] → PENDING_HANDOFF
  → [Move left roll] → MOVED_LEFT (transitions back to earlier step)
  → [External block] → EXTERNALLY_BLOCKED
  → [Priority change] → back to QUEUED_FOR_ROLE with new priority

PENDING_HANDOFF
  → [Next role has capacity] → QUEUED_FOR_ROLE (next step)
  → [Last step complete] → DONE

DONE
  → [Bug injection roll] → spawns new Bug issue
  → [Re-estimation roll on next issue from same context] → probability carried

MOVED_LEFT
  → [Target step role free] → QUEUED_FOR_ROLE at target step
  → records move_left event in event_log

EXTERNALLY_BLOCKED
  → [External block resolved — time-based or manual] → IN_PROGRESS
  → wait_time accumulates, escalation ladder applies

DESCOPED
  → issue removed from sprint
  → sprint velocity forecast recalculated
  → issue returns to BACKLOG state
```

### Move Left configuration (per workflow step)

```python
class MoveLeftConfig:
    from_step_id: str
    base_probability: float          # 0.0–1.0, rolls each tick while IN_PROGRESS
    targets: list[MoveLeftTarget]    # ordered by probability weight

class MoveLeftTarget:
    to_step_id: str
    weight: float                    # relative weight among targets
    same_step_statuses: list[str]    # statuses treated as same step (not counted as move left)
```

Dysfunction multipliers stack on top of `base_probability`:
- `LOW_QUALITY_AC` active on issue → QA→Dev move left probability × configured multiplier
- `RE_ESTIMATION` active → any move left probability × 1.2

Move left UI (Stage 2 addition — new section in WorkflowDesigner):
- Visual sequence of steps showing allowed move-left arrows
- Per-step: base probability slider + target step selector with weight inputs
- "Same step" status grouping — drag statuses into groups that don't count as move left

---

## Capacity Model

### Per-person per-day
```python
class DailyCapacity:
    member_id: str
    date: date
    total_hours: float          # from team calendar
    consumed_hours: float       # by active touch-time issues
    available_hours: float      # total - consumed
    active_wip_count: int
    is_working: bool            # False on weekends, holidays, dark events
```

### Capacity allocation rules
```
Person picks up new work when:
  available_hours > 0  AND  active_wip_count < max_concurrent_wip

Touch time consumption per tick:
  hours_advanced = min(available_hours, touch_time_remaining)
  touch_time_remaining -= hours_advanced
  consumed_hours += hours_advanced

WIP contribution:
  Each issue in IN_PROGRESS consumes wip_contribution units from the step config
  Default wip_contribution = 1.0 per step
```

### Timezone-aware handoff lag
```
Handoff from Member A (London, 17:00) to Member B (New York, 12:00):
  → B's next working moment = same day 09:00 EST
  → handoff_lag = 0 hours (B is currently working)

Handoff from Member A (New York, 17:00) to Member B (London):
  → B's next working moment = next day 09:00 GMT
  → handoff_lag = ~16 hours
  → issue sits in PENDING_HANDOFF state for handoff_lag duration
```

---

## Backlog Generation

### Depth maintenance
- Target: `backlog_depth_target` configurable per team (default: 2× sprint capacity in points)
- Checked each tick during BACKLOG_PREP and ACTIVE phases
- If depth < target: generate new issues via AI content generator

### AI content generation (Claude API)
```python
async def generate_issue(
    team: Team,
    issue_type: Literal["Story", "Bug", "Task", "Sub-task", "Epic"],
    story_points: int,
    domain_context: str,    # seeded from team name + existing issue themes
) -> GeneratedIssue:
    # Returns: summary, description, acceptance_criteria (for Stories)
    # Each team has a domain persona (e.g. "e-commerce platform", "data pipeline")
    # Persona derived from team name + project key on first generation, stored in DB
```

### Pre-seeded stories
- On team creation: seed script generates N starter issues (configurable, default 20)
- Seed issues cover all issue types and story point values
- Seeded via AI generation with team persona — not generic placeholder text

### Story point distribution (configurable per team)
```python
default_distribution = {1: 0.15, 2: 0.20, 3: 0.25, 5: 0.20, 8: 0.15, 13: 0.05}
```

---

## Simulation Events — Full Catalogue

### Existing dysfunction events (from Stage 5 — referenced here for completeness)
Low quality story, Mid-sprint scope add, Blocking dependency, Teammate goes dark,
Re-estimation, Bug injection, Cross-team dysfunctions — all defined in Stage 5 spec.

### New events defined in Stage 4

#### Move Left
- **Trigger:** Per-tick roll against `base_probability` while issue is IN_PROGRESS
- **Mechanical effect:** Issue transitions back to target step, touch_time reset to full for that step, wait_time resets, current worker notified via comment
- **Jira effect:** Status transitions back, comment: `"[{Member} - {Role}] Sending back to {step} — {AI-generated reason}"`
- **Metrics impact:** cycle_time increases, flow_efficiency drops, move_left_count tracked per issue

#### Descope
- **Trigger:** Re-estimation event pushes sprint over capacity (60–80% probability), or explicit roll during ACTIVE phase (configurable base probability, default 5%)
- **Mechanical effect:** Issue removed from sprint, returned to BACKLOG, sprint committed_points reduced, velocity_forecast recalculated
- **Jira effect:** Issue removed from sprint, comment: `"[{SM}] Descoped from Sprint {N} due to capacity constraints. Returning to backlog."`

#### Velocity Trend Drift
- **Trigger:** End of each sprint (REVIEW phase)
- **Mechanical effect:** Team's historical velocity updated with weighted moving average (last 3 sprints). Applied to next sprint's capacity estimate. Drift direction influenced by: dysfunction frequency, carry-over rate, team stability
- **No direct Jira effect** — internal metric only, surfaced in dashboard

#### Carry-over
- **Trigger:** Sprint end — any IN_PROGRESS or QUEUED issue not in DONE
- **Mechanical effect:** Issue flagged `carried_over = true`, added to next sprint automatically, counts against next sprint capacity
- **Jira effect:** Issue moved to new sprint, label `carried-over` added, comment: `"[{SM}] Carried over from Sprint {N}. Not completed due to {AI-generated reason}."`

#### Sprint Goal At Risk
- **Trigger:** Each tick — evaluated when `remaining_points / remaining_capacity > 1.2`
- **Mechanical effect:** Flag set on sprint, probability of descope events increases, SM comment posted once per sprint when threshold first breached
- **Jira effect:** Comment on sprint (via SM): `"Sprint goal is at risk. {remaining_points} points remain with {remaining_capacity_hours}h of capacity left."`
- **Alert:** Dashboard shows risk badge, email alert if configured threshold breached

#### Unplanned Absence
- **Trigger:** Random roll per person per day (configurable probability, default 2%)
- **Duration:** 1–2 business days
- **Mechanical effect:** Member capacity → 0 for duration, active issues PAUSED (touch time suspended), no reassignment (shorter than "goes dark" threshold)
- **Jira effect:** No direct Jira change — issues age visibly

#### Stale Issue Nudge
- **Trigger:** Issue in QUEUED_FOR_ROLE for > `stale_threshold_hours` (configurable, default 24h)
- **Mechanical effect:** None — detection only
- **Jira effect:** Comment from SM: `"[{SM}] This issue has been waiting for {role} for {N} hours. Is there a blocker?"`
- **Fires once per stale period** — resets if issue advances

#### Priority Change
- **Trigger:** Random roll during ACTIVE phase (configurable probability, default 8%)
- **Mechanical effect:** Issue priority updated, if IN_PROGRESS → interrupts current worker (touch_time_remaining preserved but worker drops to other work), issue re-queued at top of role queue
- **Jira effect:** Priority field updated, comment: `"[{SM}] Priority elevated due to {AI-generated business reason}. Needs immediate attention."`

#### Split Story
- **Trigger:** Issue is IN_PROGRESS, story_points ≥ 5, random roll (configurable probability, default 10%)
- **Mechanical effect:** Original issue descoped, two new issues created with combined points ≤ original, one added to current sprint (fits capacity), one to backlog
- **Jira effect:** Original issue closed as "Won't Do this sprint", two new issues created linked to original with "split from" relationship

#### Blocked by External Dependency
- **Trigger:** Random roll during IN_PROGRESS (configurable probability, default 12%)
- **Duration:** 1–5 business days (configurable range)
- **Mechanical effect:** Issue → EXTERNALLY_BLOCKED, touch_time PAUSED, assignee capacity freed
- **Escalation ladder:**
  - Day 1: comment from worker noting the block
  - Day 2: SM escalation comment
  - Day 3+: sprint goal risk probability increases
- **Jira effect:** Label `blocked-external` added, comment chain per escalation ladder, label removed on resolution

#### Uneven Load Accumulation
- **Trigger:** Detection — checked each tick, not a random roll
- **Condition:** One role at WIP ceiling for 3+ consecutive ticks while another role has 0 active issues
- **Mechanical effect:** None automatically — detection only, models realistic team dysfunction without forced fix
- **Jira effect:** SM comment on longest-waiting issue: `"[{SM}] {Role} queue is backing up. {N} issues waiting."`
- **Dashboard:** Capacity view highlights overloaded role in amber

#### Review Bottleneck
- **Trigger:** Detection — specific to Code Review step (or any step marked `is_review = true`)
- **Condition:** Single member assigned to review step with 3+ issues queued
- **Mechanical effect:** Review touch_time × 1.2x (context switching between reviews)
- **Jira effect:** Comment on oldest waiting issue: `"[{Reviewer}] Working through review queue — {N} items ahead of this."`

#### Onboarding Tax
- **Trigger:** New member added to team mid-sprint via config UI
- **Duration:** Configurable ramp-up period (default 5 business days)
- **Mechanical effect:** Member capacity × configurable ramp factor (default 0.5 for first 3 days, 0.75 for days 4–5, full from day 6)
- **Jira effect:** Comment on first issue assigned to new member: `"[{Member}] Getting up to speed — may take slightly longer on first few items."`

#### Late Sprint Planning
- **Trigger:** Random roll at PLANNING phase start (configurable probability, default 15%)
- **Mechanical effect:** Planning duration extended by 2–4 hours, deducted from sprint day 1 capacity for all members
- **Jira effect:** SM comment on sprint: `"Planning ran long today. Starting sprint slightly behind schedule."`

#### Skipped Retrospective
- **Trigger:** Random roll at RETRO phase (configurable probability, default 20%)
- **Mechanical effect:** RETRO phase skipped entirely, dysfunction probabilities NOT adjusted (no team learning this sprint), next sprint starts immediately
- **Jira effect:** No sprint retro comment posted

#### Scope Commitment Miss
- **Trigger:** PLANNING phase — detected when committed_points > team_velocity × 1.15
- **Mechanical effect:** Sprint starts overcommitted, sprint_goal_at_risk probability elevated from day 1, descope probability elevated throughout sprint
- **Jira effect:** SM comment at sprint start: `"Sprint committed to {N} points against a recent velocity of {V}. Stretch goal — may need to descope."`

---

## Event Configuration DB Model

```sql
CREATE TABLE simulation_event_config (
    id          TEXT PRIMARY KEY,
    team_id     TEXT REFERENCES teams(id),
    event_type  TEXT NOT NULL,
    enabled     BOOLEAN DEFAULT TRUE,
    probability FLOAT,              -- null for detection-based events
    params      JSON NOT NULL,      -- event-specific parameters
    updated_at  TIMESTAMP NOT NULL
);

CREATE TABLE move_left_config (
    id               TEXT PRIMARY KEY,
    team_id          TEXT REFERENCES teams(id),
    from_step_id     TEXT REFERENCES workflow_steps(id),
    base_probability FLOAT NOT NULL,
    updated_at       TIMESTAMP NOT NULL
);

CREATE TABLE move_left_targets (
    id                  TEXT PRIMARY KEY,
    move_left_config_id TEXT REFERENCES move_left_config(id),
    to_step_id          TEXT REFERENCES workflow_steps(id),
    weight              FLOAT NOT NULL DEFAULT 1.0
);

CREATE TABLE move_left_same_step_statuses (
    move_left_config_id TEXT REFERENCES move_left_config(id),
    status_name         TEXT NOT NULL,
    PRIMARY KEY (move_left_config_id, status_name)
);
```

---

## Issue Event Log

Every simulation event produces an event log entry — the audit trail your Sprint Risk Analyzer reads.

```sql
CREATE TABLE simulation_event_log (
    id           TEXT PRIMARY KEY,
    team_id      TEXT REFERENCES teams(id),
    sprint_id    TEXT REFERENCES sprints(id),
    issue_id     TEXT REFERENCES issues(id),
    event_type   TEXT NOT NULL,
    occurred_at  TIMESTAMP NOT NULL,   -- real timestamp
    sim_day      INTEGER NOT NULL,     -- day within sprint (1-based)
    payload      JSON NOT NULL,        -- event-specific detail
    jira_written BOOLEAN DEFAULT FALSE -- whether Jira write was queued
);
```

---

## New API Endpoints

```
# Simulation control
GET    /simulation/status                      # Global + per-team status
POST   /simulation/start                       # Start all teams
POST   /simulation/pause                       # Pause all teams
POST   /simulation/{team_id}/start
POST   /simulation/{team_id}/pause
POST   /simulation/{team_id}/resume
PUT    /simulation/tick-interval               # Update tick interval

# Sprint control
GET    /simulation/{team_id}/sprint/current
POST   /simulation/{team_id}/sprint/advance    # Manual phase advance
POST   /simulation/{team_id}/sprint/reset

# Event config
GET    /simulation/{team_id}/events
PUT    /simulation/{team_id}/events/{event_type}
GET    /simulation/{team_id}/move-left
PUT    /simulation/{team_id}/move-left/{from_step_id}

# Backlog
GET    /simulation/{team_id}/backlog
POST   /simulation/{team_id}/backlog/generate  # Force generate N issues

# Observability
GET    /simulation/{team_id}/event-log
GET    /simulation/{team_id}/capacity          # Current per-person capacity state
GET    /simulation/health                      # Engine health + last tick info
```

---

## DB Schema Additions Summary

```sql
-- Sprints
CREATE TABLE sprints ( ... )  -- defined above

-- Backlog
ALTER TABLE issues ADD COLUMN backlog_priority INTEGER;
ALTER TABLE issues ADD COLUMN carried_over BOOLEAN DEFAULT FALSE;
ALTER TABLE issues ADD COLUMN descoped BOOLEAN DEFAULT FALSE;
ALTER TABLE issues ADD COLUMN split_from_id TEXT REFERENCES issues(id);

-- Member timezone
ALTER TABLE members ADD COLUMN timezone TEXT;  -- overrides team default

-- Team calendar config
ALTER TABLE teams ADD COLUMN sprint_length_days INTEGER DEFAULT 10;
ALTER TABLE teams ADD COLUMN sprint_planning_strategy TEXT DEFAULT 'capacity_fitted';
ALTER TABLE teams ADD COLUMN backlog_depth_target INTEGER DEFAULT 40;
ALTER TABLE teams ADD COLUMN pause_before_planning BOOLEAN DEFAULT FALSE;
ALTER TABLE teams ADD COLUMN working_hours_start INTEGER DEFAULT 9;
ALTER TABLE teams ADD COLUMN working_hours_end INTEGER DEFAULT 17;
ALTER TABLE teams ADD COLUMN timezone TEXT DEFAULT 'UTC';
ALTER TABLE teams ADD COLUMN holidays JSON DEFAULT '[]';

-- Event system
CREATE TABLE simulation_event_config ( ... )       -- defined above
CREATE TABLE simulation_event_log ( ... )           -- defined above
CREATE TABLE move_left_config ( ... )               -- defined above
CREATE TABLE move_left_targets ( ... )              -- defined above
CREATE TABLE move_left_same_step_statuses ( ... )   -- defined above

-- Daily capacity tracking
CREATE TABLE daily_capacity_log (
    id               TEXT PRIMARY KEY,
    member_id        TEXT REFERENCES members(id),
    date             DATE NOT NULL,
    total_hours      FLOAT NOT NULL,
    consumed_hours   FLOAT NOT NULL,
    active_wip_count INTEGER NOT NULL,
    UNIQUE(member_id, date)
);
```

---

## Test Coverage

| Module | What to test |
|---|---|
| `calendar.py` | Working hours detection across timezones, holiday skipping, handoff lag calculation, business days in sprint |
| `capacity.py` | WIP ceiling respected, hours consumed correctly, timezone-aware availability |
| `issue_state_machine.py` | All state transitions, move left target selection, descope removes from sprint |
| `sprint_lifecycle.py` | Phase auto-advance conditions, pause point respected, carry-over detection, velocity calculation |
| `backlog.py` | Depth maintenance triggers generation, story point distribution within tolerance |
| Each event handler | Trigger condition, mechanical effect on time model, Jira write queued with correct payload |
| `simulation.py` (tick orchestrator) | Partial tick rollback on failure, teams processed independently, last_successful_tick updated |

---

## UAT Criteria

Claude Code considers Stage 4 done when:

- [ ] Start simulation with 1 team → issues appear in Jira, transition through statuses over real time with realistic comments
- [ ] Sprint lifecycle completes end-to-end: BACKLOG_PREP → PLANNING → ACTIVE → REVIEW → RETRO → next sprint auto-starts
- [ ] Pause before planning works — engine stops, resumes on API call
- [ ] Move left occurs and is visible in Jira history + event log
- [ ] Carry-over issues appear in next sprint with correct label and comment
- [ ] Descope removes issue from sprint, velocity forecast updates
- [ ] Sprint goal at risk flag appears in dashboard when threshold breached
- [ ] Stale issue comment appears in Jira after configured threshold
- [ ] Working hours respected — no Jira writes or capacity changes outside team's timezone working hours
- [ ] Holidays skipped — no capacity consumed on configured holiday dates
- [ ] Cross-timezone handoff lag observed — issue sits in PENDING_HANDOFF until receiving member's working hours begin
- [ ] Backlog replenished automatically when depth falls below target
- [ ] AI-generated issue content is realistic and team-persona-appropriate
- [ ] All event log entries written with correct timestamps and sim_day
- [ ] Restart backend mid-sprint → simulation resumes correctly from last persisted state
- [ ] All unit tests green
- [ ] Ruff clean, all migrations apply cleanly on fresh DB
