"""Tests for the /consumir command handler."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pytz import timezone

from src.handlers.consumir import consumir_command, parse_dd_mm_yyyy
from src.messages import (
    MSG_CONSUMED,
    ERROR_INVALID_AMOUNT,
    ERROR_INVALID_DATE,
    ERROR_INSUFFICIENT_STOCK,
    ERROR_FUTURE_DATE,
)

MADRID_TZ = timezone("Europe/Madrid")


class TestParseDdMmYyyy:
    """Tests for the parse_dd_mm_yyyy helper function."""
    
    def test_valid_date(self):
        result = parse_dd_mm_yyyy("19/05/2026")
        assert result is not None
        assert result.day == 19
        assert result.month == 5
        assert result.year == 2026
    
    def test_invalid_format(self):
        assert parse_dd_mm_yyyy("2026-05-19") is None
        assert parse_dd_mm_yyyy("19-05-2026") is None
        assert parse_dd_mm_yyyy("05/19/2026") is None
    
    def test_invalid_calendar_date(self):
        assert parse_dd_mm_yyyy("32/13/2026") is None
        assert parse_dd_mm_yyyy("31/02/2026") is None
        assert parse_dd_mm_yyyy("00/05/2026") is None
    
    def test_empty_string(self):
        assert parse_dd_mm_yyyy("") is None


class TestConsumirCommand:
    """Tests for the consumir_command handler."""
    
    @pytest.fixture
    def mock_db(self):
        """Create a mock database with get_total_stock and add_entry methods."""
        db = Mock()
        db.get_total_stock = Mock(return_value=200)
        db.add_entry = Mock(return_value=1)
        return db
    
    @pytest.fixture
    def setup_context(self, mock_db):
        """Create a mock context with the database in bot_data."""
        def _create(args: list[str] | None = None):
            ctx = Mock()
            ctx.bot.send_message = AsyncMock()
            ctx.bot_data = {"db": mock_db}
            ctx.user_data = {}
            ctx.args = args or []
            ctx.match = None
            return ctx
        return _create
    
    @pytest.fixture
    def setup_update(self):
        """Create a mock update with an authorized user."""
        def _create(user_id: int = 123):
            update = Mock()
            update.effective_user = Mock()
            update.effective_user.id = user_id
            update.effective_user.username = "test_user"
            update.effective_user.full_name = "Test User"
            update.message = Mock()
            update.message.reply_text = AsyncMock()
            update.callback_query = None
            return update
        return _create
    
    @pytest.mark.asyncio
    async def test_consumir_valid(self, setup_update, setup_context, mock_db):
        """Test valid consumption: 100ml on 19/05/2026 with 200ml stock."""
        update = setup_update(123)
        ctx = setup_context(["100", "19/05/2026"])
        
        await consumir_command(update, ctx)
        
        # Verify stock was checked
        mock_db.get_total_stock.assert_called_once()
        
        # Verify SALIDA entry was created
        mock_db.add_entry.assert_called_once()
        call_kwargs = mock_db.add_entry.call_args.kwargs
        assert call_kwargs["tipo"] == "SALIDA"
        assert call_kwargs["cantidad"] == 100
        assert call_kwargs["fecha_hora"] == "2026-05-19T12:00:00"
        assert call_kwargs["user_id"] == 123
        
        # Verify success message
        update.message.reply_text.assert_called_once_with(
            MSG_CONSUMED.format(cantidad=100, fecha="19/05/2026")
        )
    
    @pytest.mark.asyncio
    async def test_consumir_insufficient_stock(self, setup_update, setup_context, mock_db):
        """Test consumption with insufficient stock: 100ml with 0ml available."""
        mock_db.get_total_stock.return_value = 0
        
        update = setup_update(123)
        ctx = setup_context(["100", "19/05/2026"])
        
        await consumir_command(update, ctx)
        
        # Verify stock was checked
        mock_db.get_total_stock.assert_called_once()
        
        # Verify no entry was created
        mock_db.add_entry.assert_not_called()
        
        # Verify error message
        update.message.reply_text.assert_called_once_with(
            ERROR_INSUFFICIENT_STOCK.format(stock=0)
        )
    
    @pytest.mark.asyncio
    async def test_consumir_invalid_date(self, setup_update, setup_context, mock_db):
        """Test consumption with invalid calendar date: 99/99/2026."""
        update = setup_update(123)
        ctx = setup_context(["100", "99/99/2026"])
        
        await consumir_command(update, ctx)
        
        # Verify no database operations
        mock_db.get_total_stock.assert_not_called()
        mock_db.add_entry.assert_not_called()
        
        # Verify error message
        update.message.reply_text.assert_called_once_with(ERROR_INVALID_DATE)
    
    @pytest.mark.asyncio
    async def test_consumir_wrong_format(self, setup_update, setup_context, mock_db):
        """Test consumption with wrong date format: 2026-05-19 (ISO)."""
        update = setup_update(123)
        ctx = setup_context(["100", "2026-05-19"])
        
        await consumir_command(update, ctx)
        
        # Verify no database operations
        mock_db.get_total_stock.assert_not_called()
        mock_db.add_entry.assert_not_called()
        
        # Verify error message
        update.message.reply_text.assert_called_once_with(ERROR_INVALID_DATE)
    
    @pytest.mark.asyncio
    async def test_consumir_negative(self, setup_update, setup_context, mock_db):
        """Test consumption with negative amount: -50ml."""
        update = setup_update(123)
        ctx = setup_context(["-50", "19/05/2026"])
        
        await consumir_command(update, ctx)
        
        # Verify no database operations
        mock_db.get_total_stock.assert_not_called()
        mock_db.add_entry.assert_not_called()
        
        # Verify error message
        update.message.reply_text.assert_called_once_with(ERROR_INVALID_AMOUNT)
    
    @pytest.mark.asyncio
    async def test_consumir_zero(self, setup_update, setup_context, mock_db):
        """Test consumption with zero amount."""
        update = setup_update(123)
        ctx = setup_context(["0", "19/05/2026"])
        
        await consumir_command(update, ctx)
        
        # Verify no database operations
        mock_db.get_total_stock.assert_not_called()
        mock_db.add_entry.assert_not_called()
        
        # Verify error message
        update.message.reply_text.assert_called_once_with(ERROR_INVALID_AMOUNT)
    
    @pytest.mark.asyncio
    async def test_consumir_exact_stock(self, setup_update, setup_context, mock_db):
        """Test consuming exactly all available stock: 100ml with 100ml available."""
        mock_db.get_total_stock.return_value = 100
        
        update = setup_update(123)
        ctx = setup_context(["100", "19/05/2026"])
        
        await consumir_command(update, ctx)
        
        # Verify stock was checked
        mock_db.get_total_stock.assert_called_once()
        
        # Verify SALIDA entry was created (stock becomes 0)
        mock_db.add_entry.assert_called_once()
        call_kwargs = mock_db.add_entry.call_args.kwargs
        assert call_kwargs["tipo"] == "SALIDA"
        assert call_kwargs["cantidad"] == 100
        
        # Verify success message
        update.message.reply_text.assert_called_once_with(
            MSG_CONSUMED.format(cantidad=100, fecha="19/05/2026")
        )
    
    @pytest.mark.asyncio
    async def test_consumir_future_date(self, setup_update, setup_context, mock_db):
        """Test consumption with future date."""
        # Create a date far in the future
        future_date = "01/01/2099"
        
        update = setup_update(123)
        ctx = setup_context(["100", future_date])
        
        await consumir_command(update, ctx)
        
        # Verify no database operations
        mock_db.get_total_stock.assert_not_called()
        mock_db.add_entry.assert_not_called()
        
        # Verify error message
        update.message.reply_text.assert_called_once_with(ERROR_FUTURE_DATE)
    
    @pytest.mark.asyncio
    async def test_consumir_missing_args(self, setup_update, setup_context, mock_db):
        """Test consumption with missing arguments."""
        update = setup_update(123)
        ctx = setup_context([])
        
        await consumir_command(update, ctx)
        
        # Verify no database operations
        mock_db.get_total_stock.assert_not_called()
        mock_db.add_entry.assert_not_called()
        
        # Verify error message
        update.message.reply_text.assert_called_once_with(ERROR_INVALID_AMOUNT)
    
    @pytest.mark.asyncio
    async def test_consumir_missing_date(self, setup_update, setup_context, mock_db):
        """Test consumption with amount but missing date."""
        update = setup_update(123)
        ctx = setup_context(["100"])
        
        await consumir_command(update, ctx)
        
        # Verify no database operations
        mock_db.get_total_stock.assert_not_called()
        mock_db.add_entry.assert_not_called()
        
        # Verify error message
        update.message.reply_text.assert_called_once_with(ERROR_INVALID_AMOUNT)
    
    @pytest.mark.asyncio
    async def test_consumir_unauthorized(self, setup_update, setup_context, mock_db):
        """Test that unauthorized users are blocked by the decorator."""
        # User ID 999 is not in authorized list (from conftest.py, only 123 is authorized)
        update = setup_update(999)
        ctx = setup_context(["100", "19/05/2026"])
        
        await consumir_command(update, ctx)
        
        # Verify no database operations
        mock_db.get_total_stock.assert_not_called()
        mock_db.add_entry.assert_not_called()
        
        # Verify unauthorized error message
        from src.messages import ERROR_UNAUTHORIZED
        update.message.reply_text.assert_called_once_with(ERROR_UNAUTHORIZED)
    
    @pytest.mark.asyncio
    async def test_consumir_with_notes(self, setup_update, setup_context, mock_db):
        """Test consumption with notes."""
        update = setup_update(123)
        ctx = setup_context(["100", "19/05/2026", "Biberón", "de", "la", "mañana"])
        
        await consumir_command(update, ctx)
        
        # Verify SALIDA entry was created with notes
        mock_db.add_entry.assert_called_once()
        call_kwargs = mock_db.add_entry.call_args.kwargs
        assert call_kwargs["tipo"] == "SALIDA"
        assert call_kwargs["cantidad"] == 100
        assert call_kwargs["notas"] == "Biberón de la mañana"
    
    @pytest.mark.asyncio
    async def test_consumir_invalid_amount_string(self, setup_update, setup_context, mock_db):
        """Test consumption with non-numeric amount."""
        update = setup_update(123)
        ctx = setup_context(["abc", "19/05/2026"])
        
        await consumir_command(update, ctx)
        
        # Verify no database operations
        mock_db.get_total_stock.assert_not_called()
        mock_db.add_entry.assert_not_called()
        
        # Verify error message
        update.message.reply_text.assert_called_once_with(ERROR_INVALID_AMOUNT)
    
    @pytest.mark.asyncio
    async def test_consumir_no_db_in_context(self, setup_update, mock_db):
        """Test consumption when database is not in bot_data."""
        update = setup_update(123)
        ctx = Mock()
        ctx.bot.send_message = AsyncMock()
        ctx.bot_data = {}  # No db key
        ctx.user_data = {}
        ctx.args = ["100", "19/05/2026"]
        ctx.match = None
        
        await consumir_command(update, ctx)
        
        # Verify error message
        update.message.reply_text.assert_called_once_with(ERROR_INVALID_AMOUNT)
