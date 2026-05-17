"""Unit tests for RegisterForEventUseCase."""

from __future__ import annotations

import uuid

import pytest

from apps.participation.application.use_cases.register import RegisterForEventUseCase
from apps.participation.domain.entities import RegistrationEntity, WaitlistEntryEntity
from apps.participation.domain.exceptions import AlreadyRegisteredError, EventNotFoundError
from apps.participation.tests.unit.fakes import (
    FakeEventClient,
    FakeEventPublisher,
    FakeRegistrationRepository,
    FakeWaitlistRepository,
    make_event_summary,
    make_registration,
)


def _uc(event=None, regs=None, waitlist=None, publisher=None) -> RegisterForEventUseCase:
    return RegisterForEventUseCase(
        reg_repo=FakeRegistrationRepository(regs or []),
        waitlist_repo=FakeWaitlistRepository(waitlist or []),
        event_client=FakeEventClient(event),
        publisher=publisher or FakeEventPublisher(),
    )


def test_register_creates_confirmed_registration():
    """Successful registration returns a RegistrationEntity with status=confirmed."""
    event_id = uuid.uuid4()
    user_id = uuid.uuid4()
    event = make_event_summary(event_id=event_id, capacity=100, registered_count=0)
    result = _uc(event=event).execute(event_id=event_id, user_id=user_id)
    assert isinstance(result, RegistrationEntity)
    assert result.status == "confirmed"
    assert result.event_id == event_id
    assert result.user_id == user_id


def test_register_generates_8char_alphanumeric_code():
    """registration_code is exactly 8 alphanumeric characters."""
    event = make_event_summary()
    result = _uc(event=event).execute(event_id=event.event_id, user_id=uuid.uuid4())
    assert isinstance(result, RegistrationEntity)
    assert len(result.registration_code) == 8
    assert result.registration_code.isalnum()


def test_register_duplicate_active_raises():
    """Registering again for the same event raises AlreadyRegisteredError."""
    event_id = uuid.uuid4()
    user_id = uuid.uuid4()
    event = make_event_summary(event_id=event_id)
    existing = make_registration(event_id=event_id, user_id=user_id, status="confirmed")
    with pytest.raises(AlreadyRegisteredError):
        _uc(event=event, regs=[existing]).execute(event_id=event_id, user_id=user_id)


def test_register_event_not_found_raises():
    """EventNotFoundError propagates when the event client returns nothing."""
    with pytest.raises(EventNotFoundError):
        _uc(event=None).execute(event_id=uuid.uuid4(), user_id=uuid.uuid4())


def test_register_stores_notes():
    """Notes field is persisted when provided."""
    event = make_event_summary(capacity=100, registered_count=0)
    result = _uc(event=event).execute(
        event_id=event.event_id, user_id=uuid.uuid4(), quantity=1, notes="Front row please"
    )
    assert isinstance(result, RegistrationEntity)
    assert result.notes == "Front row please"


def test_register_publishes_registration_created_event():
    """Successful registration publishes participation.registration.created."""
    event = make_event_summary(capacity=100, registered_count=0)
    publisher = FakeEventPublisher()
    result = RegisterForEventUseCase(
        reg_repo=FakeRegistrationRepository(),
        waitlist_repo=FakeWaitlistRepository(),
        event_client=FakeEventClient(event),
        publisher=publisher,
    ).execute(event_id=event.event_id, user_id=uuid.uuid4())
    assert isinstance(result, RegistrationEntity)
    assert len(publisher.events) == 1
    assert publisher.events[0]["routing_key"] == "participation.registration.created"
    assert publisher.events[0]["payload"]["registration_code"] == result.registration_code


def test_register_waitlist_does_not_publish_registration_created():
    """Adding to waitlist does NOT publish registration.created."""
    event = make_event_summary(capacity=10, registered_count=10)
    publisher = FakeEventPublisher()
    result = RegisterForEventUseCase(
        reg_repo=FakeRegistrationRepository(),
        waitlist_repo=FakeWaitlistRepository(),
        event_client=FakeEventClient(event),
        publisher=publisher,
    ).execute(event_id=event.event_id, user_id=uuid.uuid4())
    assert isinstance(result, WaitlistEntryEntity)
    assert publisher.events == []


def test_register_at_capacity_adds_to_waitlist():
    """When the event is full, the user is added to the waitlist instead."""
    event_id = uuid.uuid4()
    user_id = uuid.uuid4()
    event = make_event_summary(event_id=event_id, capacity=10, registered_count=10)
    result = _uc(event=event).execute(event_id=event_id, user_id=user_id)
    assert isinstance(result, WaitlistEntryEntity)
    assert result.event_id == event_id
    assert result.user_id == user_id
    assert result.position == 1
