"""Abstract repository and client interfaces for the participation module."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime

from apps.participation.domain.entities import (
    CheckInEntity,
    EventSummary,
    RegistrationEntity,
    TicketTransferEntity,
    WaitlistEntryEntity,
)


class IRegistrationRepository(ABC):
    """Persistence contract for Registration aggregates."""

    @abstractmethod
    def create(self, entity: RegistrationEntity) -> RegistrationEntity: ...

    @abstractmethod
    def get_by_id(self, registration_id: uuid.UUID) -> RegistrationEntity: ...

    @abstractmethod
    def get_by_code(self, code: str) -> RegistrationEntity: ...

    @abstractmethod
    def has_active(self, event_id: uuid.UUID, user_id: uuid.UUID) -> bool: ...

    @abstractmethod
    def update(self, entity: RegistrationEntity) -> RegistrationEntity: ...

    @abstractmethod
    def list_by_user(self, user_id: uuid.UUID) -> list[RegistrationEntity]: ...

    @abstractmethod
    def get_by_id_for_user(
        self, registration_id: uuid.UUID, user_id: uuid.UUID
    ) -> RegistrationEntity: ...


class ICheckInRepository(ABC):
    """Persistence contract for CheckIn records."""

    @abstractmethod
    def create(self, entity: CheckInEntity) -> CheckInEntity: ...

    @abstractmethod
    def exists_for_registration(self, registration_id: uuid.UUID) -> bool: ...


class IWaitlistRepository(ABC):
    """Persistence contract for WaitlistEntry records."""

    @abstractmethod
    def add(self, entity: WaitlistEntryEntity) -> WaitlistEntryEntity: ...

    @abstractmethod
    def get_by_id(self, entry_id: uuid.UUID) -> WaitlistEntryEntity | None: ...

    @abstractmethod
    def has_entry(self, event_id: uuid.UUID, user_id: uuid.UUID) -> bool: ...

    @abstractmethod
    def next_pending_in_queue(self, event_id: uuid.UUID) -> WaitlistEntryEntity | None: ...

    @abstractmethod
    def update(self, entity: WaitlistEntryEntity) -> WaitlistEntryEntity: ...

    @abstractmethod
    def remove(self, entry_id: uuid.UUID) -> None: ...

    @abstractmethod
    def count_for_event(self, event_id: uuid.UUID) -> int: ...

    @abstractmethod
    def list_offered_before(self, cutoff: datetime) -> list[WaitlistEntryEntity]: ...


class IEventClient(ABC):
    """Port for fetching event data from the event-service."""

    @abstractmethod
    def get_event(self, event_id: uuid.UUID) -> EventSummary: ...


class IEventPublisher(ABC):
    """Port for publishing domain events to the message broker."""

    @abstractmethod
    def publish(self, *, routing_key: str, payload: dict) -> None: ...


class IParticipationContextRepository(ABC):
    """Tracks which capacity (attendee vs volunteer) each user holds for an event."""

    @abstractmethod
    def has_context(
        self, event_id: uuid.UUID, user_id: uuid.UUID, participation_type: str
    ) -> bool: ...

    @abstractmethod
    def get_context(self, event_id: uuid.UUID, user_id: uuid.UUID) -> str | None: ...

    @abstractmethod
    def set_context(
        self, event_id: uuid.UUID, user_id: uuid.UUID, participation_type: str
    ) -> None: ...

    @abstractmethod
    def delete_context(self, event_id: uuid.UUID, user_id: uuid.UUID) -> None: ...


class ITicketTransferRepository(ABC):
    """Persistence contract for TicketTransfer records."""

    @abstractmethod
    def create(self, entity: TicketTransferEntity) -> TicketTransferEntity: ...

    @abstractmethod
    def get_by_token(self, token: uuid.UUID) -> TicketTransferEntity | None: ...

    @abstractmethod
    def get_by_id(self, transfer_id: uuid.UUID) -> TicketTransferEntity | None: ...

    @abstractmethod
    def get_pending_for_registration(
        self, registration_id: uuid.UUID
    ) -> TicketTransferEntity | None: ...

    @abstractmethod
    def update(self, entity: TicketTransferEntity) -> TicketTransferEntity: ...
