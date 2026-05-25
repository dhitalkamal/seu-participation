"""DRF serializers for participation request deserialization and response shaping."""

from __future__ import annotations

from rest_framework import serializers


class RegisterSerializer(serializers.Serializer):
    """Payload for registering for an event."""

    event_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1, default=1)
    notes = serializers.CharField(max_length=500, required=False, allow_null=True)
    networking_opt_in = serializers.BooleanField(default=False, required=False)


class CancelSerializer(serializers.Serializer):
    """Payload for cancelling a registration."""

    registration_id = serializers.UUIDField()


class CheckInSerializer(serializers.Serializer):
    """Payload for checking in a registration."""

    registration_code = serializers.CharField(max_length=20)
    method = serializers.ChoiceField(choices=["qr_code", "manual"])


class RegistrationResponseSerializer(serializers.Serializer):
    """Public shape of a registration resource."""

    id = serializers.UUIDField()
    event_id = serializers.UUIDField()
    user_id = serializers.UUIDField()
    status = serializers.CharField()
    registration_code = serializers.CharField()
    quantity = serializers.IntegerField()
    notes = serializers.CharField(allow_null=True)
    checked_in_at = serializers.DateTimeField(allow_null=True)
    cancelled_at = serializers.DateTimeField(allow_null=True)
    networking_opt_in = serializers.BooleanField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class WaitlistResponseSerializer(serializers.Serializer):
    """Public shape of a waitlist entry resource."""

    id = serializers.UUIDField()
    event_id = serializers.UUIDField()
    user_id = serializers.UUIDField()
    position = serializers.IntegerField()
    status = serializers.CharField()
    offered_at = serializers.DateTimeField(allow_null=True)
    expires_at = serializers.DateTimeField(allow_null=True)
    created_at = serializers.DateTimeField()
    waitlisted = serializers.SerializerMethodField()

    def get_waitlisted(self, obj: object) -> bool:
        """Always True -- signals to the client that registration is waitlisted."""
        return True


class CheckInResponseSerializer(serializers.Serializer):
    """Response shape for a successful check-in (F3.3.6)."""

    registration_id = serializers.UUIDField()
    event_id = serializers.UUIDField()
    checked_in_at = serializers.DateTimeField()


class VolunteerShiftResponseSerializer(serializers.Serializer):
    """Public shape of a volunteer shift resource."""

    id = serializers.UUIDField()
    event_id = serializers.UUIDField()
    user_id = serializers.UUIDField()
    role = serializers.CharField()
    start_time = serializers.DateTimeField()
    end_time = serializers.DateTimeField()
    location = serializers.CharField()
    coordinator_name = serializers.CharField()
    coordinator_phone = serializers.CharField()
    status = serializers.CharField()
    notes = serializers.CharField(allow_null=True)
    created_at = serializers.DateTimeField()


class CheckInStatsResponseSerializer(serializers.Serializer):
    """Check-in progress stats for the volunteer event dashboard."""

    event_id = serializers.UUIDField()
    total = serializers.IntegerField()
    checked_in = serializers.IntegerField()
    remaining = serializers.IntegerField()
