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
    networking_opt_in: bool = False


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
    status: str = "pending"
    offered_at: datetime | None = None
    expires_at: datetime | None = None


@dataclass(slots=True)
class VolunteerShiftEntity:
    """A volunteer's assigned shift for a specific event."""

    id: uuid.UUID
    event_id: uuid.UUID
    user_id: uuid.UUID
    role: str
    start_time: datetime
    end_time: datetime
    location: str
    coordinator_name: str
    coordinator_phone: str
    status: str
    notes: str | None
    created_at: datetime


@dataclass(slots=True)
class QREncryptionKeyEntity:
    """AES-256 encryption key for a specific event, rotated every 24 hours."""

    id: uuid.UUID
    event_id: uuid.UUID
    key_hex: str
    valid_from: datetime
    expires_at: datetime
    is_active: bool


@dataclass(slots=True)
class PassportEntryEntity:
    """A single attendance or volunteer record in a user's Verified Event Passport."""

    event_id: uuid.UUID
    event_name: str
    role: str
    status: str
    attended_at: datetime
    certificate_issued: bool
    certificate_url: str | None = None
    volunteer_hours: float | None = None


@dataclass(slots=True)
class PassportEntity:
    """A user's portable Verified Event Passport - signed aggregate of participation history."""

    user_id: uuid.UUID
    entries: list
    generated_at: datetime
    signature: str


@dataclass(slots=True)
class TicketTierEntity:
    """A named tier within an event (e.g. General, VIP, Early Bird, Comp)."""

    id: uuid.UUID
    event_id: uuid.UUID
    name: str
    tier_type: str
    price: str
    capacity: int
    sold_count: int
    description: str
    created_at: datetime
    is_active: bool = True

    @property
    def is_at_capacity(self) -> bool:
        """True when no spots remain in this tier."""
        return self.sold_count >= self.capacity

    @property
    def available_spots(self) -> int:
        """How many seats are still available in this tier."""
        return self.capacity - self.sold_count


@dataclass(slots=True)
class CustomFormFieldEntity:
    """A custom question added to an event registration form."""

    id: uuid.UUID
    event_id: uuid.UUID
    label: str
    field_type: str
    is_required: bool
    options: list
    position: int
    created_at: datetime


@dataclass(slots=True)
class RegistrationAnswerEntity:
    """An attendee's answer to a custom form question."""

    id: uuid.UUID
    registration_id: uuid.UUID
    field_id: uuid.UUID
    value: str


@dataclass(slots=True)
class TicketTransferEntity:
    """A pending or completed ticket ownership transfer between two users."""

    id: uuid.UUID
    registration_id: uuid.UUID
    from_user_id: uuid.UUID
    to_email: str
    token: uuid.UUID
    status: str  # pending / completed / cancelled / expired
    created_at: datetime
    expires_at: datetime


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
