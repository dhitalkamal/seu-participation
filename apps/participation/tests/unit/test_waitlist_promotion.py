"""Unit tests for waitlist auto-promotion use cases."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from apps.participation.application.use_cases.accept_waitlist_offer import (
    AcceptWaitlistOfferUseCase,
)
from apps.participation.application.use_cases.decline_waitlist_offer import (
    DeclineWaitlistOfferUseCase,
)
from apps.participation.application.use_cases.promote_waitlist import (
    PromoteNextWaitlistUseCase,
)
from apps.participation.domain.exceptions import (
    WaitlistOfferAlreadyRespondedError,
    WaitlistOfferExpiredError,
    WaitlistOfferNotFoundError,
)
from apps.participation.tests.unit.fakes import (
    FakeEventPublisher,
    FakeRegistrationRepository,
    FakeWaitlistRepository,
    make_waitlist_entry,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# * PromoteNextWaitlistUseCase tests


def test_promote_sets_status_offered():
    """Promoting the next entry sets its status to offered, not confirmed."""
    event_id = uuid.uuid4()
    entry = make_waitlist_entry(event_id=event_id, position=1)
    waitlist = FakeWaitlistRepository([entry])
    publisher = FakeEventPublisher()

    PromoteNextWaitlistUseCase(waitlist_repo=waitlist, publisher=publisher).execute(
        event_id=event_id
    )

    updated = waitlist.get_by_id(entry.id)
    assert updated is not None
    assert updated.status == "offered"
    assert updated.offered_at is not None
    assert updated.expires_at is not None


def test_promote_sets_24h_expiry():
    """The expires_at is set 24 hours after offered_at."""
    event_id = uuid.uuid4()
    entry = make_waitlist_entry(event_id=event_id, position=1)
    waitlist = FakeWaitlistRepository([entry])

    PromoteNextWaitlistUseCase(waitlist_repo=waitlist, publisher=FakeEventPublisher()).execute(
        event_id=event_id
    )

    updated = waitlist.get_by_id(entry.id)
    assert updated is not None
    delta = updated.expires_at - updated.offered_at
    assert timedelta(hours=23, minutes=59) < delta <= timedelta(hours=24, minutes=1)


def test_promote_publishes_waitlist_promoted_event():
    """Promotion publishes participation.waitlist.promoted with correct payload."""
    event_id = uuid.uuid4()
    entry = make_waitlist_entry(event_id=event_id, position=1)
    publisher = FakeEventPublisher()

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

    PromoteNextWaitlistUseCase(waitlist_repo=waitlist, publisher=publisher).execute(
        event_id=event_id
    )

    updated_pending = waitlist.get_by_id(pending.id)
    assert updated_pending is not None
    assert updated_pending.status == "offered"
    # offered entry unchanged
    assert waitlist.get_by_id(offered.id).status == "offered"


# * AcceptWaitlistOfferUseCase tests


def test_accept_creates_confirmed_registration():
    """Accepting a valid offer creates a confirmed registration and removes the waitlist entry."""
    event_id = uuid.uuid4()
    user_id = uuid.uuid4()
    entry = make_waitlist_entry(
        event_id=event_id, user_id=user_id, status="offered", offered_at=_now()
    )
    waitlist = FakeWaitlistRepository([entry])
    reg_repo = FakeRegistrationRepository([])
    publisher = FakeEventPublisher()

    result = AcceptWaitlistOfferUseCase(
        waitlist_repo=waitlist, reg_repo=reg_repo, publisher=publisher
    ).execute(entry_id=entry.id, user_id=user_id)

    assert result.status == "confirmed"
    assert result.event_id == event_id
    assert result.user_id == user_id
    # entry removed from waitlist
    assert waitlist.get_by_id(entry.id) is None


def test_accept_publishes_registration_confirmed():
    """Accepting publishes participation.registration.confirmed."""
    event_id = uuid.uuid4()
    user_id = uuid.uuid4()
    entry = make_waitlist_entry(
        event_id=event_id, user_id=user_id, status="offered", offered_at=_now()
    )
    publisher = FakeEventPublisher()

    AcceptWaitlistOfferUseCase(
        waitlist_repo=FakeWaitlistRepository([entry]),
        reg_repo=FakeRegistrationRepository([]),
        publisher=publisher,
    ).execute(entry_id=entry.id, user_id=user_id)

    keys = [e["routing_key"] for e in publisher.events]
    assert "participation.waitlist.accepted" in keys


def test_accept_raises_not_found_for_unknown_entry():
    """Accepting a non-existent entry raises WaitlistOfferNotFoundError."""
    with pytest.raises(WaitlistOfferNotFoundError):
        AcceptWaitlistOfferUseCase(
            waitlist_repo=FakeWaitlistRepository([]),
            reg_repo=FakeRegistrationRepository([]),
            publisher=FakeEventPublisher(),
        ).execute(entry_id=uuid.uuid4(), user_id=uuid.uuid4())


def test_accept_raises_not_found_for_wrong_user():
    """Accepting another user's offer raises WaitlistOfferNotFoundError (no leaking)."""
    event_id = uuid.uuid4()
    entry = make_waitlist_entry(event_id=event_id, status="offered", offered_at=_now())
    with pytest.raises(WaitlistOfferNotFoundError):
        AcceptWaitlistOfferUseCase(
            waitlist_repo=FakeWaitlistRepository([entry]),
            reg_repo=FakeRegistrationRepository([]),
            publisher=FakeEventPublisher(),
        ).execute(entry_id=entry.id, user_id=uuid.uuid4())


