import math

from app.models.touch_time_config import TouchTimeConfig
from app.models.workflow import Workflow
from app.models.workflow_step import WorkflowStep
from app.models.timing_template import TimingTemplate


def compute_percentiles(ct_min, ct_q1, ct_median, ct_q3, ct_max):
    """Compute p25, p50, p99 from cycle-time box-plot values.

    p25 = ct_q1, p50 = ct_median, p99 derived from log-normal fit.
    Falls back to ct_max for p99 when IQR is degenerate.
    """
    p25 = ct_q1
    p50 = ct_median

    if ct_q1 <= 0 or ct_q3 <= 0 or ct_q1 >= ct_q3:
        p99 = ct_max
    else:
        sigma = math.log(ct_q3 / ct_q1) / (2 * 0.6745)
        p99 = ct_median * math.exp(2.3263 * sigma)

    return p25, p50, p99


def compute_status_weights(n_statuses: int) -> list[float]:
    """Linear-decay weights for distributing time across statuses.

    First status gets weight n, second n-1, etc., normalized to sum to 1.
    """
    if n_statuses <= 0:
        return []
    raw = [n_statuses - i for i in range(n_statuses)]
    total = sum(raw)
    return [w / total for w in raw]


def distribute_cycle_time(entry, in_progress_steps, spread_factor) -> list[dict]:
    """Distribute a template entry's cycle time across in-progress steps.

    Returns a list of config dicts keyed for TouchTimeConfig creation.
    """
    n = len(in_progress_steps)
    if n == 0:
        return []

    weights = compute_status_weights(n)
    _p25, _p50, computed_p99 = compute_percentiles(
        entry.ct_min, entry.ct_q1, entry.ct_median, entry.ct_q3, entry.ct_max
    )

    results = []
    for step, w in zip(in_progress_steps, weights):
        p25 = entry.ct_q1 * w
        p50 = entry.ct_median * w
        p99 = computed_p99 * w
        min_hours = p50 * (1 - spread_factor)
        max_hours = p50 * (1 + spread_factor)

        results.append({
            "workflow_step_id": step.id,
            "issue_type": entry.issue_type,
            "story_points": entry.story_points,
            "min_hours": round(min_hours, 4),
            "max_hours": round(max_hours, 4),
            "full_time_p25": round(p25, 4),
            "full_time_p50": round(p50, 4),
            "full_time_p99": round(p99, 4),
        })

    return results


def generate_preview(template, workflow_steps) -> list[dict]:
    """Build a full set of config items for a template + workflow.

    Groups steps by status_category and applies appropriate logic
    for todo / in_progress / done categories.
    """
    todo_steps = [s for s in workflow_steps if s.status_category == "todo"]
    done_steps = [s for s in workflow_steps if s.status_category == "done"]
    in_progress_steps = [s for s in workflow_steps if s.status_category == "in_progress"]

    configs: list[dict] = []

    for entry in template.entries:
        # todo steps: small wait-time placeholders
        for step in todo_steps:
            configs.append({
                "workflow_step_id": step.id,
                "jira_status": step.jira_status,
                "status_category": step.status_category,
                "issue_type": entry.issue_type,
                "story_points": entry.story_points,
                "min_hours": 0,
                "max_hours": 0,
                "full_time_p25": 1,
                "full_time_p50": 2,
                "full_time_p99": 8,
            })

        # done steps: all zeros
        for step in done_steps:
            configs.append({
                "workflow_step_id": step.id,
                "jira_status": step.jira_status,
                "status_category": step.status_category,
                "issue_type": entry.issue_type,
                "story_points": entry.story_points,
                "min_hours": 0,
                "max_hours": 0,
                "full_time_p25": 0,
                "full_time_p50": 0,
                "full_time_p99": 0,
            })

        # in_progress steps: distribute cycle time
        distributed = distribute_cycle_time(
            entry, in_progress_steps, template.spread_factor
        )
        for item in distributed:
            step = next(s for s in in_progress_steps if s.id == item["workflow_step_id"])
            item["jira_status"] = step.jira_status
            item["status_category"] = step.status_category
            configs.append(item)

    return configs


def apply_template_to_team(template, team_id, session) -> None:
    """Apply a timing template to a team by replacing its touch-time configs."""
    workflow = (
        session.query(Workflow)
        .filter(Workflow.team_id == team_id)
        .first()
    )
    if workflow is None:
        return

    steps = (
        session.query(WorkflowStep)
        .filter(WorkflowStep.workflow_id == workflow.id)
        .order_by(WorkflowStep.order)
        .all()
    )
    if not steps:
        return

    preview = generate_preview(template, steps)

    # Delete existing configs for all steps in this workflow
    step_ids = [s.id for s in steps]
    session.query(TouchTimeConfig).filter(
        TouchTimeConfig.workflow_step_id.in_(step_ids)
    ).delete(synchronize_session="fetch")

    # Create new configs from preview
    for item in preview:
        config = TouchTimeConfig(
            workflow_step_id=item["workflow_step_id"],
            issue_type=item["issue_type"],
            story_points=item["story_points"],
            min_hours=item["min_hours"],
            max_hours=item["max_hours"],
            full_time_p25=item.get("full_time_p25"),
            full_time_p50=item.get("full_time_p50"),
            full_time_p99=item.get("full_time_p99"),
        )
        session.add(config)

    session.commit()
