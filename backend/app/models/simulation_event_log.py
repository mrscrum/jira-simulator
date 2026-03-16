from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class SimulationEventLog(TimestampMixin, Base):
    __tablename__ = "simulation_event_log"

    team_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("teams.id"), nullable=False
    )
    sprint_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sprints.id"), nullable=False
    )
    issue_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("issues.id"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    sim_day: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[str] = mapped_column(String, nullable=False)
    jira_written: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
