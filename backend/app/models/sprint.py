from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String
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

    team: Mapped["Team"] = relationship(back_populates="sprints")
    issues: Mapped[list["Issue"]] = relationship(back_populates="sprint")
