"""Create the participation PostgreSQL schema before the first table migration."""

from __future__ import annotations

from django.db import migrations


class Migration(migrations.Migration):
    """Ensures the participation schema exists before any table is created."""

    initial = True
    dependencies: list = []

    operations = [
        migrations.RunSQL(
            sql="CREATE SCHEMA IF NOT EXISTS participation;",
            reverse_sql="DROP SCHEMA IF EXISTS participation CASCADE;",
        ),
    ]
