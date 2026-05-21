"""Handler for the /eliminar command - interactive entry deletion."""

from __future__ import annotations

import logging
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler

from src.auth import authorized_only
from src.messages import (
    ERROR_NO_ENTRIES,
    ERROR_ENTRY_NOT_FOUND,
    MSG_DELETED,
    MSG_CANCELLED,
    MSG_TIMEOUT,
    MSG_SELECT_ENTRY,
    MSG_CONFIRM_DELETE,
    BTN_CANCEL,
    BTN_CONFIRM,
)

logger = logging.getLogger(__name__)

# Conversation states
SELECTING_ENTRY = 0
CONFIRMING = 1


@authorized_only
async def eliminar_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the delete conversation - show last 20 entries.

    Displays entries as inline buttons. If no entries exist,
    shows ERROR_NO_ENTRIES and ends the conversation.
    """
    db = context.bot_data.get("db")
    if db is None:
        logger.error("Database not available in bot_data")
        await update.message.reply_text(ERROR_NO_ENTRIES)
        return ConversationHandler.END

    # Get last 20 entries
    entries = db.get_all_entries(order_by="fecha_hora DESC")[:20]

    if not entries:
        await update.message.reply_text(ERROR_NO_ENTRIES)
        return ConversationHandler.END

    # Build inline keyboard with entries
    keyboard = []
    for entry in entries:
        # Format: ID - Tipo - Fecha - Cantidad
        fecha = entry["fecha_hora"][:10] if entry["fecha_hora"] else "N/A"
        tipo_label = "ENT" if entry["tipo"] == "ENTRADA" else "SAL"
        label = f"#{entry['id']} [{tipo_label}] {fecha} - {entry['cantidad']}ml"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"del_{entry['id']}")])

    # Add cancel button
    keyboard.append([InlineKeyboardButton(BTN_CANCEL, callback_data="cancel")])

    await update.message.reply_text(
        MSG_SELECT_ENTRY, reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SELECTING_ENTRY


async def entry_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle entry selection and show confirmation prompt."""
    query = update.callback_query
    await query.answer()

    callback_data = query.data

    if callback_data == "cancel":
        await query.edit_message_text(MSG_CANCELLED)
        return ConversationHandler.END

    # Parse entry id from callback data (format: del_{id})
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

    # Verify entry exists
    entry = db.get_entry(entry_id)
    if entry is None:
        await query.edit_message_text(ERROR_ENTRY_NOT_FOUND)
        return ConversationHandler.END

    # Store entry_id in user_data for later steps
    context.user_data["delete_entry_id"] = entry_id

    # Build entry info for confirmation message
    fecha = entry["fecha_hora"][:10] if entry["fecha_hora"] else "N/A"
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


async def confirm_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle confirmation and delete the entry."""
    query = update.callback_query
    await query.answer()

    callback_data = query.data

    if callback_data == "cancel":
        await query.edit_message_text(MSG_CANCELLED)
        _clear_delete_data(context)
        return ConversationHandler.END

    entry_id = context.user_data.get("delete_entry_id")

    if not entry_id:
        await query.edit_message_text(MSG_CANCELLED)
        _clear_delete_data(context)
        return ConversationHandler.END

    db = context.bot_data.get("db")
    if db is None:
        logger.error("Database not available in bot_data")
        await query.edit_message_text(MSG_CANCELLED)
        _clear_delete_data(context)
        return ConversationHandler.END

    try:
        # Delete the entry
        success = db.delete_entry(entry_id)

        if success:
            await query.edit_message_text(MSG_DELETED)
        else:
            await query.edit_message_text(ERROR_ENTRY_NOT_FOUND)

    except Exception as e:
        logger.exception("Error deleting entry %d: %s", entry_id, e)
        await query.edit_message_text(ERROR_ENTRY_NOT_FOUND)

    _clear_delete_data(context)
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the conversation."""
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(MSG_CANCELLED)
    else:
        await update.message.reply_text(MSG_CANCELLED)
    _clear_delete_data(context)
    return ConversationHandler.END


def _clear_delete_data(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clear user_data related to the delete conversation."""
    keys_to_remove = [
        "delete_entry_id",
    ]
    for key in keys_to_remove:
        context.user_data.pop(key, None)


# Create the ConversationHandler
eliminar_conv_handler = ConversationHandler(
    entry_points=[CommandHandler("eliminar", eliminar_start)],
    states={
        SELECTING_ENTRY: [CallbackQueryHandler(entry_selected, pattern="^(del_|cancel)")],
        CONFIRMING: [CallbackQueryHandler(confirm_delete, pattern="^(confirm|cancel)")],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
    per_message=False,
)
