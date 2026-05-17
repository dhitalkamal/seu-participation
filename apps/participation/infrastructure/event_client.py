"""HTTP adapter for fetching event data from the event-service."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
import uuid

from apps.participation.domain.entities import EventSummary
from apps.participation.domain.exceptions import EventNotFoundError
from apps.participation.domain.repositories import IEventClient


class HttpEventClient(IEventClient):
    """Calls the event-service REST API to fetch event details."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    def get_event(self, event_id: uuid.UUID) -> EventSummary:
        """
        Fetch event capacity and registered_count from the event-service.

        @param event_id - the event to look up
        @returns EventSummary with capacity and registered_count
        @raises EventNotFoundError if the event returns 404 or the service is unreachable
        """
        url = f"{self._base_url}/api/v1/events/{event_id}/"
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read())["data"]
                return EventSummary(
                    event_id=uuid.UUID(data["id"]),
                    capacity=data["capacity"],
                    registered_count=data["registered_count"],
                )
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise EventNotFoundError("Event not found.")
            raise EventNotFoundError(f"Event service returned error {exc.code}.")
        except (urllib.error.URLError, KeyError, ValueError) as exc:
            raise EventNotFoundError(f"Could not reach event service: {exc}")
