"""Handler for the /stock command."""

from __future__ import annotations

import logging
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from src.auth import authorized_only
from src.messages import ERROR_NO_ENTRIES, TABLE_HEADER

logger = logging.getLogger(__name__)


@authorized_only
async def stock_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /stock command — show complete stock history.

    Retrieves all entries from the database (ordered newest-first) and
    formats them as a monospace table.  If there are no entries the
    handler replies with ERROR_NO_ENTRIES.
    """
    db = context.bot_data["db"]
    entries = db.get_all_entries(order_by="fecha_hora DESC")

    if not entries:
        logger.info("Stock list requested but no entries found")
        await update.message.reply_html(ERROR_NO_ENTRIES)
        return

    rows = []
    for entry in entries:
        dt = datetime.fromisoformat(entry["fecha_hora"])
        fecha_str = dt.strftime("%d/%m %H:%M")

        tipo_str = "+ENTRADA" if entry["tipo"] == "ENTRADA" else "-SALIDA"
        cantidad_str = f"{entry['cantidad']}ml"
        responsable = entry["username"] or "\u2014"
        notas = entry["notas"] or "\u2014"

        rows.append(
            f"{entry['id']:>3} | {fecha_str:<12} | {tipo_str:<13} "
            f"| {cantidad_str:<8} | {responsable:<12} | {notas}"
        )

    table_content = "\n".join(rows)
    full_message = f"{TABLE_HEADER}\n\n<pre>{table_content}</pre>"

    # Telegram message limit is 4096 characters
    if len(full_message) > 4096:
        trunc_suffix = "\n... y {remaining} m\u00e1s..."
        header_overhead = len(TABLE_HEADER) + len("\n\n<pre></pre>")
        available = 4096 - header_overhead - 60

        fitting = []
        current = 0
        for row in rows:
            row_len = len(row) + 1
            if current + row_len > available:
                break
            fitting.append(row)
            current += row_len

        remaining = len(entries) - len(fitting)
        table_content = "\n".join(fitting)
        full_message = (
            f"{TABLE_HEADER}\n\n<pre>{table_content}"
            f"{trunc_suffix.format(remaining=remaining)}</pre>"
        )

    logger.info("Stock list requested — %d entries returned", len(entries))
    await update.message.reply_html(full_message)
