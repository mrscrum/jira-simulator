# Simulation Engine Rewrite — Requirements

## 1. Overview

Rewrite the simulation engine to replace the current event-probability-driven model with a
deterministic, distribution-based work simulation. The engine models individual backlog items
flowing through configurable Jira-mirrored statuses, consuming team capacity, and producing
Jira events in real time.

**Keep:** Jira integration layer (`jira_client.py`, `jira_write_queue.py`, `jira_bootstrapper.py`,
`jira_health.py`), write queue operations, bootstrap process, health monitoring.

**Replace:** `engine/simulation.py`, `engine/issue_state_machine.py`, `engine/capacity.py`,
`engine/sprint_lifecycle.py`, `engine/backlog.py`, `engine/events/*`, and related models
(`issue.py`, `sprint.py`, `touch_time_config.py`, `dysfunction_config.py`,
`simulation_event_config.py`).

**Future phases (out of scope):**
- Blockers and cross-team dependencies
- Mid-sprint scope changes
- Team member availability calendar per sprint

---

## 2. Tick & Time Model

| Parameter | Value |
|-----------|-------|
| Tick granularity | Configurable. Default = **1 hour**. Minimum = **6 minutes** (0.1 hr). |
| Working hours/day | **6 hours** |
| Working days | Monday–Friday, excluding **US federal holidays** |
| Simulation speed | Default = **real time** (1 tick per tick-duration of wall clock). Speed-up mode: **1 wall-clock minute = 1 simulated hour** (for verification). |

The existing `sim_clock.py` / `calendar.py` modules handle time acceleration and working-hour
checks. These should be adapted, not rewritten from scratch.

---

## 3. Backlog Item Types

Six issue types, each with its own workflow (status flow):

- **Epic**
- **Story**
- **Bug**
- **Task**
- **Spike**
- **Enabler**

---

## 4. Size Types (Story Points)

Fibonacci scale: **1, 2, 3, 5, 8, 13**

Every combination of (item type × size) is a distinct configuration subcategory.
Total: 6 types × 6 sizes = **36 subcategories** (Epic sizing TBD — may not use points).

---

## 5. Workflow & Statuses

### 5.1 Configurable per project

Each item type defines its own ordered list of statuses. Statuses are mapped **1:1** to Jira
statuses (no simplified 3-bucket mapping).

Example (Story): `To Do → In Development → Code Review → QA → Done`
Example (Bug): `To Do → In Development → QA → Done`

### 5.2 Per-status configuration

For each status in a workflow, the following is configured:

| Field | Description |
|-------|-------------|
| **Roles** | One or more roles that can do the work in this status. Multiple roles are treated as interchangeable — any one with available capacity can be assigned. |
| **Full time in status** (p25, p50, p99) | Three percentile values in **hours**. A log-normal distribution is fitted to these. Sampled **once** when the item enters the status. Represents the total wall-clock time (working hours) the item spends in this status. |
| **Work time in status** (min, max) | Range in **hours**. Uniformly sampled **once** when the item enters the status. Represents the actual hands-on work time required. |

**Special case:** If work time = 0 for a status, no role capacity is consumed. The item simply
waits for the full-time-in-status duration to elapse (e.g., a waiting/queue status).

### 5.3 Direction probability grid (move-left)

Defined **per item type**. A matrix where each status has probabilities of regressing to each
prior status.

Example for a 5-status workflow `[S1, S2, S3, S4, S5]`:

```
From S3: → S2 (10%), → S1 (2%)    → move forward (88%)
From S4: → S3 (15%), → S2 (3%), → S1 (0%)  → move forward (82%)
```

When a move-left occurs:
- Both **full time in status** and **work time in status** reset (re-sampled) for the target status.
- All statuses between the target and the current status are also considered "not reached" — they will need to be traversed again.

---

## 6. Distributions

| Parameter | Distribution | Sampling |
|-----------|-------------|----------|
| Full time in status | **Log-normal**, fitted to p25/p50/p99 | Once, on entering a status |
| Work time in status | **Uniform** between min and max | Once, on entering a status |