def test_accept_raises_expired_when_window_passed():
    """Accepting after the 24h window raises WaitlistOfferExpiredError."""
    event_id = uuid.uuid4()
    user_id = uuid.uuid4()
    offered_at = _now() - timedelta(hours=25)
    expires_at = offered_at + timedelta(hours=24)
    entry = make_waitlist_entry(
        event_id=event_id,
        user_id=user_id,
        status="offered",
        offered_at=offered_at,
        expires_at=expires_at,
    )
    with pytest.raises(WaitlistOfferExpiredError):
        AcceptWaitlistOfferUseCase(
            waitlist_repo=FakeWaitlistRepository([entry]),
            reg_repo=FakeRegistrationRepository([]),
            publisher=FakeEventPublisher(),
        ).execute(entry_id=entry.id, user_id=user_id)


def test_accept_raises_for_pending_entry():
    """Accepting a pending (not yet offered) entry raises WaitlistOfferAlreadyRespondedError."""
    event_id = uuid.uuid4()
    user_id = uuid.uuid4()
    entry = make_waitlist_entry(event_id=event_id, user_id=user_id, status="pending")
    with pytest.raises(WaitlistOfferAlreadyRespondedError):
        AcceptWaitlistOfferUseCase(
            waitlist_repo=FakeWaitlistRepository([entry]),
            reg_repo=FakeRegistrationRepository([]),
            publisher=FakeEventPublisher(),
        ).execute(entry_id=entry.id, user_id=user_id)


# * DeclineWaitlistOfferUseCase tests


def test_decline_removes_entry_and_promotes_next():
    """Declining removes the entry and promotes the next pending person."""
    event_id = uuid.uuid4()
    user_id = uuid.uuid4()
    next_user = uuid.uuid4()
    offered = make_waitlist_entry(
        event_id=event_id,
        user_id=user_id,
        status="offered",
        offered_at=_now(),
        position=1,
    )
    pending = make_waitlist_entry(
        event_id=event_id, user_id=next_user, status="pending", position=2
    )
    waitlist = FakeWaitlistRepository([offered, pending])
    publisher = FakeEventPublisher()

    DeclineWaitlistOfferUseCase(waitlist_repo=waitlist, publisher=publisher).execute(
        entry_id=offered.id, user_id=user_id
    )

    assert waitlist.get_by_id(offered.id) is None
    next_entry = waitlist.get_by_id(pending.id)
    assert next_entry is not None
    assert next_entry.status == "offered"


def test_decline_raises_not_found_for_wrong_user():
    """Declining another user's offer raises WaitlistOfferNotFoundError."""
    entry = make_waitlist_entry(status="offered", offered_at=_now())
    with pytest.raises(WaitlistOfferNotFoundError):
        DeclineWaitlistOfferUseCase(
            waitlist_repo=FakeWaitlistRepository([entry]),
            publisher=FakeEventPublisher(),
        ).execute(entry_id=entry.id, user_id=uuid.uuid4())
