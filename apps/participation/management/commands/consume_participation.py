"""Django management command to start the participation RabbitMQ consumer."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.participation.infrastructure.consumer import start_consumer


class Command(BaseCommand):
    """Starts the RabbitMQ consumer for participation-related events."""

    help = "Start the participation service RabbitMQ consumer."

    def handle(self, *args: object, **options: object) -> None:
        """Run the consumer. Blocks indefinitely."""
        self.stdout.write("Starting participation consumer...")
        start_consumer()
