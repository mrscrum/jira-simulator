from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.issue import Issue
    from app.models.team import Team


class Sprint(TimestampMixin, Base):
    __tablename__ = "sprints"

    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), nullable=False)
    jira_sprint_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    goal: Mapped[str | None] = mapped_column(String, nullable=True)
    start_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String, default="future", nullable=False)
    planned_velocity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_velocity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scope_change_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    phase: Mapped[str] = mapped_column(
        String, default="BACKLOG_PREP", nullable=False
    )
    sprint_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    committed_points: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completed_points: Mapped[int | None] = mapped_column(Integer, nullable=True)
    carried_over_points: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    velocity: Mapped[float | None] = mapped_column(Float, nullable=True)
    goal_at_risk: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    capacity_target: Mapped[int | None] = mapped_column(Integer, nullable=True)

    team: Mapped["Team"] = relationship(back_populates="sprints")
    issues: Mapped[list["Issue"]] = relationship(back_populates="sprint")
