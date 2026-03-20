"""Workflow engine — per-item per-tick processing.

Replaces issue_state_machine.py with a distribution-based model.
Items flow through configurable Jira-mirrored statuses, consuming
team capacity based on sampled log-normal and uniform distributions.

All functions operate on plain dicts / dataclasses — no DB sessions.
"""

import random

from app.engine.capacity import (
    MemberTickState,
    find_available_member,
    mark_busy,
    release_assignment,
)
from app.engine.distributions import sample_full_time, sample_work_time
from app.engine.types import ItemTickResult, JiraWriteAction

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_touch_time_config(
    configs: dict[tuple[int, str, int], object],
    step_id: int,
    issue_type: str,
    story_points: int,
) -> object | None:
    """Lookup touch time config for (step, type, points).

    Falls back to (step, type, 0) for a size-agnostic default.
    Returns None if nothing configured.
    """
    cfg = configs.get((step_id, issue_type, story_points))
    if cfg is not None:
        return cfg
    return configs.get((step_id, issue_type, 0))


def _find_step_by_id(workflow_steps: list, step_id: int):
    """Find a workflow step by its id."""
    for step in workflow_steps:
        if step.id == step_id:
            return step
    return None


def _next_step(workflow_steps: list, current_order: int):
    """Find the workflow step with the next order after current_order."""
    candidates = [s for s in workflow_steps if s.order > current_order]
    if not candidates:
        return None
    return min(candidates, key=lambda s: s.order)


def _is_final_step(workflow_steps: list, step) -> bool:
    """Check if step is the last step in the workflow (highest order)."""
    max_order = max(s.order for s in workflow_steps)
    return step.order == max_order


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def enter_status(
    issue,
    workflow_step,
    touch_time_config,
    rng: random.Random,
) -> list[JiraWriteAction]:
    """Item enters a new status.

    1. Set issue tracking fields for the new status.
    2. Sample full_time (log-normal) and work_time (uniform).
    3. Reset elapsed counters and worker.
    4. Emit TRANSITION_ISSUE action.
    """
    issue.current_workflow_step_id = workflow_step.id
    issue.status = workflow_step.jira_status

    # Sample times from distributions (or defaults if no config)
    if touch_time_config is not None:
        p25 = touch_time_config.full_time_p25
        p50 = touch_time_config.full_time_p50
        p99 = touch_time_config.full_time_p99
        if p25 and p50 and p99:
            issue.sampled_full_time = sample_full_time(p25, p50, p99, rng)
        else:
            issue.sampled_full_time = 0.0
        issue.sampled_work_time = sample_work_time(
            touch_time_config.min_hours, touch_time_config.max_hours, rng,
        )
    else:
        issue.sampled_full_time = 0.0
        issue.sampled_work_time = 0.0

    issue.elapsed_full_time = 0.0
    issue.elapsed_work_time = 0.0
    issue.work_started = False
    issue.current_worker_id = None

    actions = [
        JiraWriteAction(
            operation_type="TRANSITION_ISSUE",
            payload={
                "issue_key": issue.jira_issue_key,
                "target_status": workflow_step.jira_status,
            },
            issue_id=issue.id,
        )
    ]
    return actions


def check_transition_ready(issue) -> bool:
    """True when both work and full_time conditions are met."""
    work_done = (
        issue.sampled_work_time == 0
        or issue.elapsed_work_time >= issue.sampled_work_time
    )
    full_time_done = issue.elapsed_full_time >= issue.sampled_full_time
    return work_done and full_time_done


