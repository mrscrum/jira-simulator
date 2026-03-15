from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.team import Team
    from app.models.workflow_step import WorkflowStep


class Workflow(TimestampMixin, Base):
    __tablename__ = "workflows"

    team_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("teams.id"), unique=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)

    team: Mapped["Team"] = relationship(back_populates="workflow")
    steps: Mapped[list["WorkflowStep"]] = relationship(
        back_populates="workflow", order_by="WorkflowStep.order"
    )
