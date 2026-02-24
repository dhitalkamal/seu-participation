"""DRF API views for participation endpoints."""

from __future__ import annotations

import uuid

from django.conf import settings
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.api.responses import created_response, error_response, success_response
from apps.common.health import check_database, check_rabbitmq, check_redis
from apps.common.permissions import IsOrgManager, IsOrgMember
from apps.participation.application.use_cases.accept_transfer import AcceptTransferUseCase
from apps.participation.application.use_cases.batch_checkin import BatchCheckInUseCase
from apps.participation.application.use_cases.cancel import CancelRegistrationUseCase
from apps.participation.application.use_cases.cancel_transfer import CancelTransferUseCase
from apps.participation.application.use_cases.check_in import CheckInUseCase
from apps.participation.application.use_cases.generate_qr_token import GenerateQRTokenUseCase
from apps.participation.application.use_cases.generate_wallet_pass import GenerateWalletPassUseCase
from apps.participation.application.use_cases.get_event_checkin_stats import (
    GetEventCheckInStatsUseCase,
)
from apps.participation.application.use_cases.get_passport import GetPassportUseCase
from apps.participation.application.use_cases.get_registration import GetRegistrationUseCase
from apps.participation.application.use_cases.initiate_transfer import InitiateTransferUseCase
from apps.participation.application.use_cases.list_my_registrations import (
    ListMyRegistrationsUseCase,
)
from apps.participation.application.use_cases.list_my_shifts import ListMyShiftsUseCase
from apps.participation.application.use_cases.register import RegisterForEventUseCase
from apps.participation.application.use_cases.validate_qr_token import ValidateQRTokenUseCase
from apps.participation.application.use_cases.verify_passport import VerifyPassportUseCase
from apps.participation.domain.entities import WaitlistEntryEntity
from apps.participation.domain.exceptions import InvalidQRTokenError
from apps.participation.infrastructure.event_client import HttpEventClient
from apps.participation.infrastructure.models import CustomFormField, TicketTier
from apps.participation.infrastructure.publisher import RabbitMQEventPublisher
from apps.participation.infrastructure.repositories import (
    DjangoCheckInRepository,
    DjangoParticipationContextRepository,
    DjangoRegistrationRepository,
    DjangoRegistrationStatsRepository,
    DjangoTicketTransferRepository,
    DjangoVolunteerShiftRepository,
    DjangoWaitlistRepository,
)
from apps.participation.infrastructure.saved_events_models import SavedEvent
from apps.participation.infrastructure.wallet import (
    StubAppleWalletPassGenerator,
    StubGoogleWalletPassGenerator,
)
from apps.participation.presentation.serializers import (
    CancelSerializer,
    CheckInResponseSerializer,
    CheckInSerializer,
    CheckInStatsResponseSerializer,
    InitiateTransferSerializer,
    RegisterSerializer,
    RegistrationResponseSerializer,
    TicketTransferResponseSerializer,
    VolunteerShiftResponseSerializer,
    WaitlistResponseSerializer,
)

# ruff anchors so imports survive before the view classes are parsed
_CANCEL_UC = CancelRegistrationUseCase
_PUBLISHER = RabbitMQEventPublisher
_CHECKIN_UC = CheckInUseCase
_GET_REG_UC = GetRegistrationUseCase
_LIST_REGS_UC = ListMyRegistrationsUseCase
_REGISTER_UC = RegisterForEventUseCase
_WAITLIST_ENTITY = WaitlistEntryEntity
_EVENT_CLIENT = HttpEventClient
_REG_REPO = DjangoRegistrationRepository
_CHECKIN_REPO = DjangoCheckInRepository
_WAITLIST_REPO = DjangoWaitlistRepository
_CONTEXT_REPO = DjangoParticipationContextRepository
_CANCEL_SER = CancelSerializer
_CHECKIN_RESP_SER = CheckInResponseSerializer
_CHECKIN_SER = CheckInSerializer
_REG_SER = RegisterSerializer
_REG_RESP_SER = RegistrationResponseSerializer
_WAITLIST_RESP_SER = WaitlistResponseSerializer
_IS_AUTH = IsAuthenticated
_GEN_QR_UC = GenerateQRTokenUseCase
_VALIDATE_QR_UC = ValidateQRTokenUseCase
_BATCH_CHECKIN_UC = BatchCheckInUseCase
_GET_PASSPORT_UC = GetPassportUseCase
_VERIFY_PASSPORT_UC = VerifyPassportUseCase
_INVALID_QR_ERROR = InvalidQRTokenError
_CREATED = created_response
_UUID = uuid.UUID
_INITIATE_TRANSFER_UC = InitiateTransferUseCase
_ACCEPT_TRANSFER_UC = AcceptTransferUseCase
_CANCEL_TRANSFER_UC = CancelTransferUseCase
_TRANSFER_REPO = DjangoTicketTransferRepository
_INITIATE_TRANSFER_SER = InitiateTransferSerializer
_TRANSFER_RESP_SER = TicketTransferResponseSerializer

