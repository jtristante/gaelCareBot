"""Tests for the /edit command handler."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest

from gaelcarebot.handlers.edit import (
    SELECTING_ENTRY,
    EDITING_FIELD,
    EDITING_VALUE,
    CONFIRMING,
    SELECTING_ENTRY_TYPE,
    edit_start,
    entry_selected,
    field_selected,
    entry_type_selected,
    receive_value,
    confirm_edit,
    cancel,
    _validate_amount,
    _validate_date,
)
from gaelcarebot.db import MilkDatabase, now_madrid
from gaelcarebot.messages import (
    ERROR_NO_ENTRIES,
    ERROR_ENTRY_NOT_FOUND,
    ERROR_INVALID_AMOUNT,
    ERROR_INVALID_DATE,
    MSG_SELECT_ENTRY,
    MSG_SELECT_FIELD,
    MSG_ENTER_NEW_VALUE,
    MSG_CONFIRM_EDIT,
    MSG_UPDATED,
    MSG_CANCELLED,
    BTN_CANCEL,
    BTN_CONFIRM,
    BTN_DENY,
    BTN_EDIT_AMOUNT,
    BTN_EDIT_DATE,
    BTN_EDIT_NOTES,
    BTN_EDIT_TYPE,
)


class TestValidateAmount:
    """Tests for the _validate_amount helper function."""

    def test_valid_positive_integer(self):
        assert _validate_amount("100") == 100
        assert _validate_amount("1") == 1
        assert _validate_amount("999999") == 999999

    def test_zero_is_invalid(self):
        assert _validate_amount("0") is None

    def test_negative_is_invalid(self):
        assert _validate_amount("-50") is None

    def test_non_numeric_is_invalid(self):
        assert _validate_amount("abc") is None
        assert _validate_amount("12.5") is None
        assert _validate_amount("") is None


class TestValidateDate:
    """Tests for the _validate_date helper function."""

    def test_valid_date(self):
        result = _validate_date("19/05/2026")
        assert result == "2026-05-19"

    def test_invalid_format(self):
        assert _validate_date("2026-05-19") is None
        assert _validate_date("19-05-2026") is None
        assert _validate_date("05/19/2026") is None

    def test_invalid_calendar_date(self):
        assert _validate_date("32/13/2026") is None
        assert _validate_date("31/02/2026") is None
        assert _validate_date("00/05/2026") is None

    def test_empty_string(self):
        assert _validate_date("") is None


class TestEditStart:
    """Tests for the edit_start handler."""

    @pytest.fixture(autouse=True)
    def setup_auth(self, patch_config):
        """Initialize auth with authorized user 123."""
        from gaelcarebot.auth import init_auth
        from gaelcarebot.config import load_config
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

    @pytest.mark.asyncio
    async def test_edit_start_empty(self, setup_update, setup_context, mock_db):
        """Test /edit with no entries - should show ERROR_NO_ENTRIES."""
        mock_db.get_all_entries.return_value = []

        update = setup_update(123)
        ctx = setup_context()

        result = await edit_start(update, ctx)

        mock_db.get_all_entries.assert_called_once_with(order_by="event_date DESC", include_consumed=True)
        update.message.reply_text.assert_called_once_with(ERROR_NO_ENTRIES)
        assert result == -1  # ConversationHandler.END

    @pytest.mark.asyncio
    async def test_edit_start_with_entries(self, setup_update, setup_context, mock_db):
        """Test /edit with entries - should show entry selection keyboard."""
        mock_db.get_all_entries.return_value = [
            {"id": 1, "entry_type": "ENTRADA", "event_date": "2026-05-19T10:00:00", "amount": 200},
            {"id": 2, "entry_type": "SALIDA", "event_date": "2026-05-18T12:00:00", "amount": 100},
        ]

        update = setup_update(123)
        ctx = setup_context()

        result = await edit_start(update, ctx)

        mock_db.get_all_entries.assert_called_once_with(order_by="event_date DESC", include_consumed=True)
        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args
        assert call_args[0][0] == MSG_SELECT_ENTRY
        assert result == SELECTING_ENTRY


class TestEditSelectEntry:
    """Tests for the entry_selected handler."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database."""
        db = Mock()
        db.get_entry = Mock(return_value=None)
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

    @pytest.mark.asyncio
    async def test_edit_select_entry(self, setup_callback_update, setup_context, mock_db):
        """Test selecting an entry - should show field selection."""
        mock_db.get_entry.return_value = {
            "id": 1,
            "entry_type": "ENTRADA",
            "event_date": "2026-05-19T10:00:00",
            "amount": 200,
            "notes": None,
        }

        update = setup_callback_update("edit_1")
        ctx = setup_context()

        result = await entry_selected(update, ctx)

        update.callback_query.answer.assert_called_once()
        mock_db.get_entry.assert_called_once_with(1, include_consumed=True)
        assert ctx.user_data["edit_entry_id"] == 1
        update.callback_query.edit_message_text.assert_called_once()
        call_args = update.callback_query.edit_message_text.call_args
        assert call_args[0][0] == MSG_SELECT_FIELD
        assert result == EDITING_FIELD


