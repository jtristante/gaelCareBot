"""Handler for the /agregar command."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from pytz import timezone
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)
from telegram.ext import ContextTypes

from src.auth import authorized_only
from src.messages import MSG_ADDED, MSG_CANCELLED, MSG_PROMPT_AMOUNT, ERROR_INVALID_AMOUNT, BTN_CONFIRM, BTN_CANCEL

logger = logging.getLogger(__name__)

# Try to import send_daily_summary - it may not exist yet (Task 12 in progress)
try:
    from src.group_notifier import send_daily_summary
    _SEND_DAILY_SUMMARY_AVAILABLE = True
except ImportError:
    _SEND_DAILY_SUMMARY_AVAILABLE = False
    send_daily_summary = None  # type: ignore

MADRID_TZ = timezone("Europe/Madrid")

# Conversation states
WAITING_AMOUNT, CONFIRMING = range(2)


async def _agregar_start_impl(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the /agregar command - dual mode entry (inline + interactive).

    Inline mode: /agregar <cantidad> [notas] - adds entry immediately
    Interactive mode: /agregar - prompts for amount, shows confirmation
    """
    if context.args:
        # Inline mode: process args directly
        try:
            cantidad = int(context.args[0])
        except (ValueError, TypeError):
            await update.message.reply_text(ERROR_INVALID_AMOUNT)
            return ConversationHandler.END

        if cantidad <= 0:
            await update.message.reply_text(ERROR_INVALID_AMOUNT)
            return ConversationHandler.END

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
            return ConversationHandler.END

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

        return ConversationHandler.END
    else:
        # Interactive mode: prompt for amount
        await update.message.reply_text(MSG_PROMPT_AMOUNT)
        return WAITING_AMOUNT


@authorized_only
async def agregar_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await _agregar_start_impl(update, context)


async def _receive_amount_impl(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw_text = update.message.text
    text = raw_text.strip() if raw_text and isinstance(raw_text, str) else ""

    try:
        cantidad = int(text)
    except (ValueError, TypeError):
        await update.message.reply_text(ERROR_INVALID_AMOUNT)
        return WAITING_AMOUNT

    if cantidad <= 0:
        await update.message.reply_text(ERROR_INVALID_AMOUNT)
        return WAITING_AMOUNT

    context.user_data["add_cantidad"] = cantidad

    keyboard = [
        [InlineKeyboardButton(BTN_CONFIRM, callback_data="confirm")],
        [InlineKeyboardButton(BTN_CANCEL, callback_data="cancel")],
    ]

    await update.message.reply_text(
        f"¿Confirmar añadir {cantidad} ml?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return CONFIRMING


@authorized_only
async def receive_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await _receive_amount_impl(update, context)


@authorized_only
async def confirm_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle confirmation or cancellation from interactive mode."""
    query = update.callback_query
    await query.answer()

    callback_data = query.data

    if callback_data == "cancel":
        await query.edit_message_text(MSG_CANCELLED)
        _clear_add_data(context)
        return ConversationHandler.END

    # Confirm path
    cantidad = context.user_data.get("add_cantidad")

    if not cantidad:
        await query.edit_message_text(MSG_CANCELLED)
        _clear_add_data(context)
        return ConversationHandler.END

    db = context.bot_data.get("db")
    if db is None:
        logger.error("Database not available in bot_data")
        await query.edit_message_text(MSG_CANCELLED)
        _clear_add_data(context)
        return ConversationHandler.END

    now_madrid = datetime.now(MADRID_TZ)
    add_at_iso = now_madrid.isoformat()
    fecha_formateada = now_madrid.strftime("%d/%m/%Y")

    user = update.effective_user
    user_id = user.id
    username = user.username or user.full_name

    try:
        entry_id = db.add_entry(
            tipo="ENTRADA",
            cantidad=cantidad,
            add_at=add_at_iso,
            user_id=user_id,
            username=username,
            notas=None,
        )
        logger.info("Added entry %d: %d ml by user %s", entry_id, cantidad, username)

        if _SEND_DAILY_SUMMARY_AVAILABLE and send_daily_summary is not None:
            try:
                await send_daily_summary(context.bot, db)
            except Exception as e:
                logger.warning("Failed to send daily summary: %s", e)

        await query.edit_message_text(
            MSG_ADDED.format(cantidad=cantidad, fecha=fecha_formateada)
        )

    except Exception as e:
        logger.exception("Error adding entry: %s", e)
        await query.edit_message_text(ERROR_INVALID_AMOUNT)

    _clear_add_data(context)
    return ConversationHandler.END


@authorized_only
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the conversation at any state."""
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(MSG_CANCELLED)
    else:
        await update.message.reply_text(MSG_CANCELLED)
    _clear_add_data(context)
    return ConversationHandler.END


def _clear_add_data(context: Any) -> None:
    """Clear user_data related to the add conversation."""
    context.user_data.pop("add_cantidad", None)


# Create the ConversationHandler
agregar_conv_handler = ConversationHandler(
    entry_points=[CommandHandler("agregar", agregar_start)],
    states={
        WAITING_AMOUNT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_amount),
        ],
        CONFIRMING: [
            CallbackQueryHandler(confirm_add, pattern="^confirm$"),
            CallbackQueryHandler(cancel, pattern="^cancel$"),
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)


# Keep old agregar_command for backward compatibility (legacy tests still import it)
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
