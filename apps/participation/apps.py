"""Django app config for the participation module."""
from __future__ import annotations

from django.apps import AppConfig


class ParticipationConfig(AppConfig):
    """Registers the participation app with Django."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.participation"
    label = "participation"
