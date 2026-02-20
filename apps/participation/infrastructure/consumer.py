"""RabbitMQ consumer for incoming payment and participation events."""

from __future__ import annotations

import json
import logging
import uuid

import pika
from django.conf import settings

from apps.participation.infrastructure.repositories import (
    DjangoParticipationContextRepository,
    DjangoRegistrationRepository,
)

logger = logging.getLogger(__name__)

_EXCHANGE = "sansaar"
_EXCHANGE_TYPE = "topic"
_QUEUE = "participation.events"
# routing keys this queue subscribes to
_ROUTING_KEYS = ["payment.#", "volunteer.#"]


def _handle_order_completed(payload: dict) -> None:
    """Update the registration's status to confirmed when payment completes."""
    registration_id = payload.get("registration_id")
    if not registration_id:
        logger.warning("payment.order.completed missing registration_id: %s", payload)
        return

    repo = DjangoRegistrationRepository()
    try:
        reg = repo.get_by_id(uuid.UUID(registration_id))
        if reg.status == "pending":
            reg.status = "confirmed"
            repo.update(reg)
            logger.info("Registration %s confirmed after payment.", registration_id)
    except Exception:
        logger.exception("Failed to confirm registration %s.", registration_id)


def _handle_volunteer_approved(payload: dict) -> None:
    """Set the participation context to 'volunteer' when an application is approved."""
    user_id_str = payload.get("user_id")
    event_id_str = payload.get("event_id")
    if not user_id_str or not event_id_str:
        logger.warning("volunteer.application.approved missing user_id or event_id: %s", payload)
        return

    try:
        context_repo = DjangoParticipationContextRepository()
        context_repo.set_context(
            uuid.UUID(event_id_str),
            uuid.UUID(user_id_str),
            "volunteer",
        )
        logger.info("Volunteer context set for user %s on event %s.", user_id_str, event_id_str)
    except Exception:
        logger.exception(
            "Failed to set volunteer context for user %s on event %s.",
            user_id_str,
            event_id_str,
        )


_HANDLERS: dict = {
    "payment.order.completed": _handle_order_completed,
    "volunteer.application.approved": _handle_volunteer_approved,
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
            logger.debug("No handler for event %s, acking.", event_name)
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

    # bind each routing key pattern to this queue
    for routing_key in _ROUTING_KEYS:
        channel.queue_bind(queue=_QUEUE, exchange=_EXCHANGE, routing_key=routing_key)

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=_QUEUE, on_message_callback=_handle_message)

    logger.info("Participation consumer started. Waiting for messages on %s.", _ROUTING_KEYS)
    channel.start_consuming()
