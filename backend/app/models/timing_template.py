from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    pass


class TimingTemplate(TimestampMixin, Base):
    __tablename__ = "timing_templates"

    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    spread_factor: Mapped[float] = mapped_column(Float, default=0.33, nullable=False)

    entries: Mapped[list["TimingTemplateEntry"]] = relationship(
        back_populates="template", cascade="all, delete-orphan"
    )


class TimingTemplateEntry(TimestampMixin, Base):
    __tablename__ = "timing_template_entries"
    __table_args__ = (
        UniqueConstraint(
            "template_id", "issue_type", "story_points",
            name="uq_template_type_points",
        ),
    )

    template_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("timing_templates.id"), nullable=False
    )
    issue_type: Mapped[str] = mapped_column(String, nullable=False)
    story_points: Mapped[int] = mapped_column(Integer, nullable=False)
    ct_min: Mapped[float] = mapped_column(Float, nullable=False)
    ct_q1: Mapped[float] = mapped_column(Float, nullable=False)
    ct_median: Mapped[float] = mapped_column(Float, nullable=False)
    ct_q3: Mapped[float] = mapped_column(Float, nullable=False)
    ct_max: Mapped[float] = mapped_column(Float, nullable=False)

    template: Mapped["TimingTemplate"] = relationship(back_populates="entries")
