"""Tests for the group notification module."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from gaelcarebot.group_notifier import (
    get_daily_summary_text,
    init_notifier,
    send_daily_summary,
)


class TestGetDailySummaryText:
    """Tests for get_daily_summary_text()."""

    def test_placeholder(self) -> None:
        """Placeholder — real tests added in Tasks 5 and 6."""
        assert True


class TestSendDailySummary:
    """Tests for send_daily_summary()."""

    def test_placeholder(self) -> None:
        """Placeholder — real tests added in Task 5."""
        assert True


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
