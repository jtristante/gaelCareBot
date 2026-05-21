"""Handler for the /consumir command."""

from __future__ import annotations

import logging
import re
from datetime import datetime

from pytz import timezone
from telegram import Update
from telegram.ext import ContextTypes

from src.auth import authorized_only
from src.messages import (
    MSG_CONSUMED,
    ERROR_INVALID_AMOUNT,
    ERROR_INVALID_DATE,
    ERROR_INSUFFICIENT_STOCK,
    ERROR_FUTURE_DATE,
)

logger = logging.getLogger(__name__)

# Try to import send_daily_summary - it may not exist yet (Task 12 in progress)
try:
    from src.group_notifier import send_daily_summary
    _SEND_DAILY_SUMMARY_AVAILABLE = True
except ImportError:
    _SEND_DAILY_SUMMARY_AVAILABLE = False
    send_daily_summary = None  # type: ignore

# Europe/Madrid timezone
MADRID_TZ = timezone("Europe/Madrid")

# Regex for DD/MM/YYYY format
DATE_REGEX = re.compile(r"^\d{2}/\d{2}/\d{4}$")


def parse_dd_mm_yyyy(date_str: str) -> datetime | None:
    """Parse a date string in DD/MM/YYYY format.
    
    Returns a datetime object if valid, None otherwise.
    Validates that the date is a real calendar date (e.g., rejects 32/13/2026).
    """
    if not DATE_REGEX.match(date_str):
        return None
    
    try:
        dt = datetime.strptime(date_str, "%d/%m/%Y")
        return MADRID_TZ.localize(dt)
    except ValueError:
        return None


@authorized_only
async def consumir_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /consumir command — register milk consumption.

    Usage: /consumir <cantidad> <DD/MM/YYYY> [notas]
    
    - cantidad: positive integer in milliliters
    - fecha: date in DD/MM/YYYY format (e.g., 19/05/2026)
    - notas: optional text notes (multiple words allowed)
    
    Validates:
    - Cantidad is a positive integer (> 0)
    - Fecha matches DD/MM/YYYY format and is a valid calendar date
    - Fecha is not in the future
    - Sufficient stock exists to cover the consumption
    
    Only accessible to authorized users via the @authorized_only decorator.
    """
    # Validate that we have at least the amount and date arguments
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(ERROR_INVALID_AMOUNT)
        return
    
    # Parse and validate the amount
    try:
        cantidad = int(context.args[0])
    except (ValueError, TypeError):
        await update.message.reply_text(ERROR_INVALID_AMOUNT)
        return
    
    # Validate that cantidad is positive
    if cantidad <= 0:
        await update.message.reply_text(ERROR_INVALID_AMOUNT)
        return
    
    # Parse and validate the date
    fecha_input = context.args[1]
    fecha_dt = parse_dd_mm_yyyy(fecha_input)
    
    if fecha_dt is None:
        await update.message.reply_text(ERROR_INVALID_DATE)
        return
    
    # Check that the date is not in the future
    today_madrid = datetime.now(MADRID_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    input_date = fecha_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    
    if input_date > today_madrid:
        await update.message.reply_text(ERROR_FUTURE_DATE)
        return
    
    # Parse notes (everything after the date, joined with spaces)
    notas = " ".join(context.args[2:]) if len(context.args) > 2 else None
    
    # Get user info
    user = update.effective_user
    user_id = user.id
    username = user.username or user.full_name
    
    # Get database from bot_data
    db = context.bot_data.get("db")
    if db is None:
        logger.error("Database not available in bot_data")
        await update.message.reply_text(ERROR_INVALID_AMOUNT)
        return
    
    try:
        # Check stock sufficiency BEFORE creating entry
        total_stock = db.get_total_stock()
        
        if cantidad > total_stock:
            await update.message.reply_text(
                ERROR_INSUFFICIENT_STOCK.format(stock=total_stock)
            )
            return
        
        # Convert DD/MM/YYYY to ISO format at noon (12:00:00)
        fecha_iso = fecha_dt.strftime("%Y-%m-%dT12:00:00")
        
        # Add the SALIDA entry to the database
        entry_id = db.add_entry(
            tipo="SALIDA",
            cantidad=cantidad,
            fecha_hora=fecha_iso,
            user_id=user_id,
            username=username,
            notas=notas,
        )
        logger.info(
            "Added SALIDA entry %d: %d ml on %s by user %s",
            entry_id, cantidad, fecha_input, username
        )
        
        # Try to send daily summary notification (gracefully handle if not available)
        if _SEND_DAILY_SUMMARY_AVAILABLE and send_daily_summary is not None:
            try:
                await send_daily_summary(context.bot, db)
            except Exception as e:
                logger.warning("Failed to send daily summary: %s", e)
        
        # Reply with success message
        await update.message.reply_text(
            MSG_CONSUMED.format(cantidad=cantidad, fecha=fecha_input)
        )
        
    except Exception as e:
        logger.exception("Error processing consumption: %s", e)
        await update.message.reply_text(ERROR_INVALID_AMOUNT)
