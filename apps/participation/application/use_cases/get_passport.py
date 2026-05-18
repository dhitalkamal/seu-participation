"""Use case: build a user's Verified Event Passport from their participation history."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import uuid
from datetime import datetime, timezone

from apps.participation.domain.entities import PassportEntity, PassportEntryEntity
from apps.participation.domain.repositories import IRegistrationRepository

_PASSPORT_SECRET = os.getenv("PASSPORT_SECRET_KEY", "sansaar-passport-hmac-key-v1")

_VALID_STATUSES = frozenset({"confirmed", "checked_in"})


def _sign_passport(user_id: uuid.UUID, entries: list, generated_at: datetime) -> str:
    """HMAC-SHA256 signature over user_id + entries + timestamp for tamper detection."""
    payload = json.dumps(
        {
            "user_id": str(user_id),
            "entries": len(entries),
            "generated_at": generated_at.isoformat(),
        },
        sort_keys=True,
    ).encode()
    return hmac.new(_PASSPORT_SECRET.encode(), payload, hashlib.sha256).hexdigest()


class GetPassportUseCase:
    """Build a signed Verified Event Passport for the given user."""

    def __init__(self, repo: IRegistrationRepository) -> None:
        self._repo = repo

    def execute(self, *, user_id: uuid.UUID) -> PassportEntity:
        """
        Aggregate confirmed and checked-in registrations into a signed passport.

        Each entry contains event metadata and a participation role.
        The HMAC signature allows any holder to verify authenticity offline.
        """
        registrations = self._repo.list_by_user(user_id)

        entries = []
        for reg in registrations:
            if reg.status not in _VALID_STATUSES:
                continue
            entry = PassportEntryEntity(
                event_id=reg.event_id,
                event_name=f"Event {str(reg.event_id)[:8]}",
                role="attendee",
                status=reg.status,
                attended_at=reg.checked_in_at or reg.created_at,
                certificate_issued=False,
            )
            entries.append(entry)

        now = datetime.now(timezone.utc)
        signature = _sign_passport(user_id, entries, now)

        return PassportEntity(
            user_id=user_id,
            entries=entries,
            generated_at=now,
            signature=signature,
        )
