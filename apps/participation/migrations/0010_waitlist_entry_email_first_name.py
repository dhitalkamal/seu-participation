"""Migration: add email and first_name to waitlist_entry for notification payloads."""

from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    """Adds email and first_name columns to participation.waitlist_entry."""

    dependencies = [
        ("participation", "0009_saved_event"),
    ]

    operations = [
        migrations.AddField(
            model_name="waitlistentry",
            name="email",
            field=models.EmailField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="waitlistentry",
            name="first_name",
            field=models.CharField(blank=True, default="", max_length=150),
        ),
    ]
