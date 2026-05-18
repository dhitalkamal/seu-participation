"""Unit tests for AES-256 offline QR ticketing."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest


def _now() -> datetime:
    return datetime.now(timezone.utc)


def test_generate_qr_token_returns_encrypted_string():
    """GenerateQRTokenUseCase returns a non-empty encrypted token string."""
    from apps.participation.application.use_cases.generate_qr_token import GenerateQRTokenUseCase
    from apps.participation.tests.unit.fakes import make_registration

    reg = make_registration(status="confirmed")
    result = GenerateQRTokenUseCase().execute(registration=reg)
    assert isinstance(result, str)
    assert len(result) > 0


def test_validate_qr_token_succeeds_for_valid_token():
    """ValidateQRTokenUseCase returns the registration_id for a valid token."""
    from apps.participation.application.use_cases.generate_qr_token import GenerateQRTokenUseCase
    from apps.participation.application.use_cases.validate_qr_token import ValidateQRTokenUseCase
    from apps.participation.tests.unit.fakes import make_registration

    reg = make_registration(status="confirmed")
    token = GenerateQRTokenUseCase().execute(registration=reg)
    payload = ValidateQRTokenUseCase().execute(token=token, event_id=reg.event_id)
    assert payload["registration_id"] == str(reg.id)
    assert payload["user_id"] == str(reg.user_id)


def test_validate_qr_token_wrong_event_raises():
    """ValidateQRTokenUseCase raises InvalidQRTokenError when event_id does not match."""
    from apps.participation.application.use_cases.generate_qr_token import GenerateQRTokenUseCase
    from apps.participation.application.use_cases.validate_qr_token import ValidateQRTokenUseCase
    from apps.participation.domain.exceptions import InvalidQRTokenError
    from apps.participation.tests.unit.fakes import make_registration

    reg = make_registration(status="confirmed")
    token = GenerateQRTokenUseCase().execute(registration=reg)
    with pytest.raises(InvalidQRTokenError):
        ValidateQRTokenUseCase().execute(token=token, event_id=uuid.uuid4())


def test_validate_qr_token_tampered_raises():
    """Tampered token raises InvalidQRTokenError."""
    from apps.participation.application.use_cases.validate_qr_token import ValidateQRTokenUseCase
    from apps.participation.domain.exceptions import InvalidQRTokenError

    with pytest.raises(InvalidQRTokenError):
        ValidateQRTokenUseCase().execute(token="notavalidtoken", event_id=uuid.uuid4())


def test_validate_qr_token_expired_raises():
    """Token with past expiry raises InvalidQRTokenError."""
    from apps.participation.application.use_cases.generate_qr_token import GenerateQRTokenUseCase
    from apps.participation.application.use_cases.validate_qr_token import ValidateQRTokenUseCase
    from apps.participation.domain.exceptions import InvalidQRTokenError
    from apps.participation.tests.unit.fakes import make_registration

    reg = make_registration(status="confirmed")
    # generate token that expired 1 hour ago
    token = GenerateQRTokenUseCase().execute(
        registration=reg,
        expires_at=_now() - timedelta(hours=1),
    )
    with pytest.raises(InvalidQRTokenError):
        ValidateQRTokenUseCase().execute(token=token, event_id=reg.event_id)
