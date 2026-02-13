"""Tests for GenerateTicketPdfUseCase (item 9)."""

from __future__ import annotations

import uuid

import pytest

from apps.participation.domain.exceptions import RegistrationNotFoundError
from apps.participation.tests.unit.fakes import FakeRegistrationRepository, make_registration


class TestGenerateTicketPdfUseCase:
    """Unit tests for GenerateTicketPdfUseCase using in-memory fakes."""

    def test_raises_when_registration_not_found(self) -> None:
        """Should raise RegistrationNotFoundError for an unknown id."""
        from apps.participation.application.use_cases.generate_ticket_pdf import (
            GenerateTicketPdfUseCase,
        )

        repo = FakeRegistrationRepository()
        uc = GenerateTicketPdfUseCase(repo)
        user_id = uuid.uuid4()

        with pytest.raises(RegistrationNotFoundError):
            uc.execute(registration_id=uuid.uuid4(), user_id=user_id)

    def test_raises_when_registration_belongs_to_other_user(self) -> None:
        """Should raise RegistrationNotFoundError when user_id does not match."""
        from apps.participation.application.use_cases.generate_ticket_pdf import (
            GenerateTicketPdfUseCase,
        )

        owner = uuid.uuid4()
        reg = make_registration(user_id=owner, registration_code="OWNED001")
        repo = FakeRegistrationRepository([reg])
        uc = GenerateTicketPdfUseCase(repo)

        with pytest.raises(RegistrationNotFoundError):
            uc.execute(registration_id=reg.id, user_id=uuid.uuid4())

    def test_returns_bytes_for_valid_registration(self) -> None:
        """Should return bytes when the registration exists and belongs to user."""
        from apps.participation.application.use_cases.generate_ticket_pdf import (
            GenerateTicketPdfUseCase,
        )

        owner = uuid.uuid4()
        reg = make_registration(user_id=owner, registration_code="PDFOK001")
        repo = FakeRegistrationRepository([reg])
        uc = GenerateTicketPdfUseCase(repo)

        result = uc.execute(
            registration_id=reg.id,
            user_id=owner,
            attendee_name="Test User",
            event_title="Test Event",
            event_date_iso="2026-06-01T09:00:00+00:00",
        )
        assert isinstance(result, bytes)
        assert result[:4] == b"%PDF"

    def test_falls_back_to_default_title_when_not_supplied(self) -> None:
        """Should use the fallback title when event_title is None."""
        from apps.participation.application.use_cases.generate_ticket_pdf import (
            GenerateTicketPdfUseCase,
        )

        owner = uuid.uuid4()
        reg = make_registration(user_id=owner, registration_code="PDFTITLE")
        repo = FakeRegistrationRepository([reg])
        uc = GenerateTicketPdfUseCase(repo)

        # should not raise
        result = uc.execute(registration_id=reg.id, user_id=owner)
        assert isinstance(result, bytes)
