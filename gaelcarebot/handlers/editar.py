"""Handler for the /editar command - interactive entry editing."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from gaelcarebot.auth import authorized_only
from gaelcarebot.db import now_madrid
from gaelcarebot.messages import (
    ERROR_ENTRY_NOT_FOUND,
    ERROR_INVALID_AMOUNT,
    ERROR_INVALID_DATE,
    ERROR_NO_ENTRIES,
    BTN_CANCEL,
    BTN_CONFIRM,
    BTN_DENY,
    BTN_EDIT_CANTIDAD,
    BTN_EDIT_FECHA,
    BTN_EDIT_NOTAS,
    BTN_EDIT_TIPO,
    MSG_CANCELLED,
    MSG_CONFIRM_EDIT,
    MSG_ENTER_NEW_VALUE,
    MSG_SELECT_ENTRY,
    MSG_SELECT_FIELD,
    MSG_UPDATED,
)

logger = logging.getLogger(__name__)

# Conversation states
SELECTING_ENTRY = 0
EDITING_FIELD = 1
EDITING_VALUE = 2
CONFIRMING = 3
SELECTING_TIPO = 4


@authorized_only
async def editar_start(update: Update, context: Any) -> int:
    """Start the edit conversation - show last 20 entries.

    Displays entries as inline buttons. If no entries exist,
    shows ERROR_NO_ENTRIES and ends the conversation.
    """
    db = context.bot_data.get("db")
    if db is None:
        logger.error("Database not available in bot_data")
        await update.message.reply_text(ERROR_NO_ENTRIES)
        return ConversationHandler.END

    # Get all entries (including consumed)
    entries = db.get_all_entries(order_by="add_at DESC", include_consumed=True)

    if not entries:
        await update.message.reply_text(ERROR_NO_ENTRIES)
        return ConversationHandler.END

    # Build inline keyboard with entries
    keyboard = []
    for entry in entries:
        # Format: ID - Tipo - Fecha - Cantidad
        fecha = entry["event_date"][:10] if entry["event_date"] else "N/A"
        tipo_label = "ENT" if entry["entry_type"] == "ENTRADA" else "SAL"
        label = f"#{entry['id']} [{tipo_label}] {fecha} - {entry['amount']}ml"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"edit_{entry['id']}")])

    # Add cancel button
    keyboard.append([InlineKeyboardButton(BTN_CANCEL, callback_data="cancel")])

    await update.message.reply_text(
        MSG_SELECT_ENTRY, reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SELECTING_ENTRY


async def entry_selected(update: Update, context: Any) -> int:
    """Handle entry selection and show field options."""
    query = update.callback_query
    await query.answer()

    callback_data = query.data

    if callback_data == "cancel":
        await query.edit_message_text(MSG_CANCELLED)
        return ConversationHandler.END

    # Parse entry id from callback data (format: edit_{id})
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

    # Verify entry exists (editing shows all entries, including consumed)
    entry = db.get_entry(entry_id, include_consumed=True)
    if entry is None:
        await query.edit_message_text(ERROR_ENTRY_NOT_FOUND)
        return ConversationHandler.END

    # Store entry_id in user_data for later steps
    context.user_data["edit_entry_id"] = entry_id
    context.user_data["edit_entry_original"] = entry

    # Show field selection keyboard
    keyboard = [
        [InlineKeyboardButton(BTN_EDIT_CANTIDAD, callback_data="field_amount")],
        [InlineKeyboardButton(BTN_EDIT_FECHA, callback_data="field_fecha")],
        [InlineKeyboardButton(BTN_EDIT_NOTAS, callback_data="field_notes")],
        [InlineKeyboardButton(BTN_EDIT_TIPO, callback_data="field_entry_type")],
        [InlineKeyboardButton(BTN_CANCEL, callback_data="cancel")],
    ]

    await query.edit_message_text(
        MSG_SELECT_FIELD, reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return EDITING_FIELD


async def field_selected(update: Update, context: Any) -> int:
    """Handle field selection and prompt for new value."""
    query = update.callback_query
    await query.answer()

    callback_data = query.data

    if callback_data == "cancel":
        await query.edit_message_text(MSG_CANCELLED)
        return ConversationHandler.END

    # Parse field name from callback data (format: field_{name})
    try:
        field_name = callback_data.split("_", 1)[1]
    except IndexError:
        await query.edit_message_text(MSG_CANCELLED)
        return ConversationHandler.END

    # Map callback names to display names
    field_display_map = {
        "amount": BTN_EDIT_CANTIDAD,
        "fecha": BTN_EDIT_FECHA,
        "notes": BTN_EDIT_NOTAS,
        "entry_type": BTN_EDIT_TIPO,
    }

    context.user_data["edit_field"] = field_name

    # Handle tipo field differently - show ENTRADA/SALIDA options
    if field_name == "entry_type":
        keyboard = [
            [InlineKeyboardButton("ENTRADA", callback_data="entry_type_ENTRADA")],
            [InlineKeyboardButton("SALIDA", callback_data="entry_type_SALIDA")],
            [InlineKeyboardButton(BTN_CANCEL, callback_data="cancel")],
        ]
        await query.edit_message_text(
            "Selecciona el nuevo tipo:", reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return SELECTING_TIPO

    await query.edit_message_text(
        MSG_ENTER_NEW_VALUE.format(campo=field_display_map.get(field_name, field_name))
    )
    return EDITING_VALUE


async def tipo_selected(update: Update, context: Any) -> int:
    """Handle tipo selection and show confirmation."""
    query = update.callback_query
    await query.answer()

    callback_data = query.data

    if callback_data == "cancel":
        await query.edit_message_text(MSG_CANCELLED)
        return ConversationHandler.END

    # Parse tipo value from callback data (format: tipo_{ENTRADA|SALIDA})
    try:
        tipo_value = callback_data.rsplit("_", 1)[1]
    except IndexError:
        await query.edit_message_text(MSG_CANCELLED)
        return ConversationHandler.END

    # Store the selected tipo
    context.user_data["edit_new_value"] = tipo_value
    context.user_data["edit_new_value_raw"] = tipo_value

    # Get original entry for display
    entry_id = context.user_data.get("edit_entry_id")
    original_entry = context.user_data.get("edit_entry_original", {})
    fecha = original_entry.get("event_date", "N/A")[:10] if original_entry.get("event_date") else "N/A"

    # Build confirmation message
    entry_info = (
        f"ID: #{entry_id}\n"
        f"Tipo: {original_entry.get('entry_type', 'N/A')}\n"
        f"Cantidad: {original_entry.get('amount', 'N/A')}ml\n"
        f"Fecha: {fecha}\n"
        f"Notas: {original_entry.get('notes') or 'Ninguna'}\n\n"
        f"Nuevo valor para tipo: {tipo_value}"
    )

    keyboard = [
        [InlineKeyboardButton(BTN_CONFIRM, callback_data="confirm")],
        [InlineKeyboardButton(BTN_DENY, callback_data="cancel")],
    ]

    await query.edit_message_text(
        MSG_CONFIRM_EDIT.format(entry_info=entry_info),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return CONFIRMING


async def receive_value(update: Update, context: Any) -> int:
    """Receive and validate the new value."""
    field_name = context.user_data.get("edit_field")
    entry_id = context.user_data.get("edit_entry_id")

    if not field_name or not entry_id:
        await update.message.reply_text(MSG_CANCELLED)
        return ConversationHandler.END

    new_value = update.message.text.strip()

    # Validate based on field type
    validated_value = None
    if field_name == "amount":
        validated_value = _validate_cantidad(new_value)
        if validated_value is None:
            await update.message.reply_text(ERROR_INVALID_AMOUNT)
            return EDITING_VALUE
    elif field_name == "fecha":
        validated_value = _validate_fecha(new_value)
        if validated_value is None:
            await update.message.reply_text(ERROR_INVALID_DATE)
            return EDITING_VALUE
    else:  # notas
        validated_value = new_value[:200] if new_value else None

    # Store validated value and show confirmation
    context.user_data["edit_new_value"] = validated_value
    context.user_data["edit_new_value_raw"] = new_value

    # Get original entry for display
    original_entry = context.user_data.get("edit_entry_original", {})
    fecha = original_entry.get("event_date", "N/A")[:10] if original_entry.get("event_date") else "N/A"

    # Build confirmation message
    entry_info = (
        f"ID: #{entry_id}\n"
        f"Tipo: {original_entry.get('entry_type', 'N/A')}\n"
        f"Cantidad: {original_entry.get('amount', 'N/A')}ml\n"
        f"Fecha: {fecha}\n"
        f"Notas: {original_entry.get('notes') or 'Ninguna'}\n\n"
        f"Nuevo valor para {field_name}: {new_value}"
    )

    keyboard = [
        [InlineKeyboardButton(BTN_CONFIRM, callback_data="confirm")],
        [InlineKeyboardButton(BTN_DENY, callback_data="cancel")],
    ]

    await update.message.reply_text(
        MSG_CONFIRM_EDIT.format(entry_info=entry_info),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return CONFIRMING


def _validate_cantidad(value: str) -> int | None:
    """Validate cantidad is a positive integer.

    Returns the integer value if valid, None otherwise.
    """
    try:
        cantidad = int(value)
        if cantidad <= 0:
            return None
        return cantidad
    except (ValueError, TypeError):
        return None


def _validate_fecha(value: str) -> str | None:
    """Validate fecha is in DD/MM/YYYY format.

    Returns ISO format date string if valid, None otherwise.
    """
    import re

    # Check format DD/MM/YYYY
    if not re.match(r"^\d{2}/\d{2}/\d{4}$", value):
        return None

    try:
        # Parse the date
        dt = datetime.strptime(value, "%d/%m/%Y")
        # Return ISO format (date only, for storage as part of datetime)
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return None


async def confirm_edit(update: Update, context: Any) -> int:
    """Handle confirmation and apply the edit."""
    query = update.callback_query
    await query.answer()

    callback_data = query.data

    if callback_data == "cancel":
        await query.edit_message_text(MSG_CANCELLED)
        _clear_edit_data(context)
        return ConversationHandler.END

    entry_id = context.user_data.get("edit_entry_id")
    field_name = context.user_data.get("edit_field")
    new_value = context.user_data.get("edit_new_value")

    if not entry_id or not field_name or new_value is None:
        await query.edit_message_text(MSG_CANCELLED)
        _clear_edit_data(context)
        return ConversationHandler.END

    db = context.bot_data.get("db")
    if db is None:
        logger.error("Database not available in bot_data")
        await query.edit_message_text(MSG_CANCELLED)
        _clear_edit_data(context)
        return ConversationHandler.END

    try:
        if field_name == "entry_type":
            original_entry = context.user_data.get("edit_entry_original", {})
            original_entry_type = original_entry.get("entry_type", "")
            if original_entry_type == "SALIDA" and new_value == "ENTRADA":
                # SALIDA → ENTRADA: clear consumed_at first, then update tipo
                db.conn.execute("BEGIN")
                try:
                    db.conn.execute(
                        "UPDATE milk_entries SET consumed_at = NULL WHERE id = ?",
                        (entry_id,),
                    )
                    success = db.update_entry(entry_id, entry_type="ENTRADA")
                    if not success:
                        raise ValueError(
                            "update_entry failed after clearing consumed_at"
                        )
                    db.conn.commit()
                except Exception:
                    db.conn.rollback()
                    success = False
            elif original_entry_type == "ENTRADA" and new_value == "SALIDA":
                # ENTRADA → SALIDA: update tipo first, then set consumed_at
                db.conn.execute("BEGIN")
                try:
                    success = db.update_entry(entry_id, entry_type="SALIDA")
                    if not success:
                        raise ValueError(
                            "update_entry failed for SALIDA change"
                        )
                    db.conn.execute(
                        "UPDATE milk_entries SET consumed_at = ? WHERE id = ?",
                        (now_madrid(), entry_id),
                    )
                    db.conn.commit()
                except Exception:
                    db.conn.rollback()
                    success = False
            else:
                # Same-value or unhandled: standard update (no consumed_at change)
                success = db.update_entry(entry_id, **{field_name: new_value})
        else:
            # Non-tipo fields: standard update
            update_kwargs = {field_name: new_value}

            if field_name == "fecha":
                original_entry = context.user_data.get("edit_entry_original", {})
                original_event_date = original_entry.get("event_date", "")
                if original_add_at and "T" in original_add_at:
                    original_time = original_add_at.split("T")[1]
                    new_value = f"{new_value}T{original_time}"
                else:
                    new_value = f"{new_value}T12:00:00"
                update_kwargs = {"event_date": new_value}

            success = db.update_entry(entry_id, **update_kwargs)

        if success:
            await query.edit_message_text(MSG_UPDATED)
        else:
            await query.edit_message_text(ERROR_ENTRY_NOT_FOUND)

    except Exception as e:
        logger.exception("Error updating entry %d: %s", entry_id, e)
        await query.edit_message_text(ERROR_ENTRY_NOT_FOUND)

    _clear_edit_data(context)
    return ConversationHandler.END


async def cancel(update: Update, context: Any) -> int:
    """Cancel the conversation."""
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(MSG_CANCELLED)
    else:
        await update.message.reply_text(MSG_CANCELLED)
    _clear_edit_data(context)
    return ConversationHandler.END


def _clear_edit_data(context: Any) -> None:
    """Clear user_data related to the edit conversation."""
    keys_to_remove = [
        "edit_entry_id",
        "edit_entry_original",
        "edit_field",
        "edit_new_value",
        "edit_new_value_raw",
    ]
    for key in keys_to_remove:
        context.user_data.pop(key, None)


# Create the ConversationHandler
editar_conv_handler = ConversationHandler(
    entry_points=[CommandHandler("editar", editar_start)],
    states={
        SELECTING_ENTRY: [
            CallbackQueryHandler(entry_selected, pattern=r"^edit_\d+$"),
            CallbackQueryHandler(cancel, pattern="^cancel$"),
        ],
        EDITING_FIELD: [
            CallbackQueryHandler(field_selected, pattern=r"^field_\w+$"),
            CallbackQueryHandler(cancel, pattern="^cancel$"),
        ],
        EDITING_VALUE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_value),
        ],
        SELECTING_TIPO: [
            CallbackQueryHandler(tipo_selected, pattern=r"^tipo_\w+$"),
            CallbackQueryHandler(cancel, pattern="^cancel$"),
        ],
        CONFIRMING: [
            CallbackQueryHandler(confirm_edit, pattern="^confirm$"),
            CallbackQueryHandler(cancel, pattern="^cancel$"),
        ],
    },
    fallbacks=[
        CallbackQueryHandler(cancel, pattern="^cancel$"),
        CommandHandler("cancel", cancel),
    ],
)
