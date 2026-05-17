"""RabbitMQ event publisher for the participation service."""

from __future__ import annotations

import json
import logging

import pika
from django.conf import settings

from apps.participation.domain.repositories import IEventPublisher

logger = logging.getLogger(__name__)

_EXCHANGE = "sansaar"
_EXCHANGE_TYPE = "topic"


class RabbitMQEventPublisher(IEventPublisher):
    """Publishes domain events to the sansaar RabbitMQ topic exchange."""

    def publish(self, *, routing_key: str, payload: dict) -> None:
        """Open a transient connection, publish the event, then close."""
        try:
            params = pika.URLParameters(settings.RABBITMQ_URL)
            connection = pika.BlockingConnection(params)
            channel = connection.channel()
            channel.exchange_declare(
                exchange=_EXCHANGE,
                exchange_type=_EXCHANGE_TYPE,
                durable=True,
            )
            channel.basic_publish(
                exchange=_EXCHANGE,
                routing_key=routing_key,
                body=json.dumps(payload),
                properties=pika.BasicProperties(
                    delivery_mode=2,
                    content_type="application/json",
                ),
            )
            connection.close()
        except Exception:
            logger.exception("Failed to publish event %s.", routing_key)
