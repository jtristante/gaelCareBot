"""Handler for the /help command."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from src.auth import authorized_only
from src.messages import HELP_MSG

logger = logging.getLogger(__name__)


@authorized_only
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /help command — show available commands.

    Sends the list of available commands with descriptions.
    Only accessible to authorized users via the @authorized_only decorator.
    """
    await update.message.reply_text(HELP_MSG, parse_mode="HTML")
