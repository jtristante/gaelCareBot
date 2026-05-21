"""Tests for the /eliminar command handler."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.handlers.eliminar import (
    SELECTING_ENTRY,
    CONFIRMING,
    eliminar_start,
    entry_selected,
    confirm_delete,
    cancel,
)
from src.messages import (
    ERROR_NO_ENTRIES,
    ERROR_ENTRY_NOT_FOUND,
    MSG_DELETED,
    MSG_CANCELLED,
    MSG_SELECT_ENTRY,
    MSG_CONFIRM_DELETE,
    BTN_CANCEL,
    BTN_CONFIRM,
)

pytestmark = pytest.mark.asyncio


class TestEliminarStart:
    """Tests for the eliminar_start handler."""

    @pytest.fixture(autouse=True)
    def setup_auth(self, patch_config):
        """Initialize auth with authorized user 123."""
        from src.auth import init_auth
        from src.config import load_config
        config = load_config()
        init_auth(config)

    @pytest.fixture
    def mock_db(self):
        """Create a mock database."""
        db = Mock()
        db.get_all_entries = Mock(return_value=[])
        return db

    @pytest.fixture
    def setup_context(self, mock_db):
        """Create a mock context with database."""
        def _create(user_data: dict | None = None):
            ctx = Mock()
            ctx.bot.send_message = AsyncMock()
            ctx.bot_data = {"db": mock_db}
            ctx.user_data = user_data or {}
            ctx.args = []
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

    async def test_eliminar_empty(self, setup_update, setup_context, mock_db):
        """Test /eliminar with no entries - should show ERROR_NO_ENTRIES."""
        mock_db.get_all_entries.return_value = []

        update = setup_update(123)
        ctx = setup_context()

        result = await eliminar_start(update, ctx)

        mock_db.get_all_entries.assert_called_once_with(order_by="fecha_hora DESC")
        update.message.reply_text.assert_called_once_with(ERROR_NO_ENTRIES)
        assert result == -1  # ConversationHandler.END

    async def test_eliminar_show_entries(self, setup_update, setup_context, mock_db):
        """Test /eliminar with 3 entries - should show MSG_SELECT_ENTRY."""
        mock_db.get_all_entries.return_value = [
            {"id": 1, "tipo": "ENTRADA", "fecha_hora": "2026-05-19T10:00:00", "cantidad": 200},
            {"id": 2, "tipo": "SALIDA", "fecha_hora": "2026-05-18T12:00:00", "cantidad": 100},
            {"id": 3, "tipo": "ENTRADA", "fecha_hora": "2026-05-17T09:00:00", "cantidad": 150},
        ]

        update = setup_update(123)
        ctx = setup_context()

        result = await eliminar_start(update, ctx)

        mock_db.get_all_entries.assert_called_once_with(order_by="fecha_hora DESC")
        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args
        assert call_args[0][0] == MSG_SELECT_ENTRY
        assert result == SELECTING_ENTRY


class TestEliminarConfirm:
    """Tests for confirming deletion."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database."""
        db = Mock()
        db.get_entry = Mock(return_value=None)
        db.delete_entry = Mock(return_value=True)
        return db

    @pytest.fixture
    def setup_callback_update(self):
        """Create a mock update with callback query."""
        def _create(callback_data: str, user_id: int = 123):
            update = Mock()
            update.effective_user = Mock()
            update.effective_user.id = user_id
            update.message = None
            update.callback_query = Mock()
            update.callback_query.data = callback_data
            update.callback_query.answer = AsyncMock()
            update.callback_query.edit_message_text = AsyncMock()
            return update
        return _create

    @pytest.fixture
    def setup_context(self, mock_db):
        """Create a mock context with database."""
        def _create(user_data: dict | None = None):
            ctx = Mock()
            ctx.bot.send_message = AsyncMock()
            ctx.bot_data = {"db": mock_db}
            ctx.user_data = user_data or {}
            ctx.args = []
            ctx.match = None
            return ctx
        return _create

    async def test_eliminar_confirm(self, setup_callback_update, setup_context, mock_db):
        """Test selecting an entry and confirming deletion - entry should be deleted."""
        # Setup: entry exists
        mock_db.get_entry.return_value = {
            "id": 1,
            "tipo": "ENTRADA",
            "fecha_hora": "2026-05-19T10:00:00",
            "cantidad": 200,
            "notas": None,
        }

        # Step 1: Select the entry
        update = setup_callback_update("del_1")
        ctx = setup_context()

        result = await entry_selected(update, ctx)

        update.callback_query.answer.assert_called_once()
        mock_db.get_entry.assert_called_once_with(1)
        assert ctx.user_data["delete_entry_id"] == 1
        assert result == CONFIRMING

        # Step 2: Confirm the deletion
        update = setup_callback_update("confirm")
        ctx = setup_context({"delete_entry_id": 1})

        result = await confirm_delete(update, ctx)

        update.callback_query.answer.assert_called_once()
        mock_db.delete_entry.assert_called_once_with(1)
        update.callback_query.edit_message_text.assert_called_once_with(MSG_DELETED)
        assert result == -1  # ConversationHandler.END


