"""Tests for the /editar command handler."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.handlers.editar import (
    SELECTING_ENTRY,
    EDITING_FIELD,
    EDITING_VALUE,
    CONFIRMING,
    SELECTING_TIPO,
    editar_start,
    entry_selected,
    field_selected,
    tipo_selected,
    receive_value,
    confirm_edit,
    cancel,
    _validate_cantidad,
    _validate_fecha,
)
from src.messages import (
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
    BTN_EDIT_CANTIDAD,
    BTN_EDIT_FECHA,
    BTN_EDIT_NOTAS,
    BTN_EDIT_TIPO,
)


class TestValidateCantidad:
    """Tests for the _validate_cantidad helper function."""

    def test_valid_positive_integer(self):
        assert _validate_cantidad("100") == 100
        assert _validate_cantidad("1") == 1
        assert _validate_cantidad("999999") == 999999

    def test_zero_is_invalid(self):
        assert _validate_cantidad("0") is None

    def test_negative_is_invalid(self):
        assert _validate_cantidad("-50") is None

    def test_non_numeric_is_invalid(self):
        assert _validate_cantidad("abc") is None
        assert _validate_cantidad("12.5") is None
        assert _validate_cantidad("") is None


class TestValidateFecha:
    """Tests for the _validate_fecha helper function."""

    def test_valid_date(self):
        result = _validate_fecha("19/05/2026")
        assert result == "2026-05-19"

    def test_invalid_format(self):
        assert _validate_fecha("2026-05-19") is None
        assert _validate_fecha("19-05-2026") is None
        assert _validate_fecha("05/19/2026") is None

    def test_invalid_calendar_date(self):
        assert _validate_fecha("32/13/2026") is None
        assert _validate_fecha("31/02/2026") is None
        assert _validate_fecha("00/05/2026") is None

    def test_empty_string(self):
        assert _validate_fecha("") is None


class TestEditarStart:
    """Tests for the editar_start handler."""

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

    @pytest.mark.asyncio
    async def test_editar_start_empty(self, setup_update, setup_context, mock_db):
        """Test /editar with no entries - should show ERROR_NO_ENTRIES."""
        mock_db.get_all_entries.return_value = []

        update = setup_update(123)
        ctx = setup_context()

        result = await editar_start(update, ctx)

        mock_db.get_all_entries.assert_called_once_with(order_by="add_at DESC", include_consumed=True)
        update.message.reply_text.assert_called_once_with(ERROR_NO_ENTRIES)
        assert result == -1  # ConversationHandler.END

    @pytest.mark.asyncio
    async def test_editar_start_with_entries(self, setup_update, setup_context, mock_db):
        """Test /editar with entries - should show entry selection keyboard."""
        mock_db.get_all_entries.return_value = [
            {"id": 1, "tipo": "ENTRADA", "add_at": "2026-05-19T10:00:00", "cantidad": 200},
            {"id": 2, "tipo": "SALIDA", "add_at": "2026-05-18T12:00:00", "cantidad": 100},
        ]

        update = setup_update(123)
        ctx = setup_context()

        result = await editar_start(update, ctx)

        mock_db.get_all_entries.assert_called_once_with(order_by="add_at DESC", include_consumed=True)
        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args
        assert call_args[0][0] == MSG_SELECT_ENTRY
        assert result == SELECTING_ENTRY


class TestEditarSelectEntry:
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
    async def test_editar_select_entry(self, setup_callback_update, setup_context, mock_db):
        """Test selecting an entry - should show field selection."""
        mock_db.get_entry.return_value = {
            "id": 1,
            "tipo": "ENTRADA",
            "add_at": "2026-05-19T10:00:00",
            "cantidad": 200,
            "notas": None,
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


class TestEditarModifyCantidad:
    """Tests for modifying the cantidad field."""

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
    async def test_editar_modify_cantidad(self, setup_callback_update, setup_message_update, setup_context, mock_db):
        """Test modifying cantidad field with valid value."""
        # Step 1: Select the cantidad field
        update = setup_callback_update("field_cantidad")
        ctx = setup_context({"edit_entry_id": 1, "edit_entry_original": {"cantidad": 100}})

        result = await field_selected(update, ctx)

        update.callback_query.answer.assert_called_once()
        assert ctx.user_data["edit_field"] == "cantidad"
        assert result == EDITING_VALUE

        # Step 2: Enter new cantidad value
        update = setup_message_update("150")

        result = await receive_value(update, ctx)

        assert ctx.user_data["edit_new_value"] == 150
        update.message.reply_text.assert_called_once()
        assert result == CONFIRMING

        # Step 3: Confirm the edit
        update = setup_callback_update("confirm")

        result = await confirm_edit(update, ctx)

        update.callback_query.answer.assert_called_once()
        mock_db.update_entry.assert_called_once_with(1, cantidad=150)
        update.callback_query.edit_message_text.assert_called_once_with(MSG_UPDATED)
        assert result == -1  # ConversationHandler.END


class TestEditarModifyNotas:
    """Tests for modifying the notas field."""

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
    async def test_editar_modify_notas(self, setup_callback_update, setup_message_update, setup_context, mock_db):
        """Test modifying notas field with valid value."""
        # Step 1: Select the notas field
        update = setup_callback_update("field_notas")
        ctx = setup_context({"edit_entry_id": 1, "edit_entry_original": {"notas": None}})

        result = await field_selected(update, ctx)

        update.callback_query.answer.assert_called_once()
        assert ctx.user_data["edit_field"] == "notas"
        assert result == EDITING_VALUE

        # Step 2: Enter new notas value
        update = setup_message_update("Nueva nota de prueba")

        result = await receive_value(update, ctx)

        assert ctx.user_data["edit_new_value"] == "Nueva nota de prueba"
        update.message.reply_text.assert_called_once()
        assert result == CONFIRMING

        # Step 3: Confirm the edit
        update = setup_callback_update("confirm")

        result = await confirm_edit(update, ctx)

        update.callback_query.answer.assert_called_once()
        mock_db.update_entry.assert_called_once_with(1, notas="Nueva nota de prueba")
        update.callback_query.edit_message_text.assert_called_once_with(MSG_UPDATED)
        assert result == -1  # ConversationHandler.END


class TestEditarCancel:
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
    async def test_editar_cancel(self, setup_callback_update, setup_context):
        """Test canceling the conversation."""
        update = setup_callback_update()
        ctx = setup_context({"edit_entry_id": 1, "edit_field": "cantidad"})

        result = await cancel(update, ctx)

        update.callback_query.answer.assert_called_once()
        update.callback_query.edit_message_text.assert_called_once_with(MSG_CANCELLED)
        assert result == -1  # ConversationHandler.END


class TestEditarInvalidCantidad:
    """Tests for invalid cantidad validation."""

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
    async def test_editar_invalid_cantidad(self, setup_callback_update, setup_message_update, setup_context, mock_db):
        """Test entering an invalid cantidad value."""
        # Step 1: Select the cantidad field
        update = setup_callback_update("field_cantidad")
        ctx = setup_context({"edit_entry_id": 1, "edit_entry_original": {"cantidad": 100}})

        result = await field_selected(update, ctx)
        assert result == EDITING_VALUE

        # Step 2: Enter invalid cantidad value (negative)
        update = setup_message_update("-50")

        result = await receive_value(update, ctx)

        update.message.reply_text.assert_called_once_with(ERROR_INVALID_AMOUNT)
        assert result == EDITING_VALUE  # Stay in EDITING_VALUE state


class TestEditarModifyTipo:
    """Tests for modifying the tipo field."""

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
    async def test_editar_select_tipo_field(self, setup_callback_update, setup_context):
        """Test selecting tipo field shows ENTRADA/SALIDA options."""
        update = setup_callback_update("field_tipo")
        ctx = setup_context({"edit_entry_id": 1, "edit_entry_original": {"tipo": "ENTRADA"}})

        result = await field_selected(update, ctx)

        update.callback_query.answer.assert_called_once()
        assert ctx.user_data["edit_field"] == "tipo"
        assert result == SELECTING_TIPO
        # Verify the keyboard has ENTRADA and SALIDA options
        call_args = update.callback_query.edit_message_text.call_args
        assert "Selecciona el nuevo tipo:" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_editar_tipo_entrada_to_salida(self, setup_callback_update, setup_context, mock_db):
        """Test changing tipo from ENTRADA to SALIDA sets consumed_at."""
        # Step 1: Select SALIDA
        update = setup_callback_update("tipo_SALIDA")
        ctx = setup_context({
            "edit_entry_id": 1,
            "edit_entry_original": {"tipo": "ENTRADA", "cantidad": 100, "add_at": "2026-05-19T10:00:00", "notas": None},
            "edit_field": "tipo"
        })

        result = await tipo_selected(update, ctx)

        update.callback_query.answer.assert_called_once()
        assert ctx.user_data["edit_new_value"] == "SALIDA"
        assert result == CONFIRMING

        # Step 2: Confirm the edit
        update = setup_callback_update("confirm")

        result = await confirm_edit(update, ctx)

        update.callback_query.answer.assert_called_once()
        mock_db.update_entry.assert_called_once_with(1, tipo="SALIDA")
        # Verify consumed_at was set
        mock_db.conn.execute.assert_called_once()
        call_args = mock_db.conn.execute.call_args
        assert "consumed_at = strftime('%Y-%m-%dT%H:%M:%S', 'now')" in call_args[0][0]
        mock_db.conn.commit.assert_called_once()
        update.callback_query.edit_message_text.assert_called_once_with(MSG_UPDATED)
        assert result == -1  # ConversationHandler.END

    @pytest.mark.asyncio
    async def test_editar_tipo_salida_to_entrada(self, setup_callback_update, setup_context, mock_db):
        """Test changing tipo from SALIDA to ENTRADA clears consumed_at."""
        # Step 1: Select ENTRADA
        update = setup_callback_update("tipo_ENTRADA")
        ctx = setup_context({
            "edit_entry_id": 1,
            "edit_entry_original": {"tipo": "SALIDA", "cantidad": 100, "add_at": "2026-05-19T10:00:00", "notas": None},
            "edit_field": "tipo"
        })

        result = await tipo_selected(update, ctx)

        update.callback_query.answer.assert_called_once()
        assert ctx.user_data["edit_new_value"] == "ENTRADA"
        assert result == CONFIRMING

        # Step 2: Confirm the edit
        update = setup_callback_update("confirm")

        result = await confirm_edit(update, ctx)

        update.callback_query.answer.assert_called_once()
        mock_db.update_entry.assert_called_once_with(1, tipo="ENTRADA")
        # Verify consumed_at was cleared
        mock_db.conn.execute.assert_called_once()
        call_args = mock_db.conn.execute.call_args
        assert "consumed_at = NULL" in call_args[0][0]
        mock_db.conn.commit.assert_called_once()
        update.callback_query.edit_message_text.assert_called_once_with(MSG_UPDATED)
        assert result == -1  # ConversationHandler.END

    @pytest.mark.asyncio
    async def test_editar_tipo_same_value_no_consumed_at_change(self, setup_callback_update, setup_context, mock_db):
        """Test changing tipo to same value doesn't modify consumed_at."""
        # Select ENTRADA when already ENTRADA
        update = setup_callback_update("tipo_ENTRADA")
        ctx = setup_context({
            "edit_entry_id": 1,
            "edit_entry_original": {"tipo": "ENTRADA", "cantidad": 100, "add_at": "2026-05-19T10:00:00", "notas": None},
            "edit_field": "tipo"
        })

        result = await tipo_selected(update, ctx)
        assert result == CONFIRMING

        # Confirm the edit
        update = setup_callback_update("confirm")
        result = await confirm_edit(update, ctx)

        mock_db.update_entry.assert_called_once_with(1, tipo="ENTRADA")
        # Verify consumed_at was NOT modified
        mock_db.conn.execute.assert_not_called()
        mock_db.conn.commit.assert_not_called()
