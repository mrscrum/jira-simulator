"""Tests for the capacity module — MemberTickState, assignment, availability."""

import random

from app.engine.capacity import (
    build_member_states,
    find_available_member,
    mark_busy,
    release_assignment,
)


def _members(*roles_and_ids):
    """Helper: build member dicts. Each arg is (id, role) or (id, role, assigned_issue_id)."""
    result = []
    for item in roles_and_ids:
        if len(item) == 2:
            result.append({"id": item[0], "role": item[1], "assigned_issue_id": None})
        else:
            result.append({"id": item[0], "role": item[1], "assigned_issue_id": item[2]})
    return result


class TestBuildMemberStates:
    def test_creates_states_for_all_members(self):
        members = _members((1, "DEV"), (2, "QA"), (3, "DEV"))
        states = build_member_states(members)
        assert len(states) == 3
        assert set(states.keys()) == {1, 2, 3}

    def test_all_start_not_busy(self):
        members = _members((1, "DEV"), (2, "QA"))
        states = build_member_states(members)
        assert all(not s.busy_this_tick for s in states.values())

    def test_preserves_role(self):
        members = _members((1, "DEV"), (2, "QA"))
        states = build_member_states(members)
        assert states[1].role == "DEV"
        assert states[2].role == "QA"

    def test_preserves_existing_assignment(self):
        members = _members((1, "DEV", 42))
        states = build_member_states(members)
        assert states[1].assigned_issue_id == 42

    def test_unassigned_members_have_none(self):
        members = _members((1, "DEV"))
        states = build_member_states(members)
        assert states[1].assigned_issue_id is None


class TestFindAvailableMember:
    def test_returns_none_when_all_busy(self):
        members = _members((1, "DEV"), (2, "DEV"))
        states = build_member_states(members)
        states = mark_busy(states, 1, 10)
        states = mark_busy(states, 2, 11)
        result = find_available_member(states, ["DEV"], issue_id=99, rng=random.Random(42))
        assert result is None

    def test_filters_by_single_role(self):
        members = _members((1, "DEV"), (2, "QA"), (3, "DEV"))
        states = build_member_states(members)
        rng = random.Random(42)
        results = set()
        for _ in range(50):
            m = find_available_member(states, ["QA"], issue_id=99, rng=rng)
            if m:
                results.add(m.member_id)
        assert results == {2}

    def test_filters_by_multiple_roles(self):
        members = _members((1, "DEV"), (2, "QA"), (3, "Designer"))
        states = build_member_states(members)
        rng = random.Random(42)
        results = set()
        for _ in range(50):
            m = find_available_member(states, ["DEV", "QA"], issue_id=99, rng=rng)
            if m:
                results.add(m.member_id)
        assert results == {1, 2}

    def test_random_among_available(self):
        members = _members((1, "DEV"), (2, "DEV"), (3, "DEV"))
        states = build_member_states(members)
        rng = random.Random(42)
        chosen = set()
        for _ in range(100):
            m = find_available_member(states, ["DEV"], issue_id=99, rng=rng)
            chosen.add(m.member_id)
        assert len(chosen) > 1

    def test_sticky_assignment_available_to_own_issue(self):
        members = _members((1, "DEV", 42))
        states = build_member_states(members)
        result = find_available_member(states, ["DEV"], issue_id=42, rng=random.Random(42))
        assert result is not None
        assert result.member_id == 1

    def test_sticky_assignment_not_available_to_other_issue(self):
        members = _members((1, "DEV", 42))
        states = build_member_states(members)
        result = find_available_member(states, ["DEV"], issue_id=99, rng=random.Random(42))
        assert result is None

    def test_returns_none_for_no_matching_role(self):
        members = _members((1, "DEV"), (2, "DEV"))
        states = build_member_states(members)
        result = find_available_member(states, ["QA"], issue_id=99, rng=random.Random(42))
        assert result is None


class TestMarkBusy:
    def test_marks_member_busy(self):
        members = _members((1, "DEV"), (2, "DEV"))
        states = build_member_states(members)
        updated = mark_busy(states, 1, issue_id=42)
        assert updated[1].busy_this_tick is True
        assert updated[1].assigned_issue_id == 42

    def test_does_not_affect_other_members(self):
        members = _members((1, "DEV"), (2, "DEV"))
        states = build_member_states(members)
        updated = mark_busy(states, 1, issue_id=42)
        assert updated[2].busy_this_tick is False

    def test_returns_new_dict(self):
        members = _members((1, "DEV"))
        states = build_member_states(members)
        updated = mark_busy(states, 1, issue_id=42)
        assert states[1].busy_this_tick is False
        assert updated[1].busy_this_tick is True


class TestReleaseAssignment:
    def test_clears_assignment(self):
        members = _members((1, "DEV", 42))
        states = build_member_states(members)
        updated = release_assignment(states, 1)
        assert updated[1].assigned_issue_id is None

    def test_does_not_affect_busy_flag(self):
        members = _members((1, "DEV", 42))
        states = build_member_states(members)
        states = mark_busy(states, 1, 42)
        updated = release_assignment(states, 1)
        assert updated[1].busy_this_tick is True
        assert updated[1].assigned_issue_id is None
