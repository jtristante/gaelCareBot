"""Handler for the /stock command."""

from __future__ import annotations

import html
import logging
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from src.auth import authorized_only
from src.messages import ERROR_NO_ENTRIES, TABLE_HEADER

logger = logging.getLogger(__name__)


@authorized_only
async def stock_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /stock command — show all ENTRADA entries (extractions).

    Retrieves ENTRADA entries from the database (ordered newest-first) and
    formats them as a monospace table.  SALIDA entries (consumptions) are
    excluded.  If there are no entries the handler replies with
    ERROR_NO_ENTRIES.
    """
    db = context.bot_data["db"]
    entries = [
        e for e in db.get_all_entries(order_by="add_at DESC", include_consumed=False)
        if e["tipo"] == "ENTRADA"
    ]

    if not entries:
        logger.info("Stock list requested but no entries found")
        await update.message.reply_html(ERROR_NO_ENTRIES)
        return

    header_row = f"{'Cantidad':>8} │ {'Fecha/Hora':^14} │ {'Usuario':<20}"
    separator = f"{'─'*8}─┼─{'─'*14}─┼─{'─'*20}"

    rows = []
    for entry in entries:
        dt = datetime.fromisoformat(entry["add_at"])
        fecha_str = dt.strftime("%d/%m %H:%M")

        cantidad_str = f"{entry['cantidad']}ml"
        responsable = html.escape(entry["username"] or "\u2014")

        rows.append(
            f"{cantidad_str:>8} │ {fecha_str:^14} │ {responsable:<20}"
        )

    table_content = "\n".join(rows)
    title = TABLE_HEADER.split("<pre>")[0].strip()
    full_message = f"{title}\n\n<pre>{header_row}\n{separator}\n{table_content}</pre>"

    # Telegram message limit is 4096 characters
    if len(full_message) > 4096:
        trunc_suffix = "\n... y {remaining} m\u00e1s..."
        prefix = f"{title}\n\n<pre>{header_row}\n{separator}\n"
        available = 4096 - len(prefix) - 60

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
            f"{prefix}{table_content}"
            f"{trunc_suffix.format(remaining=remaining)}</pre>"
        )

    logger.info("Stock list requested — %d entries returned", len(entries))
    await update.message.reply_html(full_message)
