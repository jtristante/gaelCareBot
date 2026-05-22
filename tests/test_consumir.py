"""Tests for the /consumir command handler."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pytz import timezone
from telegram.ext import ConversationHandler

from src import auth
from src.config import load_config
from src.handlers.consumir import (
    consumir_command,
    entry_selected,
    confirm_reversal,
    cancel,
    parse_dd_mm_yyyy,
    SELECTING_ENTRY,
    CONFIRMING,
)
from src.messages import (
    MSG_CONSUMED,
    MSG_CANCELLED,
    MSG_SELECT_ENTRY,
    ERROR_INVALID_AMOUNT,
    ERROR_INVALID_DATE,
    ERROR_INSUFFICIENT_STOCK,
    ERROR_FUTURE_DATE,
    ERROR_NO_ENTRIES,
    ERROR_ENTRY_NOT_FOUND,
)

MADRID_TZ = timezone("Europe/Madrid")


@pytest.fixture(autouse=True)
def init_auth_for_tests(monkeypatch):
    """Initialize auth module with test authorized user (123)."""
    monkeypatch.setenv("BOT_TOKEN", "test")
    monkeypatch.setenv("AUTHORIZED_USER_IDS", "123")
    config = load_config()
    auth.init_auth(config)


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


class TestConsumirCommandArgsMode:
    """Tests for the consumir_command handler with args (FIFO consumption mode)."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database with consume_fifo method."""
        db = Mock()
        db.consume_fifo = Mock(return_value=2)
        db.get_total_stock = Mock(return_value=200)
        return db

    @pytest.fixture
    def setup_context(self, mock_db):
        """Create a mock context with the database in bot_data."""
        def _create(args: list[str] | None = None):
            ctx = Mock()
            ctx.bot = Mock()
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

        result = await consumir_command(update, ctx)

        # Verify consume_fifo was called correctly
        mock_db.consume_fifo.assert_called_once()
        call_args = mock_db.consume_fifo.call_args
        assert call_args.kwargs["cantidad"] == 100
        assert call_args.kwargs["add_at"] == "2026-05-19T12:00:00"
        assert call_args.kwargs["user_id"] == 123
        assert call_args.kwargs["username"] == "test_user"
        assert call_args.kwargs["notas"] is None

        # Verify success message
        update.message.reply_text.assert_called_once_with(
            MSG_CONSUMED.format(cantidad=100, fecha="19/05/2026")
        )

        # Verify returned ConversationHandler.END
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_consumir_insufficient_stock(self, setup_update, setup_context, mock_db):
        """Test consumption with insufficient stock: consume_fifo raises ValueError."""
        mock_db.consume_fifo.side_effect = ValueError("Insufficient stock: need 100, available 50")
        mock_db.get_total_stock.return_value = 50

        update = setup_update(123)
        ctx = setup_context(["100", "19/05/2026"])

        result = await consumir_command(update, ctx)

        # Verify consume_fifo was called
        mock_db.consume_fifo.assert_called_once()

        # Verify error message
        update.message.reply_text.assert_called_once_with(
            ERROR_INSUFFICIENT_STOCK.format(stock=50)
        )

        # Verify returned ConversationHandler.END
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_consumir_invalid_date(self, setup_update, setup_context, mock_db):
        """Test consumption with invalid calendar date: 99/99/2026."""
        update = setup_update(123)
        ctx = setup_context(["100", "99/99/2026"])

        result = await consumir_command(update, ctx)

        # Verify no database operations
        mock_db.consume_fifo.assert_not_called()

        # Verify error message
        update.message.reply_text.assert_called_once_with(ERROR_INVALID_DATE)

        # Verify returned ConversationHandler.END
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_consumir_wrong_format(self, setup_update, setup_context, mock_db):
        """Test consumption with wrong date format: 2026-05-19 (ISO)."""
        update = setup_update(123)
        ctx = setup_context(["100", "2026-05-19"])

        result = await consumir_command(update, ctx)

        # Verify no database operations
        mock_db.consume_fifo.assert_not_called()

        # Verify error message
        update.message.reply_text.assert_called_once_with(ERROR_INVALID_DATE)

        # Verify returned ConversationHandler.END
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_consumir_negative(self, setup_update, setup_context, mock_db):
        """Test consumption with negative amount: -50ml."""
        update = setup_update(123)
        ctx = setup_context(["-50", "19/05/2026"])

        result = await consumir_command(update, ctx)

        # Verify no database operations
        mock_db.consume_fifo.assert_not_called()

        # Verify error message
        update.message.reply_text.assert_called_once_with(ERROR_INVALID_AMOUNT)

        # Verify returned ConversationHandler.END
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_consumir_zero(self, setup_update, setup_context, mock_db):
        """Test consumption with zero amount."""
        update = setup_update(123)
        ctx = setup_context(["0", "19/05/2026"])

        result = await consumir_command(update, ctx)

        # Verify no database operations
        mock_db.consume_fifo.assert_not_called()

        # Verify error message
        update.message.reply_text.assert_called_once_with(ERROR_INVALID_AMOUNT)

        # Verify returned ConversationHandler.END
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_consumir_exact_stock(self, setup_update, setup_context, mock_db):
        """Test consuming exactly all available stock: 100ml with 100ml available."""
        mock_db.consume_fifo.return_value = 2

        update = setup_update(123)
        ctx = setup_context(["100", "19/05/2026"])

        result = await consumir_command(update, ctx)

        # Verify consume_fifo was called
        mock_db.consume_fifo.assert_called_once()
        call_args = mock_db.consume_fifo.call_args
        assert call_args.kwargs["cantidad"] == 100

        # Verify success message
        update.message.reply_text.assert_called_once_with(
            MSG_CONSUMED.format(cantidad=100, fecha="19/05/2026")
        )

        # Verify returned ConversationHandler.END
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_consumir_future_date(self, setup_update, setup_context, mock_db):
        """Test consumption with future date."""
        # Create a date far in the future
        future_date = "01/01/2099"

        update = setup_update(123)
        ctx = setup_context(["100", future_date])

        result = await consumir_command(update, ctx)

        # Verify no database operations
        mock_db.consume_fifo.assert_not_called()

        # Verify error message
        update.message.reply_text.assert_called_once_with(ERROR_FUTURE_DATE)

        # Verify returned ConversationHandler.END
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_consumir_missing_args_enters_reversal_mode(self, setup_update, setup_context, mock_db):
        """Test that no args enters reversal mode (SELECTING_ENTRY state)."""
        update = setup_update(123)
        ctx = setup_context([])  # No args

        # Mock get_all_entries to return an ENTRADA entry
        mock_db.get_all_entries.return_value = [
            {"id": 1, "tipo": "ENTRADA", "cantidad": 100, "add_at": "2026-05-19T10:00:00"}
        ]

        result = await consumir_command(update, ctx)

        # Verify no consume_fifo call (not args mode)
        mock_db.consume_fifo.assert_not_called()

        # Verify get_all_entries was called (reversal mode)
        mock_db.get_all_entries.assert_called_once()

        # Verify returned SELECTING_ENTRY state
        assert result == SELECTING_ENTRY

    @pytest.mark.asyncio
    async def test_consumir_missing_date_enters_reversal_mode(self, setup_update, setup_context, mock_db):
        """Test that only amount arg (missing date) enters reversal mode."""
        update = setup_update(123)
        ctx = setup_context(["100"])  # Only amount, no date

        # Mock get_all_entries to return an ENTRADA entry
        mock_db.get_all_entries.return_value = [
            {"id": 1, "tipo": "ENTRADA", "cantidad": 100, "add_at": "2026-05-19T10:00:00"}
        ]

        result = await consumir_command(update, ctx)

        # Verify no consume_fifo call (not args mode)
        mock_db.consume_fifo.assert_not_called()

        # Verify get_all_entries was called (reversal mode)
        mock_db.get_all_entries.assert_called_once()

        # Verify returned SELECTING_ENTRY state
        assert result == SELECTING_ENTRY

    @pytest.mark.asyncio
    async def test_consumir_unauthorized(self, setup_update, setup_context, mock_db):
        """Test that unauthorized users are blocked by the decorator."""
        # User ID 999 is not in authorized list (from conftest.py, only 123 is authorized)
        update = setup_update(999)
        ctx = setup_context(["100", "19/05/2026"])

        result = await consumir_command(update, ctx)

        # Verify no database operations
        mock_db.consume_fifo.assert_not_called()

        # Verify unauthorized error message
        from src.messages import ERROR_UNAUTHORIZED
        update.message.reply_text.assert_called_once_with(ERROR_UNAUTHORIZED)

        # Decorator blocks before returning state, so no state returned
        assert result is None

    @pytest.mark.asyncio
    async def test_consumir_with_notes(self, setup_update, setup_context, mock_db):
        """Test consumption with notes."""
        update = setup_update(123)
        ctx = setup_context(["100", "19/05/2026", "Biberón", "de", "la", "mañana"])

        result = await consumir_command(update, ctx)

        # Verify consume_fifo was called with notes
        mock_db.consume_fifo.assert_called_once()
        call_args = mock_db.consume_fifo.call_args
        assert call_args.kwargs["cantidad"] == 100
        assert call_args.kwargs["notas"] == "Biberón de la mañana"

        # Verify returned ConversationHandler.END
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_consumir_invalid_amount_string(self, setup_update, setup_context, mock_db):
        """Test consumption with non-numeric amount."""
        update = setup_update(123)
        ctx = setup_context(["abc", "19/05/2026"])

        result = await consumir_command(update, ctx)

        # Verify no database operations
        mock_db.consume_fifo.assert_not_called()

        # Verify error message
        update.message.reply_text.assert_called_once_with(ERROR_INVALID_AMOUNT)

        # Verify returned ConversationHandler.END
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_consumir_no_db_in_context(self, setup_update, mock_db):
        """Test consumption when database is not in bot_data."""
        update = setup_update(123)
        ctx = Mock()
        ctx.bot = Mock()
        ctx.bot.send_message = AsyncMock()
        ctx.bot_data = {}  # No db key
        ctx.user_data = {}
        ctx.args = ["100", "19/05/2026"]
        ctx.match = None

        result = await consumir_command(update, ctx)

        # Verify error message
        update.message.reply_text.assert_called_once_with(ERROR_INVALID_AMOUNT)

        # Verify returned ConversationHandler.END
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_consumir_fifo_salida_has_consumed_at(self, db):
        """Test that consume_fifo() creates a SALIDA entry with consumed_at set.

        This is a pure DB-level test (no Telegram mocks). It uses the real
        in-memory MilkDatabase fixture directly.

        Verifies consumed_at is set by consume_fifo() on the new SALIDA entry.
        """
        db.add_entry(
            "ENTRADA", 100, "2026-05-19T10:00:00", 123, "test_user", None,
        )

        db.consume_fifo(
            cantidad=50,
            add_at="2026-05-19T12:00:00",
            user_id=123,
        )

        row = db.conn.execute(
            "SELECT * FROM transactions WHERE tipo = 'SALIDA' ORDER BY id DESC LIMIT 1"
        ).fetchone()

        assert row is not None
        assert row["consumed_at"] is not None, (
            "consumed_at is NULL — consume_fifo() does not set consumed_at on the SALIDA entry"
        )


