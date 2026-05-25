"""Unit tests for PromoteNextWaitlistUseCase."""

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


def test_promote_sets_status_offered():
    """Promoting the next entry sets its status to offered, not confirmed."""
    event_id = uuid.uuid4()
    entry = make_waitlist_entry(event_id=event_id, position=1)
    waitlist = FakeWaitlistRepository([entry])
    publisher = FakeEventPublisher()

    from apps.participation.application.use_cases.promote_waitlist import (
        PromoteNextWaitlistUseCase,
    )

    PromoteNextWaitlistUseCase(waitlist_repo=waitlist, publisher=publisher).execute(
        event_id=event_id
    )

    updated = waitlist.get_by_id(entry.id)
    assert updated is not None
    assert updated.status == "offered"
    assert updated.offered_at is not None
    assert updated.expires_at is not None


def test_promote_sets_24h_expiry():
    """The expires_at is set exactly 24 hours after offered_at."""
    event_id = uuid.uuid4()
    entry = make_waitlist_entry(event_id=event_id, position=1)
    waitlist = FakeWaitlistRepository([entry])

    from apps.participation.application.use_cases.promote_waitlist import (
        PromoteNextWaitlistUseCase,
    )

    PromoteNextWaitlistUseCase(waitlist_repo=waitlist, publisher=FakeEventPublisher()).execute(
        event_id=event_id
    )

    updated = waitlist.get_by_id(entry.id)
    assert updated is not None
    assert updated.offered_at is not None
    assert updated.expires_at is not None
    delta = updated.expires_at - updated.offered_at
    assert timedelta(hours=23, minutes=59) < delta <= timedelta(hours=24, minutes=1)


def test_promote_publishes_waitlist_promoted_event():
    """Promotion publishes participation.waitlist.promoted with correct payload."""
    event_id = uuid.uuid4()
    entry = make_waitlist_entry(event_id=event_id, position=1)
    publisher = FakeEventPublisher()

    from apps.participation.application.use_cases.promote_waitlist import (
        PromoteNextWaitlistUseCase,
    )

    PromoteNextWaitlistUseCase(
        waitlist_repo=FakeWaitlistRepository([entry]), publisher=publisher
    ).execute(event_id=event_id)

    keys = [e["routing_key"] for e in publisher.events]
    assert "participation.waitlist.promoted" in keys
    promoted = next(
        e for e in publisher.events if e["routing_key"] == "participation.waitlist.promoted"
    )
    assert promoted["payload"]["user_id"] == str(entry.user_id)
    assert promoted["payload"]["event_id"] == str(event_id)
    assert promoted["payload"]["entry_id"] == str(entry.id)


def test_promote_does_nothing_when_queue_empty():
    """With no pending entries, promote does nothing and publishes nothing."""
    event_id = uuid.uuid4()
    publisher = FakeEventPublisher()

    from apps.participation.application.use_cases.promote_waitlist import (
        PromoteNextWaitlistUseCase,
    )

    PromoteNextWaitlistUseCase(
        waitlist_repo=FakeWaitlistRepository([]), publisher=publisher
    ).execute(event_id=event_id)

    assert publisher.events == []


def test_promote_skips_already_offered_entries():
    """Promote skips entries already in offered state and takes the next pending one."""
    event_id = uuid.uuid4()
    offered = make_waitlist_entry(event_id=event_id, position=1, status="offered")
    pending = make_waitlist_entry(event_id=event_id, position=2, status="pending")
    waitlist = FakeWaitlistRepository([offered, pending])
    publisher = FakeEventPublisher()

    from apps.participation.application.use_cases.promote_waitlist import (
        PromoteNextWaitlistUseCase,
    )

    PromoteNextWaitlistUseCase(waitlist_repo=waitlist, publisher=publisher).execute(
        event_id=event_id
    )

    updated_pending = waitlist.get_by_id(pending.id)
    assert updated_pending is not None
    assert updated_pending.status == "offered"
    # offered entry stays unchanged
    assert waitlist.get_by_id(offered.id).status == "offered"
