"""Main entry point for GaelCareBot.

Wires together all handlers, database, configuration, authentication,
and group notification modules. Entry point for the application.
"""

from __future__ import annotations

import logging

from telegram.ext import Application, CommandHandler

from src.auth import init_auth
from src.config import load_config
from src.db import MilkDatabase
from src.group_notifier import init_notifier
from src.handlers.agregar import agregar_command
from src.handlers.consumir import consumir_command
from src.handlers.editar import editar_conv_handler
from src.handlers.eliminar import eliminar_conv_handler
from src.handlers.error import error_handler
from src.handlers.start import start_command
from src.handlers.stock import stock_command
from src.handlers.total import total_command

logger = logging.getLogger(__name__)


def main() -> None:
    """Initialize and start the bot.

    Loads configuration, initialises the database, authentication, and
    notifier modules, registers all command and error handlers, and
    starts polling for Telegram updates.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    config = load_config()

    db = MilkDatabase(config.db_path)
    logger.info("Database initialized at %s", config.db_path)

    init_auth(config)
    init_notifier(config)

    application = Application.builder().token(config.bot_token).build()

    application.bot_data["db"] = db

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("agregar", agregar_command))
    application.add_handler(CommandHandler("consumir", consumir_command))
    application.add_handler(CommandHandler("stock", stock_command))
    application.add_handler(CommandHandler("total", total_command))
    application.add_handler(editar_conv_handler)
    application.add_handler(eliminar_conv_handler)

    application.add_error_handler(error_handler)

    logger.info("Starting bot polling...")
    application.run_polling(allowed_updates=[])


if __name__ == "__main__":
    main()