def roll_direction(
    issue_type: str,
    current_step,
    move_left_configs: list,
    rng: random.Random,
) -> tuple[str, int | None]:
    """Roll against move-left probability grid.

    Finds matching MoveLeftConfig for current step + issue type.
    Prefers type-specific config; falls back to type-agnostic (issue_type=None).

    Returns:
        ('forward', None) or ('left', target_step_id)
    """
    # Find matching config: prefer type-specific, fall back to type-agnostic
    specific = None
    generic = None
    for cfg in move_left_configs:
        if cfg.from_step_id != current_step.id:
            continue
        if cfg.issue_type == issue_type:
            specific = cfg
        elif cfg.issue_type is None:
            generic = cfg

    config = specific or generic
    if config is None:
        return ("forward", None)

    # Roll against base probability
    if rng.random() >= config.base_probability:
        return ("forward", None)

    # Move-left triggered — pick target from weighted targets
    targets = config.targets
    if not targets:
        return ("forward", None)

    weights = [t.weight for t in targets]
    total = sum(weights)
    if total <= 0:
        return ("forward", None)

    roll = rng.random() * total
    cumulative = 0.0
    for target in targets:
        cumulative += target.weight
        if roll <= cumulative:
            return ("left", target.to_step_id)

    # Fallback (shouldn't happen with valid weights)
    return ("left", targets[-1].to_step_id)


def process_item_tick(
    issue,
    workflow_steps: list,
    touch_time_configs: dict[tuple[int, str, int], object],
    move_left_configs: list,
    member_states: dict[int, MemberTickState],
    tick_hours: float,
    rng: random.Random,
) -> ItemTickResult:
    """Process one tick for one item.

    Seven-step flow:
    1. If work_time > 0 and not started: try to assign worker
    2. If work in progress: advance work time, consume capacity
    3. Always advance full_time
    4. Check transition readiness
    5. If ready: roll direction (forward or left)
    6. Execute transition
    7. Return result
    """
    actions: list[JiraWriteAction] = []
    completed = False

    current_step = _find_step_by_id(workflow_steps, issue.current_workflow_step_id)
    if current_step is None:
        return ItemTickResult(
            jira_actions=actions,
            member_states=member_states,
            completed=False,
        )

    # --- Step 1: Try to assign worker if work needed and not started ---
    if issue.sampled_work_time > 0 and not issue.work_started:
        roles = current_step.roles
        worker = find_available_member(member_states, roles, issue_id=issue.id, rng=rng)
        if worker is not None:
            issue.work_started = True
            issue.current_worker_id = worker.member_id
            member_states = mark_busy(member_states, worker.member_id, issue.id)

    # --- Step 2: If work in progress, advance work time ---
    if issue.work_started and issue.current_worker_id is not None:
        issue.elapsed_work_time += tick_hours
        # Ensure member is marked busy this tick (may already be from step 1)
        if not member_states[issue.current_worker_id].busy_this_tick:
            member_states = mark_busy(member_states, issue.current_worker_id, issue.id)

    # --- Step 3: Always advance full time ---
    issue.elapsed_full_time += tick_hours

    # --- Step 4: Check transition readiness ---
    if not check_transition_ready(issue):
        return ItemTickResult(
            jira_actions=actions,
            member_states=member_states,
            completed=False,
        )

    # --- Step 5: Roll direction ---
    direction, target_step_id = roll_direction(
        issue.issue_type, current_step, move_left_configs, rng,
    )

    # --- Step 6: Execute transition ---
    # Release current worker's sticky assignment
    if issue.current_worker_id is not None:
        member_states = release_assignment(member_states, issue.current_worker_id)

    story_points = issue.story_points or 0

    if direction == "forward":
        next_ws = _next_step(workflow_steps, current_step.order)
        if next_ws is None or _is_final_step(workflow_steps, current_step):
            # Already at final status — mark done
            completed = True
            issue.completed_at = True  # Caller sets actual datetime
        else:
            ttc = get_touch_time_config(
                touch_time_configs, next_ws.id, issue.issue_type, story_points,
            )
            transition_actions = enter_status(issue, next_ws, ttc, rng)
            actions.extend(transition_actions)

            # If the new status is the final step, mark done
            if _is_final_step(workflow_steps, next_ws):
                completed = True
    else:
        # Move left
        target_ws = _find_step_by_id(workflow_steps, target_step_id)
        if target_ws is not None:
            ttc = get_touch_time_config(
                touch_time_configs, target_ws.id, issue.issue_type, story_points,
            )
            transition_actions = enter_status(issue, target_ws, ttc, rng)
            actions.extend(transition_actions)

    return ItemTickResult(
        jira_actions=actions,
        member_states=member_states,
        completed=completed,
    )
