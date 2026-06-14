"""Authentication middleware for GaelCareBot.

Provides a decorator-based authorization layer that restricts bot commands
to a whitelist of authorized user IDs configured via environment variables.
"""

from __future__ import annotations

import logging
from functools import wraps
from typing import Callable, Coroutine, Any, Set

from gaelcarebot.config import Config
from gaelcarebot.messages import ERROR_UNAUTHORIZED

logger = logging.getLogger(__name__)

# Module-level whitelist of authorized Telegram user IDs.
_authorized_ids: Set[int] = set()


def init_auth(config: Config) -> None:
    """Initialize the authorized user whitelist from the application config.

    Idempotent — calling this function multiple times simply replaces the set
    with the value from the provided config.

    Must be called once at startup, before any handlers are registered.
    """
    global _authorized_ids
    _authorized_ids = config.authorized_user_ids
    logger.info(
        "Auth initialized with %d authorized user(s)", len(_authorized_ids)
    )


def is_authorized(user_id: int) -> bool:
    """Check whether the given Telegram user ID is in the whitelist."""
    return user_id in _authorized_ids


def authorized_only(
    handler_fn: Callable[..., Coroutine[Any, Any, Any]],
) -> Callable[..., Coroutine[Any, Any, Any]]:
    """Decorator that restricts a handler to authorized users only.

    Usage::

        @authorized_only
        async def my_handler(update: Update, context: ContextTypes) -> None:
            ...

    If the user is not authorized:
      - Sends ``ERROR_UNAUTHORIZED`` as a reply (if ``update.message`` exists).
      - Logs the unauthorized attempt at WARNING level.
      - Returns early without calling the wrapped handler.
    """

    @wraps(handler_fn)
    async def wrapper(update: object, context: object) -> None:
        # Defensively extract the user object.
        user = getattr(update, "effective_user", None)
        if user is None:
            logger.warning(
                "Unauthorized access attempt — no effective_user in update"
            )
            return

        user_id = user.id
        username = user.username or user.full_name or str(user_id)

        if not is_authorized(user_id):
            logger.warning(
                "Unauthorized access attempt by user_id=%d username=%s",
                user_id,
                username,
            )
            # Only reply if there is a message to reply to (e.g. callback_query
            # updates do not have update.message).
            msg = getattr(update, "message", None)
            if msg is not None:
                await msg.reply_text(ERROR_UNAUTHORIZED)
            return

        return await handler_fn(update, context)

    return wrapper
