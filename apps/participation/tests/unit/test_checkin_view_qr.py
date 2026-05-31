"""Unit tests for CheckInView encrypted QR token auto-detection."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from rest_framework.test import APIRequestFactory

from apps.participation.presentation.views import CheckInView

_VALIDATE_PATH = "apps.participation.presentation.views._VALIDATE_QR_UC"
_CHECKIN_UC_PATH = "apps.participation.presentation.views._CHECKIN_UC"
_REG_REPO_PATH = "apps.participation.presentation.views._REG_REPO"
_CHECKIN_REPO_PATH = "apps.participation.presentation.views._CHECKIN_REPO"


def _view() -> object:
    """Return the CheckInView callable."""
    return CheckInView.as_view()


def _post_request(body: dict) -> object:
    """Build a POST request with a mock authenticated user via force_authenticate."""
    factory = APIRequestFactory()
    request = factory.post("/participation/api/v1/check-in/", body, format="json")
    # bypass JWT authentication by injecting a fake authenticated user
    request._force_auth_user = MagicMock()
    request._force_auth_user.is_authenticated = True
    request._force_auth_user.id = str(uuid.uuid4())
    return request


def _make_checkin_result() -> MagicMock:
    """Build a mock CheckInEntity-like result object."""
    result = MagicMock()
    result.registration_id = uuid.uuid4()
    result.event_id = uuid.uuid4()
    result.checked_in_at = datetime.now(timezone.utc)
    return result


def test_short_code_bypasses_qr_decrypt():
    """A plain registration_code (<=20 chars) goes directly to CheckInUseCase."""
    mock_checkin_uc = MagicMock()
    mock_checkin_uc.return_value.execute.return_value = _make_checkin_result()

    request = _post_request({"registration_code": "ABC12345", "method": "manual"})

    with (
        patch(_CHECKIN_UC_PATH, mock_checkin_uc),
        patch(_REG_REPO_PATH, MagicMock()),
        patch(_CHECKIN_REPO_PATH, MagicMock()),
    ):
        response = _view()(request)

    assert response.status_code == 200
    call_kwargs = mock_checkin_uc.return_value.execute.call_args.kwargs
    assert call_kwargs["registration_code"] == "ABC12345"


def test_long_code_decrypts_qr_token_and_uses_extracted_code():
    """An encrypted QR token (>20 chars) is decrypted and the inner code is used."""
    encrypted_token = "A" * 100
    inner_code = "DECRYPTED"
    event_id = uuid.uuid4()

    mock_validate_uc = MagicMock()
    mock_validate_uc.return_value.execute.return_value = {
        "registration_code": inner_code,
        "registration_id": str(uuid.uuid4()),
        "event_id": str(event_id),
        "user_id": str(uuid.uuid4()),
    }

    mock_checkin_uc = MagicMock()
    mock_checkin_uc.return_value.execute.return_value = _make_checkin_result()

    request = _post_request(
        {
            "registration_code": encrypted_token,
            "method": "qr_code",
            "event_id": str(event_id),
        }
    )

    with (
        patch(_VALIDATE_PATH, mock_validate_uc),
        patch(_CHECKIN_UC_PATH, mock_checkin_uc),
        patch(_REG_REPO_PATH, MagicMock()),
        patch(_CHECKIN_REPO_PATH, MagicMock()),
    ):
        response = _view()(request)

    assert response.status_code == 200
    mock_validate_uc.return_value.execute.assert_called_once_with(
        token=encrypted_token, event_id=event_id
    )
    call_kwargs = mock_checkin_uc.return_value.execute.call_args.kwargs
    assert call_kwargs["registration_code"] == inner_code


def test_long_code_without_event_id_returns_400():
    """Encrypted token without event_id returns 400."""
    request = _post_request({"registration_code": "B" * 100, "method": "qr_code"})

    with (
        patch(_REG_REPO_PATH, MagicMock()),
        patch(_CHECKIN_REPO_PATH, MagicMock()),
    ):
        response = _view()(request)

    assert response.status_code == 400
    assert response.data["error"]["code"] == "ERR_CHECKIN_EVENT_ID_REQUIRED"


def test_tampered_qr_token_returns_400():
    """A tampered or invalid QR token returns 400."""
    from apps.participation.domain.exceptions import InvalidQRTokenError

    event_id = uuid.uuid4()

    mock_validate_uc = MagicMock()
    mock_validate_uc.return_value.execute.side_effect = InvalidQRTokenError("token tampered")

    request = _post_request(
        {
            "registration_code": "C" * 100,
            "method": "qr_code",
            "event_id": str(event_id),
        }
    )

    with (
        patch(_VALIDATE_PATH, mock_validate_uc),
        patch(_REG_REPO_PATH, MagicMock()),
        patch(_CHECKIN_REPO_PATH, MagicMock()),
    ):
        response = _view()(request)

    assert response.status_code == 400
    assert response.data["error"]["code"] == "ERR_CHECKIN_INVALID_QR"
