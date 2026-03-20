from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    pass


class MoveLeftConfig(TimestampMixin, Base):
    __tablename__ = "move_left_config"

    team_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("teams.id"), nullable=False
    )
    from_step_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("workflow_steps.id"), nullable=False
    )
    base_probability: Mapped[float] = mapped_column(Float, nullable=False)
    issue_type: Mapped[str | None] = mapped_column(String, nullable=True)

    targets: Mapped[list["MoveLeftTarget"]] = relationship(
        back_populates="config",
        cascade="all, delete-orphan",
    )
    same_step_statuses: Mapped[list["MoveLeftSameStepStatus"]] = relationship(
        back_populates="config",
        cascade="all, delete-orphan",
    )


class MoveLeftTarget(TimestampMixin, Base):
    __tablename__ = "move_left_targets"

    move_left_config_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("move_left_config.id"), nullable=False
    )
    to_step_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("workflow_steps.id"), nullable=False
    )
    weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)

    config: Mapped["MoveLeftConfig"] = relationship(back_populates="targets")


class MoveLeftSameStepStatus(Base):
    __tablename__ = "move_left_same_step_statuses"

    move_left_config_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("move_left_config.id"),
        primary_key=True,
    )
    status_name: Mapped[str] = mapped_column(
        String,
        primary_key=True,
    )

    config: Mapped["MoveLeftConfig"] = relationship(
        back_populates="same_step_statuses"
    )
