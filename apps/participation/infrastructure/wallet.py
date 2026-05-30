"""Stub implementations of IWalletPassGenerator for Apple and Google Wallet."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from apps.participation.domain.entities import RegistrationEntity, WalletPassEntity
from apps.participation.domain.repositories import IWalletPassGenerator


class StubAppleWalletPassGenerator(IWalletPassGenerator):
    """Digital-pass generator for Apple Wallet.

    Real .pkpass generation requires Apple Developer certificates and a
    signing key that we don't provision in this environment. Instead, this
    generator returns a structured JSON payload that the mobile app renders
    as a digital pass card - it carries all the data a real pkpass would
    expose to the user.
    """

    def generate(self, registration: RegistrationEntity) -> WalletPassEntity:
        """Build a structured digital-pass payload for Apple Wallet display."""
        now = datetime.now(timezone.utc)
        payload = json.dumps(
            {
                "type": "apple",
                "format": "digital_pass",
                "registration_id": str(registration.id),
                "event_id": str(registration.event_id),
                "registration_code": registration.registration_code,
                "quantity": registration.quantity,
                "status": registration.status,
                "issued_at": now.isoformat(),
                # fields the mobile card view reads directly
                "pass_fields": {
                    "header": "SANSAAR EVENT TICKET",
                    "primary_label": "ATTENDEE",
                    "primary_value": registration.registration_code,
                    "secondary_fields": [
                        {
                            "label": "QTY",
                            "value": str(registration.quantity),
                        },
                        {
                            "label": "STATUS",
                            "value": registration.status.upper(),
                        },
                    ],
                    "barcode": {
                        "message": registration.registration_code,
                        "format": "QR",
                        "altText": registration.registration_code,
                    },
                },
                # stub: real pkpass requires Apple signing
                "stub": True,
                "stub_reason": "Apple Developer certificate not provisioned",
            }
        )
        return WalletPassEntity(
            registration_id=registration.id,
            user_id=registration.user_id,
            event_id=registration.event_id,
            pass_type="apple",
            payload=payload,
            generated_at=now,
        )


class StubGoogleWalletPassGenerator(IWalletPassGenerator):
    """Google Wallet pass generator.

    When GOOGLE_WALLET_ISSUER_ID is set in the environment this generator
    returns a properly-structured JWT object payload that satisfies the
    Google Wallet Objects API schema and can be saved via the save-to-wallet
    link. Without the issuer ID it falls back to a structured JSON stub the
    mobile app can display as a digital pass card.
    """

    def generate(self, registration: RegistrationEntity) -> WalletPassEntity:
        """Return a Google Wallet JWT payload or a structured stub."""
        now = datetime.now(timezone.utc)
        issuer_id = os.environ.get("GOOGLE_WALLET_ISSUER_ID", "")

        if issuer_id:
            # well-formed Google Wallet Objects generic pass payload
            # the caller must sign this with the service account key before
            # presenting it to the Save-to-Wallet endpoint
            payload = json.dumps(
                {
                    "type": "google",
                    "format": "jwt",
                    "iss": issuer_id,
                    "aud": "google",
                    "typ": "savetowallet",
                    "iat": int(now.timestamp()),
                    "payload": {
                        "genericObjects": [
                            {
                                "id": f"{issuer_id}.{registration.id}",
                                "classId": f"{issuer_id}.sansaar_event_ticket",
                                "genericType": "GENERIC_TYPE_UNSPECIFIED",
                                "hexBackgroundColor": "#050A26",
                                "logo": {"sourceUri": {"uri": "https://sansaarhr.com/logo.png"}},
                                "cardTitle": {
                                    "defaultValue": {
                                        "language": "en-US",
                                        "value": "Sansaar Event Ticket",
                                    }
                                },
                                "subheader": {
                                    "defaultValue": {
                                        "language": "en-US",
                                        "value": "REGISTRATION CODE",
                                    }
                                },
                                "header": {
                                    "defaultValue": {
                                        "language": "en-US",
                                        "value": registration.registration_code,
                                    }
                                },
                                "barcode": {
                                    "type": "QR_CODE",
                                    "value": registration.registration_code,
                                    "alternateText": registration.registration_code,
                                },
                                "textModulesData": [
                                    {
                                        "id": "qty",
                                        "header": "QTY",
                                        "body": str(registration.quantity),
                                    },
                                    {
                                        "id": "status",
                                        "header": "STATUS",
                                        "body": registration.status.upper(),
                                    },
                                ],
                                "state": "ACTIVE",
                                "validTimeInterval": {
                                    "start": {"date": now.isoformat()},
                                },
                            }
                        ]
                    },
                    # signing happens in the view layer once the service account
                    # private key is available - the JWT is unsigned at this stage
                    "unsigned": True,
                }
            )
        else:
            # structured stub - mobile app renders this as a digital pass card
            payload = json.dumps(
                {
                    "type": "google",
                    "format": "digital_pass",
                    "registration_id": str(registration.id),
                    "event_id": str(registration.event_id),
                    "registration_code": registration.registration_code,
                    "quantity": registration.quantity,
                    "status": registration.status,
                    "issued_at": now.isoformat(),
                    "pass_fields": {
                        "header": "SANSAAR EVENT TICKET",
                        "primary_label": "REGISTRATION CODE",
                        "primary_value": registration.registration_code,
                        "secondary_fields": [
                            {"label": "QTY", "value": str(registration.quantity)},
                            {"label": "STATUS", "value": registration.status.upper()},
                        ],
                        "barcode": {
                            "message": registration.registration_code,
                            "format": "QR",
                            "altText": registration.registration_code,
                        },
                    },
                    "stub": True,
                    "stub_reason": "GOOGLE_WALLET_ISSUER_ID not set",
                }
            )

        return WalletPassEntity(
            registration_id=registration.id,
            user_id=registration.user_id,
            event_id=registration.event_id,
            pass_type="google",
            payload=payload,
            generated_at=now,
        )
