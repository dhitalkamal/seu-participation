"""Use case: generate an AES-256-GCM encrypted QR token for offline ticket validation."""

from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timedelta, timezone

from apps.participation.domain.entities import RegistrationEntity

# platform-wide QR signing key - set QR_SECRET_KEY in env (32 bytes hex)
_QR_KEY_HEX = os.getenv("QR_SECRET_KEY", "0" * 64)


def _get_key() -> bytes:
    """Return the 32-byte AES key from env, padding if short."""
    raw = bytes.fromhex(_QR_KEY_HEX.ljust(64, "0")[:64])
    return raw


class GenerateQRTokenUseCase:
    """Encrypt registration identity into a self-contained QR token payload."""

    def execute(
        self,
        *,
        registration: RegistrationEntity,
        expires_at: datetime | None = None,
    ) -> str:
        """
        Build and AES-256-GCM encrypt a token containing registration_id, event_id,
        user_id, and expiry. Returns a URL-safe base64 string.

        The token is self-validating offline: volunteer devices decrypt and check
        expiry without hitting the server.
        """
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        if expires_at is None:
            expires_at = datetime.now(timezone.utc) + timedelta(hours=26)

        payload = json.dumps(
            {
                "registration_id": str(registration.id),
                "event_id": str(registration.event_id),
                "user_id": str(registration.user_id),
                "registration_code": registration.registration_code,
                "exp": expires_at.timestamp(),
            }
        ).encode()

        key = _get_key()
        nonce = os.urandom(12)
        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, payload, None)
        # nonce (12 bytes) + ciphertext, encoded as URL-safe base64
        return base64.urlsafe_b64encode(nonce + ciphertext).decode()
