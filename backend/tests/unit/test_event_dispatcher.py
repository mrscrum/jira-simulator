"""Tests for the event dispatcher."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.engine.event_dispatcher import EventDispatcher
from app.models.base import Base
from app.models.event_audit_log import EventAuditLog
from app.models.jira_write_queue_entry import JiraWriteQueueEntry
from app.models.scheduled_event import ScheduledEvent


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    session = factory()
    yield session, factory
    session.close()
    engine.dispose()


class TestEventDispatcher:
    def test_dispatches_due_pending_events(self, db_session):
        session, factory = db_session
        past = datetime.now(UTC) - timedelta(minutes=5)

        event = ScheduledEvent(
            team_id=1, sprint_id=1, event_type="TRANSITION_ISSUE",
            scheduled_at=past, sim_tick=1,
            payload={"issue_key": "TST-1", "target_status": "In Progress"},
            status="PENDING", batch_id="test-batch", sequence_order=0,
        )
        session.add(event)
        session.commit()

        write_queue = MagicMock()
        dispatcher = EventDispatcher(factory, write_queue)
        count = dispatcher.dispatch_due_events()

        assert count == 1
        write_queue.enqueue.assert_called_once()

    def test_skips_future_events(self, db_session):
        session, factory = db_session
        future = datetime.now(UTC) + timedelta(hours=1)

        event = ScheduledEvent(
            team_id=1, sprint_id=1, event_type="TRANSITION_ISSUE",
            scheduled_at=future, sim_tick=1,
            payload={"issue_key": "TST-1"},
            status="PENDING", batch_id="test-batch", sequence_order=0,
        )
        session.add(event)
        session.commit()

        write_queue = MagicMock()
        dispatcher = EventDispatcher(factory, write_queue)
        count = dispatcher.dispatch_due_events()

        assert count == 0
        write_queue.enqueue.assert_not_called()

    def test_skips_cancelled_events(self, db_session):
        session, factory = db_session
        past = datetime.now(UTC) - timedelta(minutes=5)

        event = ScheduledEvent(
            team_id=1, sprint_id=1, event_type="TRANSITION_ISSUE",
            scheduled_at=past, sim_tick=1,
            payload={"issue_key": "TST-1"},
            status="CANCELLED", batch_id="test-batch", sequence_order=0,
        )
        session.add(event)
        session.commit()

        write_queue = MagicMock()
        dispatcher = EventDispatcher(factory, write_queue)
        count = dispatcher.dispatch_due_events()

        assert count == 0

    def test_dispatches_modified_events(self, db_session):
        session, factory = db_session
        past = datetime.now(UTC) - timedelta(minutes=5)

        event = ScheduledEvent(
            team_id=1, sprint_id=1, event_type="TRANSITION_ISSUE",
            scheduled_at=past, sim_tick=1,
            payload={"issue_key": "TST-1"},
            status="MODIFIED", batch_id="test-batch", sequence_order=0,
        )
        session.add(event)
        session.commit()

        write_queue = MagicMock()
        dispatcher = EventDispatcher(factory, write_queue)
        count = dispatcher.dispatch_due_events()

        assert count == 1

    def test_creates_audit_log_entry(self, db_session):
        session, factory = db_session
        past = datetime.now(UTC) - timedelta(minutes=5)

        event = ScheduledEvent(
            team_id=1, sprint_id=1, event_type="TRANSITION_ISSUE",
            scheduled_at=past, sim_tick=1,
            payload={"issue_key": "TST-1"},
            status="PENDING", batch_id="test-batch", sequence_order=0,
        )
        session.add(event)
        session.commit()

        write_queue = MagicMock()
        dispatcher = EventDispatcher(factory, write_queue)
        dispatcher.dispatch_due_events()

        # Check audit log was created
        audit = session.query(EventAuditLog).first()
        assert audit is not None
        assert audit.verification_status == "PENDING"
        assert audit.scheduled_event_id == event.id
