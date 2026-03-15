from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.team import Team


class DysfunctionConfig(TimestampMixin, Base):
    __tablename__ = "dysfunction_configs"

    team_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("teams.id"), unique=True, nullable=False
    )
    low_quality_probability: Mapped[float] = mapped_column(Float, default=0.15, nullable=False)
    scope_creep_probability: Mapped[float] = mapped_column(Float, default=0.10, nullable=False)
    blocking_dependency_probability: Mapped[float] = mapped_column(
        Float, default=0.12, nullable=False
    )
    dark_teammate_probability: Mapped[float] = mapped_column(Float, default=0.05, nullable=False)
    re_estimation_probability: Mapped[float] = mapped_column(Float, default=0.10, nullable=False)
    bug_injection_probability: Mapped[float] = mapped_column(Float, default=0.20, nullable=False)
    cross_team_block_probability: Mapped[float] = mapped_column(
        Float, default=0.08, nullable=False
    )
    cross_team_handoff_lag_probability: Mapped[float] = mapped_column(
        Float, default=0.10, nullable=False
    )
    cross_team_bug_probability: Mapped[float] = mapped_column(Float, default=0.05, nullable=False)

    # --- Low Quality Story detail fields ---
    low_quality_ba_po_touch_min: Mapped[float] = mapped_column(
        Float, default=1.5, nullable=False
    )
    low_quality_ba_po_touch_max: Mapped[float] = mapped_column(
        Float, default=2.5, nullable=False
    )
    low_quality_dev_touch_min: Mapped[float] = mapped_column(
        Float, default=1.2, nullable=False
    )
    low_quality_dev_touch_max: Mapped[float] = mapped_column(
        Float, default=1.8, nullable=False
    )
    low_quality_qa_touch_min: Mapped[float] = mapped_column(
        Float, default=1.5, nullable=False
    )
    low_quality_qa_touch_max: Mapped[float] = mapped_column(
        Float, default=3.0, nullable=False
    )
    low_quality_ba_cycle_back_pct: Mapped[float] = mapped_column(
        Float, default=0.40, nullable=False
    )
    low_quality_qa_cycle_back_pct: Mapped[float] = mapped_column(
        Float, default=0.50, nullable=False
    )
    low_quality_bug_injection_boost_pct: Mapped[float] = mapped_column(
        Float, default=0.30, nullable=False
    )
    low_quality_re_estimation_boost_pct: Mapped[float] = mapped_column(
        Float, default=0.40, nullable=False
    )

    # --- Mid-Sprint Scope Add detail fields ---
    scope_add_capacity_tax_min_pct: Mapped[float] = mapped_column(
        Float, default=0.85, nullable=False
    )
    scope_add_capacity_tax_max_pct: Mapped[float] = mapped_column(
        Float, default=0.95, nullable=False
    )
    scope_add_touch_multiplier_min: Mapped[float] = mapped_column(
        Float, default=1.1, nullable=False
    )
    scope_add_touch_multiplier_max: Mapped[float] = mapped_column(
        Float, default=1.3, nullable=False
    )
    scope_add_tax_duration_days_min: Mapped[float] = mapped_column(
        Float, default=1.0, nullable=False
    )
    scope_add_tax_duration_days_max: Mapped[float] = mapped_column(
        Float, default=2.0, nullable=False
    )

    # --- Blocking Dependency detail fields ---
    blocking_dep_escalation_wait_hours: Mapped[float] = mapped_column(
        Float, default=24.0, nullable=False
    )
    blocking_dep_blocker_focus_multiplier: Mapped[float] = mapped_column(
        Float, default=0.8, nullable=False
    )

    # --- Teammate Goes Dark detail fields ---
    dark_teammate_duration_days_min: Mapped[float] = mapped_column(
        Float, default=2.0, nullable=False
    )
    dark_teammate_duration_days_max: Mapped[float] = mapped_column(
        Float, default=5.0, nullable=False
    )
    dark_teammate_reassignment_ramp_pct: Mapped[float] = mapped_column(
        Float, default=0.70, nullable=False
    )

    # --- Re-estimation detail fields ---
    re_estimation_sp_multiplier_min: Mapped[float] = mapped_column(
        Float, default=1.5, nullable=False
    )
    re_estimation_sp_multiplier_max: Mapped[float] = mapped_column(
        Float, default=2.5, nullable=False
    )
    re_estimation_descope_probability_pct: Mapped[float] = mapped_column(
        Float, default=0.70, nullable=False
    )

    # --- Bug Injection detail fields ---
    bug_injection_sp_weight_1: Mapped[float] = mapped_column(
        Float, default=0.5, nullable=False
    )
    bug_injection_sp_weight_2: Mapped[float] = mapped_column(
        Float, default=0.3, nullable=False
    )
    bug_injection_sp_weight_3: Mapped[float] = mapped_column(
        Float, default=0.2, nullable=False
    )
    bug_injection_interruption_tax_multiplier: Mapped[float] = mapped_column(
        Float, default=1.1, nullable=False
    )

    team: Mapped["Team"] = relationship(back_populates="dysfunction_config")
