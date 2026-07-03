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
    SUMMARY_ENTRY_LINE,
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
        entry_time = entry["event_date"][11:16]  # Extract HH:MM from ISO format
        sign = "+" if entry["entry_type"] == "ENTRADA" else "-"
        entry_type = "extracción" if entry["entry_type"] == "ENTRADA" else "consumo"
        lines.append(
            SUMMARY_ENTRY_LINE.format(
                time=entry_time, sign=sign, amount=amount,
                entry_type=entry_type, user=user
            )
        )

    balance = sum(
        e["amount"] if e["entry_type"] == "ENTRADA" else -e["amount"]
        for e in entries
    )
    lines.append(SUMMARY_BALANCE.format(balance=balance))

    return "\n".join(lines)


async def send_daily_summary(context, db) -> None:
    """Send or edit the daily summary in the configured group chat.

    If a summary message already exists for today, edits it. Otherwise,
    sends a new message and stores its ID for future edits.

    Silently skips if:
    - Notifier has not been initialized (_config is None).
    - Group chat ID is not configured (None or 0).

    Args:
        context: PTB CallbackContext with ``bot`` attribute.
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
    bot = context.bot

    # Check if we already have a summary message for today
    stored = db.get_daily_summary_message(today)

    if stored is not None and stored.get("chat_id") == group_chat_id:
        # Edit existing message
        try:
            await bot.edit_message_text(
                chat_id=group_chat_id,
                message_id=stored["message_id"],
                text=summary_text,
                disable_notification=True,
            )
            logger.info(
                "Daily summary updated in group chat %s (message %s)",
                group_chat_id,
                stored["message_id"],
            )
            return
        except Exception as exc:
            logger.warning(
                "Failed to edit daily summary (message %s) in group chat %s: %s",
                stored["message_id"],
                group_chat_id,
                exc,
            )
            # Fall through to send a new message

    # Send new message
    try:
        msg = await bot.send_message(
            chat_id=group_chat_id,
            text=summary_text,
            disable_notification=True,
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
