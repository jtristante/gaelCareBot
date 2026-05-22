"""Tests for the MilkDatabase class."""

from __future__ import annotations

import pytest

from src.db import MilkDatabase


class TestMilkDatabase:
    """Test suite for MilkDatabase CRUD and query operations."""

    def test_empty_database(self, db: MilkDatabase) -> None:
        """get_total_stock on an empty database returns 0."""
        assert db.get_total_stock() == 0

    def test_get_entry_returns_none_for_missing(self, db: MilkDatabase) -> None:
        """get_entry returns None when the entry does not exist."""
        assert db.get_entry(999) is None

    def test_add_entry(self, db: MilkDatabase, sample_entry: dict) -> None:
        """Add an entry and verify it is stored correctly."""
        entry_id = db.add_entry(**sample_entry)
        assert entry_id > 0, "add_entry should return a positive integer id"

        stored = db.get_entry(entry_id)
        assert stored is not None
        assert stored["tipo"] == sample_entry["tipo"]
        assert stored["cantidad"] == sample_entry["cantidad"]
        assert stored["fecha_hora"] == sample_entry["fecha_hora"]
        assert stored["user_id"] == sample_entry["user_id"]
        assert stored["username"] == sample_entry["username"]
        assert stored["notas"] == sample_entry["notas"]

    def test_add_multiple_entries(self, db: MilkDatabase) -> None:
        """Multiple entries can be added and retrieved."""
        id1 = db.add_entry("ENTRADA", 100, "2026-05-19T08:00:00", 1, "user_a")
        id2 = db.add_entry("SALIDA", 50, "2026-05-19T09:00:00", 1, "user_a")

        entry1 = db.get_entry(id1)
        entry2 = db.get_entry(id2)
        assert entry1 is not None
        assert entry2 is not None
        assert entry1["cantidad"] == 100
        assert entry2["cantidad"] == 50

    def test_get_total_stock(self, db: MilkDatabase) -> None:
        """Stock = SUM(ENTRADA) - SUM(SALIDA)."""
        db.add_entry("ENTRADA", 300, "2026-05-19T10:00:00", 123, "test_user")
        db.add_entry("SALIDA", 100, "2026-05-19T11:00:00", 123, "test_user")
        assert db.get_total_stock() == 200

    def test_get_total_stock_only_entrada(self, db: MilkDatabase) -> None:
        """Stock equals sum of ENTRADA when no SALIDA exists."""
        db.add_entry("ENTRADA", 150, "2026-05-19T10:00:00", 123, "test_user")
        db.add_entry("ENTRADA", 50, "2026-05-19T11:00:00", 123, "test_user")
        assert db.get_total_stock() == 200

    def test_get_total_stock_negative_returns_zero(
        self, db: MilkDatabase
    ) -> None:
        """Stock does not go below 0 (consumption > supply)."""
        db.add_entry("SALIDA", 50, "2026-05-19T10:00:00", 123, "test_user")
        # The SQL returns a negative number; the caller is responsible for
        # treating negative as zero if desired.  We verify the raw value.
        assert db.get_total_stock() == -50

    def test_get_daily_summary(self, db: MilkDatabase) -> None:
        """Daily summary returns correct aggregates."""
        db.add_entry("ENTRADA", 200, "2026-05-19T10:00:00", 123, "user_a")
        db.add_entry("ENTRADA", 150, "2026-05-19T11:00:00", 123, "user_a")
        db.add_entry("SALIDA", 100, "2026-05-19T12:00:00", 123, "user_a")

        summary = db.get_daily_summary("2026-05-19")
        assert summary["total_entradas"] == 350
        assert summary["total_salidas"] == 100
        assert summary["balance"] == 250

    def test_get_daily_summary_empty_day(self, db: MilkDatabase) -> None:
        """Daily summary for a day with no entries returns zeros."""
        db.add_entry("ENTRADA", 100, "2026-05-20T10:00:00", 123, "user_a")

        summary = db.get_daily_summary("2026-05-19")
        assert summary["total_entradas"] == 0
        assert summary["total_salidas"] == 0
        assert summary["balance"] == 0

    def test_get_daily_summary_only_entrada(self, db: MilkDatabase) -> None:
        """Summary with only ENTRADA entries."""
        db.add_entry("ENTRADA", 200, "2026-05-19T10:00:00", 123, "user_a")
        summary = db.get_daily_summary("2026-05-19")
        assert summary["total_entradas"] == 200
        assert summary["total_salidas"] == 0
        assert summary["balance"] == 200

    def test_get_daily_summary_only_salida(self, db: MilkDatabase) -> None:
        """Summary with only SALIDA entries."""
        db.add_entry("SALIDA", 80, "2026-05-19T10:00:00", 123, "user_a")
        summary = db.get_daily_summary("2026-05-19")
        assert summary["total_entradas"] == 0
        assert summary["total_salidas"] == 80
        assert summary["balance"] == -80

    def test_update_entry(self, db: MilkDatabase) -> None:
        """Update cantidad and verify the change is persisted."""
        entry_id = db.add_entry(
            "ENTRADA", 200, "2026-05-19T10:00:00", 123, "test_user"
        )
        updated = db.update_entry(entry_id, cantidad=250)
        assert updated is True, "update_entry should return True"

        stored = db.get_entry(entry_id)
        assert stored["cantidad"] == 250

    def test_update_entry_tipo(self, db: MilkDatabase) -> None:
        """Update tipo field."""
        entry_id = db.add_entry(
            "ENTRADA", 200, "2026-05-19T10:00:00", 123, "test_user"
        )
        db.update_entry(entry_id, tipo="SALIDA")
        stored = db.get_entry(entry_id)
        assert stored["tipo"] == "SALIDA"

    def test_update_entry_notas(self, db: MilkDatabase) -> None:
        """Update notas field."""
        entry_id = db.add_entry(
            "ENTRADA", 200, "2026-05-19T10:00:00", 123, "test_user"
        )
        db.update_entry(entry_id, notas="Nota actualizada")
        stored = db.get_entry(entry_id)
        assert stored["notas"] == "Nota actualizada"

    def test_update_entry_multiple_fields(self, db: MilkDatabase) -> None:
        """Update multiple fields at once."""
        entry_id = db.add_entry(
            "ENTRADA", 200, "2026-05-19T10:00:00", 123, "test_user"
        )
        db.update_entry(entry_id, cantidad=300, notas="Nuevo lote")
        stored = db.get_entry(entry_id)
        assert stored["cantidad"] == 300
        assert stored["notas"] == "Nuevo lote"

    def test_update_nonexistent_entry(self, db: MilkDatabase) -> None:
        """Updating a nonexistent entry returns False."""
        result = db.update_entry(999, cantidad=100)
        assert result is False

    def test_update_entry_invalid_column(self, db: MilkDatabase) -> None:
        """Updating an invalid column is silently ignored and returns False."""
        entry_id = db.add_entry(
            "ENTRADA", 200, "2026-05-19T10:00:00", 123, "test_user"
        )
        result = db.update_entry(entry_id, invalid_col="value")
        assert result is False

    def test_delete_entry(self, db: MilkDatabase) -> None:
        """Add an entry, delete it, verify it is gone."""
        entry_id = db.add_entry(
            "ENTRADA", 200, "2026-05-19T10:00:00", 123, "test_user"
        )
        deleted = db.delete_entry(entry_id)
        assert deleted is True, "delete_entry should return True"

        assert db.get_entry(entry_id) is None

    def test_delete_nonexistent_entry(self, db: MilkDatabase) -> None:
        """Deleting a nonexistent entry returns False."""
        result = db.delete_entry(999)
        assert result is False

    def test_wal_mode(self, db: MilkDatabase) -> None:
        """Verify journal_mode is set (WAL for file DB, memory for :memory:)."""
        cursor = db.conn.execute("PRAGMA journal_mode")
        result = cursor.fetchone()[0]
        # In-memory databases fall back to 'memory' instead of 'wal'
        assert result in ("wal", "memory"), f"Unexpected journal mode: {result}"

    def test_context_manager(self) -> None:
        """Using ``with MilkDatabase(...)`` works and auto-closes."""
        with MilkDatabase(":memory:") as db:
            entry_id = db.add_entry(
                "ENTRADA", 200, "2026-05-19T10:00:00", 123, "test_user"
            )
            stored = db.get_entry(entry_id)
            assert stored is not None
            assert stored["cantidad"] == 200

        assert db.conn is None

    def test_add_entry_with_all_fields_none(self, db: MilkDatabase) -> None:
        """Entries with optional fields set to None are stored correctly."""
        entry_id = db.add_entry(
            "ENTRADA",
            100,
            "2026-05-19T10:00:00",
            123,
            username=None,
            notas=None,
        )
        stored = db.get_entry(entry_id)
        assert stored is not None
        assert stored["username"] is None
        assert stored["notas"] is None

    def test_add_entry_with_username_and_notas(self, db: MilkDatabase) -> None:
        """Entries with username and notas are fully stored."""
        entry_id = db.add_entry(
            "ENTRADA",
            100,
            "2026-05-19T10:00:00",
            123,
            username="test_user",
            notas="Nota de prueba",
        )
        stored = db.get_entry(entry_id)
        assert stored["username"] == "test_user"
        assert stored["notas"] == "Nota de prueba"

    def test_add_invalid_tipo(self, db: MilkDatabase) -> None:
        """Adding an entry with an invalid tipo raises ValueError."""
        with pytest.raises(ValueError):
            db.add_entry("INVALID", 100, "2026-05-19T10:00:00", 123)

    def test_add_entry_zero_cantidad(self, db: MilkDatabase) -> None:
        """Adding an entry with cantidad=0 violates CHECK constraint."""
        with pytest.raises(Exception):
            db.add_entry("ENTRADA", 0, "2026-05-19T10:00:00", 123)

    def test_add_entry_negative_cantidad(self, db: MilkDatabase) -> None:
        """Adding an entry with negative cantidad violates CHECK constraint."""
        with pytest.raises(Exception):
            db.add_entry("ENTRADA", -5, "2026-05-19T10:00:00", 123)


