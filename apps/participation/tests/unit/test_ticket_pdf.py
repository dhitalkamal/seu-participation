"""Tests for PDF ticket generation (item 9)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from apps.participation.infrastructure.ticket_pdf import generate_ticket_pdf


class TestGenerateTicketPdf:
    """Tests for the generate_ticket_pdf infrastructure function."""

    def test_returns_bytes(self) -> None:
        """generate_ticket_pdf must return a bytes object."""
        result = generate_ticket_pdf(
            registration_code="ABC12345",
            event_title="Tech Conference 2026",
            event_date=datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc),
            attendee_name="Jane Doe",
            qr_data="https://sansaar.app/tickets/ABC12345",
        )
        assert isinstance(result, bytes)

    def test_returns_valid_pdf_header(self) -> None:
        """The output must start with the PDF magic bytes."""
        result = generate_ticket_pdf(
            registration_code="XYZ99999",
            event_title="Startup Expo",
            event_date=datetime(2026, 7, 15, 10, 0, tzinfo=timezone.utc),
            attendee_name="John Smith",
            qr_data="https://sansaar.app/tickets/XYZ99999",
        )
        assert result[:4] == b"%PDF"

    def test_output_under_500kb(self) -> None:
        """The generated PDF must not exceed 500 KB."""
        result = generate_ticket_pdf(
            registration_code="MAXSIZE1",
            event_title="Big Event",
            event_date=datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc),
            attendee_name="Alice Example",
            qr_data="https://sansaar.app/tickets/MAXSIZE1",
        )
        assert len(result) <= 500 * 1024, f"PDF size {len(result)} exceeds 500 KB"

    def test_non_empty_output(self) -> None:
        """The PDF must contain actual content."""
        result = generate_ticket_pdf(
            registration_code="NONEMPTY",
            event_title="Non Empty Event",
            event_date=datetime(2026, 9, 10, 8, 0, tzinfo=timezone.utc),
            attendee_name="Bob Builder",
            qr_data="https://sansaar.app/tickets/NONEMPTY",
        )
        assert len(result) > 1024, "PDF is unexpectedly small - likely empty"


class TestTicketPdfEndpoint:
    """Unit tests for the TicketPdfView using mocked use case and forced auth."""

    def _make_request(self, registration_id: uuid.UUID) -> object:
        """Build a DRF request with authentication bypassed."""
        from rest_framework.request import Request
        from rest_framework.test import APIRequestFactory

        factory = APIRequestFactory()
        django_request = factory.get(f"/api/v1/registrations/{registration_id}/ticket-pdf/")
        request = Request(django_request)
        fake_user = MagicMock()
        fake_user.id = str(uuid.uuid4())
        fake_user.is_authenticated = True
        # token attribute for optional attendee_name lookup
        fake_user.token = {}
        request._user = fake_user  # bypass JWT lookup
        return request

    def test_endpoint_returns_pdf_content_type(self) -> None:
        """GET /registrations/{id}/ticket-pdf/ must return application/pdf."""
        from apps.participation.presentation.views import TicketPdfView

        reg_id = uuid.uuid4()
        request = self._make_request(reg_id)

        with (
            patch(
                "apps.participation.application.use_cases.generate_ticket_pdf.GenerateTicketPdfUseCase"
            ) as mock_uc_class,
            patch("apps.participation.infrastructure.repositories.DjangoRegistrationRepository"),
        ):
            mock_uc = MagicMock()
            mock_uc.execute.return_value = b"%PDF-1.4 fake content here"
            mock_uc_class.return_value = mock_uc

            view = TicketPdfView()
            view.permission_classes = []
            view.authentication_classes = []
            view.kwargs = {}
            view.args = ()
            view.request = request
            view.format_kwarg = None
            view.headers = {}

            response = view.get(request, registration_id=reg_id)

        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"

    def test_endpoint_returns_404_for_missing_registration(self) -> None:
        """GET with an unknown id must return 404."""
        from apps.participation.domain.exceptions import RegistrationNotFoundError
        from apps.participation.presentation.views import TicketPdfView

        missing_id = uuid.uuid4()
        request = self._make_request(missing_id)

        with (
            patch(
                "apps.participation.application.use_cases.generate_ticket_pdf.GenerateTicketPdfUseCase"
            ) as mock_uc_class,
            patch("apps.participation.infrastructure.repositories.DjangoRegistrationRepository"),
        ):
            mock_uc = MagicMock()
            mock_uc.execute.side_effect = RegistrationNotFoundError("not found")
            mock_uc_class.return_value = mock_uc

            view = TicketPdfView()
            view.permission_classes = []
            view.authentication_classes = []
            view.kwargs = {}
            view.args = ()
            view.request = request
            view.format_kwarg = None
            view.headers = {}

            response = view.get(request, registration_id=missing_id)

        assert response.status_code == 404