_CHECKS = inline_serializer(
    name="DependencyChecks",
    fields={
        "database": serializers.ChoiceField(choices=["healthy", "unhealthy"]),
        "redis": serializers.ChoiceField(choices=["healthy", "unhealthy"]),
        "rabbitmq": serializers.ChoiceField(choices=["healthy", "unhealthy"]),
    },
)
_META_SCHEMA = inline_serializer(
    name="ResponseMeta",
    fields={
        "request_id": serializers.CharField(),
        "timestamp": serializers.CharField(),
    },
)


class HealthCheckView(APIView):
    """Reports the operational status of all external dependencies."""

    authentication_classes: list = []
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Health"],
        summary="Service health check",
        description=(
            "Checks connectivity to PostgreSQL, Redis, and RabbitMQ. "
            "Returns 200 when all dependencies are healthy, 503 when any are down."
        ),
        auth=[],
        responses={
            200: OpenApiResponse(
                description="All dependencies are healthy.",
                response=inline_serializer(
                    name="HealthyResponse",
                    fields={
                        "data": inline_serializer(
                            name="HealthyData",
                            fields={
                                "service": serializers.CharField(),
                                "status": serializers.CharField(),
                                "version": serializers.CharField(),
                                "checks": _CHECKS,
                            },
                        ),
                        "error": serializers.JSONField(allow_null=True),
                        "meta": _META_SCHEMA,
                    },
                ),
            ),
            503: OpenApiResponse(
                description="One or more dependencies are unavailable.",
                response=inline_serializer(
                    name="UnhealthyResponse",
                    fields={
                        "data": serializers.JSONField(allow_null=True),
                        "error": inline_serializer(
                            name="HealthError",
                            fields={
                                "code": serializers.CharField(),
                                "message": serializers.CharField(),
                                "details": serializers.JSONField(allow_null=True),
                            },
                        ),
                        "meta": _META_SCHEMA,
                    },
                ),
            ),
        },
    )
    def get(self, request: Request) -> Response:
        """Check DB, Redis, and RabbitMQ and return an aggregated status."""
        db_status, db_err = check_database()
        redis_status, redis_err = check_redis()
        rmq_status, rmq_err = check_rabbitmq()

        checks: dict = {
            "database": db_status,
            "redis": redis_status,
            "rabbitmq": rmq_status,
        }
        dep_errors: dict = {
            k: v
            for k, v in {
                "database": db_err,
                "redis": redis_err,
                "rabbitmq": rmq_err,
            }.items()
            if v is not None
        }

        all_healthy = all(s == "healthy" for s in checks.values())

        if all_healthy:
            return success_response(
                {
                    "service": settings.SERVICE_NAME,
                    "status": "healthy",
                    "version": "0.1.0",
                    "checks": checks,
                },
                request=request,
            )

        return error_response(
            code="ERR_SERVICE_UNHEALTHY",
            message="One or more dependencies are unavailable.",
            details={"checks": checks, **({"errors": dep_errors} if dep_errors else {})},
            http_status=503,
            request=request,
        )


