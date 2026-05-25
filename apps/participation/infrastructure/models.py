"""Django ORM models for the participation domain."""

from __future__ import annotations

import uuid

from django.db import models

from apps.participation.domain.entities import (
    CheckInEntity,
    RegistrationEntity,
    TicketTransferEntity,
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
    networking_opt_in = models.BooleanField(default=False)
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
            networking_opt_in=self.networking_opt_in,
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
            networking_opt_in=entity.networking_opt_in,
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

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        OFFERED = "offered", "Offered"
        EXPIRED = "expired", "Expired"

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
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    offered_at = models.DateTimeField(null=True, blank=True)
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
            status=self.status,
            offered_at=self.offered_at,
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
            status=entity.status,
            offered_at=entity.offered_at,
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


class TicketTier(models.Model):
    """A named pricing tier for an event (General, VIP, Early Bird, Comp)."""

    class TierType(models.TextChoices):
        GENERAL = "general", "General"
        VIP = "vip", "VIP"
        EARLY_BIRD = "early_bird", "Early Bird"
        COMP = "comp", "Complimentary"

    class Meta:
        db_table = '"participation"."ticket_tier"'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_id = models.UUIDField(db_index=True)
    name = models.CharField(max_length=100)
    tier_type = models.CharField(max_length=20, choices=TierType.choices, default=TierType.GENERAL)
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    capacity = models.PositiveIntegerField()
    sold_count = models.PositiveIntegerField(default=0)
    description = models.CharField(max_length=500, blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def to_entity(self) -> object:
        """Map to domain entity."""
        from apps.participation.domain.entities import TicketTierEntity  # noqa: PLC0415

        return TicketTierEntity(
            id=self.id,
            event_id=self.event_id,
            name=self.name,
            tier_type=self.tier_type,
            price=str(self.price),
            capacity=self.capacity,
            sold_count=self.sold_count,
            description=self.description,
            is_active=self.is_active,
            created_at=self.created_at,
        )


class CustomFormField(models.Model):
    """A custom question on an event registration form (up to 20 per event)."""

    class FieldType(models.TextChoices):
        TEXT = "text", "Short text"
        TEXTAREA = "textarea", "Long text"
        SELECT = "select", "Dropdown"
        CHECKBOX = "checkbox", "Checkbox"
        RADIO = "radio", "Radio buttons"

    class Meta:
        db_table = '"participation"."custom_form_field"'
        ordering = ["position"]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_id = models.UUIDField(db_index=True)
    label = models.CharField(max_length=255)
    field_type = models.CharField(max_length=20, choices=FieldType.choices, default=FieldType.TEXT)
    is_required = models.BooleanField(default=False)
    options = models.JSONField(default=list, blank=True)
    position = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)


class RegistrationAnswer(models.Model):
    """An attendee answer to a custom form field."""

    class Meta:
        db_table = '"participation"."registration_answer"'
        constraints = [
            models.UniqueConstraint(
                fields=["registration", "field"],
                name="unique_registration_answer",
            )
        ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    registration = models.ForeignKey(Registration, on_delete=models.CASCADE, related_name="answers")
    field = models.ForeignKey(CustomFormField, on_delete=models.CASCADE, related_name="answers")
    value = models.TextField()


class EventParticipationContext(models.Model):
    """Records whether a user is participating in an event as attendee or volunteer."""

    class Meta:
        db_table = '"participation"."event_participation_context"'
        constraints = [
            models.UniqueConstraint(
                fields=["event_id", "user_id"],
                name="unique_event_participation_context",
            )
        ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_id = models.UUIDField(db_index=True)
    user_id = models.UUIDField(db_index=True)
    participation_type = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)


class TicketTransfer(models.Model):
    """A pending or completed transfer of ticket ownership between two users."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"

    class Meta:
        db_table = '"participation"."ticket_transfer"'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    registration = models.ForeignKey(
        Registration, on_delete=models.CASCADE, related_name="transfers"
    )
    from_user_id = models.UUIDField(db_index=True)
    to_email = models.EmailField()
    token = models.UUIDField(unique=True, default=uuid.uuid4)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def to_entity(self) -> TicketTransferEntity:
        """Map this ORM row to a pure-Python TicketTransferEntity."""
        return TicketTransferEntity(
            id=self.id,
            registration_id=self.registration_id,
            from_user_id=self.from_user_id,
            to_email=self.to_email,
            token=self.token,
            status=self.status,
            created_at=self.created_at,
            expires_at=self.expires_at,
        )

    @classmethod
    def from_entity(cls, entity: TicketTransferEntity) -> "TicketTransfer":
        """Build an unsaved ORM instance from a TicketTransferEntity."""
        return cls(
            id=entity.id,
            registration_id=entity.registration_id,
            from_user_id=entity.from_user_id,
            to_email=entity.to_email,
            token=entity.token,
            status=entity.status,
            expires_at=entity.expires_at,
        )
