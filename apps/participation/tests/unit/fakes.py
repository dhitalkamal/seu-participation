"""Hand-rolled in-memory fakes for all participation repository interfaces."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Sequence

from apps.participation.domain.entities import (
    CheckInEntity,
    EventSummary,
    RegistrationEntity,
    WaitlistEntryEntity,
)
from apps.participation.domain.exceptions import EventNotFoundError, RegistrationNotFoundError
from apps.participation.domain.repositories import (
    ICheckInRepository,
    IEventClient,
    IRegistrationRepository,
    IWaitlistRepository,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def make_registration(**kwargs: object) -> RegistrationEntity:
    """Build a RegistrationEntity with sensible defaults for testing."""
    now = _now()
    defaults: dict = {
        "id": uuid.uuid4(),
        "event_id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "status": "confirmed",
        "registration_code": "ABC12345",
        "quantity": 1,
        "created_at": now,
        "updated_at": now,
        "checked_in_at": None,
        "cancelled_at": None,
    }
    defaults.update(kwargs)
    return RegistrationEntity(**defaults)  # type: ignore[arg-type]


def make_event_summary(
    *,
    event_id: uuid.UUID | None = None,
    capacity: int = 100,
    registered_count: int = 0,
) -> EventSummary:
    """Build an EventSummary with sensible defaults for testing."""
    return EventSummary(
        event_id=event_id or uuid.uuid4(),
        capacity=capacity,
        registered_count=registered_count,
    )


class FakeRegistrationRepository(IRegistrationRepository):
    """In-memory registration store."""

    def __init__(self, registrations: Sequence[RegistrationEntity] | None = None) -> None:
        self._store: dict[uuid.UUID, RegistrationEntity] = {r.id: r for r in (registrations or [])}

    def create(self, entity: RegistrationEntity) -> RegistrationEntity:
        """Persist and return the entity."""
        self._store[entity.id] = entity
        return entity

    def get_by_id(self, registration_id: uuid.UUID) -> RegistrationEntity:
        """Raise RegistrationNotFoundError if absent."""
        entity = self._store.get(registration_id)
        if entity is None:
            raise RegistrationNotFoundError("Registration not found.")
        return entity

    def get_by_code(self, code: str) -> RegistrationEntity:
        """Raise RegistrationNotFoundError if code not found."""
        for entity in self._store.values():
            if entity.registration_code == code:
                return entity
        raise RegistrationNotFoundError("Registration not found.")

    def has_active(self, event_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """True if a non-cancelled registration exists for this (event, user) pair."""
        return any(
            r.event_id == event_id and r.user_id == user_id and r.status != "cancelled"
            for r in self._store.values()
        )

    def update(self, entity: RegistrationEntity) -> RegistrationEntity:
        """Overwrite the stored entity and return it."""
        self._store[entity.id] = entity
        return entity


class FakeCheckInRepository(ICheckInRepository):
    """In-memory check-in store."""

    def __init__(self, check_ins: Sequence[CheckInEntity] | None = None) -> None:
        self._store: dict[uuid.UUID, CheckInEntity] = {c.id: c for c in (check_ins or [])}

    def create(self, entity: CheckInEntity) -> CheckInEntity:
        """Persist and return the entity."""
        self._store[entity.id] = entity
        return entity

    def exists_for_registration(self, registration_id: uuid.UUID) -> bool:
        """True if a check-in already exists for this registration."""
        return any(c.registration_id == registration_id for c in self._store.values())


class FakeWaitlistRepository(IWaitlistRepository):
    """In-memory waitlist store."""

    def __init__(self, entries: Sequence[WaitlistEntryEntity] | None = None) -> None:
        self._store: dict[uuid.UUID, WaitlistEntryEntity] = {e.id: e for e in (entries or [])}

    def add(self, entity: WaitlistEntryEntity) -> WaitlistEntryEntity:
        """Persist and return the entry."""
        self._store[entity.id] = entity
        return entity

    def has_entry(self, event_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """True if the user is already in the waitlist for this event."""
        return any(e.event_id == event_id and e.user_id == user_id for e in self._store.values())

    def next_in_queue(self, event_id: uuid.UUID) -> WaitlistEntryEntity | None:
        """Return the entry with the lowest position for this event."""
        entries = [e for e in self._store.values() if e.event_id == event_id]
        return min(entries, key=lambda e: e.position) if entries else None

    def remove(self, entry_id: uuid.UUID) -> None:
        """Delete the entry by id."""
        self._store.pop(entry_id, None)

    def count_for_event(self, event_id: uuid.UUID) -> int:
        """Count all waitlist entries for this event."""
        return sum(1 for e in self._store.values() if e.event_id == event_id)


class FakeEventClient(IEventClient):
    """Returns a pre-configured EventSummary or raises EventNotFoundError."""

    def __init__(self, event: EventSummary | None = None) -> None:
        self._event = event

    def get_event(self, event_id: uuid.UUID) -> EventSummary:
        """Return the configured event or raise EventNotFoundError."""
        if self._event is None:
            raise EventNotFoundError("Event not found.")
        return self._event
