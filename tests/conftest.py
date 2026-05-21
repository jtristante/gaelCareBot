"""Pytest fixtures for GaelCareBot tests.

All fixtures are function-scoped unless otherwise noted, ensuring
each test gets a clean state.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

from src.config import Config, load_config
from src.db import MilkDatabase


@pytest.fixture
def sample_entry() -> dict[str, Any]:
    """Return a sample ENTRADA dictionary for use in tests."""
    return {
        "tipo": "ENTRADA",
        "cantidad": 200,
        "fecha_hora": "2026-05-19T10:00:00",
        "user_id": 123,
        "username": "test_user",
        "notas": None,
    }


@pytest.fixture
def db() -> MilkDatabase:
    """Create a fresh in-memory MilkDatabase for each test.

    Tables are created automatically by the constructor. The database
    connection is closed after the test yields.
    """
    database = MilkDatabase(":memory:")
    yield database
    database.close()


@pytest.fixture
def db_with_entries(db: MilkDatabase) -> MilkDatabase:
    """Populate *db* with 3 sample entries (2 ENTRADA, 1 SALIDA)."""
    db.add_entry("ENTRADA", 200, "2026-05-19T10:00:00", 123, "test_user", None)
    db.add_entry("ENTRADA", 150, "2026-05-19T11:00:00", 123, "test_user", None)
    db.add_entry("SALIDA", 100, "2026-05-19T12:00:00", 456, "other_user", None)
    return db


@pytest.fixture
def patch_db(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure ``MilkDatabase.__init__`` always uses ``:memory:``."""
    original_init = MilkDatabase.__init__

    def _patched_init(self, db_path: str | None = None) -> None:
        original_init(self, ":memory:")

    monkeypatch.setattr(MilkDatabase, "__init__", _patched_init)


@pytest.fixture
def mock_update() -> Mock:
    """Create a basic ``telegram.Update`` mock with an authorized user.

    Returns:
        A :class:`unittest.mock.Mock` where:

        - ``effective_user.id`` = ``123`` (property, not callable)
        - ``message.reply_text`` = ``AsyncMock``
        - ``message.reply_html`` = ``AsyncMock``
        - ``callback_query`` = ``None``
    """
    update = Mock()
    update.effective_user.id = 123
    update.message.reply_text = AsyncMock()
    update.message.reply_html = AsyncMock()
    update.callback_query = None
    return update


@pytest.fixture
def mock_context() -> Mock:
    """Create a basic ``ext.CallbackContext`` mock.

    Returns:
        A :class:`unittest.mock.Mock` where:

        - ``bot.send_message`` = ``AsyncMock``
        - ``bot_data`` = ``{}``
        - ``user_data`` = ``{}``
        - ``args`` = ``[]``
        - ``match`` = ``None``
    """
    ctx = Mock()
    ctx.bot.send_message = AsyncMock()
    ctx.bot_data = {}
    ctx.user_data = {}
    ctx.args = []
    ctx.match = None
    return ctx


@pytest.fixture
def authorized_update() -> Mock:
    """Return a ``mock_update`` with ``user.id=123`` (authorized)."""
    update = Mock()
    update.effective_user.id = 123
    update.message.reply_text = AsyncMock()
    update.message.reply_html = AsyncMock()
    update.callback_query = None
    return update


@pytest.fixture
def unauthorized_update() -> Mock:
    """Return a ``mock_update`` with ``user.id=999`` (unauthorized)."""
    update = Mock()
    update.effective_user.id = 999
    update.message.reply_text = AsyncMock()
    update.message.reply_html = AsyncMock()
    update.callback_query = None
    return update


@pytest.fixture
def patch_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set environment variables needed by ``Config``.

    Sets ``BOT_TOKEN`` and ``AUTHORIZED_USER_IDS`` before the test and
    cleans them up after the test yields.
    """
    monkeypatch.setenv("BOT_TOKEN", "test")
    monkeypatch.setenv("AUTHORIZED_USER_IDS", "123")


@pytest.fixture
def config(patch_config: None) -> Config:
    """Load and return a ``Config`` with test environment variables."""
    return load_config()