class RegisterView(APIView):
    """List own registrations (GET) or register for an event (POST)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Registrations"],
        summary="List my registrations",
        description="Returns all registrations for the authenticated user, newest first.",
        responses={
            200: OpenApiResponse(
                description="User registrations.",
                response=RegistrationResponseSerializer(many=True),
            ),
            401: OpenApiResponse(description="Missing or invalid JWT."),
        },
    )
    def get(self, request: Request) -> Response:
        """Return all registrations owned by the authenticated user."""
        results = _LIST_REGS_UC(_REG_REPO()).execute(
            user_id=uuid.UUID(str(request.user.id)),
        )
        return success_response(_REG_RESP_SER(results, many=True).data, request=request)

    @extend_schema(
        tags=["Registrations"],
        summary="Register for an event",
        description=(
            "Creates a CONFIRMED registration or a waitlist entry if the event is full. "
            "Returns 201 in both cases; check the waitlisted field to distinguish."
        ),
        request=RegisterSerializer,
        responses={
            201: OpenApiResponse(
                description="Registered or waitlisted.", response=RegistrationResponseSerializer
            ),
            401: OpenApiResponse(description="Missing or invalid JWT."),
            404: OpenApiResponse(description="Event not found."),
            409: OpenApiResponse(description="Already registered."),
        },
    )
    def post(self, request: Request) -> Response:
        """Validate payload, check capacity, and create registration or waitlist entry."""
        ser = _REG_SER(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        result = _REGISTER_UC(
            reg_repo=_REG_REPO(),
            waitlist_repo=_WAITLIST_REPO(),
            event_client=_EVENT_CLIENT(settings.EVENT_SERVICE_URL),
            publisher=_PUBLISHER(),
            context_repo=_CONTEXT_REPO(),
        ).execute(
            event_id=d["event_id"],
            user_id=uuid.UUID(str(request.user.id)),
            quantity=d["quantity"],
            notes=d.get("notes"),
            email=request.user.token.get("email", ""),
            first_name=request.user.token.get("first_name", ""),
            networking_opt_in=d.get("networking_opt_in", False),
        )

        if isinstance(result, _WAITLIST_ENTITY):
            return _CREATED(_WAITLIST_RESP_SER(result).data, request=request)
        return _CREATED(_REG_RESP_SER(result).data, request=request)


class CancelRegistrationView(APIView):
    """Cancel an existing registration."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Registrations"],
        summary="Cancel a registration",
        request=CancelSerializer,
        responses={
            200: OpenApiResponse(
                description="Registration cancelled.", response=RegistrationResponseSerializer
            ),
            401: OpenApiResponse(description="Missing or invalid JWT."),
            404: OpenApiResponse(description="Registration not found."),
            422: OpenApiResponse(description="Cannot cancel this registration status."),
        },
    )
    def post(self, request: Request) -> Response:
        """Cancel the registration and promote the next waitlist entry if any."""
        ser = _CANCEL_SER(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        result = _CANCEL_UC(
            reg_repo=_REG_REPO(),
            waitlist_repo=_WAITLIST_REPO(),
            publisher=_PUBLISHER(),
            context_repo=_CONTEXT_REPO(),
        ).execute(
            registration_id=d["registration_id"],
            user_id=uuid.UUID(str(request.user.id)),
            email=request.user.token.get("email", ""),
        )
        return success_response(_REG_RESP_SER(result).data, request=request)


class CheckInView(APIView):
    """Check in a registration by its registration_code."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Check-in"],
        summary="Check in a registration",
        request=CheckInSerializer,
        responses={
            200: OpenApiResponse(description="Checked in.", response=CheckInResponseSerializer),
            401: OpenApiResponse(description="Missing or invalid JWT."),
            404: OpenApiResponse(description="Registration code not found."),
            422: OpenApiResponse(description="Already checked in or wrong status."),
        },
    )
    def post(self, request: Request) -> Response:
        """Validate the registration code and record the check-in.

        Accepts two formats for registration_code:
        - plain 8-char code (<=20 chars): used directly
        - encrypted QR token (>20 chars): decrypted via ValidateQRTokenUseCase first
        """
        ser = _CHECKIN_SER(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        registration_code = d["registration_code"]

        # detect and decrypt encrypted QR tokens from mobile scanner
        if len(registration_code) > 20:
            event_id = d.get("event_id")
            if not event_id:
                return error_response(
                    code="ERR_CHECKIN_EVENT_ID_REQUIRED",
                    message="event_id is required when registration_code is an encrypted QR token.",
                    http_status=400,
                    request=request,
                )
            try:
                payload = _VALIDATE_QR_UC().execute(token=registration_code, event_id=event_id)
            except _INVALID_QR_ERROR as exc:
                return error_response(
                    code="ERR_CHECKIN_INVALID_QR",
                    message=str(exc),
                    http_status=400,
                    request=request,
                )
            registration_code = payload["registration_code"]

        result = _CHECKIN_UC(
            reg_repo=_REG_REPO(),
            check_in_repo=_CHECKIN_REPO(),
        ).execute(
            registration_code=registration_code,
            method=d["method"],
            staff_user_id=uuid.UUID(str(request.user.id)),
        )
        return success_response(_CHECKIN_RESP_SER(result).data, request=request)


class RegistrationDetailView(APIView):
    """Retrieve a single registration owned by the authenticated user."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Registrations"],
        summary="Get registration by id",
        responses={
            200: OpenApiResponse(
                description="Registration found.", response=RegistrationResponseSerializer
            ),
            401: OpenApiResponse(description="Missing or invalid JWT."),
            404: OpenApiResponse(description="Registration not found."),
        },
    )
    def get(self, request: Request, registration_id: uuid.UUID) -> Response:
        """Return the registration if it exists and belongs to the authenticated user."""
        result = _GET_REG_UC(_REG_REPO()).execute(
            registration_id=registration_id,
            user_id=uuid.UUID(str(request.user.id)),
        )
        return success_response(_REG_RESP_SER(result).data, request=request)


