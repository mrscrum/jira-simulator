"""Tests for backlog module — depth check + content generation."""

import pytest

from app.engine.backlog import (
    TemplateContentGenerator,
    check_backlog_depth,
    generate_issues,
    select_story_points,
)


class TestCheckBacklogDepth:
    def test_returns_deficit_when_below_target(self):
        deficit = check_backlog_depth(current_depth=10, target_depth=40)
        assert deficit == 30

    def test_returns_zero_when_at_target(self):
        deficit = check_backlog_depth(current_depth=40, target_depth=40)
        assert deficit == 0

    def test_returns_zero_when_above_target(self):
        deficit = check_backlog_depth(current_depth=50, target_depth=40)
        assert deficit == 0


class TestSelectStoryPoints:
    def test_returns_valid_point_value(self):
        distribution = {1: 0.15, 2: 0.20, 3: 0.25, 5: 0.20, 8: 0.15, 13: 0.05}
        import random
        rng = random.Random(42)
        points = select_story_points(distribution, rng=rng)
        assert points in distribution

    def test_custom_distribution(self):
        distribution = {1: 0.5, 2: 0.5}
        import random
        rng = random.Random(42)
        points = select_story_points(distribution, rng=rng)
        assert points in {1, 2}

    def test_all_values_reachable(self):
        distribution = {1: 0.25, 2: 0.25, 3: 0.25, 5: 0.25}
        import random
        rng = random.Random(42)
        seen = set()
        for _ in range(200):
            seen.add(select_story_points(distribution, rng=rng))
        assert seen == {1, 2, 3, 5}


class TestTemplateContentGenerator:
    def test_generates_story(self):
        gen = TemplateContentGenerator()
        result = gen.generate(
            team_name="Alpha", issue_type="Story", story_points=3,
        )
        assert "summary" in result
        assert "description" in result
        assert len(result["summary"]) > 0
        assert len(result["description"]) > 0

    def test_generates_bug(self):
        gen = TemplateContentGenerator()
        result = gen.generate(
            team_name="Alpha", issue_type="Bug", story_points=2,
        )
        assert "summary" in result

    def test_generates_task(self):
        gen = TemplateContentGenerator()
        result = gen.generate(
            team_name="Alpha", issue_type="Task", story_points=1,
        )
        assert "summary" in result

    def test_team_name_in_description(self):
        gen = TemplateContentGenerator()
        result = gen.generate(
            team_name="Phoenix", issue_type="Story", story_points=5,
        )
        assert "Phoenix" in result["description"]


class TestGenerateIssues:
    @pytest.mark.asyncio
    async def test_generates_requested_count(self):
        gen = TemplateContentGenerator()
        issues = await generate_issues(
            count=5,
            team_name="Alpha",
            content_generator=gen,
        )
        assert len(issues) == 5

    @pytest.mark.asyncio
    async def test_each_issue_has_required_fields(self):
        gen = TemplateContentGenerator()
        issues = await generate_issues(
            count=3,
            team_name="Alpha",
            content_generator=gen,
        )
        for issue in issues:
            assert "summary" in issue
            assert "description" in issue
            assert "story_points" in issue
            assert "issue_type" in issue

    @pytest.mark.asyncio
    async def test_story_points_from_distribution(self):
        gen = TemplateContentGenerator()
        distribution = {1: 0.5, 2: 0.5}
        issues = await generate_issues(
            count=10,
            team_name="Alpha",
            content_generator=gen,
            point_distribution=distribution,
        )
        for issue in issues:
            assert issue["story_points"] in {1, 2}

    @pytest.mark.asyncio
    async def test_uses_provided_issue_types(self):
        gen = TemplateContentGenerator()
        issues = await generate_issues(
            count=5,
            team_name="Alpha",
            content_generator=gen,
            issue_types=["Bug"],
        )
        for issue in issues:
            assert issue["issue_type"] == "Bug"
