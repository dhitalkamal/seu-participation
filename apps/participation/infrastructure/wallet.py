"""Stub implementations of IWalletPassGenerator for Apple and Google Wallet."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from apps.participation.domain.entities import RegistrationEntity, WalletPassEntity
from apps.participation.domain.repositories import IWalletPassGenerator


class StubAppleWalletPassGenerator(IWalletPassGenerator):
    """Placeholder pkpass-style generator. Swap out for real pkpass signing when ready."""

    def generate(self, registration: RegistrationEntity) -> WalletPassEntity:
        """Build a stub Apple Wallet pass JSON."""
        payload = json.dumps(
            {
                "type": "apple",
                "format": "pkpass",
                "registration_id": str(registration.id),
                "event_id": str(registration.event_id),
                "registration_code": registration.registration_code,
                "stub": True,
            }
        )
        return WalletPassEntity(
            registration_id=registration.id,
            user_id=registration.user_id,
            event_id=registration.event_id,
            pass_type="apple",
            payload=payload,
            generated_at=datetime.now(timezone.utc),
        )


class StubGoogleWalletPassGenerator(IWalletPassGenerator):
    """Placeholder Google Wallet JWT generator. Swap out for real signing when ready."""

    def generate(self, registration: RegistrationEntity) -> WalletPassEntity:
        """Build a stub Google Wallet pass JSON."""
        payload = json.dumps(
            {
                "type": "google",
                "format": "jwt",
                "registration_id": str(registration.id),
                "event_id": str(registration.event_id),
                "registration_code": registration.registration_code,
                "stub": True,
            }
        )
        return WalletPassEntity(
            registration_id=registration.id,
            user_id=registration.user_id,
            event_id=registration.event_id,
            pass_type="google",
            payload=payload,
            generated_at=datetime.now(timezone.utc),
        )
