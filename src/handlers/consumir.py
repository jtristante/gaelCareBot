"""Handler for the /consumir command - two-mode consumption (FIFO or reversal)."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

from pytz import timezone
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler

from src.auth import authorized_only
from src.messages import (
    MSG_CONSUMED,
    MSG_CANCELLED,
    MSG_SELECT_ENTRY,
    MSG_CONFIRM_DELETE,
    BTN_CANCEL,
    BTN_CONFIRM,
    ERROR_INVALID_AMOUNT,
    ERROR_INVALID_DATE,
    ERROR_INSUFFICIENT_STOCK,
    ERROR_FUTURE_DATE,
    ERROR_NO_ENTRIES,
    ERROR_ENTRY_NOT_FOUND,
)

logger = logging.getLogger(__name__)

# Europe/Madrid timezone
MADRID_TZ = timezone("Europe/Madrid")

# Regex for DD/MM/YYYY format
DATE_REGEX = re.compile(r"^\d{2}/\d{2}/\d{4}$")

# Conversation states
SELECTING_ENTRY = 0
CONFIRMING = 1

# Try to import send_daily_summary - it may not exist yet (Task 12 in progress)
try:
    from src.group_notifier import send_daily_summary
    _SEND_DAILY_SUMMARY_AVAILABLE = True
except ImportError:
    _SEND_DAILY_SUMMARY_AVAILABLE = False
    send_daily_summary = None  # type: ignore


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


def _validate_consumption_args(context: ContextTypes.DEFAULT_TYPE) -> tuple[int, datetime, str | None, str | None]:
    """Validate /consumir command arguments.

    Args:
        context: The Telegram context with args

    Returns:
        Tuple of (cantidad, fecha_dt, notas, error_message)
        If validation fails, returns (None, None, None, error_message)
    """
    args = context.args or []

    # Validate that we have at least the amount and date arguments
    if len(args) < 2:
        return None, None, None, ERROR_INVALID_AMOUNT

    # Parse and validate the amount
    try:
        cantidad = int(args[0])
    except (ValueError, TypeError):
        return None, None, None, ERROR_INVALID_AMOUNT

    # Validate that cantidad is positive
    if cantidad <= 0:
        return None, None, None, ERROR_INVALID_AMOUNT

    # Parse and validate the date
    fecha_input = args[1]
    fecha_dt = parse_dd_mm_yyyy(fecha_input)

    if fecha_dt is None:
        return None, None, None, ERROR_INVALID_DATE

    # Check that the date is not in the future
    today_madrid = datetime.now(MADRID_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    input_date = fecha_dt.replace(hour=0, minute=0, second=0, microsecond=0)

    if input_date > today_madrid:
        return None, None, None, ERROR_FUTURE_DATE

    # Parse notes (everything after the date, joined with spaces)
    notas = " ".join(args[2:]) if len(args) > 2 else None

    return cantidad, fecha_dt, notas, None


@authorized_only
async def consumir_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the /consumir command — dual mode: FIFO consumption or reversal.

    Usage with args: /consumir <cantidad> <DD/MM/YYYY> [notas]
        - FIFO consumption mode: marks ENTRADAs as consumed and creates SALIDA

    Usage without args: /consumir
        - Reversal mode: shows ENTRADA entries to convert to SALIDA

    Returns:
        ConversationHandler.END if args mode (immediate completion),
        SELECTING_ENTRY state if no-args mode (conversation flow)
    """
    # Check if we have arguments - if so, use FIFO consumption mode
    if context.args and len(context.args) >= 2:
        return await _handle_fifo_consumption(update, context)
    else:
        # No args - enter reversal mode (conversation flow)
        return await _start_reversal_mode(update, context)


