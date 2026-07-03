"""Tests for the group notification module."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from gaelcarebot.config import Config
from gaelcarebot.db import MilkDatabase
from gaelcarebot.group_notifier import (
    _config,
    get_daily_summary_text,
    init_notifier,
    send_daily_summary,
)
from gaelcarebot.messages import (
    SUMMARY_BALANCE,
    SUMMARY_HEADER,
    SUMMARY_NO_ACTIVITY,
)


class TestGetDailySummaryText:
    """Tests for get_daily_summary_text()."""

    def test_entries_chronological_order(self, db_with_entries: MilkDatabase) -> None:
        """Entries should appear in chronological order (oldest first)."""
        result = get_daily_summary_text(db_with_entries, "2026-05-19")
        lines = result.split("\n")

        # Find the entry lines (skip header, balance is last)
        entry_lines = [l for l in lines[1:-1] if l.strip()]

        # Should have 3 entries: ENTRADA at 10:00, ENTRADA at 11:00, SALIDA at 12:00
        assert len(entry_lines) == 3

        # Oldest entry first (200ml at 10:00)
        assert "+200 ml (extracción)" in entry_lines[0], "Oldest entry should be first"
        # Middle entry (150ml at 11:00)
        assert "+150 ml (extracción)" in entry_lines[1], "Middle entry should be second"
        # Newest entry (100ml at 12:00)
        assert "-100 ml (consumo)" in entry_lines[2], "Newest entry should be third"

    def test_entry_format(self, db_with_entries: MilkDatabase) -> None:
        """Entry format should show + for ENTRADA, - for SALIDA."""
        result = get_daily_summary_text(db_with_entries, "2026-05-19")

        # ENTRADA should have + sign and "extracción"
        assert "+200 ml (extracción)" in result
        assert "+150 ml (extracción)" in result

        # SALIDA should have - sign and "consumo"
        assert "-100 ml (consumo)" in result

        # Should include usernames
        assert "test_user" in result
        assert "other_user" in result

    def test_balance_unchanged(self, db_with_entries: MilkDatabase) -> None:
        """Balance line should still be present and correct."""
        result = get_daily_summary_text(db_with_entries, "2026-05-19")

        # Balance should be: 200 + 150 - 100 = 250
        assert "Balance: 250 ml" in result

    def test_no_activity_message(self, db: MilkDatabase) -> None:
        """Returns SUMMARY_NO_ACTIVITY when no entries exist."""
        result = get_daily_summary_text(db, "2026-05-19")
        assert result == SUMMARY_NO_ACTIVITY


class TestSendDailySummary:
    """Tests for send_daily_summary()."""

    @pytest.fixture(autouse=True)
    def setup_delete_message(self, mock_context: Mock) -> None:
        """Ensure delete_message is AsyncMock."""
        mock_context.bot.delete_message = AsyncMock()

    @pytest.fixture(autouse=True)
    def setup_config(self, config: Config) -> None:
        """Initialize notifier with test config before each test."""
        init_notifier(config)
        yield
        # Reset _config after test
        global _config
        _config = None

    @pytest.fixture
    def db_with_summary_table(self, db: MilkDatabase) -> MilkDatabase:
        """Extend the in-memory db with the daily_summary_messages table."""
        db.conn.execute(
            """CREATE TABLE IF NOT EXISTS daily_summary_messages (
                date TEXT PRIMARY KEY,
                message_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL
            )"""
        )
        db.conn.commit()
        return db

    @pytest.mark.asyncio
    async def test_first_call_sends_new_message(
        self, mock_context: Mock, db_with_summary_table: MilkDatabase
    ) -> None:
        """When no stored message exists, send_message should be called."""
        # Mock the message returned by send_message
        mock_msg = Mock()
        mock_msg.message_id = 123
        mock_context.bot.send_message.return_value = mock_msg

        await send_daily_summary(mock_context, db_with_summary_table)

        # Should call send_message
        mock_context.bot.send_message.assert_called_once()
        call_kwargs = mock_context.bot.send_message.call_args.kwargs
        assert call_kwargs["chat_id"] == -987654321  # from test config

        # Should NOT call delete_message
        mock_context.bot.delete_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_second_call_deletes_then_sends(
        self, mock_context: Mock, db_with_summary_table: MilkDatabase
    ) -> None:
        """When stored message exists, delete old then send new."""
        today = datetime.now().strftime("%Y-%m-%d")
        db_with_summary_table.save_daily_summary_message(today, 42, -987654321)

        mock_msg = Mock()
        mock_msg.message_id = 99
        mock_context.bot.send_message.return_value = mock_msg

        await send_daily_summary(mock_context, db_with_summary_table)

        mock_context.bot.delete_message.assert_called_once_with(
            chat_id=-987654321, message_id=42
        )
        mock_context.bot.send_message.assert_called_once()
        stored = db_with_summary_table.get_daily_summary_message(today)
        assert stored["message_id"] == 99

    @pytest.mark.asyncio
    async def test_delete_failure_still_sends(
        self, mock_context: Mock, db_with_summary_table: MilkDatabase
    ) -> None:
        """When delete fails, should still send the new message."""
        today = datetime.now().strftime("%Y-%m-%d")
        db_with_summary_table.save_daily_summary_message(today, 42, -987654321)
        mock_context.bot.delete_message.side_effect = Exception("delete failed")

        mock_msg = Mock()
        mock_msg.message_id = 99
        mock_context.bot.send_message.return_value = mock_msg

        await send_daily_summary(mock_context, db_with_summary_table)

        mock_context.bot.delete_message.assert_called_once()
        mock_context.bot.send_message.assert_called_once()
        stored = db_with_summary_table.get_daily_summary_message(today)
        assert stored["message_id"] == 99

    @pytest.mark.asyncio
    async def test_date_change_sends_new_message(
        self, mock_context: Mock, db_with_summary_table: MilkDatabase
    ) -> None:
        """When date changes, should send new message even if old date has stored message."""
        # Store a message for yesterday
        db_with_summary_table.save_daily_summary_message("2026-07-02", 42, -987654321)

        # Mock datetime.now to return today (2026-07-03)
        mock_now = datetime(2026, 7, 3, 12, 0, 0)

        with patch("gaelcarebot.group_notifier.datetime") as mock_datetime:
            mock_datetime.now.return_value = mock_now
            mock_datetime.strptime = datetime.strptime

            # Mock the message returned by send_message
            mock_msg = Mock()
            mock_msg.message_id = 100
            mock_context.bot.send_message.return_value = mock_msg

            await send_daily_summary(mock_context, db_with_summary_table)

        # Should call send_message for the new date
        mock_context.bot.send_message.assert_called_once()

        # Should NOT call delete_message (different date)
        mock_context.bot.delete_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_group_chat_configured_skips(
        self, mock_context: Mock, db: MilkDatabase, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When group_chat_id is None or 0, should skip without calling bot methods."""
        # Create config with no group_chat_id
        test_config = Config(
            bot_token="test_token",
            authorized_user_ids={123},
            group_chat_id=0,
            db_path=":memory:",
            timezone="Europe/Madrid",
            conversation_timeout=300,
        )
        init_notifier(test_config)

        await send_daily_summary(mock_context, db)

        # Should not call any bot methods
        mock_context.bot.send_message.assert_not_called()
        mock_context.bot.delete_message.assert_not_called()

