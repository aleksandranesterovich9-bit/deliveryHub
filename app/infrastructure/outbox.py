"""Transactional outbox.

Problem: "save the order, then publish an event" are two separate systems.
If the app crashes between them (or RabbitMQ is down), the order exists
but nobody ever hears about it.

Solution: command handlers only *stage* the event — insert it into the
`outbox` table in the same DB transaction as the order. Either both are
saved or neither. The relay then publishes staged events to RabbitMQ.

Delivery guarantee is "at least once": if the relay crashes after publishing
but before marking the row as published, the event is sent again.
That is why consumers must be idempotent.
"""

import asyncio
import contextlib
import logging
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import OutboxMessage
from app.db.session import utc_now
from app.domain.events import Event

logger = logging.getLogger(__name__)


def stage_event(session: AsyncSession, event: Event) -> None:
    """Add an event to the current transaction. It is published after commit."""
    session.add(
        OutboxMessage(
            event_id=event.event_id,
            routing_key=event.routing_key,
            payload=event.model_dump_json(),
        )
    )


class Publisher(Protocol):
    async def publish(self, routing_key: str, body: bytes, message_id: str) -> None: ...


class OutboxRelay:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        publisher: Publisher,
        batch_size: int = 100,
    ) -> None:
        self._session_factory = session_factory
        self._publisher = publisher
        self._batch_size = batch_size

    async def publish_pending(self) -> int:
        """Publish one batch of unpublished events. Returns how many were sent."""
        async with self._session_factory() as session:
            statement = (
                select(OutboxMessage)
                .where(OutboxMessage.published_at.is_(None))
                .order_by(OutboxMessage.id)
                .limit(self._batch_size)
                # Lets several relay instances run in parallel without
                # picking the same rows.
                .with_for_update(skip_locked=True)
            )
            messages = (await session.scalars(statement)).all()

            for message in messages:
                await self._publisher.publish(
                    routing_key=message.routing_key,
                    body=message.payload.encode(),
                    message_id=str(message.event_id),
                )
                message.published_at = utc_now()
                logger.info("Published %s (event_id=%s)", message.routing_key, message.event_id)

            await session.commit()
            return len(messages)

    async def run(self, stop: asyncio.Event, poll_interval_seconds: float) -> None:
        logger.info("Outbox relay started")
        while not stop.is_set():
            try:
                published = await self.publish_pending()
            except Exception:
                logger.exception("Outbox relay iteration failed, will retry")
                published = 0

            if published == 0:
                # Sleep, but wake up immediately on shutdown.
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(stop.wait(), timeout=poll_interval_seconds)
        logger.info("Outbox relay stopped")
