"""Tests for the /stock command handler."""

from __future__ import annotations

import pytest

from src.auth import init_auth
from src.handlers.stock import stock_command
from src.messages import ERROR_NO_ENTRIES, TABLE_HEADER

pytestmark = pytest.mark.asyncio


@pytest.fixture
def auth_init(config):
    """Initialize auth with test config."""
    init_auth(config)
    return config


async def test_stock_empty(db, mock_update, mock_context, auth_init):
    """With no entries, the handler should reply with ERROR_NO_ENTRIES."""
    mock_context.bot_data["db"] = db

    await stock_command(mock_update, mock_context)

    mock_update.message.reply_html.assert_awaited_once_with(ERROR_NO_ENTRIES)


async def test_stock_with_entries(db, mock_update, mock_context, auth_init):
    """With 3 entries, the handler should display them formatted in a table."""
    db.add_entry("ENTRADA", 200, "2026-05-19T10:00:00", 123, "test_user", "Nota 1")
    db.add_entry("ENTRADA", 150, "2026-05-19T11:00:00", 123, "test_user", None)
    db.add_entry("SALIDA", 100, "2026-05-19T12:00:00", 456, "other_user", None)

    mock_context.bot_data["db"] = db

    await stock_command(mock_update, mock_context)

    mock_update.message.reply_html.assert_awaited_once()
    call_args = mock_update.message.reply_html.call_args[0][0]

    assert "🗓️ Historial de stock:" in call_args
    assert "+ENTRADA" in call_args
    assert "-SALIDA" in call_args
    assert "200ml" in call_args
    assert "150ml" in call_args
    assert "100ml" in call_args
    assert "test_user" in call_args
    assert "other_user" in call_args
    assert "Nota 1" in call_args
    assert "📭 No hay entradas registradas." not in call_args
    assert len(call_args) <= 4096


async def test_stock_pagination(db, mock_update, mock_context, auth_init):
    """With many long-nota entries, the response should truncate."""
    long_nota = (
        "Nota larga para ocupar más espacio "
        "en la tabla de historial de stock"
    )
    for i in range(35):
        db.add_entry(
            "ENTRADA", 100, f"2026-05-19T10:{i:02d}:00",
            123, "test_user", long_nota,
        )

    mock_context.bot_data["db"] = db

    await stock_command(mock_update, mock_context)

    mock_update.message.reply_html.assert_awaited_once()
    call_args = mock_update.message.reply_html.call_args[0][0]

    assert "... y " in call_args
    assert "más..." in call_args
    assert len(call_args) <= 4096
