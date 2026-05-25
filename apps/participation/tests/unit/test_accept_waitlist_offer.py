"""Unit tests for AcceptWaitlistOfferUseCase."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

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


def test_accept_creates_confirmed_registration():
    """Accepting a valid offer creates a confirmed registration and removes the waitlist entry."""
    from apps.participation.application.use_cases.accept_waitlist_offer import (
        AcceptWaitlistOfferUseCase,
    )

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
    assert waitlist.get_by_id(entry.id) is None


def test_accept_publishes_registration_confirmed():
    """Accepting publishes participation.waitlist.accepted."""
    from apps.participation.application.use_cases.accept_waitlist_offer import (
        AcceptWaitlistOfferUseCase,
    )

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
    from apps.participation.application.use_cases.accept_waitlist_offer import (
        AcceptWaitlistOfferUseCase,
    )

    with pytest.raises(WaitlistOfferNotFoundError):
        AcceptWaitlistOfferUseCase(
            waitlist_repo=FakeWaitlistRepository([]),
            reg_repo=FakeRegistrationRepository([]),
            publisher=FakeEventPublisher(),
        ).execute(entry_id=uuid.uuid4(), user_id=uuid.uuid4())


def test_accept_raises_not_found_for_wrong_user():
    """Accepting another user's offer raises WaitlistOfferNotFoundError (no leaking)."""
    from apps.participation.application.use_cases.accept_waitlist_offer import (
        AcceptWaitlistOfferUseCase,
    )

    entry = make_waitlist_entry(status="offered", offered_at=_now())
    with pytest.raises(WaitlistOfferNotFoundError):
        AcceptWaitlistOfferUseCase(
            waitlist_repo=FakeWaitlistRepository([entry]),
            reg_repo=FakeRegistrationRepository([]),
            publisher=FakeEventPublisher(),
        ).execute(entry_id=entry.id, user_id=uuid.uuid4())


def test_accept_raises_expired_when_window_passed():
    """Accepting after the 24h window raises WaitlistOfferExpiredError."""
    from apps.participation.application.use_cases.accept_waitlist_offer import (
        AcceptWaitlistOfferUseCase,
    )

    user_id = uuid.uuid4()
    offered_at = _now() - timedelta(hours=25)
    expires_at = offered_at + timedelta(hours=24)
    entry = make_waitlist_entry(
        user_id=user_id, status="offered", offered_at=offered_at, expires_at=expires_at
    )
    with pytest.raises(WaitlistOfferExpiredError):
        AcceptWaitlistOfferUseCase(
            waitlist_repo=FakeWaitlistRepository([entry]),
            reg_repo=FakeRegistrationRepository([]),
            publisher=FakeEventPublisher(),
        ).execute(entry_id=entry.id, user_id=user_id)


def test_accept_raises_for_pending_entry():
    """Accepting a still-pending entry raises WaitlistOfferAlreadyRespondedError."""
    from apps.participation.application.use_cases.accept_waitlist_offer import (
        AcceptWaitlistOfferUseCase,
    )

    user_id = uuid.uuid4()
    entry = make_waitlist_entry(user_id=user_id, status="pending")
    with pytest.raises(WaitlistOfferAlreadyRespondedError):
        AcceptWaitlistOfferUseCase(
            waitlist_repo=FakeWaitlistRepository([entry]),
            reg_repo=FakeRegistrationRepository([]),
            publisher=FakeEventPublisher(),
        ).execute(entry_id=entry.id, user_id=user_id)
