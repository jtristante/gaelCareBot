"""Tests for the /add command handler (inline backward compatibility)."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, Mock, patch

from telegram.ext import ConversationHandler

from gaelcarebot.handlers.add import (
    add_start,
    receive_amount,
    confirm_add,
    cancel,
    WAITING_AMOUNT,
    CONFIRMING,
)
from gaelcarebot.messages import (
    MSG_CANCELLED,
    MSG_PROMPT_AMOUNT,
    ERROR_INVALID_AMOUNT,
    ERROR_UNAUTHORIZED,
)
from gaelcarebot.auth import init_auth


pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def setup_auth(config):
    init_auth(config)


class TestAddInlineMode:
    """Tests for /add inline mode (backward compatibility with args)."""

    @pytest.fixture
    def setup_update(self):
        """Factory fixture for creating update mocks."""
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
    def setup_context(self):
        """Factory fixture for creating context mocks."""
        def _create(db, user_data: dict | None = None, args: list | None = None):
            ctx = Mock()
            ctx.bot = Mock()
            ctx.bot.send_message = AsyncMock()
            ctx.bot_data = {"db": db}
            ctx.user_data = user_data or {}
            ctx.args = args or []
            ctx.match = None
            return ctx
        return _create

    async def test_add_inline_valid(self, setup_update, setup_context, db):
        """Test /add 150 adds entry and returns END."""
        update = setup_update(user_id=123)
        ctx = setup_context(db, args=["150"])

        result = await add_start(update, ctx)

        assert result == ConversationHandler.END
        entries = db.get_all_entries()
        assert len(entries) == 1
        assert entries[0]["amount"] == 150
        assert entries[0]["entry_type"] == "ENTRADA"

    async def test_add_inline_with_notes(self, setup_update, setup_context, db):
        """Test /add 200 guardado en congelador adds entry with notes."""
        update = setup_update(user_id=123)
        ctx = setup_context(db, args=["200", "guardado", "en", "congelador"])

        result = await add_start(update, ctx)

        assert result == ConversationHandler.END
        entries = db.get_all_entries()
        assert len(entries) == 1
        assert entries[0]["amount"] == 200
        assert entries[0]["notes"] == "guardado en congelador"

    async def test_add_inline_negative(self, setup_update, setup_context, db):
        """Test /add -50 returns ERROR_INVALID_AMOUNT and no entry added."""
        update = setup_update(user_id=123)
        ctx = setup_context(db, args=["-50"])

        result = await add_start(update, ctx)

        assert result == ConversationHandler.END
        update.message.reply_text.assert_called_once_with(ERROR_INVALID_AMOUNT)
        assert len(db.get_all_entries()) == 0

    async def test_add_inline_zero(self, setup_update, setup_context, db):
        """Test /add 0 returns ERROR_INVALID_AMOUNT."""
        update = setup_update(user_id=123)
        ctx = setup_context(db, args=["0"])

        result = await add_start(update, ctx)

        assert result == ConversationHandler.END
        update.message.reply_text.assert_called_once_with(ERROR_INVALID_AMOUNT)
        assert len(db.get_all_entries()) == 0

    async def test_add_inline_non_numeric(self, setup_update, setup_context, db):
        """Test /add abc returns ERROR_INVALID_AMOUNT."""
        update = setup_update(user_id=123)
        ctx = setup_context(db, args=["abc"])

        result = await add_start(update, ctx)

        assert result == ConversationHandler.END
        update.message.reply_text.assert_called_once_with(ERROR_INVALID_AMOUNT)
        assert len(db.get_all_entries()) == 0

    async def test_add_inline_unauthorized(self, setup_update, setup_context, db):
        """Test unauthorized user returns ERROR_UNAUTHORIZED."""
        update = setup_update(user_id=999)
        ctx = setup_context(db, args=["150"])

        result = await add_start(update, ctx)

        assert result is None or result == ConversationHandler.END
        update.message.reply_text.assert_called_once_with(ERROR_UNAUTHORIZED)
        assert len(db.get_all_entries()) == 0


class TestAddInteractiveFlow:
    """Tests for the interactive conversation flow of /add command."""

    @pytest.fixture
    def setup_message_update(self):
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
    def setup_callback_update(self):
        def _create(user_id: int = 123, data: str = "confirm"):
            update = Mock()
            update.effective_user = Mock()
            update.effective_user.id = user_id
            update.effective_user.username = "test_user"
            update.effective_user.full_name = "Test User"
            update.message = None
            update.callback_query = Mock()
            update.callback_query.data = data
            update.callback_query.answer = AsyncMock()
            update.callback_query.edit_message_text = AsyncMock()
            return update
        return _create

    @pytest.fixture
    def setup_context(self, db):
        def _create(args: list | None = None, user_data: dict | None = None):
            ctx = Mock()
            ctx.bot = Mock()
            ctx.bot.send_message = AsyncMock()
            ctx.bot_data = {"db": db}
            ctx.user_data = user_data or {}
            ctx.args = args or []
            ctx.match = None
            return ctx
        return _create

    async def test_interactive_no_args_enters_conversation(self, setup_message_update, setup_context):
        update = setup_message_update(user_id=123)
        ctx = setup_context(args=[])

        result = await add_start(update, ctx)

        update.message.reply_text.assert_called_once_with(MSG_PROMPT_AMOUNT)
        assert result == WAITING_AMOUNT

    async def test_interactive_receive_valid_amount(self, setup_message_update, setup_context):
        update = setup_message_update(user_id=123)
        update.message.text = "150"
        ctx = setup_context(user_data={"add_flow": True})

        result = await receive_amount(update, ctx)

        assert result == CONFIRMING
        assert ctx.user_data["add_amount"] == 150
        call_args = update.message.reply_text.call_args
        assert call_args.kwargs["reply_markup"] is not None

    async def test_interactive_receive_invalid_amount(self, setup_message_update, setup_context):
        update = setup_message_update(user_id=123)
        update.message.text = "abc"
        ctx = setup_context(user_data={"add_flow": True})

        result = await receive_amount(update, ctx)

        update.message.reply_text.assert_called_once_with(ERROR_INVALID_AMOUNT)
        assert result == WAITING_AMOUNT

    async def test_interactive_receive_negative(self, setup_message_update, setup_context):
        update = setup_message_update(user_id=123)
        update.message.text = "-50"
        ctx = setup_context(user_data={"add_flow": True})

        result = await receive_amount(update, ctx)

        update.message.reply_text.assert_called_once_with(ERROR_INVALID_AMOUNT)
        assert result == WAITING_AMOUNT

    async def test_interactive_confirm_add(self, setup_callback_update, setup_context, db):
        update = setup_callback_update(user_id=123, data="confirm")
        ctx = setup_context(user_data={"add_amount": 150})

        result = await confirm_add(update, ctx)

        entries = db.get_all_entries()
        assert len(entries) == 1
        assert entries[0]["amount"] == 150
        assert entries[0]["entry_type"] == "ENTRADA"
        update.callback_query.edit_message_text.assert_called_once()
        assert result == ConversationHandler.END

    async def test_interactive_cancel_in_waiting(self, setup_message_update, setup_context):
        update = setup_message_update(user_id=123)
        ctx = setup_context(user_data={"add_flow": True})

        result = await cancel(update, ctx)

        update.message.reply_text.assert_called_once_with(MSG_CANCELLED)
        assert result == ConversationHandler.END

    async def test_interactive_cancel_in_confirming(self, setup_callback_update, setup_context):
        update = setup_callback_update(user_id=123, data="cancel")
        ctx = setup_context(user_data={"add_cantidad": 150})

        result = await confirm_add(update, ctx)

        update.callback_query.edit_message_text.assert_called_once_with(MSG_CANCELLED)
        assert result == ConversationHandler.END

    async def test_interactive_unauthorized(self, setup_message_update, setup_context):
        update = setup_message_update(user_id=999)
        ctx = setup_context(args=[])

        result = await add_start(update, ctx)

        update.message.reply_text.assert_called_once_with(ERROR_UNAUTHORIZED)

    async def test_interactive_confirm_sends_notification(self, setup_callback_update, setup_context):
        update = setup_callback_update(user_id=123, data="confirm")
        ctx = setup_context(user_data={"add_amount": 150})

        with patch("gaelcarebot.handlers.add.send_daily_summary", new_callable=AsyncMock) as mock_notify:
            result = await confirm_add(update, ctx)

            mock_notify.assert_called_once()

        assert result == ConversationHandler.END

    async def test_interactive_confirm_shows_correct_date(self, setup_callback_update, setup_context):
        update = setup_callback_update(user_id=123, data="confirm")
        ctx = setup_context(user_data={"add_amount": 150})

        result = await confirm_add(update, ctx)

        call_args = update.callback_query.edit_message_text.call_args
        msg_text = call_args[0][0]
        assert "150 ml" in msg_text
        assert result == ConversationHandler.END
