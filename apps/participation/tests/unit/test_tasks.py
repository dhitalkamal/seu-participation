"""Unit tests for the participation Celery tasks."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from apps.participation.tests.unit.fakes import (
    FakeEventPublisher,
    FakeWaitlistRepository,
    make_waitlist_entry,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def test_expire_stale_offers_marks_entries_expired_and_promotes():
    """Entries whose expires_at has passed are removed and their event's next entry is promoted."""
    from apps.participation.tasks import _expire_and_promote

    event_id = uuid.uuid4()
    expired_at = _now() - timedelta(minutes=1)
    stale = make_waitlist_entry(
        event_id=event_id,
        status="offered",
        offered_at=_now() - timedelta(hours=25),
        expires_at=expired_at,
        position=1,
    )
    next_pending = make_waitlist_entry(event_id=event_id, status="pending", position=2)
    waitlist = FakeWaitlistRepository([stale, next_pending])
    publisher = FakeEventPublisher()

    _expire_and_promote(waitlist_repo=waitlist, publisher=publisher)

    # stale entry removed
    assert waitlist.get_by_id(stale.id) is None
    # next pending entry promoted to offered
    updated = waitlist.get_by_id(next_pending.id)
    assert updated is not None
    assert updated.status == "offered"
    assert "participation.waitlist.promoted" in [e["routing_key"] for e in publisher.events]


def test_expire_stale_offers_does_nothing_when_no_stale():
    """When no entries are expired, nothing is modified and nothing is published."""
    from apps.participation.tasks import _expire_and_promote

    fresh = make_waitlist_entry(
        status="offered",
        offered_at=_now(),
        expires_at=_now() + timedelta(hours=20),
    )
    waitlist = FakeWaitlistRepository([fresh])
    publisher = FakeEventPublisher()

    _expire_and_promote(waitlist_repo=waitlist, publisher=publisher)

    assert waitlist.get_by_id(fresh.id) is not None
    assert publisher.events == []
