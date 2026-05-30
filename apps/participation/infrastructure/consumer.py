"""RabbitMQ consumer for incoming payment and participation events."""

from __future__ import annotations

import json
import logging
import random
import string
import uuid
from datetime import datetime, timezone

import pika
from django.conf import settings

from apps.participation.domain.entities import RegistrationEntity
from apps.participation.infrastructure.repositories import (
    DjangoParticipationContextRepository,
    DjangoRegistrationRepository,
)

logger = logging.getLogger(__name__)

_EXCHANGE = "sansaar"
_EXCHANGE_TYPE = "topic"
_QUEUE = "participation.events"


def _publish_registration_created(
    *,
    user_id: uuid.UUID,
    event_id: uuid.UUID,
    registration_id: uuid.UUID,
    registration_code: str,
    email: str,
    first_name: str,
) -> None:
    """Publish registration.created so event-service can increment registered_count."""
    try:
        params = pika.URLParameters(settings.RABBITMQ_URL)
        conn = pika.BlockingConnection(params)
        ch = conn.channel()
        ch.exchange_declare(exchange=_EXCHANGE, exchange_type=_EXCHANGE_TYPE, durable=True)
        ch.basic_publish(
            exchange=_EXCHANGE,
            routing_key="participation.registration.created",
            body=json.dumps(
                {
                    "user_id": str(user_id),
                    "event_id": str(event_id),
                    "registration_id": str(registration_id),
                    "registration_code": registration_code,
                    "email": email,
                    "first_name": first_name,
                }
            ),
            properties=pika.BasicProperties(content_type="application/json", delivery_mode=2),
        )
        conn.close()
    except Exception:
        logger.exception("Failed to publish registration.created event")


# routing keys this queue subscribes to
_ROUTING_KEYS = ["payment.#", "volunteer.#"]


def _generate_code() -> str:
    """Generate a unique 8-character alphanumeric registration code."""
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=8))


def _handle_order_completed(payload: dict) -> None:
    """Create or confirm a registration when payment completes.

    For paid events, no registration exists before payment. This handler
    creates the registration automatically after successful payment.
    """
    user_id_str = payload.get("user_id")
    event_id_str = payload.get("event_id")
    registration_id_str = payload.get("registration_id")

    if not user_id_str or not event_id_str:
        logger.warning("payment.order.completed missing user_id or event_id: %s", payload)
        return

    repo = DjangoRegistrationRepository()
    user_id = uuid.UUID(user_id_str)
    event_id = uuid.UUID(event_id_str)

    # if a registration_id was provided, try to confirm an existing one
    if registration_id_str and registration_id_str != "None":
        try:
            reg = repo.get_by_id(uuid.UUID(registration_id_str))
            if reg.status == "pending":
                reg.status = "confirmed"
                repo.update(reg)
                logger.info("Registration %s confirmed after payment.", registration_id_str)
            return
        except Exception:
            logger.info("Registration %s not found, will create new.", registration_id_str)

    # no existing registration - create one (paid event flow)
    if repo.has_active(event_id, user_id):
        logger.info("User %s already registered for event %s, skipping.", user_id, event_id)
        return

    now = datetime.now(timezone.utc)
    registration = RegistrationEntity(
        id=uuid.uuid4(),
        event_id=event_id,
        user_id=user_id,
        status="confirmed",
        registration_code=_generate_code(),
        quantity=1,
        created_at=now,
        updated_at=now,
    )
    try:
        created = repo.create(registration)
        context_repo = DjangoParticipationContextRepository()
        context_repo.set_context(event_id, user_id, "attendee")

        # publish registration event so event-service increments registered_count
        _publish_registration_created(
            user_id=user_id,
            event_id=event_id,
            registration_id=created.id,
            registration_code=created.registration_code,
            email=payload.get("email", ""),
            first_name=payload.get("first_name", ""),
        )
        logger.info(
            "Registration created for user %s on event %s after payment.", user_id, event_id
        )
    except Exception:
        logger.exception(
            "Failed to create registration for user %s on event %s.", user_id, event_id
        )


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
