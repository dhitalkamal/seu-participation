from __future__ import annotations

import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("participation", "0006_waitlist_offer_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="EventParticipationContext",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("event_id", models.UUIDField(db_index=True)),
                ("user_id", models.UUIDField(db_index=True)),
                ("participation_type", models.CharField(max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": '"participation"."event_participation_context"',
            },
        ),
        migrations.AddConstraint(
            model_name="eventparticipationcontext",
            constraint=models.UniqueConstraint(
                fields=["event_id", "user_id"],
                name="unique_event_participation_context",
            ),
        ),
    ]
