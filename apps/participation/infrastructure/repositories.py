"""Concrete repository implementations backed by the Django ORM."""

from __future__ import annotations

import uuid
from datetime import datetime

from apps.participation.domain.entities import (
    CheckInEntity,
    RegistrationEntity,
    WaitlistEntryEntity,
)
from apps.participation.domain.exceptions import RegistrationNotFoundError
from apps.participation.domain.repositories import (
    ICheckInRepository,
    IParticipationContextRepository,
    IRegistrationRepository,
    IWaitlistRepository,
)
from apps.participation.infrastructure.models import (
    CheckIn,
    EventParticipationContext,
    Registration,
    WaitlistEntry,
)


class DjangoRegistrationRepository(IRegistrationRepository):
    """Persists Registration entities using the Django ORM."""

    def create(self, entity: RegistrationEntity) -> RegistrationEntity:
        """Persist a new registration and return the saved entity."""
        obj = Registration.from_entity(entity)
        obj.save(using="default")
        return obj.to_entity()

    def get_by_id(self, registration_id: uuid.UUID) -> RegistrationEntity:
        """Fetch by id. Raises RegistrationNotFoundError if absent."""
        try:
            return Registration.objects.get(id=registration_id).to_entity()
        except Registration.DoesNotExist:
            raise RegistrationNotFoundError("Registration not found.")

    def get_by_code(self, code: str) -> RegistrationEntity:
        """Fetch by registration_code. Raises RegistrationNotFoundError if absent."""
        try:
            return Registration.objects.get(registration_code=code).to_entity()
        except Registration.DoesNotExist:
            raise RegistrationNotFoundError("Registration not found.")

    def has_active(self, event_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """True if a non-cancelled registration exists for this (event, user) pair."""
        return (
            Registration.objects.filter(event_id=event_id, user_id=user_id)
            .exclude(status="cancelled")
            .exists()
        )

    def update(self, entity: RegistrationEntity) -> RegistrationEntity:
        """Fetch the existing row, update mutable fields, and save."""
        obj = Registration.objects.get(id=entity.id)
        obj.status = entity.status
        obj.checked_in_at = entity.checked_in_at
        obj.cancelled_at = entity.cancelled_at
        obj.save()
        return obj.to_entity()

    def list_by_user(self, user_id: object) -> list[RegistrationEntity]:
        """Return all registrations for this user, newest first."""
        return [
            obj.to_entity()
            for obj in Registration.objects.filter(user_id=user_id).order_by("-created_at")
        ]

    def get_by_id_for_user(
        self, registration_id: uuid.UUID, user_id: uuid.UUID
    ) -> RegistrationEntity:
        """Fetch by id enforcing ownership. Raises RegistrationNotFoundError if absent."""
        try:
            return Registration.objects.get(id=registration_id, user_id=user_id).to_entity()
        except Registration.DoesNotExist:
            raise RegistrationNotFoundError("Registration not found.")


class DjangoCheckInRepository(ICheckInRepository):
    """Persists CheckIn entities using the Django ORM."""

    def create(self, entity: CheckInEntity) -> CheckInEntity:
        """Persist a new check-in and return the saved entity."""
        obj = CheckIn.from_entity(entity)
        obj.save(using="default")
        return obj.to_entity()

    def exists_for_registration(self, registration_id: uuid.UUID) -> bool:
        """True if a check-in already exists for this registration."""
        return CheckIn.objects.filter(registration_id=registration_id).exists()


class DjangoWaitlistRepository(IWaitlistRepository):
    """Persists WaitlistEntry entities using the Django ORM."""

    def add(self, entity: WaitlistEntryEntity) -> WaitlistEntryEntity:
        """Persist a new waitlist entry and return the saved entity."""
        obj = WaitlistEntry.from_entity(entity)
        obj.save(using="default")
        return obj.to_entity()

    def get_by_id(self, entry_id: uuid.UUID) -> WaitlistEntryEntity | None:
        """Return the entry entity or None if not found."""
        try:
            return WaitlistEntry.objects.get(id=entry_id).to_entity()
        except WaitlistEntry.DoesNotExist:
            return None

    def has_entry(self, event_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """True if the user is already in the waitlist for this event."""
        return WaitlistEntry.objects.filter(event_id=event_id, user_id=user_id).exists()

    def next_pending_in_queue(self, event_id: uuid.UUID) -> WaitlistEntryEntity | None:
        """Return the pending entry with the lowest position, or None if none exist."""
        obj = (
            WaitlistEntry.objects.filter(event_id=event_id, status="pending")
            .order_by("position")
            .first()
        )
        return obj.to_entity() if obj else None

    def update(self, entity: WaitlistEntryEntity) -> WaitlistEntryEntity:
        """Fetch the existing row, update mutable fields, and save."""
        obj = WaitlistEntry.objects.get(id=entity.id)
        obj.status = entity.status
        obj.offered_at = entity.offered_at
        obj.expires_at = entity.expires_at
        obj.save()
        return obj.to_entity()

    def remove(self, entry_id: uuid.UUID) -> None:
        """Delete the waitlist entry by id."""
        WaitlistEntry.objects.filter(id=entry_id).delete()

    def count_for_event(self, event_id: uuid.UUID) -> int:
        """Count all waitlist entries for this event (used for position calculation)."""
        return WaitlistEntry.objects.filter(event_id=event_id).count()

    def list_offered_before(self, cutoff: datetime) -> list[WaitlistEntryEntity]:
        """Return all offered entries whose expires_at is at or before cutoff."""
        return [
            obj.to_entity()
            for obj in WaitlistEntry.objects.filter(status="offered", expires_at__lte=cutoff)
        ]


class DjangoVolunteerShiftRepository:
    """ORM-backed volunteer shift repository."""

    def list_for_user(self, user_id: uuid.UUID) -> list:
        """Return all shifts for a volunteer ordered by start time."""
        from apps.participation.infrastructure.models import VolunteerShift

        return [
            s.to_entity()
            for s in VolunteerShift.objects.filter(user_id=user_id).order_by("start_time")
        ]


class DjangoRegistrationStatsRepository:
    """ORM-backed stats repository for the volunteer dashboard."""

    def count_for_event(self, event_id: uuid.UUID) -> int:
        """Total confirmed registrations for an event."""
        return Registration.objects.filter(
            event_id=event_id,
            status__in=["confirmed", "checked_in"],
        ).count()

    def count_checked_in_for_event(self, event_id: uuid.UUID) -> int:
        """How many attendees have been checked in for an event."""
        return Registration.objects.filter(event_id=event_id, status="checked_in").count()


class DjangoParticipationContextRepository(IParticipationContextRepository):
    """Persists EventParticipationContext records using the Django ORM."""

    def has_context(self, event_id: uuid.UUID, user_id: uuid.UUID, participation_type: str) -> bool:
        """True if a context row exists with the given type for this (event, user) pair."""
        return EventParticipationContext.objects.filter(
            event_id=event_id, user_id=user_id, participation_type=participation_type
        ).exists()

    def get_context(self, event_id: uuid.UUID, user_id: uuid.UUID) -> str | None:
        """Return the participation_type string or None if no row exists."""
        obj = EventParticipationContext.objects.filter(event_id=event_id, user_id=user_id).first()
        return obj.participation_type if obj else None

    def set_context(self, event_id: uuid.UUID, user_id: uuid.UUID, participation_type: str) -> None:
        """Upsert the participation context for this (event, user) pair."""
        EventParticipationContext.objects.update_or_create(
            event_id=event_id,
            user_id=user_id,
            defaults={"participation_type": participation_type},
        )

    def delete_context(self, event_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Remove the participation context row for this (event, user) pair."""
        EventParticipationContext.objects.filter(event_id=event_id, user_id=user_id).delete()
