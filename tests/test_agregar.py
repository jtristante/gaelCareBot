"""Tests for the /agregar command handler."""

from __future__ import annotations

import pytest
from unittest.mock import Mock

from src.handlers.agregar import agregar_command
from src.messages import MSG_ADDED, ERROR_INVALID_AMOUNT, ERROR_UNAUTHORIZED
from src.auth import init_auth


pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def setup_auth(config):
    init_auth(config)


def _setup_user_mock(update):
    update.effective_user.username = "test_user"
    update.effective_user.full_name = "Test User"


async def test_agregar_valid(authorized_update, mock_context, db):
    _setup_user_mock(authorized_update)
    mock_context.args = ["150"]
    mock_context.bot_data = {"db": db}
    
    await agregar_command(authorized_update, mock_context)
    
    authorized_update.message.reply_text.assert_called_once()
    call_args = authorized_update.message.reply_text.call_args[0][0]
    assert "150" in call_args
    assert "ml de leche añadidos" in call_args
    
    entries = db.get_all_entries()
    assert len(entries) == 1
    assert entries[0]["cantidad"] == 150
    assert entries[0]["tipo"] == "ENTRADA"


async def test_agregar_invalid_negative(authorized_update, mock_context, db):
    _setup_user_mock(authorized_update)
    mock_context.args = ["-50"]
    mock_context.bot_data = {"db": db}
    
    await agregar_command(authorized_update, mock_context)
    
    authorized_update.message.reply_text.assert_called_once_with(ERROR_INVALID_AMOUNT)
    assert len(db.get_all_entries()) == 0


async def test_agregar_invalid_zero(authorized_update, mock_context, db):
    _setup_user_mock(authorized_update)
    mock_context.args = ["0"]
    mock_context.bot_data = {"db": db}
    
    await agregar_command(authorized_update, mock_context)
    
    authorized_update.message.reply_text.assert_called_once_with(ERROR_INVALID_AMOUNT)
    assert len(db.get_all_entries()) == 0


async def test_agregar_non_numeric(authorized_update, mock_context, db):
    _setup_user_mock(authorized_update)
    mock_context.args = ["abc"]
    mock_context.bot_data = {"db": db}
    
    await agregar_command(authorized_update, mock_context)
    
    authorized_update.message.reply_text.assert_called_once_with(ERROR_INVALID_AMOUNT)
    assert len(db.get_all_entries()) == 0


async def test_agregar_with_notes(authorized_update, mock_context, db):
    _setup_user_mock(authorized_update)
    mock_context.args = ["200", "guardado", "en", "congelador"]
    mock_context.bot_data = {"db": db}
    
    await agregar_command(authorized_update, mock_context)
    
    authorized_update.message.reply_text.assert_called_once()
    
    entries = db.get_all_entries()
    assert len(entries) == 1
    assert entries[0]["cantidad"] == 200
    assert entries[0]["notas"] == "guardado en congelador"


async def test_agregar_missing_args(authorized_update, mock_context, db):
    _setup_user_mock(authorized_update)
    mock_context.args = []
    mock_context.bot_data = {"db": db}
    
    await agregar_command(authorized_update, mock_context)
    
    authorized_update.message.reply_text.assert_called_once_with(ERROR_INVALID_AMOUNT)
    assert len(db.get_all_entries()) == 0


async def test_agregar_unauthorized(unauthorized_update, mock_context, db):
    unauthorized_update.effective_user.username = "unauthorized_user"
    unauthorized_update.effective_user.full_name = "Unauthorized User"
    mock_context.args = ["150"]
    mock_context.bot_data = {"db": db}
    
    await agregar_command(unauthorized_update, mock_context)
    
    unauthorized_update.message.reply_text.assert_called_once_with(ERROR_UNAUTHORIZED)
    assert len(db.get_all_entries()) == 0
