"""Django ORM models for the participation domain. Maps domain entities to the participation schema."""

from __future__ import annotations

import uuid

from django.db import models

from apps.participation.domain.entities import (
    CheckInEntity,
    RegistrationEntity,
    VolunteerShiftEntity,
    WaitlistEntryEntity,
)


class Registration(models.Model):
    """A user's registration for an event."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"
        CHECKED_IN = "checked_in", "Checked In"
        WAITLISTED = "waitlisted", "Waitlisted"
        NO_SHOW = "no_show", "No Show"

    class Meta:
        db_table = '"participation"."registration"'
        constraints = [
            models.UniqueConstraint(
                fields=["event_id", "user_id"],
                condition=~models.Q(status="cancelled"),
                name="unique_active_registration",
            )
        ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_id = models.UUIDField()
    user_id = models.UUIDField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CONFIRMED)
    registration_code = models.CharField(max_length=20, unique=True)
    quantity = models.PositiveIntegerField(default=1)
    notes = models.TextField(null=True, blank=True)
    checked_in_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def to_entity(self) -> RegistrationEntity:
        """Map this ORM row to a pure-Python RegistrationEntity."""
        return RegistrationEntity(
            id=self.id,
            event_id=self.event_id,
            user_id=self.user_id,
            status=self.status,
            registration_code=self.registration_code,
            quantity=self.quantity,
            created_at=self.created_at,
            updated_at=self.updated_at,
            checked_in_at=self.checked_in_at,
            cancelled_at=self.cancelled_at,
            notes=self.notes,
        )

    @classmethod
    def from_entity(cls, entity: RegistrationEntity) -> "Registration":
        """Build an unsaved ORM instance from a RegistrationEntity."""
        return cls(
            id=entity.id,
            event_id=entity.event_id,
            user_id=entity.user_id,
            status=entity.status,
            registration_code=entity.registration_code,
            quantity=entity.quantity,
            checked_in_at=entity.checked_in_at,
            cancelled_at=entity.cancelled_at,
            notes=entity.notes,
        )


class CheckIn(models.Model):
    """A check-in record tied one-to-one with a registration."""

    class Method(models.TextChoices):
        QR_CODE = "qr_code", "QR Code"
        MANUAL = "manual", "Manual"

    class Meta:
        db_table = '"participation"."check_in"'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    registration = models.OneToOneField(
        Registration, on_delete=models.CASCADE, related_name="check_in"
    )
    event_id = models.UUIDField()
    user_id = models.UUIDField()
    method = models.CharField(max_length=20, choices=Method.choices)
    checked_in_at = models.DateTimeField(auto_now_add=True)

    def to_entity(self) -> CheckInEntity:
        """Map this ORM row to a pure-Python CheckInEntity."""
        return CheckInEntity(
            id=self.id,
            registration_id=self.registration_id,
            event_id=self.event_id,
            user_id=self.user_id,
            method=self.method,
            checked_in_at=self.checked_in_at,
        )

    @classmethod
    def from_entity(cls, entity: CheckInEntity) -> "CheckIn":
        """Build an unsaved ORM instance from a CheckInEntity."""
        return cls(
            id=entity.id,
            registration_id=entity.registration_id,
            event_id=entity.event_id,
            user_id=entity.user_id,
            method=entity.method,
        )


class WaitlistEntry(models.Model):
    """A queued position for a user waiting for a spot at a full event."""

    class Meta:
        db_table = '"participation"."waitlist_entry"'
        constraints = [
            models.UniqueConstraint(
                fields=["event_id", "user_id"],
                name="unique_waitlist_entry",
            )
        ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_id = models.UUIDField()
    user_id = models.UUIDField()
    position = models.PositiveIntegerField()
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def to_entity(self) -> WaitlistEntryEntity:
        """Map this ORM row to a pure-Python WaitlistEntryEntity."""
        return WaitlistEntryEntity(
            id=self.id,
            event_id=self.event_id,
            user_id=self.user_id,
            position=self.position,
            created_at=self.created_at,
            expires_at=self.expires_at,
        )

    @classmethod
    def from_entity(cls, entity: WaitlistEntryEntity) -> "WaitlistEntry":
        """Build an unsaved ORM instance from a WaitlistEntryEntity."""
        return cls(
            id=entity.id,
            event_id=entity.event_id,
            user_id=entity.user_id,
            position=entity.position,
            expires_at=entity.expires_at,
        )


class VolunteerShift(models.Model):
    """A volunteer's assigned shift for a specific event."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    class Meta:
        db_table = '"participation"."volunteer_shift"'
        constraints = [
            models.UniqueConstraint(
                fields=["event_id", "user_id"],
                condition=~models.Q(status="cancelled"),
                name="unique_active_volunteer_shift",
            )
        ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_id = models.UUIDField(db_index=True)
    user_id = models.UUIDField(db_index=True)
    role = models.CharField(max_length=100)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    location = models.CharField(max_length=200)
    coordinator_name = models.CharField(max_length=100)
    coordinator_phone = models.CharField(max_length=30)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CONFIRMED)
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def to_entity(self) -> VolunteerShiftEntity:
        """Map this ORM row to a pure-Python VolunteerShiftEntity."""
        return VolunteerShiftEntity(
            id=self.id,
            event_id=self.event_id,
            user_id=self.user_id,
            role=self.role,
            start_time=self.start_time,
            end_time=self.end_time,
            location=self.location,
            coordinator_name=self.coordinator_name,
            coordinator_phone=self.coordinator_phone,
            status=self.status,
            notes=self.notes,
            created_at=self.created_at,
        )
