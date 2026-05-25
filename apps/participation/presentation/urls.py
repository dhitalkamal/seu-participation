"""URL routes for the participation app."""

from __future__ import annotations

from django.urls import URLPattern, path

from .views import (
    BatchCheckInView,
    CancelRegistrationView,
    CheckInView,
    EventCheckInStatsView,
    HealthCheckView,
    InternalParticipationContextView,
    MyShiftsView,
    PassportView,
    QRTokenView,
    RegisterView,
    RegistrationDetailView,
    WaitlistAcceptView,
    WaitlistDeclineView,
)

urlpatterns: list[URLPattern] = [
    path("health/", HealthCheckView.as_view(), name="health"),
    path("registrations/", RegisterView.as_view(), name="registration-list-create"),
    path(
        "registrations/<uuid:registration_id>/",
        RegistrationDetailView.as_view(),
        name="registration-detail",
    ),
    path(
        "registrations/<uuid:registration_id>/qr-token/",
        QRTokenView.as_view(),
        name="registration-qr-token",
    ),
    path("registrations/cancel/", CancelRegistrationView.as_view(), name="cancel-registration"),
    path("check-in/", CheckInView.as_view(), name="check-in"),
    path("check-in/batch/", BatchCheckInView.as_view(), name="check-in-batch"),
    path("volunteer/shifts/", MyShiftsView.as_view(), name="volunteer-shifts"),
    path(
        "volunteer/events/<uuid:event_id>/stats/",
        EventCheckInStatsView.as_view(),
        name="volunteer-event-stats",
    ),
    path("passport/me/", PassportView.as_view(), name="passport-me"),
    path("waitlist/<uuid:entry_id>/accept/", WaitlistAcceptView.as_view(), name="waitlist-accept"),
    path(
        "waitlist/<uuid:entry_id>/decline/", WaitlistDeclineView.as_view(), name="waitlist-decline"
    ),
    path(
        "internal/participation-context/<uuid:event_id>/<uuid:user_id>/",
        InternalParticipationContextView.as_view(),
        name="internal-participation-context",
    ),
]
