"""Handler for the /start command."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from src.auth import authorized_only
from src.messages import HELP_MSG, WELCOME_MSG

logger = logging.getLogger(__name__)


@authorized_only
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /start command — show welcome message and help.

    Sends the welcome greeting followed by the list of available commands.
    Only accessible to authorized users via the @authorized_only decorator.
    """
    await update.message.reply_text(
        f"{WELCOME_MSG}\n\n{HELP_MSG}",
        parse_mode="Markdown",
    )
