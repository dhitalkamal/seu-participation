"""Pure Python domain entities for the participation module with no framework dependencies."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class RegistrationEntity:
    """A single event registration owned by a user."""

    id: uuid.UUID
    event_id: uuid.UUID
    user_id: uuid.UUID
    status: str
    registration_code: str
    quantity: int
    created_at: datetime
    updated_at: datetime
    checked_in_at: datetime | None = None
    cancelled_at: datetime | None = None
    notes: str | None = None


@dataclass(slots=True)
class CheckInEntity:
    """A check-in record tied one-to-one with a registration."""

    id: uuid.UUID
    registration_id: uuid.UUID
    event_id: uuid.UUID
    user_id: uuid.UUID
    method: str
    checked_in_at: datetime


@dataclass(slots=True)
class WaitlistEntryEntity:
    """A queued position for a user waiting for a spot at a full event."""

    id: uuid.UUID
    event_id: uuid.UUID
    user_id: uuid.UUID
    position: int
    created_at: datetime
    expires_at: datetime | None = None


@dataclass(frozen=True)
class EventSummary:
    """Read-only snapshot of an event fetched from the event-service."""

    event_id: uuid.UUID
    capacity: int
    registered_count: int

    @property
    def is_at_capacity(self) -> bool:
        """True when no spots remain."""
        return self.registered_count >= self.capacity
