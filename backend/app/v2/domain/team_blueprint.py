"""Frozen, fully materialized v2 Scrum blueprint contract."""

import json
import re
from collections.abc import Iterator, Mapping
from datetime import UTC, date, datetime, time
from types import MappingProxyType
from typing import Annotated, Any, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    field_serializer,
    model_validator,
)

from app.v2.domain.canonical_json import canonical_json

IssueType = Literal["STORY", "BUG", "TASK", "SPIKE", "ENABLER"]
StoryPoints = Literal[1, 2, 3, 5, 8, 13]
Weekday = Literal["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
StatusCategory = Literal["TODO", "IN_PROGRESS", "DONE"]
JsonScalar = None | bool | int | float | str
WEEKDAYS = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")


def _require_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
        raise ValueError("instant must be aware UTC")
    return value.astimezone(UTC)


UtcDateTime = Annotated[datetime, AfterValidator(_require_utc)]
PositiveFloat = Annotated[float, Field(gt=0, allow_inf_nan=False)]
NonNegativeFloat = Annotated[float, Field(ge=0, allow_inf_nan=False)]
Probability = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


class FrozenModel(BaseModel):
    """Base contract shared by every resolved snapshot object."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


def _freeze_json(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze_json(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_json(item) for item in value)
    return value


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


class FrozenJsonMap(RootModel[dict[str, JsonScalar]]):
    """Immutable JSON object with scalar values."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    @model_validator(mode="after")
    def freeze_root(self) -> "FrozenJsonMap":
        object.__setattr__(self, "root", _freeze_json(self.root))
        return self

    @field_serializer("root")
    def serialize_root(self, value: Mapping[str, JsonScalar]) -> dict[str, JsonScalar]:
        return _thaw_json(value)

    def __getitem__(self, key: str) -> JsonScalar:
        return self.root[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.root)

    def items(self):
        return self.root.items()


class PositiveWeightMap(RootModel[dict[str, PositiveFloat]]):
    """Immutable non-empty positive weight object."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    @model_validator(mode="after")
    def validate_and_freeze(self) -> "PositiveWeightMap":
        if not self.root:
            raise ValueError("weight map must not be empty")
        object.__setattr__(self, "root", MappingProxyType(dict(self.root)))
        return self

    @field_serializer("root")
    def serialize_root(self, value: Mapping[str, float]) -> dict[str, float]:
        return dict(value)

    def __getitem__(self, key: str) -> float:
        return self.root[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.root)

    def keys(self):
        return self.root.keys()


class TeamBlueprintTeam(FrozenModel):
    name: str
    purpose: str
    summary: str
    description: str
    methodology: Literal["SCRUM"]
    archetype: str
    timezone: str
    locale: str


class JiraBlueprint(FrozenModel):
    project_name: str
    project_key: str
    board_name: str
    project_type: Literal["COMPANY_MANAGED"]
    topology_strategy: Literal["OFFICIAL_PROJECT_SCOPED_V1"]


class CalendarBlueprint(FrozenModel):
    working_weekdays: tuple[Weekday, ...]
    workday_start: str
    workday_end: str
    holiday_calendar_profile: str
    holiday_calendar_version: str
    holiday_horizon_end: date
    holidays: tuple[date, ...]

    @model_validator(mode="after")
    def validate_calendar(self) -> "CalendarBlueprint":
        weekday_positions = tuple(WEEKDAYS.index(day) for day in self.working_weekdays)
        if not weekday_positions or weekday_positions != tuple(sorted(set(weekday_positions))):
            raise ValueError("working weekdays must be unique and ordered")
        if _local_time(self.workday_start) >= _local_time(self.workday_end):
            raise ValueError("workday interval must be ordered")
        if self.holidays != tuple(sorted(set(self.holidays))):
            raise ValueError("holidays must be unique and ordered")
        if any(holiday > self.holiday_horizon_end for holiday in self.holidays):
            raise ValueError("holiday exceeds configured horizon")
        return self


def _local_time(value: str) -> time:
    if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", value):
        raise ValueError("local work time must use HH:MM")
    return time.fromisoformat(value)


class AvailabilityInterval(FrozenModel):
    starts_at: UtcDateTime
    ends_at: UtcDateTime
    availability_fraction: Probability
    daily_capacity_hours_override: PositiveFloat
    reason: str

    @model_validator(mode="after")
    def validate_interval(self) -> "AvailabilityInterval":
        if self.starts_at >= self.ends_at:
            raise ValueError("availability interval must have positive duration")
        return self


class Responsibility(FrozenModel):
    activity: str
    proficiency: Annotated[float, Field(ge=0.25, le=2, allow_inf_nan=False)]


class MemberBlueprint(FrozenModel):
    name: str
    roles: tuple[str, ...]
    daily_capacity_hours: Annotated[float, Field(gt=0, le=24, allow_inf_nan=False)]
    max_concurrent_wip: Annotated[int, Field(ge=1, le=10)]
    responsibilities: tuple[Responsibility, ...]
    availability: tuple[AvailabilityInterval, ...]

    @model_validator(mode="after")
    def validate_member(self) -> "MemberBlueprint":
        if not self.roles or len(set(self.roles)) != len(self.roles):
            raise ValueError("member roles must be non-empty and unique")
        activities = tuple(item.activity for item in self.responsibilities)
        if not activities or len(set(activities)) != len(activities):
            raise ValueError("responsibilities must be non-empty and unique")
        for previous, current in zip(self.availability, self.availability[1:], strict=False):
            if previous.ends_at > current.starts_at:
                raise ValueError("availability intervals must be ordered and non-overlapping")
        return self


class WorkflowStatus(FrozenModel):
    key: str
    jira_name: str
    category: StatusCategory
    activities: tuple[str, ...]
    consumes_capacity: bool
    pauses_service_clock: bool


class WorkflowRouteStep(FrozenModel):
    status_key: str
    required_activity: str | None


class WorkflowRoute(FrozenModel):
    issue_type: IssueType
    steps: tuple[WorkflowRouteStep, ...]


class WorkflowBlueprint(FrozenModel):
    statuses: tuple[WorkflowStatus, ...]
    routes: tuple[WorkflowRoute, ...]


class TimingEntry(FrozenModel):
    status_key: str
    issue_type: IssueType
    story_points: StoryPoints
    min: NonNegativeFloat
    p25: NonNegativeFloat
    p50: NonNegativeFloat
    p99: NonNegativeFloat
    max: NonNegativeFloat
    touch_min: NonNegativeFloat
    touch_max: NonNegativeFloat

    @model_validator(mode="after")
    def validate_bounds(self) -> "TimingEntry":
        anchors = (self.min, self.p25, self.p50, self.p99, self.max)
        if anchors != tuple(sorted(anchors)):
            raise ValueError("timing anchors must be ordered")
        if self.touch_min > self.touch_max:
            raise ValueError("touch bounds must be ordered")
        return self


class TimingBlueprint(FrozenModel):
    profile_name: str
    profile_version: int
    algorithm_version: str
    entries: tuple[TimingEntry, ...]


class BacklogBlueprint(FrozenModel):
    target_depth: Annotated[int, Field(ge=1, le=1000)]
    issue_type_weights: PositiveWeightMap
    story_point_weights: PositiveWeightMap
    priority_weights: PositiveWeightMap
    manual_import_default_issue_type: IssueType
    manual_import_default_story_points: StoryPoints
    arrival_pattern: str
    replenishment_policy: str


class ProbabilityClamp(FrozenModel):
    min: Probability
    max: Probability

    @model_validator(mode="after")
    def validate_bounds(self) -> "ProbabilityClamp":
        if self.min > self.max:
            raise ValueError("probability clamp must be ordered")
        return self


class RiskRule(FrozenModel):
    key: str
    trigger: str
    base_probability: Probability
    coefficients: FrozenJsonMap
    clamp: ProbabilityClamp
    mechanical_parameters: FrozenJsonMap

    @model_validator(mode="after")
    def validate_materialization(self) -> "RiskRule":
        if not self.mechanical_parameters.root:
            raise ValueError("risk mechanical parameters must be materialized")
        return self


class RisksBlueprint(FrozenModel):
    profile_name: str
    profile_version: int
    algorithm_version: str
    rules: tuple[RiskRule, ...]


class ContentBlueprint(FrozenModel):
    generation_policy_version: str
    transcript_policy_version: str
    generation_enabled: bool
    daily_transcript: bool
    jira_comments: bool


class ScrumBlueprint(FrozenModel):
    cadence_days: Annotated[int, Field(gt=0)]
    first_boundary: UtcDateTime
    capacity_min_points: Annotated[int, Field(ge=0)]
    capacity_max_points: Annotated[int, Field(ge=0)]
    planning_policy_version: str
    ranking_policy_version: str
    carryover_policy_version: str

    @model_validator(mode="after")
    def validate_capacity(self) -> "ScrumBlueprint":
        if self.capacity_min_points > self.capacity_max_points:
            raise ValueError("Scrum capacity range must be ordered")
        return self


class ResolvedTeamBlueprint(FrozenModel):
    """A canonical, fully resolved Scrum team snapshot."""

    schema_version: Literal["2.0"]
    team: TeamBlueprintTeam
    jira: JiraBlueprint
    calendar: CalendarBlueprint
    members: tuple[MemberBlueprint, ...]
    workflow: WorkflowBlueprint
    timing: TimingBlueprint
    backlog: BacklogBlueprint
    risks: RisksBlueprint
    content: ContentBlueprint
    scrum: ScrumBlueprint
    seed: str

    @model_validator(mode="after")
    def validate_cross_fields(self) -> "ResolvedTeamBlueprint":
        _validate_unique_identity(self)
        _validate_routes(self)
        _validate_timing_grid(self)
        _validate_risks(self)
        return self

    @classmethod
    def from_canonical_json(cls, document: str) -> "ResolvedTeamBlueprint":
        """Parse only a byte-for-byte canonical resolved blueprint document."""
        try:
            raw_document = json.loads(document, parse_constant=_reject_non_finite)
        except (json.JSONDecodeError, ValueError) as error:
            raise ValueError("blueprint must be valid finite JSON") from error
        blueprint = cls.model_validate(raw_document)
        if blueprint.canonical_json() != document:
            raise ValueError("blueprint JSON is not canonical")
        return blueprint

    def canonical_json(self) -> str:
        """Return this frozen snapshot in canonical JSON form."""
        return canonical_json(self.model_dump(mode="json"))


def _reject_non_finite(token: str) -> None:
    raise ValueError(f"non-finite number: {token}")


def _validate_unique_identity(blueprint: ResolvedTeamBlueprint) -> None:
    member_names = tuple(member.name for member in blueprint.members)
    status_keys = tuple(status.key for status in blueprint.workflow.statuses)
    jira_names = tuple(status.jira_name for status in blueprint.workflow.statuses)
    route_types = tuple(route.issue_type for route in blueprint.workflow.routes)
    for values, label in (
        (member_names, "member names"),
        (status_keys, "status keys"),
        (jira_names, "Jira status names"),
        (route_types, "route issue types"),
    ):
        if not values or len(set(values)) != len(values):
            raise ValueError(f"{label} must be non-empty and unique")


def _validate_routes(blueprint: ResolvedTeamBlueprint) -> None:
    status_by_key = {status.key: status for status in blueprint.workflow.statuses}
    staffed = {item.activity for member in blueprint.members for item in member.responsibilities}
    for route in blueprint.workflow.routes:
        if len(route.steps) < 2:
            raise ValueError("workflow routes require at least two steps")
        for step in route.steps:
            if step.status_key not in status_by_key:
                raise ValueError("route references an unknown status")
            if step.required_activity is None:
                continue
            if step.required_activity not in status_by_key[step.status_key].activities:
                raise ValueError("route activity is not mapped by its status")
            if step.required_activity not in staffed:
                raise ValueError("route activity has no proficient member")


def _validate_timing_grid(blueprint: ResolvedTeamBlueprint) -> None:
    statuses = {status.key: status for status in blueprint.workflow.statuses}
    routes = {route.issue_type: route for route in blueprint.workflow.routes}
    points = {int(value) for value in blueprint.backlog.story_point_weights.keys()}
    actual = {
        (item.status_key, item.issue_type, item.story_points) for item in blueprint.timing.entries
    }
    if len(actual) != len(blueprint.timing.entries):
        raise ValueError("timing grid cells must be unique")
    expected = {
        (step.status_key, route.issue_type, point)
        for route in routes.values()
        for step in route.steps
        if statuses[step.status_key].consumes_capacity
        for point in points
    }
    if not expected or not expected <= actual:
        raise ValueError("timing grid is not fully materialized")
    if any(status not in statuses or issue_type not in routes for status, issue_type, _ in actual):
        raise ValueError("timing cell references unknown workflow data")


def _validate_risks(blueprint: ResolvedTeamBlueprint) -> None:
    keys = tuple(rule.key for rule in blueprint.risks.rules)
    if not keys or len(set(keys)) != len(keys):
        raise ValueError("risk rules must be materialized and unique")
    weighted_types = set(blueprint.backlog.issue_type_weights.keys())
    route_types = {route.issue_type for route in blueprint.workflow.routes}
    if not weighted_types <= route_types:
        raise ValueError("weighted issue type has no workflow route")
