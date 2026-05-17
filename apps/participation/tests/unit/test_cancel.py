"""Unit tests for CancelRegistrationUseCase."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from apps.participation.application.use_cases.cancel import CancelRegistrationUseCase
from apps.participation.domain.entities import WaitlistEntryEntity
from apps.participation.domain.exceptions import (
    InvalidRegistrationStatusError,
    RegistrationNotFoundError,
)
from apps.participation.tests.unit.fakes import (
    FakeEventPublisher,
    FakeRegistrationRepository,
    FakeWaitlistRepository,
    make_registration,
)


def _uc(regs=None, waitlist=None, publisher=None) -> CancelRegistrationUseCase:
    return CancelRegistrationUseCase(
        reg_repo=FakeRegistrationRepository(regs or []),
        waitlist_repo=FakeWaitlistRepository(waitlist or []),
        publisher=publisher or FakeEventPublisher(),
    )


def test_cancel_sets_cancelled_status_and_timestamp():
    """Cancelling sets status=cancelled and populates cancelled_at."""
    user_id = uuid.uuid4()
    reg = make_registration(user_id=user_id, status="confirmed")
    result = _uc(regs=[reg]).execute(registration_id=reg.id, user_id=user_id)
    assert result.status == "cancelled"
    assert result.cancelled_at is not None


def test_cancel_wrong_user_raises_not_found():
    """A different user's registration raises RegistrationNotFoundError to prevent leaking."""
    reg = make_registration(user_id=uuid.uuid4(), status="confirmed")
    with pytest.raises(RegistrationNotFoundError):
        _uc(regs=[reg]).execute(registration_id=reg.id, user_id=uuid.uuid4())


def test_cancel_non_cancellable_status_raises():
    """Cancelling a checked_in registration raises InvalidRegistrationStatusError."""
    user_id = uuid.uuid4()
    reg = make_registration(user_id=user_id, status="checked_in")
    with pytest.raises(InvalidRegistrationStatusError):
        _uc(regs=[reg]).execute(registration_id=reg.id, user_id=user_id)


def test_cancel_promotes_next_waitlist_entry():
    """Cancellation removes the next waitlist entry and creates a confirmed registration."""
    user_id = uuid.uuid4()
    waitlist_user = uuid.uuid4()
    event_id = uuid.uuid4()
    reg = make_registration(user_id=user_id, event_id=event_id, status="confirmed")
    entry = WaitlistEntryEntity(
        id=uuid.uuid4(),
        event_id=event_id,
        user_id=waitlist_user,
        position=1,
        created_at=datetime.now(timezone.utc),
    )
    reg_repo = FakeRegistrationRepository([reg])
    waitlist_repo = FakeWaitlistRepository([entry])
    CancelRegistrationUseCase(reg_repo=reg_repo, waitlist_repo=waitlist_repo).execute(
        registration_id=reg.id, user_id=user_id
    )
    assert len(waitlist_repo._store) == 0
    promoted = [r for r in reg_repo._store.values() if r.user_id == waitlist_user]
    assert len(promoted) == 1
    assert promoted[0].status == "confirmed"


def test_cancel_publishes_waitlist_promoted_event():
    """Promoting a waitlist entry publishes participation.waitlist.promoted."""
    user_id = uuid.uuid4()
    waitlist_user = uuid.uuid4()
    event_id = uuid.uuid4()
    reg = make_registration(user_id=user_id, event_id=event_id, status="confirmed")
    entry = WaitlistEntryEntity(
        id=uuid.uuid4(),
        event_id=event_id,
        user_id=waitlist_user,
        position=1,
        created_at=datetime.now(timezone.utc),
    )
    publisher = FakeEventPublisher()
    CancelRegistrationUseCase(
        reg_repo=FakeRegistrationRepository([reg]),
        waitlist_repo=FakeWaitlistRepository([entry]),
        publisher=publisher,
    ).execute(registration_id=reg.id, user_id=user_id)
    # two events: cancellation + waitlist.promoted
    routing_keys = [e["routing_key"] for e in publisher.events]
    assert "participation.registration.cancelled" in routing_keys
    assert "participation.waitlist.promoted" in routing_keys
    promoted = next(
        e for e in publisher.events if e["routing_key"] == "participation.waitlist.promoted"
    )
    assert promoted["payload"]["user_id"] == str(waitlist_user)
    assert promoted["payload"]["event_id"] == str(event_id)


def test_cancel_no_waitlist_only_publishes_cancelled():
    """Without a waitlist entry, only the cancellation event is published."""
    user_id = uuid.uuid4()
    reg = make_registration(user_id=user_id, status="confirmed")
    publisher = FakeEventPublisher()
    _uc(regs=[reg], publisher=publisher).execute(
        registration_id=reg.id, user_id=user_id
    )
    routing_keys = [e["routing_key"] for e in publisher.events]
    assert routing_keys == ["participation.registration.cancelled"]


def test_cancel_publishes_registration_cancelled_event():
    """Cancellation always publishes participation.registration.cancelled."""
    user_id = uuid.uuid4()
    reg = make_registration(user_id=user_id, status="confirmed")
    publisher = FakeEventPublisher()
    _uc(regs=[reg], publisher=publisher).execute(
        registration_id=reg.id, user_id=user_id
    )
    key = "participation.registration.cancelled"
    cancelled_events = [e for e in publisher.events if e["routing_key"] == key]
    assert len(cancelled_events) == 1
    assert cancelled_events[0]["payload"]["registration_id"] == str(reg.id)
    assert cancelled_events[0]["payload"]["user_id"] == str(user_id)
