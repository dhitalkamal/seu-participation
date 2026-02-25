"""Unit tests for GenerateWalletPassUseCase."""

from __future__ import annotations

import uuid

import pytest

from apps.participation.application.use_cases.generate_wallet_pass import GenerateWalletPassUseCase
from apps.participation.domain.entities import RegistrationEntity, WalletPassEntity
from apps.participation.domain.exceptions import (
    InvalidRegistrationStatusError,
    RegistrationNotFoundError,
)
from apps.participation.domain.repositories import IWalletPassGenerator
from apps.participation.tests.unit.fakes import FakeRegistrationRepository, make_registration


class StubPassGenerator(IWalletPassGenerator):
    """Returns a minimal WalletPassEntity for the given pass_type."""

    def __init__(self, pass_type: str) -> None:
        self._pass_type = pass_type

    def generate(self, registration: RegistrationEntity) -> WalletPassEntity:
        """Return a stub pass entity."""
        from datetime import datetime, timezone

        return WalletPassEntity(
            registration_id=registration.id,
            user_id=registration.user_id,
            event_id=registration.event_id,
            pass_type=self._pass_type,
            payload=f'{{"type": "{self._pass_type}", "code": "{registration.registration_code}"}}',
            generated_at=datetime.now(timezone.utc),
        )


def _uc(repo: FakeRegistrationRepository) -> GenerateWalletPassUseCase:
    return GenerateWalletPassUseCase(
        registration_repo=repo,
        generators={
            "apple": StubPassGenerator("apple"),
            "google": StubPassGenerator("google"),
        },
    )


def test_generate_apple_pass_returns_entity() -> None:
    """Generates an apple WalletPassEntity for a confirmed registration."""
    reg = make_registration(status="confirmed")
    repo = FakeRegistrationRepository([reg])

    result = _uc(repo).execute(
        registration_id=reg.id,
        user_id=reg.user_id,
        pass_type="apple",
    )

    assert isinstance(result, WalletPassEntity)
    assert result.pass_type == "apple"
    assert result.registration_id == reg.id
    assert result.user_id == reg.user_id
    assert result.event_id == reg.event_id


def test_generate_google_pass_returns_entity() -> None:
    """Generates a google WalletPassEntity for a confirmed registration."""
    reg = make_registration(status="confirmed")
    repo = FakeRegistrationRepository([reg])

    result = _uc(repo).execute(
        registration_id=reg.id,
        user_id=reg.user_id,
        pass_type="google",
    )

    assert result.pass_type == "google"


def test_pass_payload_is_non_empty_string() -> None:
    """The generated payload is a non-empty string."""
    reg = make_registration(status="confirmed")
    repo = FakeRegistrationRepository([reg])

    result = _uc(repo).execute(
        registration_id=reg.id,
        user_id=reg.user_id,
        pass_type="apple",
    )

    assert isinstance(result.payload, str)
    assert len(result.payload) > 0


def test_invalid_pass_type_raises_value_error() -> None:
    """ValueError when pass_type is not apple or google."""
    reg = make_registration(status="confirmed")
    repo = FakeRegistrationRepository([reg])

    with pytest.raises(ValueError, match="pass_type"):
        _uc(repo).execute(
            registration_id=reg.id,
            user_id=reg.user_id,
            pass_type="samsung",
        )


def test_non_confirmed_registration_raises_invalid_status() -> None:
    """InvalidRegistrationStatusError when registration is not confirmed."""
    reg = make_registration(status="cancelled")
    repo = FakeRegistrationRepository([reg])

    with pytest.raises(InvalidRegistrationStatusError):
        _uc(repo).execute(
            registration_id=reg.id,
            user_id=reg.user_id,
            pass_type="apple",
        )


def test_pending_registration_raises_invalid_status() -> None:
    """InvalidRegistrationStatusError when registration is pending, not yet confirmed."""
    reg = make_registration(status="pending")
    repo = FakeRegistrationRepository([reg])

    with pytest.raises(InvalidRegistrationStatusError):
        _uc(repo).execute(
            registration_id=reg.id,
            user_id=reg.user_id,
            pass_type="google",
        )


def test_registration_not_found_raises_error() -> None:
    """RegistrationNotFoundError when the registration does not exist."""
    repo = FakeRegistrationRepository()

    with pytest.raises(RegistrationNotFoundError):
        _uc(repo).execute(
            registration_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            pass_type="apple",
        )


def test_wrong_user_raises_not_found() -> None:
    """RegistrationNotFoundError when the registration belongs to a different user."""
    reg = make_registration(status="confirmed")
    repo = FakeRegistrationRepository([reg])

    with pytest.raises(RegistrationNotFoundError):
        _uc(repo).execute(
            registration_id=reg.id,
            user_id=uuid.uuid4(),
            pass_type="apple",
        )
