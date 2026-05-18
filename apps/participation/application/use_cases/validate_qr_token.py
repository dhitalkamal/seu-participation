"""Use case: validate an AES-256-GCM encrypted QR token for offline check-in."""

from __future__ import annotations

import base64
import json
import uuid
from datetime import datetime, timezone

from apps.participation.application.use_cases.generate_qr_token import _get_key
from apps.participation.domain.exceptions import InvalidQRTokenError


class ValidateQRTokenUseCase:
    """Decrypt and verify an offline QR token without hitting the database."""

    def execute(self, *, token: str, event_id: uuid.UUID) -> dict:
        """
        Decrypt the token and assert event_id matches and expiry has not passed.

        Returns the payload dict on success.
        Raises InvalidQRTokenError for any failure (tampered, expired, wrong event).
        """
        from cryptography.exceptions import InvalidTag
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        try:
            raw = base64.urlsafe_b64decode(token.encode() + b"==")
        except Exception:
            raise InvalidQRTokenError("QR token is not valid base64.")

        if len(raw) < 13:
            raise InvalidQRTokenError("QR token is too short.")

        nonce, ciphertext = raw[:12], raw[12:]
        key = _get_key()
        aesgcm = AESGCM(key)

        try:
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        except InvalidTag:
            raise InvalidQRTokenError("QR token authentication failed - token has been tampered.")

        try:
            payload = json.loads(plaintext)
        except ValueError:
            raise InvalidQRTokenError("QR token payload is not valid JSON.")

        # check event_id matches
        if payload.get("event_id") != str(event_id):
            raise InvalidQRTokenError("QR token event_id does not match.")

        # check expiry
        exp = payload.get("exp", 0)
        if datetime.now(timezone.utc).timestamp() > exp:
            raise InvalidQRTokenError("QR token has expired.")

        return payload
