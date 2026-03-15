from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.touch_time_config import TouchTimeConfig
    from app.models.workflow import Workflow


class WorkflowStep(TimestampMixin, Base):
    __tablename__ = "workflow_steps"
    __table_args__ = (
        UniqueConstraint("workflow_id", "order", name="uq_workflow_order"),
        UniqueConstraint("workflow_id", "jira_status", name="uq_workflow_jira_status"),
    )

    workflow_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("workflows.id"), nullable=False
    )
    jira_status: Mapped[str] = mapped_column(String, nullable=False)
    role_required: Mapped[str] = mapped_column(String, nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    max_wait_hours: Mapped[float] = mapped_column(Float, default=24.0, nullable=False)
    wip_contribution: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)

    workflow: Mapped["Workflow"] = relationship(back_populates="steps")
    touch_time_configs: Mapped[list["TouchTimeConfig"]] = relationship(
        back_populates="workflow_step"
    )