class TestEditModifyAmount:
    """Tests for modifying the amount field."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database."""
        db = Mock()
        db.update_entry = Mock(return_value=True)
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
    def setup_message_update(self):
        """Create a mock update with message."""
        def _create(text: str, user_id: int = 123):
            update = Mock()
            update.effective_user = Mock()
            update.effective_user.id = user_id
            update.message = Mock()
            update.message.text = text
            update.message.reply_text = AsyncMock()
            update.callback_query = None
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

    @pytest.mark.asyncio
    async def test_edit_modify_amount(self, setup_callback_update, setup_message_update, setup_context, mock_db):
        """Test modifying amount field with valid value."""
        # Step 1: Select the amount field
        update = setup_callback_update("field_amount")
        ctx = setup_context({"edit_entry_id": 1, "edit_entry_original": {"amount": 100}})

        result = await field_selected(update, ctx)

        update.callback_query.answer.assert_called_once()
        assert ctx.user_data["edit_field"] == "amount"
        assert result == EDITING_VALUE

        # Step 2: Enter new amount value
        update = setup_message_update("150")

        result = await receive_value(update, ctx)

        assert ctx.user_data["edit_new_value"] == 150
        update.message.reply_text.assert_called_once()
        assert result == CONFIRMING

        # Step 3: Confirm the edit
        update = setup_callback_update("confirm")

        result = await confirm_edit(update, ctx)

        update.callback_query.answer.assert_called_once()
        mock_db.update_entry.assert_called_once_with(1, amount=150)
        update.callback_query.edit_message_text.assert_called_once_with(MSG_UPDATED)
        assert result == -1  # ConversationHandler.END


class TestEditModifyNotes:
    """Tests for modifying the notes field."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database."""
        db = Mock()
        db.update_entry = Mock(return_value=True)
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
    def setup_message_update(self):
        """Create a mock update with message."""
        def _create(text: str, user_id: int = 123):
            update = Mock()
            update.effective_user = Mock()
            update.effective_user.id = user_id
            update.message = Mock()
            update.message.text = text
            update.message.reply_text = AsyncMock()
            update.callback_query = None
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

    @pytest.mark.asyncio
    async def test_edit_modify_notes(self, setup_callback_update, setup_message_update, setup_context, mock_db):
        """Test modifying notes field with valid value."""
        # Step 1: Select the notes field
        update = setup_callback_update("field_notes")
        ctx = setup_context({"edit_entry_id": 1, "edit_entry_original": {"notes": None}})

        result = await field_selected(update, ctx)

        update.callback_query.answer.assert_called_once()
        assert ctx.user_data["edit_field"] == "notes"
        assert result == EDITING_VALUE

        # Step 2: Enter new notes value
        update = setup_message_update("Nueva nota de prueba")

        result = await receive_value(update, ctx)

        assert ctx.user_data["edit_new_value"] == "Nueva nota de prueba"
        update.message.reply_text.assert_called_once()
        assert result == CONFIRMING

        # Step 3: Confirm the edit
        update = setup_callback_update("confirm")

        result = await confirm_edit(update, ctx)

        update.callback_query.answer.assert_called_once()
        mock_db.update_entry.assert_called_once_with(1, notes="Nueva nota de prueba")
        update.callback_query.edit_message_text.assert_called_once_with(MSG_UPDATED)
        assert result == -1  # ConversationHandler.END


