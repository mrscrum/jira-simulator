# Phase 5: Workflow Engine (Core)

## Context

This is the heart of the rewrite. Replaces `issue_state_machine.py` with a distribution-based workflow engine where items flow through configurable Jira-mirrored statuses, consuming capacity based on sampled times.

Full requirements: `docs/simulation-engine-rewrite-requirements.md`

---

## Create: `backend/app/engine/types.py` (NEW)

Move `JiraWriteAction` from `issue_state_machine.py`:

```python
@dataclass(frozen=True)
class JiraWriteAction:
    operation_type: str
    payload: dict
    issue_id: int | None = None
```

Also define:

```python
@dataclass
class ItemTickResult:
    jira_actions: list[JiraWriteAction]
    member_states: dict[int, MemberTickState]  # updated states after this item
    completed: bool  # item reached final status
```

---

## Create: `backend/app/engine/workflow_engine.py` (NEW)

### Functions:

```python
def enter_status(
    issue: Issue,
    workflow_step: WorkflowStep,
    touch_time_config: TouchTimeConfig | None,
    rng: random.Random,
) -> list[JiraWriteAction]:
    """Item enters a new status.

    1. Set issue.current_workflow_step_id = workflow_step.id
    2. Set issue.status = workflow_step.jira_status
    3. Sample full_time from log-normal (p25, p50, p99) → issue.sampled_full_time
    4. Sample work_time from uniform (min, max) → issue.sampled_work_time
    5. Reset elapsed_full_time = 0, elapsed_work_time = 0, work_started = False
    6. Clear current_worker_id
    7. Emit TRANSITION_ISSUE action with target_status = workflow_step.jira_status

    If touch_time_config is None (no config for this type/size/step), use defaults (0,0).
    """

def process_item_tick(
    issue: Issue,
    workflow_steps: list[WorkflowStep],  # ordered steps for this item's workflow
    touch_time_configs: dict,  # keyed by (step_id, issue_type, story_points)
    move_left_configs: list[MoveLeftConfig],  # for this item type
    member_states: dict[int, MemberTickState],
    tick_hours: float,
    rng: random.Random,
) -> ItemTickResult:
    """Process one tick for one item.

    Step 1: If work_time > 0 and not work_started:
        - Check sticky assignment first (member already assigned to this issue)
        - If no sticky worker, find_available_member for step's roles
        - If found: assign, mark work_started = True, mark member busy
        - If not found: no work progress this tick

    Step 2: If work in progress (work_started and worker assigned):
        - Subtract tick_hours from remaining work time
          (issue.elapsed_work_time += tick_hours)
        - Mark member busy this tick

    Step 3: Always advance full time:
        - issue.elapsed_full_time += tick_hours

    Step 4: Check transition readiness:
        - work_done = (sampled_work_time == 0) or (elapsed_work_time >= sampled_work_time)
        - full_time_done = (elapsed_full_time >= sampled_full_time)
        - ready = work_done AND full_time_done

    Step 5: If ready, roll direction:
        - Use roll_direction() with move_left_configs
        - If 'forward': find next step in workflow_steps by order
        - If 'left': get target step from move_left config

    Step 6: Execute transition:
        - Call enter_status() for the target step
        - If forward and target is final step: mark issue as Done
        - If left: re-enter target status (times re-sampled)

    Returns ItemTickResult with actions and updated member_states.
    """

def check_transition_ready(issue: Issue) -> bool:
    """True when both conditions met:
    - work done: sampled_work_time == 0 OR elapsed_work_time >= sampled_work_time
    - full time done: elapsed_full_time >= sampled_full_time
    """

def roll_direction(
    issue_type: str,
    current_step: WorkflowStep,
    move_left_configs: list[MoveLeftConfig],
    rng: random.Random,
) -> tuple[str, int | None]:
    """Roll against move-left probability grid.

    1. Find MoveLeftConfig matching (from_step_id=current_step.id, issue_type or NULL)
    2. Roll against base_probability
    3. If move-left triggered: pick target from weighted targets
    4. Return ('forward', None) or ('left', target_step_id)
    """

def get_touch_time_config(
    configs: dict,
    step_id: int,
    issue_type: str,
    story_points: int,
) -> TouchTimeConfig | None:
    """Lookup touch time config for (step, type, points). Returns None if not configured."""
```

### Key behaviors:
- Status with work_time=0: skip worker assignment, only track full_time, transition when elapsed
- Move-left: both timers reset, re-sample from distributions, clear worker
- Forward to final status: set issue.status = final step's jira_status, set completed_at
- TRANSITION_ISSUE payload: `{"issue_key": issue.jira_issue_key, "target_status": step.jira_status}`
- UPDATE_ISSUE payload for assignee changes: `{"issue_key": ..., "fields": {"sim_assignee": member.name}}`

---

## Test file: `backend/tests/unit/test_workflow_engine.py`

Test cases:
- `enter_status` samples times and emits TRANSITION_ISSUE
- `enter_status` with no touch_time_config uses defaults
- `process_item_tick` assigns worker when capacity available
- `process_item_tick` waits when no capacity (full_time still advances)
- `process_item_tick` completes work and transitions forward
- `process_item_tick` handles move-left with time reset
- `process_item_tick` with work_time=0 transitions on full_time only
- `check_transition_ready` both conditions required
- `roll_direction` respects probability grid
- `roll_direction` with no config always returns forward
- Forward to final status marks Done
- Sticky assignment: same worker continues across ticks

---

## Existing files to reference:
- `backend/app/engine/issue_state_machine.py` — old state machine (being replaced), contains JiraWriteAction
- `backend/app/engine/distributions.py` — from Phase 1b (sample_full_time, sample_work_time)
- `backend/app/engine/capacity.py` — from Phase 3 (find_available_member, mark_busy)
- `backend/app/models/workflow_step.py` — WorkflowStep.roles property
- `backend/app/models/touch_time_config.py` — TouchTimeConfig with p25/p50/p99
- `backend/app/models/move_left_config.py` — MoveLeftConfig with targets and weights

## Dependencies:
- Phase 1b (distributions.py)
- Phase 2 (model updates — issue tracking fields, workflow_step.roles)
- Phase 3 (capacity module)

## What comes next:
- Phase 6 (Simulation Engine) calls process_item_tick for each item each tick
