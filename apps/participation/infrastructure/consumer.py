"""RabbitMQ consumer for incoming payment and participation events."""

from __future__ import annotations

import json
import logging

import pika
from django.conf import settings

from apps.participation.infrastructure.repositories import DjangoRegistrationRepository

logger = logging.getLogger(__name__)

_EXCHANGE = "sansaar"
_EXCHANGE_TYPE = "topic"
_QUEUE = "participation.events"
_ROUTING_KEY = "payment.#"


def _handle_order_completed(payload: dict) -> None:
    """Update the registration's status to confirmed when payment completes."""
    registration_id = payload.get("registration_id")
    if not registration_id:
        logger.warning("payment.order.completed missing registration_id: %s", payload)
        return

    repo = DjangoRegistrationRepository()
    try:
        import uuid
        reg = repo.get_by_id(uuid.UUID(registration_id))
        if reg.status == "pending":
            reg.status = "confirmed"
            repo.update(reg)
            logger.info("Registration %s confirmed after payment.", registration_id)
    except Exception:
        logger.exception("Failed to confirm registration %s.", registration_id)


_HANDLERS: dict = {
    "payment.order.completed": _handle_order_completed,
}


def _handle_message(
    channel: pika.channel.Channel,
    method: pika.spec.Basic.Deliver,
    properties: pika.spec.BasicProperties,
    body: bytes,
) -> None:
    """Dispatch incoming message to the appropriate handler."""
    event_name = method.routing_key
    try:
        payload = json.loads(body)
        handler = _HANDLERS.get(event_name)
        if handler:
            handler(payload)
        else:
            logger.debug("No handler for event %s — acking.", event_name)
    except Exception:
        logger.exception("Error processing event %s.", event_name)
    finally:
        channel.basic_ack(delivery_tag=method.delivery_tag)


def start_consumer() -> None:
    """Connect to RabbitMQ and begin consuming participation-relevant events."""
    params = pika.URLParameters(settings.RABBITMQ_URL)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()

    channel.exchange_declare(exchange=_EXCHANGE, exchange_type=_EXCHANGE_TYPE, durable=True)
    channel.queue_declare(queue=_QUEUE, durable=True)
    channel.queue_bind(queue=_QUEUE, exchange=_EXCHANGE, routing_key=_ROUTING_KEY)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=_QUEUE, on_message_callback=_handle_message)

    logger.info("Participation consumer started. Waiting for messages on %s.", _ROUTING_KEY)
    channel.start_consuming()