### 6.1 Log-normal fitting

Given three percentiles (p25, p50, p99), fit a log-normal distribution:
- `mu = ln(p50)` (median of log-normal = exp(mu))
- `sigma` derived from p25 and p99 (use average of both estimates for robustness)
- Sample: `value = exp(normal(mu, sigma))`

---

## 7. Roles & Team Configuration

### 7.1 Roles

Roles are **configurable per project**. Examples: Developer, QA, Designer, Tech Lead.

### 7.2 Team members

Each team member has:
- A **role** (one of the project's defined roles)
- Available for **6 working hours per day** (default)

### 7.3 Capacity model

- Each team member can work on **at most 1 item per tick**.
- "Available capacity" for a role = at least 1 team member with that role who has **not already
  made progress on another item in this tick**.
- If multiple items need the same role in a tick, assignment is **random** among waiting items.
- A member working on an item remains assigned to it until the work for that status is complete
  (no context switching mid-status).

---

## 8. Simulation Flow — Per Tick

For each backlog item in an active sprint, in each tick:

### Step 1: Attempt to start work

If the item is in a status where work time > 0 **and** work has not yet started:
- Check if any team member with the required role(s) has available capacity this tick.
- If yes: assign the member, mark work as "started," decrement member's available ticks for
  this tick.
- If no: item waits (no progress this tick on work time; full time still elapses).

### Step 2: Advance work time

If the item has an assigned worker and work is in progress:
- Subtract the tick duration (in hours) from the remaining work time.
- The assigned member's capacity for this tick is consumed.

### Step 3: Check work completion

When remaining work time reaches 0:
- Compare the elapsed full time in status against the sampled full-time-in-status value.
- Record which percentile bucket the item falls into (< p25, p25–p50, p50–p99, > p99).

### Step 4: Check transition readiness

- The item can transition to the next status only after **both**:
  - Work time is complete (or was 0), **and**
  - Full time in status has elapsed.
- If work finishes early, the item waits until full time elapses.
- If full time elapses before work is done, work continues (full time is a floor when work > 0,
  but the item cannot move until work is also done).

**Clarification:** The item moves when `max(elapsed_full_time >= sampled_full_time, work_done)` —
i.e., both conditions must be true. The item stays until whichever takes longer.

### Step 5: Direction check (move-left)

When the system determines the item can transition:
- Roll against the direction probability grid for the item's type and current status.
- If "left": determine which prior status to move to (weighted by the per-status probabilities).
- If "forward": move to the next status in the workflow.

### Step 6: Handle move-left

If the item moves left:
- Work time **resets** for the target status (re-sampled from the distribution).
- Full time in status **resets** for the target status (re-sampled).
- The item must traverse all intermediate statuses again.

### Step 7: Handle forward move

If the item moves forward:
- Enter the next status.
- Sample new full-time-in-status and work-time-in-status for the new status.
- If the new status is the final status: mark the item as **Done**.

---

## 9. Sprint Simulation

### 9.1 Sprint planning

1. Sprint capacity is a **range** (min, max) in **story points**, set in team configuration.
2. At the start of each sprint, a capacity target is drawn uniformly from [min, max].
3. Items are pulled from the top of the backlog (priority order) until:
   - The next item would cause total points to exceed the target, **and**
   - Total points are >= minimum capacity.
4. If total points < minimum after exhausting the backlog, the sprint proceeds with what's available.

**Priority mode:** Items in the backlog can optionally have their priorities **randomized** before
sprint planning (configurable toggle). This simulates real-world priority churn.

### 9.2 Sprint execution

1. Sprint has a **configurable duration** (default: 2 weeks / 10 working days).
2. Sprint **start date** is configurable for the first sprint; subsequent sprints start
   immediately after the previous one ends.
3. The engine ticks through each working hour of the sprint.
4. All items in the sprint are processed each tick (Steps 1–7 above).

### 9.3 Sprint completion

When the sprint's calendar time is reached:
- Items that have reached the **final status** are marked as completed.
- Items that have **not** reached the final status are treated as **carryover**.

### 9.4 Carryover handling

For each carryover item:
1. **Current status** (the status the item is in when the sprint ends):
   - Remaining work time is multiplied by **1.25** (25% increase).
   - Full time in status is also extended proportionally.
2. **Completed statuses** (statuses already passed): no change.
3. **Future statuses** (statuses not yet reached): no change.
4. Carryover items are placed at the **top** of the next sprint's backlog (ahead of new items).

### 9.5 Continuous operation

- The simulation runs **indefinitely** until manually stopped.
- Each sprint ends and a new one begins automatically.
- Carryover accumulates naturally across sprints.

---

## 10. Jira Integration (Preserved)

### 10.1 Events pushed to Jira

All existing write queue operations are preserved:

| Operation | When |
|-----------|------|
| `CREATE_SPRINT` | New sprint begins |
| `CREATE_ISSUE` | New backlog item generated |
| `ADD_TO_SPRINT` | Item assigned to sprint during planning |
| `TRANSITION_ISSUE` | Item moves to a new status (forward or left) |
| `ADD_COMMENT` | Carryover note, move-left reason, etc. |
| `UPDATE_ISSUE` | Assignment changes, field updates |
| `UPDATE_SPRINT` | Sprint started/dates updated |
| `COMPLETE_SPRINT` | Sprint finished |

### 10.2 Status mapping

Statuses are mapped **1:1** to Jira statuses. The workflow configuration must match the Jira
project's workflow exactly. The bootstrap process validates this.

### 10.3 Assignee

The simulation assigns **specific team members** to items. The `sim_assignee` custom field is
updated in Jira when assignment changes.

---

## 11. Configuration Summary

### 11.1 Global / per-project

| Setting | Type | Default |
|---------|------|---------|
| Tick duration | hours | 1.0 |
| Tick minimum | hours | 0.1 (6 min) |
| Working hours/day | hours | 6 |
| Working days | weekdays | Mon–Fri |
| Holidays | list of dates | US federal holidays |
| Simulation speed | multiplier | 1x (real time) |
| Speed-up ratio | - | 1 min wall = 1 hr sim |

### 11.2 Per-team

| Setting | Type | Default |
|---------|------|---------|
| Sprint duration | working days | 10 |
| First sprint start date | date | - |
| Sprint capacity range | (min, max) story points | - |
| Priority randomization | boolean | false |
| Roles | list of role names | - |

### 11.3 Per-item-type

| Setting | Type |
|---------|------|
| Workflow (ordered statuses) | list of status names |
| Direction probability grid | matrix per status |

### 11.4 Per-item-type × per-size × per-status

| Setting | Type |
|---------|------|
| Full time in status (p25, p50, p99) | hours |
| Work time in status (min, max) | hours |
| Role(s) for the status | list of role names |

---

## 12. Out of Scope (Future Phases)

1. **Blockers & cross-team dependencies** — Items blocked by other teams' work items
2. **Mid-sprint scope changes** — Adding/removing items during an active sprint
3. **Team member availability calendar** — Per-member, per-sprint availability overrides (PTO, part-time, etc.)
4. **Templates for distribution presets** — Editable but low priority

---

## 13. Acceptance Criteria

1. A single simulation run processes backlog items through configurable, per-item-type workflows.
2. Each status respects both full-time-in-status (log-normal) and work-time-in-status (uniform)
   distributions, sampled once on entry.
3. Work time consumes role capacity; statuses with work_time=0 require no capacity.
4. Move-left probability grid drives regressions; both timers reset on move-left.
5. Sprint planning fills from prioritized backlog up to a randomly drawn capacity target within
   the configured [min, max] range.
6. Carryover items get a 25% work-time penalty on their current status and go to the top of the
   next sprint.
7. Jira receives 1:1 status transitions, sprint lifecycle events, and assignee updates in real time.
8. Speed-up mode (1 min = 1 hr) allows fast verification of the full simulation loop.
9. The simulation runs indefinitely across sprints until manually stopped.