# * Volunteer shift views


class MyShiftsView(APIView):
    """List all volunteer shifts assigned to the authenticated user."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Volunteer"],
        summary="List my volunteer shifts",
        responses={200: VolunteerShiftResponseSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        """Return all shifts for the current volunteer ordered by start time."""
        shifts = ListMyShiftsUseCase(DjangoVolunteerShiftRepository()).execute(
            user_id=uuid.UUID(str(request.user.id))
        )
        data = [VolunteerShiftResponseSerializer(s).data for s in shifts]
        return success_response(data, request=request)


class EventCheckInStatsView(APIView):
    """Return live check-in stats for a specific event (volunteer dashboard)."""

    # org_id is read from query_params["organisation_id"] by IsOrgMember
    permission_classes = [IsAuthenticated, IsOrgMember]

    @extend_schema(
        tags=["Volunteer"],
        summary="Event check-in stats",
        responses={200: CheckInStatsResponseSerializer},
    )
    def get(self, request: Request, event_id: uuid.UUID) -> Response:
        """Compute and return total, checked_in, and remaining counts for the event."""
        stats = GetEventCheckInStatsUseCase(DjangoRegistrationStatsRepository()).execute(
            event_id=event_id
        )
        payload = {"event_id": str(event_id), **stats}
        return success_response(CheckInStatsResponseSerializer(payload).data, request=request)


class QRTokenView(APIView):
    """GET /registrations/{registration_id}/qr-token/ - encrypted offline QR token."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Offline QR"],
        summary="Get encrypted QR token for offline validation",
        description=(
            "Returns an AES-256-GCM encrypted QR token. Volunteer devices decrypt "
            "this token locally without a network round-trip, enabling 100% offline "
            "ticket validation at venues with intermittent connectivity."
        ),
        responses={
            200: OpenApiResponse(description="Encrypted QR token returned."),
            404: OpenApiResponse(description="Registration not found."),
        },
    )
    def get(self, request: Request, registration_id: uuid.UUID) -> Response:
        """Generate and return an encrypted QR token for the registration."""
        from apps.participation.infrastructure.repositories import DjangoRegistrationRepository

        try:
            reg = DjangoRegistrationRepository().get_by_id(registration_id)
        except Exception:
            return error_response(
                code="ERR_REGISTRATION_NOT_FOUND",
                message="Registration not found.",
                http_status=404,
                request=request,
            )
        token = _GEN_QR_UC().execute(registration=reg)
        return success_response(
            {"token": token, "registration_id": str(registration_id)},
            request=request,
        )


class BatchCheckInView(APIView):
    """POST /check-in/batch/ - sync offline QR check-ins after connectivity restored."""

    # org_id is read from request.data["organisation_id"] by IsOrgManager
    permission_classes = [IsAuthenticated, IsOrgManager]

    @extend_schema(
        tags=["Offline QR"],
        summary="Batch sync offline check-ins",
        description=(
            "Accepts a list of encrypted QR tokens captured while offline. "
            "Processes each token and returns a per-token result summary."
        ),
        responses={
            200: OpenApiResponse(description="Batch processed."),
        },
    )
    def post(self, request: Request) -> Response:
        """Process a list of offline QR tokens and return results."""
        tokens = request.data.get("tokens", [])
        event_id_str = request.data.get("event_id", "")
        if not tokens or not event_id_str:
            return error_response(
                code="ERR_BATCH_CHECKIN_INVALID",
                message="tokens (list) and event_id are required.",
                http_status=400,
                request=request,
            )
        try:
            event_id = uuid.UUID(event_id_str)
        except ValueError:
            return error_response(
                code="ERR_BATCH_CHECKIN_INVALID_EVENT",
                message="Invalid event_id.",
                http_status=400,
                request=request,
            )
        result = _BATCH_CHECKIN_UC(_REG_REPO(), _CHECKIN_REPO()).execute(
            event_id=event_id,
            tokens=tokens,
            staff_user_id=uuid.UUID(str(request.user.id)),
        )
        return success_response(result, request=request)


