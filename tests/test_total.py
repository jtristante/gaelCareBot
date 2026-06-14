"""Tests for the /total command handler."""

from __future__ import annotations

import pytest

from gaelcarebot.auth import init_auth
from gaelcarebot.handlers.total import total_command
from gaelcarebot.messages import MSG_STOCK_TOTAL, MSG_STOCK_TOTAL_ZERO


@pytest.fixture
def auth_init(config):
    """Initialize auth with test config."""
    init_auth(config)
    return config


@pytest.mark.asyncio
async def test_total_positive(db, mock_update, mock_context, auth_init):
    """Adding 200+100 and a SALIDA 50 should report total of 300 (sum of ENTRADAs)."""
    db.add_entry("ENTRADA", 200, "2026-05-19T10:00:00", 123, "test_user")
    db.add_entry("ENTRADA", 100, "2026-05-19T11:00:00", 123, "test_user")
    db.add_entry("SALIDA", 50, "2026-05-19T12:00:00", 123, "test_user")

    mock_context.bot_data["db"] = db

    await total_command(mock_update, mock_context)

    expected = MSG_STOCK_TOTAL.format(cantidad=300)
    mock_update.message.reply_text.assert_awaited_once_with(expected)


@pytest.mark.asyncio
async def test_total_zero(db, mock_update, mock_context, auth_init):
    """With no entries, the handler should return the zero message."""
    mock_context.bot_data["db"] = db

    await total_command(mock_update, mock_context)

    mock_update.message.reply_text.assert_awaited_once_with(MSG_STOCK_TOTAL_ZERO)


@pytest.mark.asyncio
async def test_total_after_full_consumption(db, mock_update, mock_context, auth_init):
    """SALIDA doesn't reduce total — ENTRADA still counts until consumed via consume_fifo."""
    db.add_entry("ENTRADA", 100, "2026-05-19T10:00:00", 123, "test_user")
    db.add_entry("SALIDA", 100, "2026-05-19T12:00:00", 123, "test_user")

    mock_context.bot_data["db"] = db

    await total_command(mock_update, mock_context)

    expected = MSG_STOCK_TOTAL.format(cantidad=100)
    mock_update.message.reply_text.assert_awaited_once_with(expected)