@pytest.mark.asyncio
async def test_notifier_not_initialized_skips(
    mock_context: Mock, db: MilkDatabase
) -> None:
    """When _config is None, should skip without calling bot methods."""
    # Ensure _config is None (should be from teardown of previous tests)
    import gaelcarebot.group_notifier as gn
    original_config = gn._config
    gn._config = None

    try:
        await send_daily_summary(mock_context, db)

        # Should not call any bot methods
        mock_context.bot.send_message.assert_not_called()
        mock_context.bot.delete_message.assert_not_called()
    finally:
        # Restore original config
        gn._config = original_config


@pytest.fixture
def db_with_summary_table(db: MilkDatabase) -> MilkDatabase:
    """Extend the in-memory db with the daily_summary_messages table.

    This table is normally created by ``_create_tables()`` in production
    (Task 1 of the group-notifier feature). For :memory: databases in tests
    we create it explicitly so the DB methods can operate.
    """
    db.conn.execute(
        """CREATE TABLE IF NOT EXISTS daily_summary_messages (
            date TEXT PRIMARY KEY,
            message_id INTEGER NOT NULL,
            chat_id INTEGER NOT NULL
        )"""
    )
    db.conn.commit()
    return db


class TestDailySummaryMessage:
    """Test suite for get/save/delete daily summary message references."""

    def test_get_returns_none_for_missing_date(
        self, db_with_summary_table: MilkDatabase
    ) -> None:
        """get_daily_summary_message returns None when no message stored."""
        result = db_with_summary_table.get_daily_summary_message("2026-07-03")
        assert result is None

    def test_save_and_get_roundtrip(
        self, db_with_summary_table: MilkDatabase
    ) -> None:
        """Save a message reference and retrieve it."""
        db_with_summary_table.save_daily_summary_message(
            "2026-07-03", 42, -100123456
        )
        result = db_with_summary_table.get_daily_summary_message("2026-07-03")
        assert result is not None
        assert result["message_id"] == 42
        assert result["chat_id"] == -100123456

    def test_save_overwrites_existing(
        self, db_with_summary_table: MilkDatabase
    ) -> None:
        """INSERT OR REPLACE overwrites an existing entry for the same date."""
        db_with_summary_table.save_daily_summary_message(
            "2026-07-03", 42, -100123456
        )
        db_with_summary_table.save_daily_summary_message(
            "2026-07-03", 99, -100999999
        )
        result = db_with_summary_table.get_daily_summary_message("2026-07-03")
        assert result is not None
        assert result["message_id"] == 99
        assert result["chat_id"] == -100999999

    def test_delete_removes_row(
        self, db_with_summary_table: MilkDatabase
    ) -> None:
        """Delete removes the stored message reference."""
        db_with_summary_table.save_daily_summary_message(
            "2026-07-03", 42, -100123456
        )
        db_with_summary_table.delete_daily_summary_message("2026-07-03")
        result = db_with_summary_table.get_daily_summary_message("2026-07-03")
        assert result is None

    def test_delete_nonexistent_does_not_raise(
        self, db_with_summary_table: MilkDatabase
    ) -> None:
        """Deleting a nonexistent date does not raise."""
        db_with_summary_table.delete_daily_summary_message("2026-07-03")
        result = db_with_summary_table.get_daily_summary_message("2026-07-03")
        assert result is None

    def test_multiple_dates_independent(
        self, db_with_summary_table: MilkDatabase
    ) -> None:
        """Messages for different dates are stored independently."""
        db_with_summary_table.save_daily_summary_message(
            "2026-07-03", 42, -100123456
        )
        db_with_summary_table.save_daily_summary_message(
            "2026-07-04", 43, -100123456
        )
        result1 = db_with_summary_table.get_daily_summary_message("2026-07-03")
        result2 = db_with_summary_table.get_daily_summary_message("2026-07-04")
        assert result1 is not None
        assert result2 is not None
        assert result1["message_id"] == 42
        assert result2["message_id"] == 43