class PassportView(APIView):
    """GET /passport/me/ - Verified Event Passport for the authenticated user."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Passport"],
        summary="Get Verified Event Passport",
        description=(
            "Returns a signed Verified Event Passport containing the user's full "
            "participation history. The HMAC-SHA256 signature allows offline verification "
            "of authenticity by any holder."
        ),
        responses={200: OpenApiResponse(description="Passport returned.")},
    )
    def get(self, request: Request) -> Response:
        """Build and return the signed passport for the authenticated user."""
        user_id = uuid.UUID(str(request.user.id))
        passport = _GET_PASSPORT_UC(_REG_REPO()).execute(user_id=user_id)
        entries_data = [
            {
                "event_id": str(e.event_id),
                "event_name": e.event_name,
                "role": e.role,
                "status": e.status,
                "attended_at": e.attended_at.isoformat(),
                "certificate_issued": e.certificate_issued,
            }
            for e in passport.entries
        ]
        return success_response(
            {
                "user_id": str(passport.user_id),
                "entries": entries_data,
                "entry_count": len(entries_data),
                "generated_at": passport.generated_at.isoformat(),
                "signature": passport.signature,
            },
            request=request,
        )


# * Ticket tier views


class TicketTierListCreateView(APIView):
    """List tiers for an event or create a new one (organiser only)."""

    def get_permissions(self) -> list:
        """GET is public; POST requires authentication."""
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated()]

    def get(self, request: Request, event_id: uuid.UUID) -> Response:
        """Return all active tiers for the event."""
        tiers = TicketTier.objects.filter(event_id=event_id, is_active=True).order_by("price")
        data = [
            {
                "id": str(t.id),
                "event_id": str(t.event_id),
                "name": t.name,
                "tier_type": t.tier_type,
                "price": str(t.price),
                "capacity": t.capacity,
                "sold_count": t.sold_count,
                "available_spots": max(0, t.capacity - t.sold_count),
                "description": t.description,
                "is_active": t.is_active,
            }
            for t in tiers
        ]
        return success_response(data, request=request)

    def post(self, request: Request, event_id: uuid.UUID) -> Response:
        """Create a new ticket tier for the event."""
        from rest_framework import serializers as drf_serializers

        class _S(drf_serializers.Serializer):
            name = drf_serializers.CharField(max_length=100)
            tier_type = drf_serializers.ChoiceField(
                choices=["general", "vip", "early_bird", "comp"], default="general"
            )
            price = drf_serializers.DecimalField(max_digits=12, decimal_places=2, default="0.00")
            capacity = drf_serializers.IntegerField(min_value=1)
            description = drf_serializers.CharField(max_length=500, required=False, default="")

        ser = _S(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        tier = TicketTier.objects.create(event_id=event_id, **d)
        return created_response(
            {
                "id": str(tier.id),
                "name": tier.name,
                "tier_type": tier.tier_type,
                "price": str(tier.price),
                "capacity": tier.capacity,
                "sold_count": 0,
                "available_spots": tier.capacity,
            },
            request=request,
        )


class TicketTierDetailView(APIView):
    """Update or deactivate a ticket tier."""

    permission_classes = [IsAuthenticated]

    def patch(self, request: Request, event_id: uuid.UUID, tier_id: uuid.UUID) -> Response:
        """Partially update a tier."""
        try:
            tier = TicketTier.objects.get(id=tier_id, event_id=event_id)
        except TicketTier.DoesNotExist:
            return error_response(
                code="ERR_TIER_NOT_FOUND",
                message="Tier not found.",
                http_status=404,
                request=request,
            )
        for field in ("name", "price", "capacity", "description", "is_active"):
            if field in request.data:
                setattr(tier, field, request.data[field])
        tier.save()
        return success_response(
            {"id": str(tier.id), "name": tier.name, "price": str(tier.price)}, request=request
        )

    def delete(self, request: Request, event_id: uuid.UUID, tier_id: uuid.UUID) -> Response:
        """Soft-delete a tier by setting is_active=False."""
        try:
            tier = TicketTier.objects.get(id=tier_id, event_id=event_id)
        except TicketTier.DoesNotExist:
            return error_response(
                code="ERR_TIER_NOT_FOUND",
                message="Tier not found.",
                http_status=404,
                request=request,
            )
        tier.is_active = False
        tier.save()
        return success_response({"deactivated": True}, request=request)


#  Custom form field views


class CustomFormFieldListCreateView(APIView):
    """Manage custom registration form fields for an event."""

    def get_permissions(self) -> list:
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated()]

    def get(self, request: Request, event_id: uuid.UUID) -> Response:
        """Return all form fields for the event."""
        fields = CustomFormField.objects.filter(event_id=event_id).order_by("position")
        data = [
            {
                "id": str(f.id),
                "label": f.label,
                "field_type": f.field_type,
                "is_required": f.is_required,
                "options": f.options,
                "position": f.position,
            }
            for f in fields
        ]
        return success_response(data, request=request)

    def post(self, request: Request, event_id: uuid.UUID) -> Response:
        """Add a custom field - max 20 per event."""
        if CustomFormField.objects.filter(event_id=event_id).count() >= 20:
            return error_response(
                code="ERR_FORM_FIELD_LIMIT",
                message="Maximum 20 custom fields per event.",
                http_status=422,
                request=request,
            )
        from rest_framework import serializers as drf_serializers

        class _S(drf_serializers.Serializer):
            label = drf_serializers.CharField(max_length=255)
            field_type = drf_serializers.ChoiceField(
                choices=["text", "textarea", "select", "checkbox", "radio"], default="text"
            )
            is_required = drf_serializers.BooleanField(default=False)
            options = drf_serializers.ListField(
                child=drf_serializers.CharField(), required=False, default=list
            )
            position = drf_serializers.IntegerField(min_value=0, default=0)

        ser = _S(data=request.data)
        ser.is_valid(raise_exception=True)
        field = CustomFormField.objects.create(event_id=event_id, **ser.validated_data)
        return created_response(
            {
                "id": str(field.id),
                "label": field.label,
                "field_type": field.field_type,
                "is_required": field.is_required,
            },
            request=request,
        )


class WaitlistAcceptView(APIView):
    """Accept a waitlist offer within the 24h acceptance window."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Waitlist"],
        summary="Accept waitlist offer",
        description="Accept a waitlist offer. Creates a confirmed registration.",
        responses={
            200: OpenApiResponse(description="Offer accepted; registration created."),
            404: OpenApiResponse(description="Offer not found or not owned by current user."),
            409: OpenApiResponse(description="Offer already responded to."),
            422: OpenApiResponse(description="Acceptance window has expired."),
        },
    )
    def post(self, request: Request, entry_id: uuid.UUID) -> Response:
        """Accept the waitlist offer identified by entry_id."""
        from apps.participation.application.use_cases.accept_waitlist_offer import (
            AcceptWaitlistOfferUseCase,
        )

        user_id = uuid.UUID(str(request.user.id))
        registration = AcceptWaitlistOfferUseCase(
            waitlist_repo=DjangoWaitlistRepository(),
            reg_repo=DjangoRegistrationRepository(),
            publisher=RabbitMQEventPublisher(),
        ).execute(entry_id=entry_id, user_id=user_id)
        ser = RegistrationResponseSerializer(registration)
        return success_response(ser.data, request=request)


