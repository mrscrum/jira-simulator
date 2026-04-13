# Phase 8: Backlog & API Updates

## Context

Add new issue types (Spike, Enabler) to backlog generation and update API endpoints to remove obsolete event/dysfunction endpoints and reflect new sprint phases.

Full requirements: `docs/simulation-engine-rewrite-requirements.md`

---

## Modify: `backend/app/engine/backlog.py`

### Changes:

1. Expand `DEFAULT_ISSUE_TYPES` to include all 6 types:
```python
DEFAULT_ISSUE_TYPES = {
    "Story": 0.35,
    "Bug": 0.20,
    "Task": 0.15,
    "Spike": 0.10,
    "Enabler": 0.10,
    "Epic": 0.10,
}
```
(Weights are approximate — adjust as needed)

2. Add summary/description templates for Spike and Enabler:
- Spike: "Investigate {topic} feasibility for {team}"
- Enabler: "Enable {capability} infrastructure for {team}"

3. Keep existing Story, Bug, Task, Epic templates.

---

## Modify: `backend/app/api/routers/simulation.py`

### Changes:

1. Remove or comment out event config endpoints (if they exist as routes)
2. Remove dysfunction injection endpoint (if present)
3. Update `GET /simulation/status` response to show new phase names (PLANNING, ACTIVE, COMPLETED)
4. Keep all control endpoints: start, stop, pause, resume, tick, clock/speed, tick-interval

### Verify main.py router includes:
- Remove `dysfunctions` router include if present
- Keep simulation, teams, members, workflow, jira_integration routers

---

## Existing files to reference:
- `backend/app/engine/backlog.py` — current templates and issue type weights
- `backend/app/api/routers/simulation.py` — current endpoints
- `backend/app/main.py` — router registration

## Dependencies:
- Phase 6 (Simulation Engine rewrite)

## What comes next:
- Phase 9 (Delete obsolete code)
