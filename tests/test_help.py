"""Tests for the /help command handler."""

from __future__ import annotations

import pytest

from src.handlers.help import help_command
from src.messages import HELP_MSG, ERROR_UNAUTHORIZED
from src.auth import init_auth


pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def setup_auth(config):
    init_auth(config)


async def test_help_authorized(authorized_update, mock_context):
    """Authorized user should receive HELP_MSG."""
    await help_command(authorized_update, mock_context)
    authorized_update.message.reply_text.assert_called_once_with(
        HELP_MSG, parse_mode="Markdown"
    )


async def test_help_unauthorized(unauthorized_update, mock_context):
    """Unauthorized user should receive ERROR_UNAUTHORIZED."""
    await help_command(unauthorized_update, mock_context)
    unauthorized_update.message.reply_text.assert_called_once_with(ERROR_UNAUTHORIZED)


async def test_help_content(authorized_update, mock_context):
    """HELP_MSG should list all 8 commands."""
    await help_command(authorized_update, mock_context)
    call_args = authorized_update.message.reply_text.call_args[0][0]
    for cmd in ["/start", "/help", "/agregar", "/consumir", "/stock", "/total", "/editar", "/eliminar"]:
        assert cmd in call_args, f"Missing command: {cmd}"