class WaitlistDeclineView(APIView):
    """Decline a waitlist offer, freeing the slot for the next person."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Waitlist"],
        summary="Decline waitlist offer",
        description="Decline a waitlist offer. Removes the entry from the waitlist.",
        responses={
            200: OpenApiResponse(description="Offer declined."),
            404: OpenApiResponse(description="Offer not found or not owned by current user."),
            409: OpenApiResponse(description="Offer already responded to."),
        },
    )
    def post(self, request: Request, entry_id: uuid.UUID) -> Response:
        """Decline the waitlist offer identified by entry_id."""
        from apps.participation.application.use_cases.decline_waitlist_offer import (
            DeclineWaitlistOfferUseCase,
        )

        user_id = uuid.UUID(str(request.user.id))
        DeclineWaitlistOfferUseCase(
            waitlist_repo=DjangoWaitlistRepository(),
            publisher=RabbitMQEventPublisher(),
        ).execute(entry_id=entry_id, user_id=user_id)
        return success_response({"declined": True}, request=request)


class InternalParticipationContextView(APIView):
    """Internal endpoint used by management-service to read and write participation context."""

    authentication_classes: list = []
    permission_classes = [AllowAny]

    @extend_schema(exclude=True)
    def get(self, request: Request, event_id: uuid.UUID, user_id: uuid.UUID) -> Response:
        """Return the participation_type for this (event, user) pair, or 404 if absent."""
        from django.http import JsonResponse

        from apps.participation.infrastructure.repositories import (
            DjangoParticipationContextRepository,
        )

        participation_type = DjangoParticipationContextRepository().get_context(event_id, user_id)
        if participation_type is None:
            return JsonResponse({"detail": "Not found."}, status=404)
        return JsonResponse({"participation_type": participation_type})

    @extend_schema(exclude=True)
    def post(self, request: Request, event_id: uuid.UUID, user_id: uuid.UUID) -> Response:
        """Upsert the participation context for this (event, user) pair."""
        import json as _json

        from django.http import JsonResponse

        from apps.participation.infrastructure.repositories import (
            DjangoParticipationContextRepository,
        )

        try:
            body = _json.loads(request.body)
            participation_type = body["participation_type"]
        except (KeyError, _json.JSONDecodeError):
            return JsonResponse({"detail": "participation_type is required."}, status=400)

        DjangoParticipationContextRepository().set_context(event_id, user_id, participation_type)
        return JsonResponse({"participation_type": participation_type})


class InitiateTransferView(APIView):
    """Initiate a ticket ownership transfer for a confirmed registration."""

    permission_classes = [_IS_AUTH]

    @extend_schema(
        tags=["Transfers"],
        summary="Initiate a ticket transfer",
        description=(
            "Creates a pending transfer token for the specified registration. "
            "The recipient has 48 hours to accept via the accept endpoint."
        ),
        request=_INITIATE_TRANSFER_SER,
        responses={
            201: OpenApiResponse(description="Transfer initiated.", response=_TRANSFER_RESP_SER),
            400: OpenApiResponse(description="Invalid request payload."),
            401: OpenApiResponse(description="Missing or invalid JWT."),
            404: OpenApiResponse(description="Registration not found."),
            409: OpenApiResponse(description="Transfer not allowed or already pending."),
        },
    )
    def post(self, request: Request, registration_id: _UUID) -> Response:
        """Validate ownership and create a pending transfer."""
        ser = _INITIATE_TRANSFER_SER(data=request.data)
        ser.is_valid(raise_exception=True)

        result = _INITIATE_TRANSFER_UC(
            reg_repo=_REG_REPO(),
            transfer_repo=_TRANSFER_REPO(),
            publisher=_PUBLISHER(),
        ).execute(
            registration_id=registration_id,
            from_user_id=_UUID(str(request.user.id)),
            to_email=ser.validated_data["to_email"],
        )
        return _CREATED(_TRANSFER_RESP_SER(result).data, request=request)


class AcceptTransferView(APIView):
    """Accept a pending ticket transfer using the one-time token."""

    permission_classes = [_IS_AUTH]

    @extend_schema(
        tags=["Transfers"],
        summary="Accept a ticket transfer",
        description=(
            "Accepts the pending transfer identified by token, cancels the original "
            "registration, and creates a new confirmed registration for the caller."
        ),
        responses={
            201: OpenApiResponse(
                description="Transfer accepted, new registration created.",
                response=RegistrationResponseSerializer,
            ),
            401: OpenApiResponse(description="Missing or invalid JWT."),
            404: OpenApiResponse(description="Transfer not found."),
            409: OpenApiResponse(description="Transfer already accepted or cancelled."),
            422: OpenApiResponse(description="Transfer has expired."),
        },
    )
    def post(self, request: Request, token: _UUID) -> Response:
        """Accept the transfer and return the new registration."""
        result = _ACCEPT_TRANSFER_UC(
            reg_repo=_REG_REPO(),
            transfer_repo=_TRANSFER_REPO(),
        ).execute(
            token=token,
            recipient_user_id=_UUID(str(request.user.id)),
        )
        return _CREATED(_REG_RESP_SER(result).data, request=request)


class CancelTransferView(APIView):
    """Cancel a pending transfer initiated by the authenticated user."""

    permission_classes = [_IS_AUTH]

    @extend_schema(
        tags=["Transfers"],
        summary="Cancel a ticket transfer",
        description=(
            "Cancels a pending transfer. Only the user who initiated the transfer can cancel it."
        ),
        responses={
            200: OpenApiResponse(description="Transfer cancelled."),
            401: OpenApiResponse(description="Missing or invalid JWT."),
            404: OpenApiResponse(description="Transfer not found."),
            409: OpenApiResponse(description="Transfer already completed or cancelled."),
        },
    )
    def delete(self, request: Request, transfer_id: _UUID) -> Response:
        """Cancel the transfer and return an empty success response."""
        _CANCEL_TRANSFER_UC(
            transfer_repo=_TRANSFER_REPO(),
        ).execute(
            transfer_id=transfer_id,
            user_id=_UUID(str(request.user.id)),
        )
        return success_response({}, request=request)


class SavedEventListCreateView(APIView):
    """List saved events for the authenticated user or save a new event."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Saved Events"],
        summary="List saved events",
        description="Returns all events saved/bookmarked by the authenticated user.",
        responses={
            200: OpenApiResponse(description="List of saved events."),
            401: OpenApiResponse(description="Missing or invalid JWT."),
        },
    )
    def get(self, request: Request) -> Response:
        """Return all saved events for the authenticated user."""
        user_id = _UUID(str(request.user.id))
        saved = SavedEvent.objects.filter(user_id=user_id).order_by("-saved_at")
        data = [
            {
                "id": str(s.id),
                "event_id": str(s.event_id),
                "saved_at": s.saved_at.isoformat(),
            }
            for s in saved
        ]
        return success_response(data, request=request)

    @extend_schema(
        tags=["Saved Events"],
        summary="Save an event",
        description="Bookmark an event for later. Body must include event_id.",
        responses={
            201: OpenApiResponse(description="Event saved."),
            400: OpenApiResponse(description="event_id missing or invalid."),
            401: OpenApiResponse(description="Missing or invalid JWT."),
            409: OpenApiResponse(description="Event already saved."),
        },
    )
    def post(self, request: Request) -> Response:
        """Save the event to the authenticated user's saved list."""
        from rest_framework import serializers as drf_serializers

        class _S(drf_serializers.Serializer):
            event_id = drf_serializers.UUIDField()

        ser = _S(data=request.data)
        ser.is_valid(raise_exception=True)
        user_id = _UUID(str(request.user.id))
        event_id = ser.validated_data["event_id"]

        if SavedEvent.objects.filter(user_id=user_id, event_id=event_id).exists():
            return error_response(
                code="ERR_ALREADY_SAVED",
                message="Event already saved.",
                http_status=409,
                request=request,
            )

        saved = SavedEvent.objects.create(user_id=user_id, event_id=event_id)
        return created_response(
            {
                "id": str(saved.id),
                "event_id": str(saved.event_id),
                "saved_at": saved.saved_at.isoformat(),
            },
            request=request,
        )


