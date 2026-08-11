"""Frozen, fully materialized v2 Scrum blueprint contract."""

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator

from app.v2.domain.canonical_json import canonical_json

_REQUIRED_SECTIONS = frozenset(
    {
        "schema_version",
        "team",
        "jira",
        "calendar",
        "members",
        "workflow",
        "timing",
        "backlog",
        "risks",
        "content",
        "scrum",
        "seed",
    }
)


class ResolvedTeamBlueprint(BaseModel):
    """A canonical, fully resolved Scrum team snapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    schema_version: str
    team: dict[str, Any]
    jira: dict[str, Any]
    calendar: dict[str, Any]
    members: list[dict[str, Any]]
    workflow: dict[str, Any]
    timing: dict[str, Any]
    backlog: dict[str, Any]
    risks: dict[str, Any]
    content: dict[str, Any]
    scrum: dict[str, Any]
    seed: str

    @model_validator(mode="after")
    def validate_resolved_scrum(self) -> "ResolvedTeamBlueprint":
        """Reject incomplete/non-Scrum snapshots before persistence."""
        if self.schema_version != "2.0":
            raise ValueError("schema_version must be 2.0")
        if self.team.get("methodology") != "SCRUM":
            raise ValueError("M1 accepts only SCRUM blueprints")
        self._require_fields(
            self.team,
            {"name", "summary", "description", "archetype", "locale", "timezone", "methodology"},
            "team",
        )
        self._require_fields(
            self.jira,
            {"project_name", "project_key", "board_name", "project_type", "topology_strategy"},
            "jira",
        )
        self._require_fields(
            self.calendar,
            {
                "working_weekdays",
                "workday_start",
                "workday_end",
                "holiday_calendar_profile",
                "holiday_horizon_end",
                "holidays",
            },
            "calendar",
        )
        self._require_fields(
            self.timing,
            {"profile_name", "profile_version", "algorithm_version", "entries"},
            "timing",
        )
        self._require_fields(
            self.risks, {"profile_name", "profile_version", "algorithm_version", "rules"}, "risks"
        )
        self._require_fields(
            self.scrum,
            {
                "cadence_days",
                "first_boundary",
                "capacity_min_points",
                "capacity_max_points",
                "planning_policy_version",
                "ranking_policy_version",
                "carryover_policy_version",
            },
            "scrum",
        )
        if not self.members or not self.timing["entries"] or not self.risks["rules"]:
            raise ValueError("members, timing entries, and risk rules must be materialized")
        return self

    @staticmethod
    def _require_fields(section: dict[str, Any], expected: set[str], section_name: str) -> None:
        missing = expected.difference(section)
        if missing:
            raise ValueError(f"{section_name} missing required fields: {sorted(missing)}")

    @classmethod
    def from_canonical_json(cls, document: str) -> "ResolvedTeamBlueprint":
        """Parse only a byte-for-byte canonical resolved blueprint document."""
        try:
            raw_document: Any = json.loads(
                document,
                parse_constant=lambda token: (_ for _ in ()).throw(
                    ValueError(f"non-finite number: {token}")
                ),
            )
        except (json.JSONDecodeError, ValueError) as error:
            raise ValueError("blueprint must be valid finite JSON") from error
        if not isinstance(raw_document, dict) or set(raw_document) != _REQUIRED_SECTIONS:
            raise ValueError("blueprint has missing or extra snapshot sections")
        blueprint = cls.model_validate(raw_document)
        if blueprint.canonical_json() != document:
            raise ValueError("blueprint JSON is not canonical")
        return blueprint

    def canonical_json(self) -> str:
        """Return this frozen snapshot in canonical JSON form."""
        return canonical_json(self.model_dump(mode="json"))
