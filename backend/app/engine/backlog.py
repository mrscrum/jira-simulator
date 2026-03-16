"""Backlog depth maintenance and AI content generation."""

import random as _random
from abc import ABC, abstractmethod

DEFAULT_POINT_DISTRIBUTION = {1: 0.15, 2: 0.20, 3: 0.25, 5: 0.20, 8: 0.15, 13: 0.05}
DEFAULT_ISSUE_TYPES = ["Story", "Bug", "Task"]
ISSUE_TYPE_WEIGHTS = [0.50, 0.30, 0.20]

_STORY_TEMPLATES = [
    "Implement {feature} for {team} platform",
    "Add {feature} to improve user experience",
    "Create {feature} integration module",
    "Build {feature} dashboard component",
    "Design {feature} workflow automation",
]

_BUG_TEMPLATES = [
    "Fix {area} validation error on edge cases",
    "Resolve intermittent {area} timeout issue",
    "Correct {area} display rendering bug",
    "Address {area} data inconsistency",
]

_TASK_TEMPLATES = [
    "Update {area} configuration for new environment",
    "Migrate {area} to latest library version",
    "Refactor {area} for improved maintainability",
    "Add monitoring for {area} service",
]

_FEATURES = [
    "user authentication", "search", "notifications", "reporting",
    "data export", "file upload", "permissions", "analytics",
    "caching layer", "API gateway", "rate limiting", "audit logging",
]

_AREAS = [
    "payment", "login", "dashboard", "API", "database",
    "scheduler", "email", "webhook", "config", "session",
]


def check_backlog_depth(current_depth: int, target_depth: int) -> int:
    """Return the number of issues needed to reach target depth."""
    return max(0, target_depth - current_depth)


def select_story_points(
    distribution: dict[int, float] | None = None,
    rng: _random.Random | None = None,
) -> int:
    """Select story points using weighted random from distribution."""
    dist = distribution or DEFAULT_POINT_DISTRIBUTION
    rng = rng or _random.Random()
    values = list(dist.keys())
    weights = list(dist.values())
    return rng.choices(values, weights=weights, k=1)[0]


class ContentGenerator(ABC):
    """Interface for generating issue content."""

    @abstractmethod
    def generate(
        self,
        team_name: str,
        issue_type: str,
        story_points: int,
    ) -> dict:
        """Return dict with 'summary' and 'description' keys."""


class TemplateContentGenerator(ContentGenerator):
    """Generates issue content from predefined templates (no API key needed)."""

    def __init__(self, rng: _random.Random | None = None):
        self._rng = rng or _random.Random()

    def generate(
        self,
        team_name: str,
        issue_type: str,
        story_points: int,
    ) -> dict:
        feature = self._rng.choice(_FEATURES)
        area = self._rng.choice(_AREAS)

        if issue_type == "Bug":
            templates = _BUG_TEMPLATES
        elif issue_type == "Task":
            templates = _TASK_TEMPLATES
        else:
            templates = _STORY_TEMPLATES

        template = self._rng.choice(templates)
        summary = template.format(feature=feature, area=area, team=team_name)
        description = (
            f"[{team_name}] {issue_type} — {story_points} story points.\n"
            f"{summary}\n"
            f"Auto-generated for backlog maintenance."
        )
        return {"summary": summary, "description": description}


class OpenAIContentGenerator(ContentGenerator):
    """Generates issue content via OpenAI GPT API."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self._api_key = api_key
        self._model = model

    def generate(
        self,
        team_name: str,
        issue_type: str,
        story_points: int,
    ) -> dict:
        try:
            import openai
            client = openai.OpenAI(api_key=self._api_key)
            response = client.chat.completions.create(
                model=self._model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            f"Generate a Jira {issue_type} for team '{team_name}'. "
                            f"Story points: {story_points}. "
                            "Return JSON with 'summary' (one line) and "
                            "'description' (2-3 paragraphs)."
                        ),
                    },
                ],
                response_format={"type": "json_object"},
                max_tokens=300,
            )
            import json
            return json.loads(response.choices[0].message.content)
        except Exception:
            return TemplateContentGenerator().generate(
                team_name=team_name,
                issue_type=issue_type,
                story_points=story_points,
            )


async def generate_issues(
    count: int,
    team_name: str,
    content_generator: ContentGenerator,
    point_distribution: dict[int, float] | None = None,
    issue_types: list[str] | None = None,
    rng: _random.Random | None = None,
) -> list[dict]:
    """Generate a batch of issues for backlog replenishment."""
    rng = rng or _random.Random()
    types = issue_types or DEFAULT_ISSUE_TYPES
    issues = []
    for _ in range(count):
        if len(types) == 1:
            issue_type = types[0]
        else:
            issue_type = rng.choices(
                types,
                weights=ISSUE_TYPE_WEIGHTS[: len(types)],
                k=1,
            )[0]
        points = select_story_points(point_distribution, rng=rng)
        content = content_generator.generate(
            team_name=team_name,
            issue_type=issue_type,
            story_points=points,
        )
        issues.append({
            "summary": content["summary"],
            "description": content["description"],
            "story_points": points,
            "issue_type": issue_type,
        })
    return issues
