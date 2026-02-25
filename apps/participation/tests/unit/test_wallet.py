"""Unit tests for StubAppleWalletPassGenerator and StubGoogleWalletPassGenerator."""

from __future__ import annotations

import json

from apps.participation.infrastructure.wallet import (
    StubAppleWalletPassGenerator,
    StubGoogleWalletPassGenerator,
)
from apps.participation.tests.unit.fakes import make_registration


def test_apple_generator_pass_type() -> None:
    """Apple generator returns an entity with pass_type='apple'."""
    reg = make_registration(status="confirmed")
    result = StubAppleWalletPassGenerator().generate(reg)
    assert result.pass_type == "apple"


def test_apple_generator_ids_match_registration() -> None:
    """Apple pass carries the correct registration_id, user_id, event_id."""
    reg = make_registration(status="confirmed")
    result = StubAppleWalletPassGenerator().generate(reg)
    assert result.registration_id == reg.id
    assert result.user_id == reg.user_id
    assert result.event_id == reg.event_id


def test_apple_payload_is_valid_json() -> None:
    """Apple payload is parseable JSON containing the registration_code."""
    reg = make_registration(status="confirmed", registration_code="XYZ99")
    result = StubAppleWalletPassGenerator().generate(reg)
    data = json.loads(result.payload)
    assert data["registration_code"] == "XYZ99"
    assert data["type"] == "apple"


def test_google_generator_pass_type() -> None:
    """Google generator returns an entity with pass_type='google'."""
    reg = make_registration(status="confirmed")
    result = StubGoogleWalletPassGenerator().generate(reg)
    assert result.pass_type == "google"


def test_google_generator_ids_match_registration() -> None:
    """Google pass carries the correct registration_id, user_id, event_id."""
    reg = make_registration(status="confirmed")
    result = StubGoogleWalletPassGenerator().generate(reg)
    assert result.registration_id == reg.id
    assert result.user_id == reg.user_id
    assert result.event_id == reg.event_id


def test_google_payload_is_valid_json() -> None:
    """Google payload is parseable JSON containing the registration_code."""
    reg = make_registration(status="confirmed", registration_code="ABC11")
    result = StubGoogleWalletPassGenerator().generate(reg)
    data = json.loads(result.payload)
    assert data["registration_code"] == "ABC11"
    assert data["type"] == "google"