class TestEditCancel:
    """Tests for canceling the edit conversation."""

    @pytest.fixture
    def setup_callback_update(self):
        """Create a mock update with callback query."""
        def _create(user_id: int = 123):
            update = Mock()
            update.effective_user = Mock()
            update.effective_user.id = user_id
            update.message = None
            update.callback_query = Mock()
            update.callback_query.data = "cancel"
            update.callback_query.answer = AsyncMock()
            update.callback_query.edit_message_text = AsyncMock()
            return update
        return _create

    @pytest.fixture
    def setup_context(self):
        """Create a mock context."""
        def _create(user_data: dict | None = None):
            ctx = Mock()
            ctx.bot.send_message = AsyncMock()
            ctx.bot_data = {}
            ctx.user_data = user_data or {}
            ctx.args = []
            ctx.match = None
            return ctx
        return _create

    @pytest.mark.asyncio
    async def test_edit_cancel(self, setup_callback_update, setup_context):
        """Test canceling the conversation."""
        update = setup_callback_update()
        ctx = setup_context({"edit_entry_id": 1, "edit_field": "amount"})

        result = await cancel(update, ctx)

        update.callback_query.answer.assert_called_once()
        update.callback_query.edit_message_text.assert_called_once_with(MSG_CANCELLED)
        assert result == -1  # ConversationHandler.END


class TestEditInvalidAmount:
    """Tests for invalid amount validation."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database."""
        db = Mock()
        db.update_entry = Mock(return_value=True)
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
    def setup_message_update(self):
        """Create a mock update with message."""
        def _create(text: str, user_id: int = 123):
            update = Mock()
            update.effective_user = Mock()
            update.effective_user.id = user_id
            update.message = Mock()
            update.message.text = text
            update.message.reply_text = AsyncMock()
            update.callback_query = None
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

    @pytest.mark.asyncio
    async def test_edit_invalid_amount(self, setup_callback_update, setup_message_update, setup_context, mock_db):
        """Test entering an invalid amount value."""
        # Step 1: Select the amount field
        update = setup_callback_update("field_amount")
        ctx = setup_context({"edit_entry_id": 1, "edit_entry_original": {"amount": 100}})

        result = await field_selected(update, ctx)
        assert result == EDITING_VALUE

        # Step 2: Enter invalid amount value (negative)
        update = setup_message_update("-50")

        result = await receive_value(update, ctx)

        update.message.reply_text.assert_called_once_with(ERROR_INVALID_AMOUNT)
        assert result == EDITING_VALUE  # Stay in EDITING_VALUE state


