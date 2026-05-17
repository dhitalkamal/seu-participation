"""Unit tests for volunteer shift use cases. No database, hand-rolled fakes."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from apps.participation.application.use_cases.list_my_shifts import ListMyShiftsUseCase
from apps.participation.application.use_cases.get_event_checkin_stats import GetEventCheckInStatsUseCase
from apps.participation.domain.entities import VolunteerShiftEntity


def _shift(**kwargs) -> VolunteerShiftEntity:
    """Build a VolunteerShiftEntity with sensible defaults."""
    now = datetime.now(timezone.utc)
    return VolunteerShiftEntity(
        id=kwargs.get("id", uuid.uuid4()),
        event_id=kwargs.get("event_id", uuid.uuid4()),
        user_id=kwargs.get("user_id", uuid.uuid4()),
        role=kwargs.get("role", "Registration Desk"),
        start_time=kwargs.get("start_time", now),
        end_time=kwargs.get("end_time", now),
        location=kwargs.get("location", "East Atrium"),
        coordinator_name=kwargs.get("coordinator_name", "Sarah Jenkins"),
        coordinator_phone=kwargs.get("coordinator_phone", "+977-9800000000"),
        status=kwargs.get("status", "confirmed"),
        notes=kwargs.get("notes", None),
        created_at=now,
    )


class FakeShiftRepository:
    """In-memory shift store."""

    def __init__(self, shifts: list[VolunteerShiftEntity] | None = None) -> None:
        self._shifts = shifts or []

    def list_for_user(self, user_id: uuid.UUID) -> list[VolunteerShiftEntity]:
        """Return all shifts for a given user."""
        return [s for s in self._shifts if s.user_id == user_id]


class FakeRegistrationRepository:
    """In-memory registration store for stats."""

    def __init__(self, total: int = 0, checked_in: int = 0) -> None:
        self._total = total
        self._checked_in = checked_in

    def count_for_event(self, event_id: uuid.UUID) -> int:
        """Return total confirmed registrations for the event."""
        return self._total

    def count_checked_in_for_event(self, event_id: uuid.UUID) -> int:
        """Return checked-in count for the event."""
        return self._checked_in


def test_list_my_shifts_returns_only_own_shifts():
    """Only shifts assigned to the requesting user are returned."""
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()
    repo = FakeShiftRepository([_shift(user_id=user_a), _shift(user_id=user_b)])

    result = ListMyShiftsUseCase(repo).execute(user_id=user_a)

    assert len(result) == 1
    assert result[0].user_id == user_a


def test_list_my_shifts_empty_when_no_shifts():
    """Empty list returned when the user has no shifts."""
    repo = FakeShiftRepository([])
    result = ListMyShiftsUseCase(repo).execute(user_id=uuid.uuid4())
    assert result == []


def test_list_my_shifts_returns_all_own_shifts():
    """Multiple shifts for the same user are all returned."""
    user = uuid.uuid4()
    repo = FakeShiftRepository([_shift(user_id=user), _shift(user_id=user)])
    result = ListMyShiftsUseCase(repo).execute(user_id=user)
    assert len(result) == 2


def test_get_checkin_stats_returns_correct_counts():
    """Stats use case returns total and checked-in counts."""
    reg_repo = FakeRegistrationRepository(total=50, checked_in=23)
    event_id = uuid.uuid4()

    stats = GetEventCheckInStatsUseCase(reg_repo).execute(event_id=event_id)

    assert stats["total"] == 50
    assert stats["checked_in"] == 23
    assert stats["remaining"] == 27


def test_get_checkin_stats_zero_when_empty():
    """Stats are all zero when no registrations exist."""
    reg_repo = FakeRegistrationRepository(total=0, checked_in=0)
    stats = GetEventCheckInStatsUseCase(reg_repo).execute(event_id=uuid.uuid4())
    assert stats == {"total": 0, "checked_in": 0, "remaining": 0}
