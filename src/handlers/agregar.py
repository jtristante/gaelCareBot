"""Handler for the /agregar command."""

from __future__ import annotations

import logging
from datetime import datetime

from pytz import timezone
from telegram import Update
from telegram.ext import ContextTypes

from src.auth import authorized_only
from src.messages import MSG_ADDED, ERROR_INVALID_AMOUNT

logger = logging.getLogger(__name__)

# Try to import send_daily_summary - it may not exist yet (Task 12 in progress)
try:
    from src.group_notifier import send_daily_summary
    _SEND_DAILY_SUMMARY_AVAILABLE = True
except ImportError:
    _SEND_DAILY_SUMMARY_AVAILABLE = False
    send_daily_summary = None  # type: ignore

MADRID_TZ = timezone("Europe/Madrid")


@authorized_only
async def agregar_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /agregar command — register milk extraction.

    Usage: /agregar <cantidad> [notas]
    
    - cantidad: positive integer in milliliters
    - notas: optional text notes (multiple words allowed)
    
    Only accessible to authorized users via the @authorized_only decorator.
    """
    if not context.args or len(context.args) < 1:
        await update.message.reply_text(ERROR_INVALID_AMOUNT)
        return
    
    try:
        cantidad = int(context.args[0])
    except (ValueError, TypeError):
        await update.message.reply_text(ERROR_INVALID_AMOUNT)
        return
    
    if cantidad <= 0:
        await update.message.reply_text(ERROR_INVALID_AMOUNT)
        return
    
    notas = " ".join(context.args[1:]) if len(context.args) > 1 else None
    
    now_madrid = datetime.now(MADRID_TZ)
    add_at_iso = now_madrid.isoformat()
    fecha_formateada = now_madrid.strftime("%d/%m/%Y")
    
    user = update.effective_user
    user_id = user.id
    username = user.username or user.full_name
    
    db = context.bot_data.get("db")
    if db is None:
        logger.error("Database not available in bot_data")
        await update.message.reply_text(ERROR_INVALID_AMOUNT)
        return
    
    try:
        entry_id = db.add_entry(
            tipo="ENTRADA",
            cantidad=cantidad,
            add_at=add_at_iso,
            user_id=user_id,
            username=username,
            notas=notas,
        )
        logger.info("Added entry %d: %d ml by user %s", entry_id, cantidad, username)
        
        if _SEND_DAILY_SUMMARY_AVAILABLE and send_daily_summary is not None:
            try:
                await send_daily_summary(context.bot, db)
            except Exception as e:
                logger.warning("Failed to send daily summary: %s", e)
        
        await update.message.reply_text(
            MSG_ADDED.format(cantidad=cantidad, fecha=fecha_formateada)
        )
        
    except Exception as e:
        logger.exception("Error adding entry: %s", e)
        await update.message.reply_text(ERROR_INVALID_AMOUNT)
