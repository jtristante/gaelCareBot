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

    # Sort chronologically (oldest first) — DB returns DESC
    sorted_entries = sorted(entries, key=lambda e: e["event_date"])

    for entry in sorted_entries:
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


async def send_daily_summary(context, db) -> None:
    """Send daily summary to configured group chat; deletes previous if present."""
    if _config is None:
        logger.debug("Notifier not initialized; skipping daily summary")
        return

    group_chat_id = _config.group_chat_id
    if group_chat_id is None or group_chat_id == 0:
        logger.debug("Group chat ID not configured; skipping daily summary")
        return

    today = datetime.now(pytz.timezone("Europe/Madrid")).strftime("%Y-%m-%d")
    summary_text = get_daily_summary_text(db, today)
    bot = context.bot

    # Delete existing summary message for today if present
    stored = db.get_daily_summary_message(today)
    if stored is not None and stored.get("chat_id") == group_chat_id:
        try:
            await bot.delete_message(
                chat_id=group_chat_id,
                message_id=stored["message_id"],
            )
            logger.info(
                "Deleted previous daily summary (message %s) from group chat %s",
                stored["message_id"],
                group_chat_id,
            )
        except Exception:
            logger.debug(
                "Could not delete previous daily summary (message %s); may have been removed already",
                stored["message_id"],
            )

    # Send new message
    try:
        msg = await bot.send_message(
            chat_id=group_chat_id,
            text=summary_text,
        )
        db.save_daily_summary_message(today, msg.message_id, group_chat_id)
        logger.info(
            "Daily summary sent to group chat %s (message %s)",
            group_chat_id,
            msg.message_id,
        )
    except Exception as exc:
        logger.warning(
            "Failed to send daily summary to group chat %s: %s",
            group_chat_id,
            exc,
        )
