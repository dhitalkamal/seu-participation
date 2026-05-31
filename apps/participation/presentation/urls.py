"""URL routes for the participation app."""

from __future__ import annotations

from django.urls import URLPattern, path

from .views import (
    AcceptTransferView,
    BatchCheckInView,
    CancelRegistrationView,
    CancelTransferView,
    CheckInView,
    CustomFormFieldListCreateView,
    EventCheckInStatsView,
    EventRegistrationsView,
    EventWaitlistView,
    HealthCheckView,
    InitiateTransferView,
    InternalParticipationContextView,
    MyShiftsView,
    PassportView,
    QRTokenView,
    RegisterView,
    RegistrationDetailView,
    SavedEventDeleteView,
    SavedEventListCreateView,
    TicketPdfView,
    TicketTierDetailView,
    TicketTierListCreateView,
    WaitlistAcceptView,
    WaitlistDeclineView,
    WalletPassView,
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
    path(
        "registrations/<uuid:registration_id>/ticket-pdf/",
        TicketPdfView.as_view(),
        name="registration-ticket-pdf",
    ),
    path("saved-events/", SavedEventListCreateView.as_view(), name="saved-events-list-create"),
    path(
        "saved-events/<uuid:event_id>/",
        SavedEventDeleteView.as_view(),
        name="saved-events-delete",
    ),
    path(
        "registrations/<uuid:registration_id>/transfer/",
        InitiateTransferView.as_view(),
        name="registration-initiate-transfer",
    ),
    path(
        "transfers/<uuid:token>/accept/",
        AcceptTransferView.as_view(),
        name="transfer-accept",
    ),
    path(
        "transfers/<uuid:transfer_id>/",
        CancelTransferView.as_view(),
        name="transfer-cancel",
    ),
    path(
        "registrations/<uuid:registration_id>/wallet/<str:pass_type>/",
        WalletPassView.as_view(),
        name="registration-wallet-pass",
    ),
    path(
        "events/<uuid:event_id>/ticket-tiers/",
        TicketTierListCreateView.as_view(),
        name="ticket-tier-list-create",
    ),
    path(
        "events/<uuid:event_id>/ticket-tiers/<uuid:tier_id>/",
        TicketTierDetailView.as_view(),
        name="ticket-tier-detail",
    ),
    path(
        "events/<uuid:event_id>/custom-fields/",
        CustomFormFieldListCreateView.as_view(),
        name="custom-form-field-list-create",
    ),
    path(
        "events/<uuid:event_id>/waitlist/",
        EventWaitlistView.as_view(),
        name="event-waitlist",
    ),
    path(
        "events/<uuid:event_id>/registrations/",
        EventRegistrationsView.as_view(),
        name="event-registrations",
    ),
]
