"""Use case: verify the HMAC signature on a Verified Event Passport."""

from __future__ import annotations

import hmac

from apps.participation.application.use_cases.get_passport import _sign_passport
from apps.participation.domain.entities import PassportEntity


class VerifyPassportUseCase:
    """Verify that a passport's HMAC signature is authentic."""

    def execute(self, *, passport: PassportEntity) -> bool:
        """
        Recompute the expected signature and compare in constant time.

        Returns True if the signature matches, False if tampered.
        """
        expected = _sign_passport(passport.user_id, passport.entries, passport.generated_at)
        return hmac.compare_digest(expected, passport.signature)
