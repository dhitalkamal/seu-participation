"""Abstract repository and client interfaces for the participation module."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from apps.participation.domain.entities import (
    CheckInEntity,
    EventSummary,
    RegistrationEntity,
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
    def has_entry(self, event_id: uuid.UUID, user_id: uuid.UUID) -> bool: ...

    @abstractmethod
    def next_in_queue(self, event_id: uuid.UUID) -> WaitlistEntryEntity | None: ...

    @abstractmethod
    def remove(self, entry_id: uuid.UUID) -> None: ...

    @abstractmethod
    def count_for_event(self, event_id: uuid.UUID) -> int: ...


class IEventClient(ABC):
    """Port for fetching event data from the event-service."""

    @abstractmethod
    def get_event(self, event_id: uuid.UUID) -> EventSummary: ...
