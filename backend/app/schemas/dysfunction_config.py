from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DysfunctionConfigBase(BaseModel):
    # Probability fields
    low_quality_probability: float = 0.15
    scope_creep_probability: float = 0.10
    blocking_dependency_probability: float = 0.12
    dark_teammate_probability: float = 0.05
    re_estimation_probability: float = 0.10
    bug_injection_probability: float = 0.20
    cross_team_block_probability: float = 0.08
    cross_team_handoff_lag_probability: float = 0.10
    cross_team_bug_probability: float = 0.05

    # Low Quality Story detail fields
    low_quality_ba_po_touch_min: float = 1.5
    low_quality_ba_po_touch_max: float = 2.5
    low_quality_dev_touch_min: float = 1.2
    low_quality_dev_touch_max: float = 1.8
    low_quality_qa_touch_min: float = 1.5
    low_quality_qa_touch_max: float = 3.0
    low_quality_ba_cycle_back_pct: float = 0.40
    low_quality_qa_cycle_back_pct: float = 0.50
    low_quality_bug_injection_boost_pct: float = 0.30
    low_quality_re_estimation_boost_pct: float = 0.40

    # Mid-Sprint Scope Add detail fields
    scope_add_capacity_tax_min_pct: float = 0.85
    scope_add_capacity_tax_max_pct: float = 0.95
    scope_add_touch_multiplier_min: float = 1.1
    scope_add_touch_multiplier_max: float = 1.3
    scope_add_tax_duration_days_min: float = 1.0
    scope_add_tax_duration_days_max: float = 2.0

    # Blocking Dependency detail fields
    blocking_dep_escalation_wait_hours: float = 24.0
    blocking_dep_blocker_focus_multiplier: float = 0.8

    # Teammate Goes Dark detail fields
    dark_teammate_duration_days_min: float = 2.0
    dark_teammate_duration_days_max: float = 5.0
    dark_teammate_reassignment_ramp_pct: float = 0.70

    # Re-estimation detail fields
    re_estimation_sp_multiplier_min: float = 1.5
    re_estimation_sp_multiplier_max: float = 2.5
    re_estimation_descope_probability_pct: float = 0.70

    # Bug Injection detail fields
    bug_injection_sp_weight_1: float = 0.5
    bug_injection_sp_weight_2: float = 0.3
    bug_injection_sp_weight_3: float = 0.2
    bug_injection_interruption_tax_multiplier: float = 1.1


class DysfunctionConfigCreate(DysfunctionConfigBase):
    team_id: int


class DysfunctionConfigRead(DysfunctionConfigBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    team_id: int
    created_at: datetime
    updated_at: datetime


class DysfunctionConfigUpdate(BaseModel):
    low_quality_probability: float | None = None
    scope_creep_probability: float | None = None
    blocking_dependency_probability: float | None = None
    dark_teammate_probability: float | None = None
    re_estimation_probability: float | None = None
    bug_injection_probability: float | None = None
    cross_team_block_probability: float | None = None
    cross_team_handoff_lag_probability: float | None = None
    cross_team_bug_probability: float | None = None

    low_quality_ba_po_touch_min: float | None = None
    low_quality_ba_po_touch_max: float | None = None
    low_quality_dev_touch_min: float | None = None
    low_quality_dev_touch_max: float | None = None
    low_quality_qa_touch_min: float | None = None
    low_quality_qa_touch_max: float | None = None
    low_quality_ba_cycle_back_pct: float | None = None
    low_quality_qa_cycle_back_pct: float | None = None
    low_quality_bug_injection_boost_pct: float | None = None
    low_quality_re_estimation_boost_pct: float | None = None

    scope_add_capacity_tax_min_pct: float | None = None
    scope_add_capacity_tax_max_pct: float | None = None
    scope_add_touch_multiplier_min: float | None = None
    scope_add_touch_multiplier_max: float | None = None
    scope_add_tax_duration_days_min: float | None = None
    scope_add_tax_duration_days_max: float | None = None

    blocking_dep_escalation_wait_hours: float | None = None
    blocking_dep_blocker_focus_multiplier: float | None = None

    dark_teammate_duration_days_min: float | None = None
    dark_teammate_duration_days_max: float | None = None
    dark_teammate_reassignment_ramp_pct: float | None = None

    re_estimation_sp_multiplier_min: float | None = None
    re_estimation_sp_multiplier_max: float | None = None
    re_estimation_descope_probability_pct: float | None = None

    bug_injection_sp_weight_1: float | None = None
    bug_injection_sp_weight_2: float | None = None
    bug_injection_sp_weight_3: float | None = None
    bug_injection_interruption_tax_multiplier: float | None = None
