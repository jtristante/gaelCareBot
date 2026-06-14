"""Handler for the /total command."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from gaelcarebot.auth import authorized_only
from gaelcarebot.messages import MSG_STOCK_TOTAL, MSG_STOCK_TOTAL_ZERO

logger = logging.getLogger(__name__)


@authorized_only
async def total_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /total command — show current total milk stock.

    Retrieves the net balance (ENTRADA - SALIDA) from the database and
    replies with a formatted message indicating the amount available.
    Only accessible to authorized users via the @authorized_only decorator.
    """
    db = context.bot_data["db"]
    stock = db.get_total_stock()

    if stock > 0:
        await update.message.reply_text(MSG_STOCK_TOTAL.format(cantidad=stock))
    else:
        await update.message.reply_text(MSG_STOCK_TOTAL_ZERO)
