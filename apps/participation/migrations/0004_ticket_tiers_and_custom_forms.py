"""Migration: add TicketTier, CustomFormField, RegistrationAnswer tables."""

from __future__ import annotations

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("participation", "0003_volunteer_shift"),
    ]

    operations = [
        migrations.CreateModel(
            name="TicketTier",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ("event_id", models.UUIDField(db_index=True)),
                ("name", models.CharField(max_length=100)),
                (
                    "tier_type",
                    models.CharField(
                        choices=[
                            ("general", "General"),
                            ("vip", "VIP"),
                            ("early_bird", "Early Bird"),
                            ("comp", "Complimentary"),
                        ],
                        default="general",
                        max_length=20,
                    ),
                ),
                ("price", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("capacity", models.PositiveIntegerField()),
                ("sold_count", models.PositiveIntegerField(default=0)),
                ("description", models.CharField(blank=True, default="", max_length=500)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": "participation_ticket_tier"},
        ),
        migrations.CreateModel(
            name="CustomFormField",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ("event_id", models.UUIDField(db_index=True)),
                ("label", models.CharField(max_length=255)),
                (
                    "field_type",
                    models.CharField(
                        choices=[
                            ("text", "Short text"),
                            ("textarea", "Long text"),
                            ("select", "Dropdown"),
                            ("checkbox", "Checkbox"),
                            ("radio", "Radio buttons"),
                        ],
                        default="text",
                        max_length=20,
                    ),
                ),
                ("is_required", models.BooleanField(default=False)),
                ("options", models.JSONField(blank=True, default=list)),
                ("position", models.PositiveSmallIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": "participation_custom_form_field", "ordering": ["position"]},
        ),
        migrations.CreateModel(
            name="RegistrationAnswer",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                (
                    "registration",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="answers",
                        to="participation.registration",
                    ),
                ),
                (
                    "field",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="answers",
                        to="participation.customformfield",
                    ),
                ),
                ("value", models.TextField()),
            ],
            options={"db_table": "participation_registration_answer"},
        ),
        migrations.AddConstraint(
            model_name="registrationanswer",
            constraint=models.UniqueConstraint(
                fields=["registration", "field"],
                name="unique_registration_answer",
            ),
        ),
    ]
