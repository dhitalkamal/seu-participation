"""Use case: generate a PDF ticket for a registration."""

from __future__ import annotations

import uuid

from apps.participation.domain.exceptions import RegistrationNotFoundError
from apps.participation.domain.repositories import IRegistrationRepository
from apps.participation.infrastructure.ticket_pdf import generate_ticket_pdf


class GenerateTicketPdfUseCase:
    """Fetch registration data then delegate PDF rendering to the infrastructure layer.

    The use case owns no PDF knowledge - it just resolves the registration, extracts
    the fields needed, and hands them to the generator.
    """

    # placeholder event data - a real implementation would call the event-service
    # to resolve title and date; we return sensible stubs when unavailable
    _UNKNOWN_TITLE = "Sansaar Event"

    def __init__(self, registration_repo: IRegistrationRepository) -> None:
        self._reg_repo = registration_repo

    def execute(
        self,
        registration_id: uuid.UUID,
        user_id: uuid.UUID,
        attendee_name: str = "Attendee",
        event_title: str | None = None,
        event_date_iso: str | None = None,
    ) -> bytes:
        """Return raw PDF bytes for the given registration.

        Raises RegistrationNotFoundError when the registration does not exist or
        does not belong to user_id.
        """
        from datetime import datetime, timezone

        try:
            reg = self._reg_repo.get_by_id_for_user(registration_id, user_id)
        except RegistrationNotFoundError:
            raise

        # fall back to stubs when caller does not supply event metadata
        title = event_title or self._UNKNOWN_TITLE
        if event_date_iso:
            try:
                event_date = datetime.fromisoformat(event_date_iso)
            except ValueError:
                event_date = datetime.now(timezone.utc)
        else:
            event_date = datetime.now(timezone.utc)

        qr_data = f"https://sansaar.app/tickets/{reg.registration_code}"

        return generate_ticket_pdf(
            registration_code=reg.registration_code,
            event_title=title,
            event_date=event_date,
            attendee_name=attendee_name,
            qr_data=qr_data,
        )
