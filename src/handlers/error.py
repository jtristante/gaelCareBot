"""Global error handler for GaelCareBot."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from src.messages import ERROR_GENERIC

logger = logging.getLogger(__name__)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle unhandled exceptions in the bot.

    Logs the full error traceback and notifies the user if possible.
    Never re-raises the exception — always consumes the error gracefully.
    """
    logger.error(
        "Exception while handling an update: %s",
        context.error,
        exc_info=context.error,
    )

    if update is not None and update.effective_message is not None:
        await update.effective_message.reply_text(ERROR_GENERIC)
