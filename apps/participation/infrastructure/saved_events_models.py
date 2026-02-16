"""Django ORM model for saved events (bookmarked events per user)."""

from __future__ import annotations

import uuid

from django.db import models


class SavedEvent(models.Model):
    """A user bookmarking an event they want to attend later.

    The (user_id, event_id) pair is enforced unique so a user cannot
    save the same event more than once.
    """

    class Meta:
        db_table = '"participation"."saved_event"'
        constraints = [
            models.UniqueConstraint(
                fields=["user_id", "event_id"],
                name="unique_saved_event",
            )
        ]
        ordering = ["-saved_at"]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.UUIDField(db_index=True)
    event_id = models.UUIDField()
    saved_at = models.DateTimeField(auto_now_add=True)