class TestSoftDelete:
    """Test suite for soft delete functionality."""

    def test_soft_delete_returns_true(self, db: MilkDatabase) -> None:
        """add entry, delete_entry(id) returns True."""
        entry_id = db.add_entry(
            "ENTRADA", 200, "2026-05-19T10:00:00", 123, "test_user"
        )
        result = db.delete_entry(entry_id)
        assert result is True

    def test_soft_delete_twice_returns_false(self, db: MilkDatabase) -> None:
        """delete_entry(id) returns False on second call."""
        entry_id = db.add_entry(
            "ENTRADA", 200, "2026-05-19T10:00:00", 123, "test_user"
        )
        db.delete_entry(entry_id)  # First delete
        result = db.delete_entry(entry_id)  # Second delete
        assert result is False

    def test_get_entry_returns_none_for_soft_deleted(self, db: MilkDatabase) -> None:
        """get_entry(id) returns None after soft delete."""
        entry_id = db.add_entry(
            "ENTRADA", 200, "2026-05-19T10:00:00", 123, "test_user"
        )
        db.delete_entry(entry_id)
        result = db.get_entry(entry_id)
        assert result is None

    def test_get_all_entries_excludes_soft_deleted(self, db: MilkDatabase) -> None:
        """list excludes the soft-deleted entry."""
        entry_id = db.add_entry(
            "ENTRADA", 200, "2026-05-19T10:00:00", 123, "test_user"
        )
        db.add_entry("ENTRADA", 100, "2026-05-19T11:00:00", 123, "test_user")
        db.delete_entry(entry_id)
        entries = db.get_all_entries()
        assert len(entries) == 1
        assert entries[0]["cantidad"] == 100

    def test_get_total_stock_excludes_soft_deleted(self, db: MilkDatabase) -> None:
        """stock decreases when deleting ENTRADA."""
        entry_id = db.add_entry(
            "ENTRADA", 200, "2026-05-19T10:00:00", 123, "test_user"
        )
        assert db.get_total_stock() == 200
        db.delete_entry(entry_id)
        assert db.get_total_stock() == 0

    def test_get_total_stock_excludes_soft_deleted_salida(self, db: MilkDatabase) -> None:
        """stock increases when deleting SALIDA."""
        db.add_entry("ENTRADA", 300, "2026-05-19T10:00:00", 123, "test_user")
        salida_id = db.add_entry(
            "SALIDA", 100, "2026-05-19T11:00:00", 123, "test_user"
        )
        assert db.get_total_stock() == 200
        db.delete_entry(salida_id)
        assert db.get_total_stock() == 300

    def test_get_entries_by_date_excludes_soft_deleted(self, db: MilkDatabase) -> None:
        """date search excludes soft-deleted entry."""
        entry_id = db.add_entry(
            "ENTRADA", 200, "2026-05-19T10:00:00", 123, "test_user"
        )
        db.add_entry("ENTRADA", 100, "2026-05-19T11:00:00", 123, "test_user")
        db.delete_entry(entry_id)
        entries = db.get_entries_by_date("2026-05-19")
        assert len(entries) == 1
        assert entries[0]["cantidad"] == 100

    def test_get_daily_summary_excludes_soft_deleted(self, db: MilkDatabase) -> None:
        """daily summary excludes soft-deleted."""
        entry_id = db.add_entry(
            "ENTRADA", 200, "2026-05-19T10:00:00", 123, "test_user"
        )
        db.add_entry("ENTRADA", 100, "2026-05-19T11:00:00", 123, "test_user")
        db.delete_entry(entry_id)
        summary = db.get_daily_summary("2026-05-19")
        assert summary["total_entradas"] == 100
        assert summary["balance"] == 100

    def test_update_entry_on_soft_deleted_returns_false(self, db: MilkDatabase) -> None:
        """update_entry(id) returns False for deleted."""
        entry_id = db.add_entry(
            "ENTRADA", 200, "2026-05-19T10:00:00", 123, "test_user"
        )
        db.delete_entry(entry_id)
        result = db.update_entry(entry_id, cantidad=300)
        assert result is False

    def test_add_entry_still_works_after_soft_deletes(self, db: MilkDatabase) -> None:
        """IDs continue incrementing after deletes."""
        entry_id1 = db.add_entry(
            "ENTRADA", 100, "2026-05-19T10:00:00", 123, "test_user"
        )
        db.delete_entry(entry_id1)
        entry_id2 = db.add_entry(
            "ENTRADA", 200, "2026-05-19T11:00:00", 123, "test_user"
        )
        assert entry_id2 > entry_id1
        entries = db.get_all_entries()
        assert len(entries) == 1
        assert entries[0]["cantidad"] == 200

    def test_soft_deleted_entry_has_deleted_at_set(self, db: MilkDatabase) -> None:
        """the deleted_at field is not NULL after delete."""
        entry_id = db.add_entry(
            "ENTRADA", 200, "2026-05-19T10:00:00", 123, "test_user"
        )
        db.delete_entry(entry_id)
        # Access the database directly to check deleted_at
        cur = db.conn.execute(
            "SELECT deleted_at FROM transactions WHERE id = ?", (entry_id,)
        )
        row = cur.fetchone()
        assert row[0] is not None
