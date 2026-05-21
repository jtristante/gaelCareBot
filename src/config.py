"""Configuration module for GaelCareBot.

Reads configuration from environment variables and provides a typed Config dataclass.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Optional, Set

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Config:
    """Application configuration loaded from environment variables."""

    bot_token: str
    authorized_user_ids: Set[int]
    group_chat_id: Optional[int] = None
    db_path: str = "data/milk.db"
    timezone: str = "Europe/Madrid"
    conversation_timeout: int = field(default=300)


def load_config(dotenv_path: Optional[str] = None) -> Config:
    """Load configuration from environment variables.

    Args:
        dotenv_path: Optional path to a .env file. If provided, it's loaded
                     via python-dotenv (must be installed separately).

    Returns:
        A Config dataclass instance with validated values.

    Raises:
        ValueError: If BOT_TOKEN is missing/empty or AUTHORIZED_USER_IDS
                    has fewer than 1 valid integer.
    """
    if dotenv_path is not None:
        try:
            from dotenv import load_dotenv

            load_dotenv(dotenv_path)
        except ImportError:
            logger.warning(
                "python-dotenv not installed; ignoring dotenv_path=%s", dotenv_path
            )

    bot_token = os.environ.get("BOT_TOKEN", "")
    if not bot_token:
        raise ValueError("BOT_TOKEN environment variable is required and must not be empty")

    raw_ids = os.environ.get("AUTHORIZED_USER_IDS", "")
    if not raw_ids:
        raise ValueError(
            "AUTHORIZED_USER_IDS environment variable is required "
            "and must contain at least one valid integer"
        )

    authorized_user_ids: Set[int] = set()
    for part in raw_ids.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            authorized_user_ids.add(int(part))
        except ValueError:
            raise ValueError(
                f"Invalid integer in AUTHORIZED_USER_IDS: {part!r}"
            ) from None

    if not authorized_user_ids:
        raise ValueError(
            "AUTHORIZED_USER_IDS must contain at least one valid integer"
        )

    raw_group = os.environ.get("GROUP_CHAT_ID", "")
    group_chat_id: Optional[int] = None
    if raw_group and raw_group.strip():
        try:
            group_chat_id = int(raw_group.strip())
        except ValueError:
            logger.warning("Invalid GROUP_CHAT_ID value: %r; ignoring", raw_group)

    db_path = os.environ.get("DB_PATH", "data/milk.db")
    timezone = os.environ.get("TIMEZONE", "Europe/Madrid")
    timeout_raw = os.environ.get("CONVERSATION_TIMEOUT", "300")
    try:
        conversation_timeout = int(timeout_raw)
    except ValueError:
        logger.warning(
            "Invalid CONVERSATION_TIMEOUT value: %r; using default 300", timeout_raw
        )
        conversation_timeout = 300

    logger.info(
        "Config loaded: %d authorized user(s), group_chat_id=%s, "
        "db_path=%s, timezone=%s, conversation_timeout=%d",
        len(authorized_user_ids),
        group_chat_id,
        db_path,
        timezone,
        conversation_timeout,
    )

    return Config(
        bot_token=bot_token,
        authorized_user_ids=authorized_user_ids,
        group_chat_id=group_chat_id,
        db_path=db_path,
        timezone=timezone,
        conversation_timeout=conversation_timeout,
    )