class SavedEventDeleteView(APIView):
    """Remove an event from the authenticated user's saved list."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Saved Events"],
        summary="Unsave an event",
        description="Remove an event from the authenticated user's saved list.",
        responses={
            200: OpenApiResponse(description="Event unsaved."),
            401: OpenApiResponse(description="Missing or invalid JWT."),
            404: OpenApiResponse(description="Event was not saved."),
        },
    )
    def delete(self, request: Request, event_id: _UUID) -> Response:
        """Delete the saved event record if it exists."""
        user_id = _UUID(str(request.user.id))
        deleted_count, _ = SavedEvent.objects.filter(user_id=user_id, event_id=event_id).delete()
        if not deleted_count:
            return error_response(
                code="ERR_SAVED_EVENT_NOT_FOUND",
                message="Saved event not found.",
                http_status=404,
                request=request,
            )
        return success_response({"unsaved": True}, request=request)


class TicketPdfView(APIView):
    """Return a PDF ticket for a confirmed registration."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Registrations"],
        summary="Download PDF ticket",
        description=(
            "Generates and returns a PDF ticket for the given registration. "
            "The PDF includes the event title, date, attendee name, QR code, and registration code."
        ),
        responses={
            200: OpenApiResponse(description="PDF file returned (application/pdf)."),
            401: OpenApiResponse(description="Missing or invalid JWT."),
            404: OpenApiResponse(description="Registration not found."),
        },
    )
    def get(self, request: Request, registration_id: _UUID) -> Response:
        """Generate the PDF and return it as a file response."""
        from django.http import HttpResponse

        from apps.participation.application.use_cases.generate_ticket_pdf import (
            GenerateTicketPdfUseCase,
        )
        from apps.participation.domain.exceptions import RegistrationNotFoundError

        try:
            pdf_bytes = GenerateTicketPdfUseCase(DjangoRegistrationRepository()).execute(
                registration_id=registration_id,
                user_id=_UUID(str(request.user.id)),
                attendee_name=request.user.token.get("full_name", "Attendee")
                if hasattr(request.user, "token")
                else "Attendee",
            )
        except RegistrationNotFoundError:
            return error_response(
                code="ERR_REGISTRATION_NOT_FOUND",
                message="Registration not found.",
                http_status=404,
                request=request,
            )

        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="ticket-{registration_id}.pdf"'
        return response


