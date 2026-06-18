"""Main entry point for GaelCareBot.

Wires together all handlers, database, configuration, authentication,
and group notification modules. Entry point for the application.
"""

from __future__ import annotations

import logging

from telegram.ext import Application, CommandHandler

from gaelcarebot.auth import init_auth
from gaelcarebot.config import load_config
from gaelcarebot.db import MilkDatabase
from gaelcarebot.group_notifier import init_notifier
from gaelcarebot.handlers.add import add_conv_handler
from gaelcarebot.handlers.consume import consume_conv_handler
from gaelcarebot.handlers.edit import edit_conv_handler
from gaelcarebot.handlers.error import error_handler
from gaelcarebot.handlers.start import start_command
from gaelcarebot.handlers.stock import stock_command
from gaelcarebot.handlers.help import help_command
from gaelcarebot.handlers.total import total_command

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
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(add_conv_handler)
    application.add_handler(consume_conv_handler)
    application.add_handler(CommandHandler("stock", stock_command))
    application.add_handler(CommandHandler("total", total_command))
    application.add_handler(edit_conv_handler)

    application.add_error_handler(error_handler)

    logger.info("Starting bot polling...")
    application.run_polling(allowed_updates=[])


if __name__ == "__main__":
    main()
