"""Pydantic schemas for scheduled events, audit, and precomputation."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

# -- Scheduled Event schemas --

class ScheduledEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    team_id: int
    sprint_id: int
    issue_id: int | None
    event_type: str
    scheduled_at: datetime
    sim_tick: int
    payload: dict
    status: str
    dispatched_at: datetime | None
    cancelled_at: datetime | None
    cancel_reason: str | None
    modified_at: datetime | None
    original_payload: dict | None
    original_scheduled_at: datetime | None
    batch_id: str
    sequence_order: int
    created_at: datetime
    updated_at: datetime


class ScheduledEventUpdate(BaseModel):
    scheduled_at: datetime | None = None
    payload: dict | None = None


class ScheduledEventCancel(BaseModel):
    reason: str | None = None


class ScheduledEventListResponse(BaseModel):
    events: list[ScheduledEventRead]
    total: int
    page: int
    page_size: int


# -- Event Audit schemas --

class EventAuditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    scheduled_event_id: int
    jira_queue_entry_id: str | None
    expected_at: datetime
    dispatched_at: datetime | None
    verified_at: datetime | None
    verification_status: str
    failure_reason: str | None
    alert_sent: bool
    created_at: datetime
    updated_at: datetime


class AuditSummary(BaseModel):
    total: int
    pending: int
    dispatched: int
    verified: int
    failed: int
    timeout: int
    failures: list[EventAuditRead]


# -- Precomputation schemas --

class PrecomputeRequest(BaseModel):
    rng_seed: int | None = None


class PrecomputeResponse(BaseModel):
    batch_id: str
    total_events: int
    total_ticks: int
    sprint_id: int


# -- Sprint cadence schemas --

class SprintCadenceUpdate(BaseModel):
    sprint_cadence_rule: str | None = None
    sprint_cadence_time: str | None = None
    sprint_auto_schedule: bool | None = None
