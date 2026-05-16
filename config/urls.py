"""Root URL configuration for the participation-service."""
from __future__ import annotations

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("apps.participation.presentation.urls")),
]
