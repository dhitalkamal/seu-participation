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
from apps.participation.application.use_cases.cancel import CancelRegistrationUseCase
from apps.participation.application.use_cases.check_in import CheckInUseCase
from apps.participation.application.use_cases.get_registration import GetRegistrationUseCase
from apps.participation.application.use_cases.list_my_registrations import (
    ListMyRegistrationsUseCase,
)
from apps.participation.application.use_cases.register import RegisterForEventUseCase
from apps.participation.domain.entities import WaitlistEntryEntity
from apps.participation.infrastructure.event_client import HttpEventClient
from apps.participation.infrastructure.publisher import RabbitMQEventPublisher
from apps.participation.infrastructure.repositories import (
    DjangoCheckInRepository,
    DjangoRegistrationRepository,
    DjangoWaitlistRepository,
)
from apps.participation.presentation.serializers import (
    CancelSerializer,
    CheckInResponseSerializer,
    CheckInSerializer,
    RegisterSerializer,
    RegistrationResponseSerializer,
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
_CANCEL_SER = CancelSerializer
_CHECKIN_RESP_SER = CheckInResponseSerializer
_CHECKIN_SER = CheckInSerializer
_REG_SER = RegisterSerializer
_REG_RESP_SER = RegistrationResponseSerializer
_WAITLIST_RESP_SER = WaitlistResponseSerializer
_IS_AUTH = IsAuthenticated
_CREATED = created_response
_UUID = uuid.UUID

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
        ).execute(
            event_id=d["event_id"],
            user_id=uuid.UUID(str(request.user.id)),
            quantity=d["quantity"],
            notes=d.get("notes"),
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
        ).execute(
            registration_id=d["registration_id"],
            user_id=uuid.UUID(str(request.user.id)),
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
        """Validate the registration code and record the check-in."""
        ser = _CHECKIN_SER(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        result = _CHECKIN_UC(
            reg_repo=_REG_REPO(),
            check_in_repo=_CHECKIN_REPO(),
        ).execute(
            registration_code=d["registration_code"],
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


# ── Volunteer shift views ──────────────────────────────────────────────────────

from apps.participation.application.use_cases.get_event_checkin_stats import GetEventCheckInStatsUseCase
from apps.participation.application.use_cases.list_my_shifts import ListMyShiftsUseCase
from apps.participation.infrastructure.repositories import (
    DjangoRegistrationStatsRepository,
    DjangoVolunteerShiftRepository,
)
from apps.participation.presentation.serializers import (
    CheckInStatsResponseSerializer,
    VolunteerShiftResponseSerializer,
)


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

    permission_classes = [IsAuthenticated]

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