class TestEliminarCancel:
    """Tests for canceling deletion."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database."""
        db = Mock()
        db.get_entry = Mock(return_value=None)
        db.delete_entry = Mock(return_value=True)
        return db

    @pytest.fixture
    def setup_callback_update(self):
        """Create a mock update with callback query."""
        def _create(callback_data: str, user_id: int = 123):
            update = Mock()
            update.effective_user = Mock()
            update.effective_user.id = user_id
            update.message = None
            update.callback_query = Mock()
            update.callback_query.data = callback_data
            update.callback_query.answer = AsyncMock()
            update.callback_query.edit_message_text = AsyncMock()
            return update
        return _create

    @pytest.fixture
    def setup_context(self, mock_db):
        """Create a mock context with database."""
        def _create(user_data: dict | None = None):
            ctx = Mock()
            ctx.bot.send_message = AsyncMock()
            ctx.bot_data = {"db": mock_db}
            ctx.user_data = user_data or {}
            ctx.args = []
            ctx.match = None
            return ctx
        return _create

    async def test_eliminar_cancel(self, setup_callback_update, setup_context, mock_db):
        """Test selecting an entry and canceling - entry should still exist."""
        # Setup: entry exists
        mock_db.get_entry.return_value = {
            "id": 1,
            "tipo": "ENTRADA",
            "fecha_hora": "2026-05-19T10:00:00",
            "cantidad": 200,
            "notas": None,
        }

        # Step 1: Select the entry
        update = setup_callback_update("del_1")
        ctx = setup_context()

        result = await entry_selected(update, ctx)
        assert result == CONFIRMING

        # Step 2: Cancel the deletion
        update = setup_callback_update("cancel")
        ctx = setup_context({"delete_entry_id": 1})

        result = await confirm_delete(update, ctx)

        update.callback_query.answer.assert_called_once()
        # Verify delete_entry was NOT called
        mock_db.delete_entry.assert_not_called()
        update.callback_query.edit_message_text.assert_called_once_with(MSG_CANCELLED)
        assert result == -1  # ConversationHandler.END


class TestEliminarInvalidEntry:
    """Tests for invalid/non-existent entry."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database."""
        db = Mock()
        db.get_entry = Mock(return_value=None)
        db.delete_entry = Mock(return_value=False)
        return db

    @pytest.fixture
    def setup_callback_update(self):
        """Create a mock update with callback query."""
        def _create(callback_data: str, user_id: int = 123):
            update = Mock()
            update.effective_user = Mock()
            update.effective_user.id = user_id
            update.message = None
            update.callback_query = Mock()
            update.callback_query.data = callback_data
            update.callback_query.answer = AsyncMock()
            update.callback_query.edit_message_text = AsyncMock()
            return update
        return _create

    @pytest.fixture
    def setup_context(self, mock_db):
        """Create a mock context with database."""
        def _create(user_data: dict | None = None):
            ctx = Mock()
            ctx.bot.send_message = AsyncMock()
            ctx.bot_data = {"db": mock_db}
            ctx.user_data = user_data or {}
            ctx.args = []
            ctx.match = None
            return ctx
        return _create

    async def test_eliminar_invalid_entry(self, setup_callback_update, setup_context, mock_db):
        """Test selecting a non-existent entry - should show ERROR_ENTRY_NOT_FOUND."""
        # Setup: entry does not exist (get_entry returns None)
        mock_db.get_entry.return_value = None

        update = setup_callback_update("del_999")
        ctx = setup_context()

        result = await entry_selected(update, ctx)

        update.callback_query.answer.assert_called_once()
        mock_db.get_entry.assert_called_once_with(999)
        update.callback_query.edit_message_text.assert_called_once_with(ERROR_ENTRY_NOT_FOUND)
        assert result == -1  # ConversationHandler.END
