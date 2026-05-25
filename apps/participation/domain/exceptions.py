"""Domain errors raised by participation use cases and never swallowed silently."""

from __future__ import annotations

from apps.common.api.exceptions import DomainError


class RegistrationNotFoundError(DomainError):
    """No registration matches the given identifier."""

    http_status = 404
    code = "ERR_REGISTRATION_NOT_FOUND"


class AlreadyRegisteredError(DomainError):
    """The user already has an active registration for this event."""

    http_status = 409
    code = "ERR_REGISTRATION_ALREADY_EXISTS"


class EventAtCapacityError(DomainError):
    """The event has no remaining spots."""

    http_status = 409
    code = "ERR_EVENT_AT_CAPACITY"


class InvalidRegistrationStatusError(DomainError):
    """The requested operation is not allowed for the current registration status."""

    http_status = 422
    code = "ERR_REGISTRATION_INVALID_STATUS"


class EventNotFoundError(DomainError):
    """The event does not exist or the event-service is unreachable."""

    http_status = 404
    code = "ERR_EVENT_NOT_FOUND"


class InvalidQRTokenError(DomainError):
    """QR token is expired, tampered, or has the wrong event_id."""

    http_status = 422
    code = "ERR_QR_TOKEN_INVALID"


class WaitlistOfferNotFoundError(DomainError):
    """No waitlist offer matches the given identifier or belongs to the user."""

    http_status = 404
    code = "ERR_WAITLIST_OFFER_NOT_FOUND"


class WaitlistOfferExpiredError(DomainError):
    """The 24-hour acceptance window for this waitlist offer has passed."""

    http_status = 422
    code = "ERR_WAITLIST_OFFER_EXPIRED"


class WaitlistOfferAlreadyRespondedError(DomainError):
    """The offer was already accepted or declined."""

    http_status = 409
    code = "ERR_WAITLIST_OFFER_ALREADY_RESPONDED"
