"""Django admin registrations for participation domain models."""

from __future__ import annotations

from django.contrib import admin

from apps.participation.infrastructure.models import CheckIn, Registration, WaitlistEntry

admin.site.register(Registration)
admin.site.register(CheckIn)
admin.site.register(WaitlistEntry)
