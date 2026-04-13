# Phase 7: Jira Write Queue Update

## Context

Small but critical change: remove the hardcoded `JIRA_STATUS_MAP` that maps internal simulator states to 3 Jira buckets (To Do / In Progress / Done). The new engine passes Jira status names directly from workflow_step.jira_status.

Full requirements: `docs/simulation-engine-rewrite-requirements.md`

---

## Modify: `backend/app/integrations/jira_write_queue.py`

### Changes:

1. **Delete** the `JIRA_STATUS_MAP` dict (lines 13-23):
```python
# DELETE THIS ENTIRE BLOCK:
JIRA_STATUS_MAP: dict[str, str] = {
    "SPRINT_COMMITTED": "To Do",
    "QUEUED_FOR_ROLE": "To Do",
    ...
}
```

2. **Update** `_resolve_and_transition()` method (line 284):
```python
# BEFORE:
jira_status = JIRA_STATUS_MAP.get(target_status, target_status)

# AFTER:
jira_status = target_status
```

That's it. ~5 lines changed.

### Why this works:
The engine now passes `workflow_step.jira_status` (e.g., "In Development", "Code Review", "QA") directly as the `target_status` in the TRANSITION_ISSUE payload. The `_resolve_and_transition` method already fetches available transitions from Jira and matches by name, so it will find the correct transition ID for any valid Jira status name.

---

## Existing file to reference:
- `backend/app/integrations/jira_write_queue.py` — lines 13-23 (map) and 278-301 (_resolve_and_transition)

## Dependencies:
- Independent (can be done anytime), but should be tested with Phase 6

## What comes next:
- Phase 8 (Backlog + API updates)
