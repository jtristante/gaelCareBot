"""Group notification module for GaelCareBot.

Handles daily summary notifications sent to a Telegram group chat.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import pytz

from gaelcarebot.config import Config
from gaelcarebot.messages import (
    SUMMARY_ADDITIONS,
    SUMMARY_BALANCE,
    SUMMARY_CONSUMPTIONS,
    SUMMARY_HEADER,
    SUMMARY_NO_ACTIVITY,
)

logger = logging.getLogger(__name__)

# Module-level config reference (set via init_notifier at startup).
_config: Optional[Config] = None


def init_notifier(config: Config) -> None:
    """Initialize the notifier with the application config.

    Must be called at startup after config is loaded.
    """
    global _config
    _config = config
    logger.info("Notifier initialized with config")


def get_daily_summary_text(db, date: str) -> str:
    """Build a formatted daily summary string.

    Args:
        db: MilkDatabase instance.
        date: ISO date string (YYYY-MM-DD).

    Returns:
        Formatted summary text, or ``SUMMARY_NO_ACTIVITY`` if no entries exist.
    """
    entries = db.get_entries_by_date(date)

    if not entries:
        return SUMMARY_NO_ACTIVITY

    # Convert ISO date (2026-05-19) to DD/MM/YYYY for display
    dt = datetime.strptime(date, "%Y-%m-%d")
    formatted_date = dt.strftime("%d/%m/%Y")

    lines = [SUMMARY_HEADER.format(date=formatted_date)]

    for entry in entries:
        amount = entry["amount"]
        user = entry.get("username") or "Desconocido"

        if entry["entry_type"] == "ENTRADA":
            lines.append(
                SUMMARY_ADDITIONS.format(amount=amount, user=user)
            )
        else:
            lines.append(
                SUMMARY_CONSUMPTIONS.format(amount=amount, user=user)
            )

    balance = sum(
        e["amount"] if e["entry_type"] == "ENTRADA" else -e["amount"]
        for e in entries
    )
    lines.append(SUMMARY_BALANCE.format(balance=balance))

    return "\n".join(lines)


async def send_daily_summary(bot, db) -> None:
    """Send the daily summary to the configured group chat.

    Silently skips if:
    - Notifier has not been initialized (_config is None).
    - Group chat ID is not configured (None or 0).

    Args:
        bot: PTB Bot instance (must have ``send_message`` async method).
        db: MilkDatabase instance.
    """
    if _config is None:
        logger.debug("Notifier not initialized; skipping daily summary")
        return

    group_chat_id = _config.group_chat_id
    if group_chat_id is None or group_chat_id == 0:
        logger.debug("Group chat ID not configured; skipping daily summary")
        return

    today = datetime.now(pytz.timezone("Europe/Madrid")).strftime("%Y-%m-%d")
    summary_text = get_daily_summary_text(db, today)

    try:
        await bot.send_message(chat_id=group_chat_id, text=summary_text)
        logger.info("Daily summary sent to group chat %s", group_chat_id)
    except Exception as exc:
        logger.warning(
            "Failed to send daily summary to group chat %s: %s",
            group_chat_id,
            exc,
        )
