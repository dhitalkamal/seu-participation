"""URL routes for the participation app."""

from __future__ import annotations

from django.urls import URLPattern, path

from .views import (
    CancelRegistrationView,
    CheckInView,
    EventCheckInStatsView,
    HealthCheckView,
    MyShiftsView,
    RegisterView,
    RegistrationDetailView,
)

urlpatterns: list[URLPattern] = [
    path("health/", HealthCheckView.as_view(), name="health"),
    path("registrations/", RegisterView.as_view(), name="registration-list-create"),
    path(
        "registrations/<uuid:registration_id>/",
        RegistrationDetailView.as_view(),
        name="registration-detail",
    ),
    path("registrations/cancel/", CancelRegistrationView.as_view(), name="cancel-registration"),
    path("check-in/", CheckInView.as_view(), name="check-in"),
    path("volunteer/shifts/", MyShiftsView.as_view(), name="volunteer-shifts"),
    path(
        "volunteer/events/<uuid:event_id>/stats/",
        EventCheckInStatsView.as_view(),
        name="volunteer-event-stats",
    ),
]
