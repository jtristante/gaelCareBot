"""Handler for the /consumir command - reversal mode (ENTRADA → SALIDA)."""

from __future__ import annotations

import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler

from gaelcarebot.auth import authorized_only
from gaelcarebot.db import now_madrid
from gaelcarebot.messages import (
    MSG_CONSUMED,
    MSG_CANCELLED,
    MSG_SELECT_ENTRY,
    MSG_CONFIRM_DELETE,
    BTN_CANCEL,
    BTN_CONFIRM,
    ERROR_NO_ENTRIES,
    ERROR_ENTRY_NOT_FOUND,
)

logger = logging.getLogger(__name__)

# Conversation states
SELECTING_ENTRY = 0
CONFIRMING = 1

# Try to import send_daily_summary - it may not exist yet (Task 12 in progress)
try:
    from gaelcarebot.group_notifier import send_daily_summary
    _SEND_DAILY_SUMMARY_AVAILABLE = True
except ImportError:
    _SEND_DAILY_SUMMARY_AVAILABLE = False
    send_daily_summary = None  # type: ignore


@authorized_only
async def consumir_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await _start_reversal_mode(update, context)


async def _start_reversal_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the reversal conversation - show ENTRADA entries."""
    db = context.bot_data.get("db")
    if db is None:
        logger.error("Database not available in bot_data")
        await update.message.reply_text(ERROR_NO_ENTRIES)
        return ConversationHandler.END

    # Get all entries, then filter for ENTRADA only (not consumed)
    all_entries = db.get_all_entries(order_by="event_date DESC", include_consumed=False)
    entrada_entries = [e for e in all_entries if e["entry_type"] == "ENTRADA"]

    if not entrada_entries:
        await update.message.reply_text(ERROR_NO_ENTRIES)
        return ConversationHandler.END

    # Build inline keyboard with ENTRADA entries only
    keyboard = []
    for entry in entrada_entries:
        # Format: ID - Fecha - Cantidad
        fecha = entry["event_date"][:10] if entry["event_date"] else "N/A"
        label = f"#{entry['id']} [ENTRADA] {fecha} - {entry['amount']}ml"
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

    if entry["entry_type"] != "ENTRADA":
        await query.edit_message_text(ERROR_ENTRY_NOT_FOUND)
        return ConversationHandler.END

    # Store entry_id in user_data for later steps
    context.user_data["reverse_entry_id"] = entry_id

    # Build entry info for confirmation message
    fecha = entry["event_date"][:10] if entry["event_date"] else "N/A"
    entry_info = (
        f"ID: #{entry_id}\n"
        f"Tipo: {entry['entry_type']}\n"
        f"Cantidad: {entry['amount']}ml\n"
        f"Fecha: {fecha}\n"
        f"Notas: {entry.get('notes') or 'Ninguna'}"
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
    cantidad = entry["amount"]
    event_date_raw = entry.get("event_date", "")

    try:
        # Change tipo to SALIDA
        success = db.update_entry(entry_id, entry_type="SALIDA")

        if success:
            # Also set consumed_at to now() for the entry
            db.conn.execute(
                "UPDATE milk_entries SET consumed_at = ? WHERE id = ?",
                (now_madrid(), entry_id)
            )
            db.conn.commit()

            if event_date_raw:
                fecha_parts = event_date_raw[:10].split("-")
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
