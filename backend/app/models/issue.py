from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.member import Member
    from app.models.sprint import Sprint
    from app.models.team import Team
    from app.models.workflow_step import WorkflowStep


class Issue(TimestampMixin, Base):
    __tablename__ = "issues"

    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), nullable=False)
    jira_issue_key: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    jira_issue_id: Mapped[str | None] = mapped_column(String, nullable=True)
    issue_type: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    story_points: Mapped[int | None] = mapped_column(Integer, nullable=True)
    priority: Mapped[str] = mapped_column(String, default="Medium", nullable=False)
    current_workflow_step_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("workflow_steps.id"), nullable=True
    )
    current_worker_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("members.id"), nullable=True
    )
    jira_assignee_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("members.id"), nullable=True
    )
    jira_reporter_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("members.id"), nullable=True
    )
    touch_time_remaining_hours: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    wait_time_accumulated_hours: Mapped[float] = mapped_column(
        Float, default=0.0, nullable=False
    )
    total_cycle_time_hours: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    sprint_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("sprints.id"), nullable=True
    )
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    blocked_by_issue_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("issues.id"), nullable=True
    )
    dysfunction_flags: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="backlog", nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    team: Mapped["Team"] = relationship(back_populates="issues")
    current_workflow_step: Mapped["WorkflowStep | None"] = relationship(
        foreign_keys=[current_workflow_step_id]
    )
    current_worker: Mapped["Member | None"] = relationship(
        foreign_keys=[current_worker_id]
    )
    jira_assignee: Mapped["Member | None"] = relationship(
        foreign_keys=[jira_assignee_id]
    )
    jira_reporter: Mapped["Member | None"] = relationship(
        foreign_keys=[jira_reporter_id]
    )
    sprint: Mapped["Sprint | None"] = relationship(back_populates="issues")
    blocked_by: Mapped["Issue | None"] = relationship(
        remote_side="Issue.id", foreign_keys=[blocked_by_issue_id]
    )
