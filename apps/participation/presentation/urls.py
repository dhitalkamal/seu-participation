"""URL routes for the participation app."""

from __future__ import annotations

from django.urls import URLPattern, path

from .views import (
    CancelRegistrationView,
    CheckInView,
    HealthCheckView,
    RegisterView,
    RegistrationDetailView,
    RegistrationListView,
)

urlpatterns: list[URLPattern] = [
    path("health/", HealthCheckView.as_view(), name="health"),
    path("registrations/", RegistrationListView.as_view(), name="registration-list"),
    path("registrations/create/", RegisterView.as_view(), name="register"),
    path(
        "registrations/<uuid:registration_id>/",
        RegistrationDetailView.as_view(),
        name="registration-detail",
    ),
    path("registrations/cancel/", CancelRegistrationView.as_view(), name="cancel-registration"),
    path("check-in/", CheckInView.as_view(), name="check-in"),
]
