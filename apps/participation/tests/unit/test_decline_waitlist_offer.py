"""Unit tests for DeclineWaitlistOfferUseCase."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from apps.participation.domain.exceptions import (
    WaitlistOfferAlreadyRespondedError,
    WaitlistOfferNotFoundError,
)
from apps.participation.tests.unit.fakes import (
    FakeEventPublisher,
    FakeWaitlistRepository,
    make_waitlist_entry,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def test_decline_removes_entry():
    """Declining a valid offer removes the waitlist entry entirely."""
    from apps.participation.application.use_cases.decline_waitlist_offer import (
        DeclineWaitlistOfferUseCase,
    )

    user_id = uuid.uuid4()
    entry = make_waitlist_entry(user_id=user_id, status="offered", offered_at=_now())
    waitlist = FakeWaitlistRepository([entry])

    DeclineWaitlistOfferUseCase(waitlist_repo=waitlist, publisher=FakeEventPublisher()).execute(
        entry_id=entry.id, user_id=user_id
    )

    assert waitlist.get_by_id(entry.id) is None


def test_decline_publishes_waitlist_declined():
    """Declining publishes participation.waitlist.declined."""
    from apps.participation.application.use_cases.decline_waitlist_offer import (
        DeclineWaitlistOfferUseCase,
    )

    user_id = uuid.uuid4()
    entry = make_waitlist_entry(user_id=user_id, status="offered", offered_at=_now())
    publisher = FakeEventPublisher()

    DeclineWaitlistOfferUseCase(
        waitlist_repo=FakeWaitlistRepository([entry]), publisher=publisher
    ).execute(entry_id=entry.id, user_id=user_id)

    keys = [e["routing_key"] for e in publisher.events]
    assert "participation.waitlist.declined" in keys


def test_decline_raises_not_found_for_unknown_entry():
    """Declining a non-existent entry raises WaitlistOfferNotFoundError."""
    from apps.participation.application.use_cases.decline_waitlist_offer import (
        DeclineWaitlistOfferUseCase,
    )

    with pytest.raises(WaitlistOfferNotFoundError):
        DeclineWaitlistOfferUseCase(
            waitlist_repo=FakeWaitlistRepository([]),
            publisher=FakeEventPublisher(),
        ).execute(entry_id=uuid.uuid4(), user_id=uuid.uuid4())


def test_decline_raises_not_found_for_wrong_user():
    """Declining another user's offer raises WaitlistOfferNotFoundError."""
    from apps.participation.application.use_cases.decline_waitlist_offer import (
        DeclineWaitlistOfferUseCase,
    )

    entry = make_waitlist_entry(status="offered", offered_at=_now())
    with pytest.raises(WaitlistOfferNotFoundError):
        DeclineWaitlistOfferUseCase(
            waitlist_repo=FakeWaitlistRepository([entry]),
            publisher=FakeEventPublisher(),
        ).execute(entry_id=entry.id, user_id=uuid.uuid4())


def test_decline_raises_for_pending_entry():
    """Declining a still-pending entry raises WaitlistOfferAlreadyRespondedError."""
    from apps.participation.application.use_cases.decline_waitlist_offer import (
        DeclineWaitlistOfferUseCase,
    )

    user_id = uuid.uuid4()
    entry = make_waitlist_entry(user_id=user_id, status="pending")
    with pytest.raises(WaitlistOfferAlreadyRespondedError):
        DeclineWaitlistOfferUseCase(
            waitlist_repo=FakeWaitlistRepository([entry]),
            publisher=FakeEventPublisher(),
        ).execute(entry_id=entry.id, user_id=user_id)
