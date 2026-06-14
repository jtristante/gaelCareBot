"""Tests for the /help command handler."""

from __future__ import annotations

import pytest

from gaelcarebot.handlers.help import help_command
from gaelcarebot.messages import HELP_MSG, ERROR_UNAUTHORIZED
from gaelcarebot.auth import init_auth


pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def setup_auth(config):
    init_auth(config)


async def test_help_authorized(authorized_update, mock_context):
    """Authorized user should receive HELP_MSG."""
    await help_command(authorized_update, mock_context)
    authorized_update.message.reply_text.assert_called_once_with(
        HELP_MSG, parse_mode="HTML"
    )


async def test_help_unauthorized(unauthorized_update, mock_context):
    """Unauthorized user should receive ERROR_UNAUTHORIZED."""
    await help_command(unauthorized_update, mock_context)
    unauthorized_update.message.reply_text.assert_called_once_with(ERROR_UNAUTHORIZED)


async def test_help_content(authorized_update, mock_context):
    """HELP_MSG should list all 7 commands."""
    await help_command(authorized_update, mock_context)
    call_args = authorized_update.message.reply_text.call_args[0][0]
    for cmd in ["/start", "/help", "/agregar", "/consumir", "/stock", "/total", "/editar"]:
        assert cmd in call_args, f"Missing command: {cmd}"
