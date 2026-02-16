"""Migration: add saved_event table to the participation schema."""

from __future__ import annotations

import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    """Creates the SavedEvent table for user event bookmarks."""

    dependencies = [
        ("participation", "0008_ticket_transfer"),
    ]

    operations = [
        migrations.CreateModel(
            name="SavedEvent",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("user_id", models.UUIDField(db_index=True)),
                ("event_id", models.UUIDField()),
                ("saved_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": '"participation"."saved_event"',
                "ordering": ["-saved_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="savedevent",
            constraint=models.UniqueConstraint(
                fields=["user_id", "event_id"],
                name="unique_saved_event",
            ),
        ),
    ]
