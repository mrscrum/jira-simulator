# Phase 6: New Simulation Engine

## Context

Rewrite the main tick orchestrator to use the new workflow engine, capacity model, and sprint lifecycle. The engine drops from ~530 lines in `_tick_team` to ~150 lines by delegating to the modules from Phases 3-5.

Full requirements: `docs/simulation-engine-rewrite-requirements.md`

---

## Rewrite: `backend/app/engine/simulation.py`

### Keep (same interface):
- `SimulationEngine` class
- `__init__(session_factory, write_queue, sim_clock)`
- `start()`, `pause()`, `resume()`, `stop()`
- `should_tick() -> bool`
- `enqueue_actions(team_id, actions, session)`
- `record_tick_success(at)`
- `async tick() -> list[TeamTickResult]`
- `_paused_teams`, `_state`, `_clock`, `_tick_count`

### Rewrite `_tick_team(session, team)`:

```python
async def _tick_team(self, session, team) -> TeamTickResult:
    tick_hours = team.tick_duration_hours  # default 1.0
    sim_now = self._clock.now()
    jira_actions = []

    # 1. Calendar check (reuse calendar.is_working_time)
    if self._clock.speed <= 1.0:
        if not is_working_time(team.timezone, team.working_hours_start,
                                team.working_hours_end, team.holidays,
                                DEFAULT_WORKING_DAYS, sim_now):
            return TeamTickResult(...)

    # 2. Build member tick states
    members = session.query(Member).filter_by(team_id=team.id, is_active=True).all()
    member_states = build_member_states(members)

    # 3. Get current sprint (or handle no sprint)
    sprint = get_active_or_planning_sprint(session, team.id)

    # 4. Phase dispatch
    if sprint is None or sprint.phase == "COMPLETED":
        # Create first sprint or transition from completed
        if sprint and sprint.phase == "COMPLETED":
            # Handle carryover from just-completed sprint
            incomplete = [i for i in sprint.issues if i.status != final_status]
            carryover_issues = handle_carryover(incomplete)
            jira_actions += carryover_comment_actions(carryover_issues)

        new_sprint = create_next_sprint(team, sprint, next_sprint_number)
        session.add(new_sprint)
        jira_actions.append(JiraWriteAction("CREATE_SPRINT", {...}))
        sprint = new_sprint
        sprint.phase = "PLANNING"

    if sprint.phase == "PLANNING":
        # Get backlog (carryover at top + new items by priority)
        backlog = get_prioritized_backlog(session, team.id)
        selected, capacity_target = plan_sprint(
            backlog, team.sprint_capacity_min, team.sprint_capacity_max,
            team.priority_randomization, self._rng
        )
        sprint.capacity_target = capacity_target
        sprint.committed_points = sum(i.story_points or 0 for i in selected)

        for issue in selected:
            issue.sprint_id = sprint.id
            # Enter first workflow step
            first_step = get_first_step(session, team, issue.issue_type)
            actions = enter_status(issue, first_step, get_ttc(...), self._rng)
            jira_actions += actions
            jira_actions.append(JiraWriteAction("ADD_TO_SPRINT", {...}))

        sprint.phase = "ACTIVE"
        jira_actions.append(JiraWriteAction("UPDATE_SPRINT", {...}))  # start sprint

    elif sprint.phase == "ACTIVE":
        # Process each item in the sprint
        sprint_issues = session.query(Issue).filter_by(sprint_id=sprint.id).all()

        for issue in sprint_issues:
            if issue.completed_at is not None:
                continue  # already done

            result = process_item_tick(
                issue, workflow_steps, touch_time_configs,
                move_left_configs, member_states, tick_hours, self._rng
            )
            jira_actions += result.jira_actions
            member_states = result.member_states

            if result.completed:
                issue.completed_at = sim_now
                sprint.completed_points = (sprint.completed_points or 0) + (issue.story_points or 0)

        # Check sprint end
        if check_sprint_end(sprint, sim_now, team.timezone, ...):
            sprint.phase = "COMPLETED"
            jira_actions.append(JiraWriteAction("COMPLETE_SPRINT", {...}))

    # 5. Backlog maintenance (reuse backlog.py)
    deficit = check_backlog_depth(current_depth, team.backlog_depth_target)
    if deficit > 0:
        new_issues = await generate_issues(deficit, team.name, ...)
        for issue_data in new_issues:
            issue = Issue(**issue_data, team_id=team.id)
            session.add(issue)
            jira_actions.append(JiraWriteAction("CREATE_ISSUE", {...}))

    # 6. Enqueue
    self.enqueue_actions(team.id, jira_actions, session)

    return TeamTickResult(...)
```

### Remove entirely:
- All `TickContext` building
- All event registry / evaluation code
- References to `IssueState` enum
- References to `DysfunctionConfig`
- All event imports from `engine/events/`

### Helper functions to add (in same file or a helpers module):

```python
def get_active_or_planning_sprint(session, team_id) -> Sprint | None
def get_prioritized_backlog(session, team_id) -> list[Issue]
def get_first_step(session, team, issue_type) -> WorkflowStep
def get_workflow_steps_for_issue(session, issue) -> list[WorkflowStep]
def get_touch_time_configs_for_team(session, team_id) -> dict
def get_move_left_configs_for_team(session, team_id) -> list[MoveLeftConfig]
def carryover_comment_actions(issues) -> list[JiraWriteAction]
```

---

## Existing files to reference:
- `backend/app/engine/simulation.py` — current implementation (class structure to keep)
- `backend/app/engine/workflow_engine.py` — from Phase 5
- `backend/app/engine/sprint_lifecycle.py` — from Phase 4
- `backend/app/engine/capacity.py` — from Phase 3
- `backend/app/engine/calendar.py` — PRESERVE, reuse is_working_time
- `backend/app/engine/sim_clock.py` — PRESERVE, reuse SimClock
- `backend/app/engine/backlog.py` — PRESERVE, reuse generate_issues, check_backlog_depth
- `backend/app/integrations/jira_write_queue.py` — enqueue interface

## Dependencies:
- Phase 3 (capacity)
- Phase 4 (sprint lifecycle)
- Phase 5 (workflow engine)

## What comes next:
- Phase 7 (Jira write queue JIRA_STATUS_MAP removal)
- Phase 8 (Backlog + API updates)
