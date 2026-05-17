"""Migration: add volunteer_shift table to the participation schema."""

from __future__ import annotations

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("participation", "0002_add_notes_to_registration"),
    ]

    operations = [
        migrations.CreateModel(
            name="VolunteerShift",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ("event_id", models.UUIDField(db_index=True)),
                ("user_id", models.UUIDField(db_index=True)),
                ("role", models.CharField(max_length=100)),
                ("start_time", models.DateTimeField()),
                ("end_time", models.DateTimeField()),
                ("location", models.CharField(max_length=200)),
                ("coordinator_name", models.CharField(max_length=100)),
                ("coordinator_phone", models.CharField(max_length=30)),
                ("status", models.CharField(
                    choices=[
                        ("pending", "Pending"),
                        ("confirmed", "Confirmed"),
                        ("completed", "Completed"),
                        ("cancelled", "Cancelled"),
                    ],
                    default="confirmed",
                    max_length=20,
                )),
                ("notes", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": '"participation"."volunteer_shift"'},
        ),
        migrations.AddConstraint(
            model_name="volunteershift",
            constraint=models.UniqueConstraint(
                condition=~models.Q(status="cancelled"),
                fields=["event_id", "user_id"],
                name="unique_active_volunteer_shift",
            ),
        ),
    ]