class TestEditModifyEntryType:
    """Tests for modifying the entry_type field."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database with conn.execute."""
        db = Mock()
        db.update_entry = Mock(return_value=True)
        db.conn = Mock()
        db.conn.execute = Mock()
        db.conn.commit = Mock()
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

    @pytest.mark.asyncio
    async def test_edit_select_entry_type_field(self, setup_callback_update, setup_context):
        """Test selecting entry_type field shows ENTRADA/SALIDA options."""
        update = setup_callback_update("field_entry_type")
        ctx = setup_context({"edit_entry_id": 1, "edit_entry_original": {"entry_type": "ENTRADA"}})

        result = await field_selected(update, ctx)

        update.callback_query.answer.assert_called_once()
        assert ctx.user_data["edit_field"] == "entry_type"
        assert result == SELECTING_ENTRY_TYPE
        # Verify the keyboard has ENTRADA and SALIDA options
        call_args = update.callback_query.edit_message_text.call_args
        assert "Selecciona el nuevo tipo:" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_edit_entry_type_entrada_to_salida(self, setup_callback_update, setup_context, mock_db):
        """Test changing entry_type from ENTRADA to SALIDA sets consumed_at."""
        # Step 1: Select SALIDA
        update = setup_callback_update("entry_type_SALIDA")
        ctx = setup_context({
            "edit_entry_id": 1,
            "edit_entry_original": {"entry_type": "ENTRADA", "amount": 100, "event_date": "2026-05-19T10:00:00", "notes": None},
            "edit_field": "entry_type"
        })

        result = await entry_type_selected(update, ctx)

        update.callback_query.answer.assert_called_once()
        assert ctx.user_data["edit_new_value"] == "SALIDA"
        assert result == CONFIRMING

        # Step 2: Confirm the edit
        update = setup_callback_update("confirm")

        result = await confirm_edit(update, ctx)

        update.callback_query.answer.assert_called_once()
        mock_db.update_entry.assert_called_once_with(1, entry_type="SALIDA")
        # Verify consumed_at was set (now using now_madrid() as bound parameter)
        assert mock_db.conn.execute.call_count == 2  # BEGIN + consumed_at
        begin_call, consumed_call = mock_db.conn.execute.call_args_list
        assert begin_call[0][0] == "BEGIN"
        assert "consumed_at = ?" in consumed_call[0][0]
        assert consumed_call[0][1][1] == 1  # second param is entry_id
        mock_db.conn.commit.assert_called_once()
        update.callback_query.edit_message_text.assert_called_once_with(MSG_UPDATED)
        assert result == -1  # ConversationHandler.END

    @pytest.mark.asyncio
    async def test_edit_entry_type_salida_to_entrada(self, setup_callback_update, setup_context, mock_db):
        """Test changing entry_type from SALIDA to ENTRADA clears consumed_at."""
        # Step 1: Select ENTRADA
        update = setup_callback_update("entry_type_ENTRADA")
        ctx = setup_context({
            "edit_entry_id": 1,
            "edit_entry_original": {"entry_type": "SALIDA", "amount": 100, "event_date": "2026-05-19T10:00:00", "notes": None},
            "edit_field": "entry_type"
        })

        result = await entry_type_selected(update, ctx)

        update.callback_query.answer.assert_called_once()
        assert ctx.user_data["edit_new_value"] == "ENTRADA"
        assert result == CONFIRMING

        # Step 2: Confirm the edit
        update = setup_callback_update("confirm")

        result = await confirm_edit(update, ctx)

        update.callback_query.answer.assert_called_once()
        mock_db.update_entry.assert_called_once_with(1, entry_type="ENTRADA")
        # Verify consumed_at was cleared
        assert mock_db.conn.execute.call_count == 2  # BEGIN + consumed_at=NULL
        begin_call, consumed_call = mock_db.conn.execute.call_args_list
        assert begin_call[0][0] == "BEGIN"
        assert "consumed_at = NULL" in consumed_call[0][0]
        mock_db.conn.commit.assert_called_once()
        update.callback_query.edit_message_text.assert_called_once_with(MSG_UPDATED)
        assert result == -1  # ConversationHandler.END

    @pytest.mark.asyncio
    async def test_edit_entry_type_same_value_no_consumed_at_change(self, setup_callback_update, setup_context, mock_db):
        """Test changing entry_type to same value doesn't modify consumed_at."""
        # Select ENTRADA when already ENTRADA
        update = setup_callback_update("entry_type_ENTRADA")
        ctx = setup_context({
            "edit_entry_id": 1,
            "edit_entry_original": {"entry_type": "ENTRADA", "amount": 100, "event_date": "2026-05-19T10:00:00", "notes": None},
            "edit_field": "entry_type"
        })

        result = await entry_type_selected(update, ctx)
        assert result == CONFIRMING

        # Confirm the edit
        update = setup_callback_update("confirm")
        result = await confirm_edit(update, ctx)

        mock_db.update_entry.assert_called_once_with(1, entry_type="ENTRADA")
        # Verify consumed_at was NOT modified
        mock_db.conn.execute.assert_not_called()
        mock_db.conn.commit.assert_not_called()