class WalletPassView(APIView):
    """Return a wallet pass payload for a confirmed registration."""

    permission_classes = [IsAuthenticated]

    _generators = {
        "apple": StubAppleWalletPassGenerator(),
        "google": StubGoogleWalletPassGenerator(),
    }

    @extend_schema(
        tags=["Wallet"],
        summary="Get wallet pass",
        description=(
            "Returns an Apple (.pkpass) or Google Wallet JWT payload for the given confirmed "
            "registration. pass_type must be 'apple' or 'google'."
        ),
        responses={
            200: OpenApiResponse(description="Wallet pass payload returned."),
            401: OpenApiResponse(description="Missing or invalid JWT."),
            404: OpenApiResponse(description="Registration not found."),
            422: OpenApiResponse(description="Registration is not confirmed."),
        },
    )
    def get(self, request: Request, registration_id: _UUID, pass_type: str) -> Response:
        """Generate and return the wallet pass payload."""
        result = GenerateWalletPassUseCase(
            registration_repo=DjangoRegistrationRepository(),
            generators=self._generators,
        ).execute(
            registration_id=registration_id,
            user_id=_UUID(str(request.user.id)),
            pass_type=pass_type,
        )
        return success_response(
            {
                "registration_id": str(result.registration_id),
                "pass_type": result.pass_type,
                "payload": result.payload,
                "generated_at": result.generated_at.isoformat(),
            },
            request=request,
        )