async def _handle_fifo_consumption(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle FIFO consumption mode with args."""
    # Validate arguments
    cantidad, fecha_dt, notas, error = _validate_consumption_args(context)
    if error:
        await update.message.reply_text(error)
        return ConversationHandler.END

    # Get user info
    user = update.effective_user
    user_id = user.id
    username = user.username or user.full_name

    # Get database from bot_data
    db = context.bot_data.get("db")
    if db is None:
        logger.error("Database not available in bot_data")
        await update.message.reply_text(ERROR_INVALID_AMOUNT)
        return ConversationHandler.END

    try:
        # Convert DD/MM/YYYY to ISO format at noon (12:00:00)
        fecha_iso = fecha_dt.strftime("%Y-%m-%dT12:00:00")
        fecha_input = context.args[1]

        # Use consume_fifo to mark ENTRADAs and create SALIDA
        entry_id = db.consume_fifo(
            cantidad=cantidad,
            add_at=fecha_iso,
            user_id=user_id,
            username=username,
            notas=notas,
        )
        logger.info(
            "FIFO consumption: marked ENTRADAs and created SALIDA entry %d: %d ml on %s by user %s",
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

    except ValueError as e:
        # consume_fifo raises ValueError for insufficient stock
        if "Insufficient stock" in str(e) or "insufficient" in str(e).lower():
            # Extract available stock from error message if possible
            available = db.get_total_stock()
            await update.message.reply_text(
                ERROR_INSUFFICIENT_STOCK.format(stock=available)
            )
        else:
            logger.exception("Error processing FIFO consumption: %s", e)
            await update.message.reply_text(ERROR_INVALID_AMOUNT)
    except Exception as e:
        logger.exception("Error processing consumption: %s", e)
        await update.message.reply_text(ERROR_INVALID_AMOUNT)

    return ConversationHandler.END


async def _start_reversal_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the reversal conversation - show ENTRADA entries."""
    db = context.bot_data.get("db")
    if db is None:
        logger.error("Database not available in bot_data")
        await update.message.reply_text(ERROR_NO_ENTRIES)
        return ConversationHandler.END

    # Get all entries, then filter for ENTRADA only (not consumed)
    all_entries = db.get_all_entries(order_by="add_at DESC", include_consumed=False)
    entrada_entries = [e for e in all_entries if e["tipo"] == "ENTRADA"]

    if not entrada_entries:
        await update.message.reply_text(ERROR_NO_ENTRIES)
        return ConversationHandler.END

    # Build inline keyboard with ENTRADA entries only
    keyboard = []
    for entry in entrada_entries:
        # Format: ID - Fecha - Cantidad
        fecha = entry["add_at"][:10] if entry["add_at"] else "N/A"
        label = f"#{entry['id']} [ENTRADA] {fecha} - {entry['cantidad']}ml"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"reverse_{entry['id']}")])

    # Add cancel button
    keyboard.append([InlineKeyboardButton(BTN_CANCEL, callback_data="cancel")])

    await update.message.reply_text(
        MSG_SELECT_ENTRY, reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SELECTING_ENTRY


async def entry_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle entry selection and show confirmation prompt for reversal."""
    query = update.callback_query
    await query.answer()

    callback_data = query.data

    if callback_data == "cancel":
        await query.edit_message_text(MSG_CANCELLED)
        return ConversationHandler.END

    # Parse entry id from callback data (format: reverse_{id})
    try:
        entry_id = int(callback_data.split("_")[1])
    except (IndexError, ValueError):
        await query.edit_message_text(ERROR_ENTRY_NOT_FOUND)
        return ConversationHandler.END

    db = context.bot_data.get("db")
    if db is None:
        logger.error("Database not available in bot_data")
        await query.edit_message_text(ERROR_ENTRY_NOT_FOUND)
        return ConversationHandler.END

    # Verify entry exists and is still ENTRADA
    entry = db.get_entry(entry_id)
    if entry is None:
        await query.edit_message_text(ERROR_ENTRY_NOT_FOUND)
        return ConversationHandler.END

    if entry["tipo"] != "ENTRADA":
        await query.edit_message_text(ERROR_ENTRY_NOT_FOUND)
        return ConversationHandler.END

    # Store entry_id in user_data for later steps
    context.user_data["reverse_entry_id"] = entry_id

    # Build entry info for confirmation message
    fecha = entry["add_at"][:10] if entry["add_at"] else "N/A"
    entry_info = (
        f"ID: #{entry_id}\n"
        f"Tipo: {entry['tipo']}\n"
        f"Cantidad: {entry['cantidad']}ml\n"
        f"Fecha: {fecha}\n"
        f"Notas: {entry.get('notas') or 'Ninguna'}"
    )

    # Show confirmation keyboard
    keyboard = [
        [InlineKeyboardButton(BTN_CONFIRM, callback_data="confirm")],
        [InlineKeyboardButton(BTN_CANCEL, callback_data="cancel")],
    ]

    await query.edit_message_text(
        MSG_CONFIRM_DELETE.format(entry_info=entry_info),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return CONFIRMING


async def confirm_reversal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle confirmation and reverse the entry (ENTRADA → SALIDA + consumed_at)."""
    query = update.callback_query
    await query.answer()

    callback_data = query.data

    if callback_data == "cancel":
        await query.edit_message_text(MSG_CANCELLED)
        _clear_reversal_data(context)
        return ConversationHandler.END

    entry_id = context.user_data.get("reverse_entry_id")

    if not entry_id:
        await query.edit_message_text(MSG_CANCELLED)
        _clear_reversal_data(context)
        return ConversationHandler.END

    db = context.bot_data.get("db")
    if db is None:
        logger.error("Database not available in bot_data")
        await query.edit_message_text(MSG_CANCELLED)
        _clear_reversal_data(context)
        return ConversationHandler.END

    # Capture entry data BEFORE mutation (get_entry filters by consumed_at IS NULL)
    entry = db.get_entry(entry_id)
    if not entry:
        await query.edit_message_text(ERROR_ENTRY_NOT_FOUND)
        _clear_reversal_data(context)
        return ConversationHandler.END
    cantidad = entry["cantidad"]
    add_at_raw = entry.get("add_at", "")

    try:
        # Change tipo to SALIDA
        success = db.update_entry(entry_id, tipo="SALIDA")

        if success:
            # Also set consumed_at to now() for the entry
            db.conn.execute(
                "UPDATE transactions SET consumed_at = strftime('%Y-%m-%dT%H:%M:%S', 'now') WHERE id = ?",
                (entry_id,)
            )
            db.conn.commit()

            if add_at_raw:
                fecha_parts = add_at_raw[:10].split("-")
                formatted_date = f"{fecha_parts[2]}/{fecha_parts[1]}/{fecha_parts[0]}"
            else:
                formatted_date = "N/A"

            # Try to send daily summary notification (gracefully handle if not available)
            if _SEND_DAILY_SUMMARY_AVAILABLE and send_daily_summary is not None:
                try:
                    await send_daily_summary(context.bot, db)
                except Exception as e:
                    logger.warning("Failed to send daily summary: %s", e)

            await query.edit_message_text(
                MSG_CONSUMED.format(cantidad=cantidad, fecha=formatted_date)
            )
        else:
            await query.edit_message_text(ERROR_ENTRY_NOT_FOUND)

    except Exception as e:
        logger.exception("Error reversing entry %d: %s", entry_id, e)
        await query.edit_message_text(ERROR_ENTRY_NOT_FOUND)

    _clear_reversal_data(context)
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the conversation."""
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(MSG_CANCELLED)
    else:
        await update.message.reply_text(MSG_CANCELLED)
    _clear_reversal_data(context)
    return ConversationHandler.END


def _clear_reversal_data(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clear user_data related to the reversal conversation."""
    keys_to_remove = [
        "reverse_entry_id",
    ]
    for key in keys_to_remove:
        context.user_data.pop(key, None)


# Create the ConversationHandler
consumir_conv_handler = ConversationHandler(
    entry_points=[CommandHandler("consumir", consumir_command)],
    states={
        SELECTING_ENTRY: [CallbackQueryHandler(entry_selected, pattern="^(reverse_|cancel)")],
        CONFIRMING: [CallbackQueryHandler(confirm_reversal, pattern="^(confirm|cancel)")],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)