class TestReversalMode:
    """Tests for the /consumir command no-args mode (reversal)."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database with required methods."""
        db = Mock()
        db.get_all_entries = Mock(return_value=[])
        db.get_entry = Mock(return_value=None)
        db.update_entry = Mock(return_value=True)
        db.conn = Mock()
        db.conn.execute = Mock()
        db.conn.commit = Mock()
        return db

    @pytest.fixture
    def setup_context(self, mock_db):
        """Create a mock context with the database in bot_data."""
        def _create(args: list[str] | None = None, user_data: dict | None = None):
            ctx = Mock()
            ctx.bot = Mock()
            ctx.bot.send_message = AsyncMock()
            ctx.bot_data = {"db": mock_db}
            ctx.user_data = user_data or {}
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

    @pytest.fixture
    def setup_callback_query(self):
        """Create a mock callback query."""
        def _create(data: str):
            query = Mock()
            query.data = data
            query.answer = AsyncMock()
            query.edit_message_text = AsyncMock()
            return query
        return _create

    @pytest.mark.asyncio
    async def test_reversal_no_entries(self, setup_update, setup_context, mock_db):
        """Test reversal mode with no entries shows error."""
        update = setup_update(123)
        ctx = setup_context([])  # No args
        mock_db.get_all_entries.return_value = []

        result = await consumir_command(update, ctx)

        # Verify error message
        update.message.reply_text.assert_called_once_with(ERROR_NO_ENTRIES)

        # Verify returned ConversationHandler.END
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_reversal_shows_only_entrada_entries(self, setup_update, setup_context, mock_db):
        """Test that reversal mode shows only ENTRADA entries."""
        update = setup_update(123)
        ctx = setup_context([])
        mock_db.get_all_entries.return_value = [
            {"id": 1, "tipo": "ENTRADA", "cantidad": 100, "add_at": "2026-05-19T10:00:00", "notas": None},
            {"id": 2, "tipo": "SALIDA", "cantidad": 50, "add_at": "2026-05-19T11:00:00", "notas": None},
            {"id": 3, "tipo": "ENTRADA", "cantidad": 200, "add_at": "2026-05-19T12:00:00", "notas": None},
        ]

        result = await consumir_command(update, ctx)

        # Verify returned SELECTING_ENTRY state
        assert result == SELECTING_ENTRY

        # Verify reply_text was called with keyboard markup
        call_args = update.message.reply_text.call_args
        assert call_args.kwargs["reply_markup"] is not None

        # Verify keyboard only has ENTRADA entries (id 1 and 3) + cancel button
        keyboard = call_args.kwargs["reply_markup"].inline_keyboard
        assert len(keyboard) == 3  # 2 entries + cancel button

        # Check first entry button text contains ENTRADA label
        assert "ENTRADA" in keyboard[0][0].text
        assert "#1" in keyboard[0][0].text

        # Check second entry button text contains ENTRADA label
        assert "ENTRADA" in keyboard[1][0].text
        assert "#3" in keyboard[1][0].text

    @pytest.mark.asyncio
    async def test_reversal_selecting_entry_callback(self, setup_update, setup_context, mock_db, setup_callback_query):
        """Test selecting an entry in reversal mode shows confirmation."""
        update = setup_update(123)
        update.callback_query = setup_callback_query("reverse_1")

        ctx = setup_context(user_data={})
        mock_db.get_entry.return_value = {
            "id": 1,
            "tipo": "ENTRADA",
            "cantidad": 100,
            "add_at": "2026-05-19T10:00:00",
            "notas": "Test notes"
        }

        result = await entry_selected(update, ctx)

        # Verify entry_id stored in user_data
        assert ctx.user_data["reverse_entry_id"] == 1

        # Verify returned CONFIRMING state
        assert result == CONFIRMING

        # Verify edit_message_text was called
        assert update.callback_query.edit_message_text.called

    @pytest.mark.asyncio
    async def test_reversal_cancel_in_selecting(self, setup_update, setup_context, mock_db, setup_callback_query):
        """Test canceling during entry selection."""
        update = setup_update(123)
        update.callback_query = setup_callback_query("cancel")

        ctx = setup_context(user_data={})

        result = await entry_selected(update, ctx)

        # Verify cancel message shown
        update.callback_query.edit_message_text.assert_called_once_with(MSG_CANCELLED)

        # Verify returned ConversationHandler.END
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_reversal_confirm_changes_tipo(self, setup_update, setup_context, mock_db, setup_callback_query):
        """Test confirming reversal changes tipo to SALIDA and sets consumed_at."""
        update = setup_update(123)
        update.callback_query = setup_callback_query("confirm")

        ctx = setup_context(user_data={"reverse_entry_id": 1})
        mock_db.update_entry.return_value = True
        mock_db.get_entry.return_value = {
            "id": 1,
            "tipo": "ENTRADA",
            "cantidad": 100,
            "add_at": "2026-05-19T10:00:00",
            "notas": "Test notes",
            "username": "test_user"
        }

        result = await confirm_reversal(update, ctx)

        # Verify update_entry called with tipo='SALIDA'
        mock_db.update_entry.assert_called_once_with(1, tipo="SALIDA")

        # Verify consumed_at was set via raw SQL
        mock_db.conn.execute.assert_called_once()
        call_args = mock_db.conn.execute.call_args
        assert "consumed_at" in call_args[0][0]
        assert call_args[0][1] == (1,)  # entry_id

        # Verify commit was called
        mock_db.conn.commit.assert_called_once()

        # Verify success message
        update.callback_query.edit_message_text.assert_called_once_with(
            MSG_CONSUMED.format(cantidad=100, fecha="19/05/2026")
        )

        # Verify returned ConversationHandler.END
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_reversal_cancel_in_confirming(self, setup_update, setup_context, mock_db, setup_callback_query):
        """Test canceling during confirmation."""
        update = setup_update(123)
        update.callback_query = setup_callback_query("cancel")

        ctx = setup_context(user_data={"reverse_entry_id": 1})

        result = await confirm_reversal(update, ctx)

        # Verify no update_entry call
        mock_db.update_entry.assert_not_called()

        # Verify cancel message shown
        update.callback_query.edit_message_text.assert_called_once_with(MSG_CANCELLED)

        # Verify returned ConversationHandler.END
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_reversal_entry_not_found(self, setup_update, setup_context, mock_db, setup_callback_query):
        """Test reversal when selected entry no longer exists."""
        update = setup_update(123)
        update.callback_query = setup_callback_query("reverse_999")

        ctx = setup_context(user_data={})
        mock_db.get_entry.return_value = None  # Entry not found

        result = await entry_selected(update, ctx)

        # Verify error message
        update.callback_query.edit_message_text.assert_called_once_with(ERROR_ENTRY_NOT_FOUND)

        # Verify returned ConversationHandler.END
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_reversal_entry_not_entrada(self, setup_update, setup_context, mock_db, setup_callback_query):
        """Test reversal when selected entry is not ENTRADA."""
        update = setup_update(123)
        update.callback_query = setup_callback_query("reverse_1")

        ctx = setup_context(user_data={})
        mock_db.get_entry.return_value = {
            "id": 1,
            "tipo": "SALIDA",  # Not ENTRADA
            "cantidad": 100,
            "add_at": "2026-05-19T10:00:00",
            "notas": None
        }

        result = await entry_selected(update, ctx)

        # Verify error message (treated as not found)
        update.callback_query.edit_message_text.assert_called_once_with(ERROR_ENTRY_NOT_FOUND)

        # Verify returned ConversationHandler.END
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_reversal_update_entry_fails(self, setup_update, setup_context, mock_db, setup_callback_query):
        """Test reversal when update_entry returns False."""
        update = setup_update(123)
        update.callback_query = setup_callback_query("confirm")

        ctx = setup_context(user_data={"reverse_entry_id": 1})
        mock_db.update_entry.return_value = False  # Update failed

        result = await confirm_reversal(update, ctx)

        # Verify error message
        update.callback_query.edit_message_text.assert_called_once_with(ERROR_ENTRY_NOT_FOUND)

        # Verify returned ConversationHandler.END
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_reversal_sends_notification(self, setup_update, setup_context, mock_db, setup_callback_query):
        """Test that reversal triggers a daily summary notification."""
        update = setup_update(123)
        update.callback_query = setup_callback_query("confirm")

        ctx = setup_context(user_data={"reverse_entry_id": 1})
        mock_db.update_entry.return_value = True
        mock_db.get_entry.return_value = {
            "id": 1,
            "tipo": "ENTRADA",
            "cantidad": 100,
            "add_at": "2026-05-19T10:00:00",
            "notas": "Test notes",
            "username": "test_user"
        }

        with patch("src.handlers.consumir.send_daily_summary", new_callable=AsyncMock) as mock_notify:
            result = await confirm_reversal(update, ctx)

            # Verify notification was sent
            mock_notify.assert_called_once_with(ctx.bot, mock_db)

        # Verify success message
        update.callback_query.edit_message_text.assert_called_once_with(
            MSG_CONSUMED.format(cantidad=100, fecha="19/05/2026")
        )

        # Verify returned ConversationHandler.END
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_reversal_notification_failure_does_not_block(self, setup_update, setup_context, mock_db, setup_callback_query):
        """Test that reversal succeeds even if notification fails."""
        update = setup_update(123)
        update.callback_query = setup_callback_query("confirm")

        ctx = setup_context(user_data={"reverse_entry_id": 1})
        mock_db.update_entry.return_value = True
        mock_db.get_entry.return_value = {
            "id": 1,
            "tipo": "ENTRADA",
            "cantidad": 100,
            "add_at": "2026-05-19T10:00:00",
            "notas": "Test notes",
            "username": "test_user"
        }

        with patch("src.handlers.consumir.send_daily_summary", new_callable=AsyncMock) as mock_notify:
            mock_notify.side_effect = Exception("API error")

            result = await confirm_reversal(update, ctx)

            # Verify update still happened
            mock_db.update_entry.assert_called_once_with(1, tipo="SALIDA")
            mock_db.conn.commit.assert_called_once()

            # Verify success message still shown despite notification failure
            update.callback_query.edit_message_text.assert_called_once_with(
                MSG_CONSUMED.format(cantidad=100, fecha="19/05/2026")
            )

        # Verify returned ConversationHandler.END
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_cancel_command(self, setup_update, setup_context, mock_db):
        """Test /cancel command during reversal conversation."""
        update = setup_update(123)
        ctx = setup_context(user_data={"reverse_entry_id": 1})

        result = await cancel(update, ctx)

        # Verify cancel message shown
        update.message.reply_text.assert_called_once_with(MSG_CANCELLED)

        # Verify user_data cleared
        assert "reverse_entry_id" not in ctx.user_data

        # Verify returned ConversationHandler.END
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_cancel_callback(self, setup_update, setup_context, mock_db, setup_callback_query):
        """Test cancel via callback during reversal conversation."""
        update = setup_update(123)
        update.callback_query = setup_callback_query("cancel")

        ctx = setup_context(user_data={"reverse_entry_id": 1})

        result = await cancel(update, ctx)

        # Verify answer and edit called
        assert update.callback_query.answer.called
        update.callback_query.edit_message_text.assert_called_once_with(MSG_CANCELLED)

        # Verify user_data cleared
        assert "reverse_entry_id" not in ctx.user_data

        # Verify returned ConversationHandler.END
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_confirm_reversal_shows_correct_data(self, db, monkeypatch):
        """Test that confirm_reversal displays correct cantidad and date (not 0/N/A).

        This MUST FAIL (RED) because confirm_reversal() calls db.get_entry()
        AFTER setting consumed_at, and get_entry() filters by consumed_at IS NULL,
        so it returns None -> cantidad=0, fecha="N/A".

        The fix must move get_entry() BEFORE the mutation.
        """
        # Disable send_daily_summary to avoid import issues
        monkeypatch.setattr("src.handlers.consumir._SEND_DAILY_SUMMARY_AVAILABLE", False)

        # Add an ENTRADA entry to the real in-memory database
        entry_id = db.add_entry(
            "ENTRADA", 150, "2026-05-19T10:00:00", 123, "test_user", None,
        )

        # Create mock update with callback_query
        update = Mock()
        update.callback_query = Mock()
        update.callback_query.data = "confirm"
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()

        # Create mock context with real db
        context = Mock()
        context.bot = Mock()
        context.bot.send_message = AsyncMock()
        context.bot_data = {"db": db}
        context.user_data = {"reverse_entry_id": entry_id}

        result = await confirm_reversal(update, context)

        # Verify the mutation still happened (sanity check — the bug is in display, not mutation)
        row = db.conn.execute("SELECT * FROM transactions WHERE id = ?", (entry_id,)).fetchone()
        assert row["tipo"] == "SALIDA"
        assert row["consumed_at"] is not None

        # Verify the displayed message — now shows correct data after fix
        call_args = update.callback_query.edit_message_text.call_args
        msg_text = call_args[0][0]

        expected = MSG_CONSUMED.format(cantidad=150, fecha="19/05/2026")
        assert msg_text == expected, f"Expected '{expected}', got: {msg_text}"

        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_reversal_confirm_reversal_updates_entry_and_consumed_at(self, db, monkeypatch):
        """Test that confirm_reversal correctly updates tipo to SALIDA and sets consumed_at.

        This test verifies the mutation part works (update_entry + consumed_at).
        It queries the database directly via SQL.
        """
        # Disable send_daily_summary to avoid import issues
        monkeypatch.setattr("src.handlers.consumir._SEND_DAILY_SUMMARY_AVAILABLE", False)

        # Add an ENTRADA entry to the real in-memory database
        entry_id = db.add_entry(
            "ENTRADA", 150, "2026-05-19T10:00:00", 123, "test_user", None,
        )

        # Create mock update with callback_query
        update = Mock()
        update.callback_query = Mock()
        update.callback_query.data = "confirm"
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()

        # Create mock context with real db
        context = Mock()
        context.bot = Mock()
        context.bot.send_message = AsyncMock()
        context.bot_data = {"db": db}
        context.user_data = {"reverse_entry_id": entry_id}

        result = await confirm_reversal(update, context)

        # Query directly via SQL to verify the mutation
        row = db.conn.execute("SELECT * FROM transactions WHERE id = ?", (entry_id,)).fetchone()

        # Verify tipo was changed to SALIDA
        assert row["tipo"] == "SALIDA", (
            f"Expected tipo='SALIDA', got '{row['tipo']}'"
        )

        # Verify consumed_at was set (not NULL)
        assert row["consumed_at"] is not None, (
            "consumed_at is NULL — confirm_reversal did not set consumed_at"
        )

        assert result == ConversationHandler.END