class TestEditEntryTypeIntegration:
    """RED tests — integration tests for editing entry_type field with a REAL MilkDatabase.

    These tests MUST FAIL because ``update_entry()`` has
    ``WHERE consumed_at IS NULL`` at ``db.py:237``, which silently
    prevents updating entries marked as consumed (SALIDA entries).

    Using ``MilkDatabase(":memory:")`` — no mocks.
    """

    def test_edit_entrada_to_salida_to_entrada_roundtrip(self) -> None:
        """SALIDA→ENTRADA round-trip: clear consumed_at first, then update_entry.

        GREEN: clearing consumed_at before update_entry simulates the
        fixed confirm_edit() path.
        """
        db = MilkDatabase(":memory:")
        db.add_entry("ENTRADA", 100, "2026-05-19T10:00:00", 123, "test_user")

        db.update_entry(1, entry_type="SALIDA")
        db.conn.execute(
            "UPDATE milk_entries SET consumed_at = ? WHERE id = ?",
            (now_madrid(), 1),
        )
        db.conn.commit()

        db.conn.execute(
            "UPDATE milk_entries SET consumed_at = NULL WHERE id = ?",
            (1,),
        )
        db.conn.commit()
        db.update_entry(1, entry_type="ENTRADA")

        entry = db.get_entry(1, include_consumed=True)
        assert entry["consumed_at"] is None
        assert entry["entry_type"] == "ENTRADA"

    def test_edit_roundtrip_preserves_stock(self) -> None:
        """Stock IS preserved after SALIDA→ENTRADA with consumed_at cleared first.

        GREEN: clearing consumed_at before update_entry restores the
        entry to valid stock calculations.
        """
        db = MilkDatabase(":memory:")
        db.add_entry("ENTRADA", 200, "2026-05-19T10:00:00", 123, "test_user")
        initial_stock = db.get_total_stock()

        db.update_entry(1, entry_type="SALIDA")
        db.conn.execute(
            "UPDATE milk_entries SET consumed_at = ? WHERE id = ?",
            (now_madrid(), 1),
        )
        db.conn.commit()

        db.conn.execute(
            "UPDATE milk_entries SET consumed_at = NULL WHERE id = ?",
            (1,),
        )
        db.conn.commit()
        db.update_entry(1, entry_type="ENTRADA")

        assert db.get_total_stock() == initial_stock

    def test_edit_salida_to_entrada_when_consumed_at_set(self) -> None:
        """SALIDA→ENTRADA: clear consumed_at first, then update_entry succeeds.

        GREEN: clearing consumed_at before update_entry follows the
        fixed confirm_edit() path — consumed_at=NULL guard is bypassed.
        """
        db = MilkDatabase(":memory:")
        db.add_entry("ENTRADA", 100, "2026-05-19T10:00:00", 123, "test_user")

        db.conn.execute(
            "UPDATE milk_entries SET consumed_at = ?, entry_type = ? WHERE id = ?",
            (now_madrid(), "SALIDA", 1),
        )
        db.conn.commit()

        db.conn.execute(
            "UPDATE milk_entries SET consumed_at = NULL WHERE id = ?",
            (1,),
        )
        db.conn.commit()
        success = db.update_entry(1, entry_type="ENTRADA")
        entry = db.get_entry(1, include_consumed=True)

        assert success is True
        assert entry["entry_type"] == "ENTRADA"
        assert entry["consumed_at"] is None
