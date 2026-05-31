"""Create registration, check_in, and waitlist_entry tables."""

from __future__ import annotations

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Initial participation tables."""

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Registration",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("event_id", models.UUIDField()),
                ("user_id", models.UUIDField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("confirmed", "Confirmed"),
                            ("cancelled", "Cancelled"),
                            ("checked_in", "Checked In"),
                            ("waitlisted", "Waitlisted"),
                            ("no_show", "No Show"),
                        ],
                        default="confirmed",
                        max_length=20,
                    ),
                ),
                ("registration_code", models.CharField(max_length=20, unique=True)),
                ("quantity", models.PositiveIntegerField(default=1)),
                ("checked_in_at", models.DateTimeField(blank=True, null=True)),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "participation_registration"},
        ),
        migrations.AddConstraint(
            model_name="registration",
            constraint=models.UniqueConstraint(
                condition=~models.Q(status="cancelled"),
                fields=["event_id", "user_id"],
                name="unique_active_registration",
            ),
        ),
        migrations.CreateModel(
            name="CheckIn",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                (
                    "registration",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="check_in",
                        to="participation.registration",
                    ),
                ),
                ("event_id", models.UUIDField()),
                ("user_id", models.UUIDField()),
                (
                    "method",
                    models.CharField(
                        choices=[("qr_code", "QR Code"), ("manual", "Manual")],
                        max_length=20,
                    ),
                ),
                ("checked_in_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": "participation_check_in"},
        ),
        migrations.CreateModel(
            name="WaitlistEntry",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("event_id", models.UUIDField()),
                ("user_id", models.UUIDField()),
                ("position", models.PositiveIntegerField()),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": "participation_waitlist_entry"},
        ),
        migrations.AddConstraint(
            model_name="waitlistentry",
            constraint=models.UniqueConstraint(
                fields=["event_id", "user_id"],
                name="unique_waitlist_entry",
            ),
        ),
    ]
