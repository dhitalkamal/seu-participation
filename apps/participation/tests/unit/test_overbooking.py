"""Unit tests for overbooking support in participation domain."""

from __future__ import annotations

import uuid

from apps.participation.application.use_cases.register import RegisterForEventUseCase
from apps.participation.domain.entities import EventSummary, RegistrationEntity, WaitlistEntryEntity
from apps.participation.tests.unit.fakes import (
    FakeEventClient,
    FakeEventPublisher,
    FakeRegistrationRepository,
    FakeWaitlistRepository,
    make_event_summary,
)


def _uc(event=None, regs=None, waitlist=None) -> RegisterForEventUseCase:
    """Build the use case with fakes."""
    return RegisterForEventUseCase(
        reg_repo=FakeRegistrationRepository(regs or []),
        waitlist_repo=FakeWaitlistRepository(waitlist or []),
        event_client=FakeEventClient(event),
        publisher=FakeEventPublisher(),
    )


def test_event_summary_has_overbooking_percent():
    """EventSummary dataclass has an overbooking_percent field defaulting to 0."""
    summary = make_event_summary(capacity=100, registered_count=0)
    assert hasattr(summary, "overbooking_percent")
    assert summary.overbooking_percent == 0


def test_is_at_capacity_zero_overbooking_strict():
    """At 0% overbooking, event is at capacity when registered == capacity."""
    summary = EventSummary(
        event_id=uuid.uuid4(),
        capacity=10,
        registered_count=10,
        overbooking_percent=0,
    )
    assert summary.is_at_capacity is True


def test_is_at_capacity_zero_overbooking_not_full():
    """At 0% overbooking, event is not at capacity when registered < capacity."""
    summary = EventSummary(
        event_id=uuid.uuid4(),
        capacity=10,
        registered_count=9,
        overbooking_percent=0,
    )
    assert summary.is_at_capacity is False


def test_is_at_capacity_ten_percent_allows_one_extra():
    """At 10% overbooking, effective capacity is 11 for capacity=10."""
    summary = EventSummary(
        event_id=uuid.uuid4(),
        capacity=10,
        registered_count=10,
        overbooking_percent=10,
    )
    # effective = 10 * 1.1 = 11; 10 < 11 so NOT at capacity
    assert summary.is_at_capacity is False


def test_is_at_capacity_ten_percent_full_at_effective():
    """At 10% overbooking, at_capacity when registered >= 11 for capacity=10."""
    summary = EventSummary(
        event_id=uuid.uuid4(),
        capacity=10,
        registered_count=11,
        overbooking_percent=10,
    )
    assert summary.is_at_capacity is True


def test_is_at_capacity_twenty_percent():
    """At 20% overbooking, effective capacity is 12 for capacity=10."""
    summary = EventSummary(
        event_id=uuid.uuid4(),
        capacity=10,
        registered_count=11,
        overbooking_percent=20,
    )
    # effective = 10 * 1.2 = 12; 11 < 12 so NOT at capacity
    assert summary.is_at_capacity is False


def test_register_uses_overbooking_for_capacity_check():
    """RegisterForEventUseCase respects overbooking_percent when checking capacity."""
    event_id = uuid.uuid4()
    # 10% overbooking: effective capacity = 11 for capacity=10
    event = EventSummary(
        event_id=event_id,
        capacity=10,
        registered_count=10,
        overbooking_percent=10,
    )
    # should succeed (slot available via overbooking)
    result = _uc(event=event).execute(event_id=event_id, user_id=uuid.uuid4())
    assert isinstance(result, RegistrationEntity)


def test_register_adds_to_waitlist_when_overbooking_exhausted():
    """RegisterForEventUseCase adds to waitlist when effective capacity is full."""
    event_id = uuid.uuid4()
    event = EventSummary(
        event_id=event_id,
        capacity=10,
        registered_count=11,
        overbooking_percent=10,
    )
    # effective = 11; 11 >= 11 so full
    result = _uc(event=event).execute(event_id=event_id, user_id=uuid.uuid4())
    assert isinstance(result, WaitlistEntryEntity)
