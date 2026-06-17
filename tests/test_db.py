"""Tests for the MilkDatabase class."""

from __future__ import annotations

import pytest

from gaelcarebot.db import MilkDatabase, now_madrid


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
        assert stored["add_at"] == sample_entry["add_at"]
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
        """Stock = SUM(ENTRADA WHERE consumed_at IS NULL)."""
        db.add_entry("ENTRADA", 300, "2026-05-19T10:00:00", 123, "test_user")
        db.add_entry("SALIDA", 100, "2026-05-19T11:00:00", 123, "test_user")
        # Stock = sum of unconsumed ENTRADAs = 300
        assert db.get_total_stock() == 300

    def test_get_total_stock_only_entrada(self, db: MilkDatabase) -> None:
        """Stock equals sum of ENTRADA when no SALIDA exists."""
        db.add_entry("ENTRADA", 150, "2026-05-19T10:00:00", 123, "test_user")
        db.add_entry("ENTRADA", 50, "2026-05-19T11:00:00", 123, "test_user")
        assert db.get_total_stock() == 200

    def test_get_total_stock_no_entradas_returns_zero(
        self, db: MilkDatabase
    ) -> None:
        """Stock is 0 when SALIDAs exceed ENTRADAs (never negative)."""
        db.add_entry("SALIDA", 50, "2026-05-19T10:00:00", 123, "test_user")
        # Stock = 0 - 50 = -50, but max(0, -50) = 0
        assert db.get_total_stock() == 0

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
        """Soft-deleted ENTRADAs are excluded from stock (consumed_at IS NOT NULL)."""
        entry_id = db.add_entry(
            "ENTRADA", 200, "2026-05-19T10:00:00", 123, "test_user"
        )
        assert db.get_total_stock() == 200
        db.delete_entry(entry_id)
        # Soft-deleted ENTRADA excluded → stock = 0
        assert db.get_total_stock() == 0

    def test_get_total_stock_with_salidas(self, db: MilkDatabase) -> None:
        """Stock = SUM(ENTRADA WHERE consumed_at IS NULL); SALIDAs don't affect it."""
        db.add_entry("ENTRADA", 300, "2026-05-19T10:00:00", 123, "test_user")
        salida_id = db.add_entry(
            "SALIDA", 100, "2026-05-19T11:00:00", 123, "test_user"
        )
        # Stock = unconsumed ENTRADAs = 300 (SALIDAs not subtracted)
        assert db.get_total_stock() == 300
        # Deleting SALIDA doesn't change stock either
        db.delete_entry(salida_id)
        assert db.get_total_stock() == 300

    def test_get_entries_by_date_includes_soft_deleted(self, db: MilkDatabase) -> None:
        """date search includes ENTRADA entries even if later soft-deleted/consumed."""
        entry_id = db.add_entry(
            "ENTRADA", 200, "2026-05-19T10:00:00", 123, "test_user"
        )
        db.add_entry("ENTRADA", 100, "2026-05-19T11:00:00", 123, "test_user")
        db.delete_entry(entry_id)
        entries = db.get_entries_by_date("2026-05-19")
        assert len(entries) == 2
        assert {e["cantidad"] for e in entries} == {200, 100}

    def test_get_daily_summary_includes_soft_deleted(self, db: MilkDatabase) -> None:
        """daily summary includes ENTRADA entries even if later soft-deleted/consumed."""
        entry_id = db.add_entry(
            "ENTRADA", 200, "2026-05-19T10:00:00", 123, "test_user"
        )
        db.add_entry("ENTRADA", 100, "2026-05-19T11:00:00", 123, "test_user")
        db.delete_entry(entry_id)
        summary = db.get_daily_summary("2026-05-19")
        assert summary["total_entradas"] == 300
        assert summary["balance"] == 300

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

    def test_soft_deleted_entry_has_consumed_at_set(self, db: MilkDatabase) -> None:
        """the consumed_at field is not NULL after delete."""
        entry_id = db.add_entry(
            "ENTRADA", 200, "2026-05-19T10:00:00", 123, "test_user"
        )
        db.delete_entry(entry_id)
        # Access the database directly to check consumed_at
        cur = db.conn.execute(
            "SELECT consumed_at FROM transactions WHERE id = ?", (entry_id,)
        )
        row = cur.fetchone()
        assert row[0] is not None


class TestResetDatabase:
    """Test suite for database reset functionality."""

    def test_reset_clears_all_entries(self, db: MilkDatabase) -> None:
        """reset_database removes all entries."""
        db.add_entry("ENTRADA", 200, "2026-05-19T10:00:00", 123, "test_user")
        db.add_entry("SALIDA", 50, "2026-05-19T11:00:00", 123, "test_user")
        db.reset_database(confirm=True)
        assert db.get_all_entries() == []

    def test_reset_zeroes_total_stock(self, db: MilkDatabase) -> None:
        """reset_database makes total stock 0."""
        db.add_entry("ENTRADA", 300, "2026-05-19T10:00:00", 123, "test_user")
        db.add_entry("SALIDA", 100, "2026-05-19T11:00:00", 123, "test_user")
        db.reset_database(confirm=True)
        assert db.get_total_stock() == 0

    def test_reset_resets_id_sequence(self, db: MilkDatabase) -> None:
        """after reset, next entry gets id 1."""
        db.add_entry("ENTRADA", 200, "2026-05-19T10:00:00", 123, "test_user")
        db.add_entry("SALIDA", 50, "2026-05-19T11:00:00", 123, "test_user")
        db.reset_database(confirm=True)
        new_id = db.add_entry("ENTRADA", 100, "2026-05-20T10:00:00", 123, "test_user")
        assert new_id == 1

    def test_reset_preserves_schema(self, db: MilkDatabase) -> None:
        """after reset, the consumed_at column still exists."""
        db.add_entry("ENTRADA", 200, "2026-05-19T10:00:00", 123, "test_user")
        db.reset_database(confirm=True)
        cur = db.conn.execute("PRAGMA table_info(transactions)")
        columns = {row[1] for row in cur.fetchall()}
        assert "consumed_at" in columns

    def test_reset_idempotent(self, db: MilkDatabase) -> None:
        """calling reset_database twice does not raise."""
        db.add_entry("ENTRADA", 200, "2026-05-19T10:00:00", 123, "test_user")
        db.reset_database(confirm=True)
        # Second reset returns 0 (no rows to delete)
        deleted = db.reset_database(confirm=True)
        assert deleted == 0

    def test_reset_raises_without_confirm(self, db: MilkDatabase) -> None:
        """reset_database() without confirm raises ValueError."""
        with pytest.raises(ValueError, match="Must pass confirm=True to reset database"):
            db.reset_database()


class TestFIFOConsumption:
    """Test suite for FIFO consumption functionality."""

    def test_consume_fifo_basic(self, db: MilkDatabase) -> None:
        """Consume 100 from 200 ENTRADA → stock = 0 (ENTRADA fully consumed, SALIDA matched)."""
        db.add_entry('ENTRADA', 200, '2026-05-22T10:00:00', 123)
        assert db.get_total_stock() == 200
        entry_id = db.consume_fifo(100, '2026-05-22T12:00:00', 123, 'test')
        # The full 200ml ENTRADA is marked consumed (consumed_at IS NOT NULL) and
        # a 100ml SALIDA (consumed_at IS NOT NULL) is created. Both cancel out.
        assert db.get_total_stock() == 0
        assert entry_id > 0

    def test_consume_fifo_insufficient_stock(self, db: MilkDatabase) -> None:
        """Consuming more than available raises ValueError."""
        db.add_entry('ENTRADA', 50, '2026-05-22T10:00:00', 123)
        with pytest.raises(ValueError, match="Insufficient stock"):
            db.consume_fifo(100, '2026-05-22T12:00:00', 123, 'test')

    def test_consume_fifo_exact_match(self, db: MilkDatabase) -> None:
        """Consume exactly what's available → stock = 0."""
        db.add_entry('ENTRADA', 100, '2026-05-22T10:00:00', 123)
        entry_id = db.consume_fifo(100, '2026-05-22T12:00:00', 123, 'test')
        assert db.get_total_stock() == 0

    def test_consume_fifo_fifo_order(self, db: MilkDatabase) -> None:
        """FIFO: oldest ENTRADAs are consumed first."""
        id1 = db.add_entry('ENTRADA', 100, '2026-05-22T10:00:00', 123)  # oldest
        id2 = db.add_entry('ENTRADA', 200, '2026-05-22T11:00:00', 123)  # middle
        id3 = db.add_entry('ENTRADA', 150, '2026-05-22T12:00:00', 123)  # newest

        db.consume_fifo(250, '2026-05-22T13:00:00', 123, 'test')

        # Check consumed_at is set for id1 and id2, not id3
        cur = db.conn.execute("SELECT id, consumed_at FROM transactions WHERE tipo='ENTRADA'")
        rows = {row[0]: row[1] for row in cur.fetchall()}
        assert rows[id1] is not None, "id1 should be consumed"
        assert rows[id2] is not None, "id2 should be consumed"
        assert rows[id3] is None, "id3 should NOT be consumed (over-marking is OK)"

        # Stock = unconsumed ENTRADA (id3=150) - no unpaired SALIDA = 150
        assert db.get_total_stock() == 150

    def test_consume_fifo_creates_salida_entry(self, db: MilkDatabase) -> None:
        """consume_fifo creates a SALIDA entry with exact amount (not marked as consumed)."""
        db.add_entry('ENTRADA', 200, '2026-05-22T10:00:00', 123)
        entry_id = db.consume_fifo(100, '2026-05-22T12:00:00', 123, 'test', 'notas_test')

        # Verify the SALIDA entry was created
        cur = db.conn.execute("SELECT * FROM transactions WHERE id = ?", (entry_id,))
        row = cur.fetchone()
        assert row is not None
        assert row["tipo"] == "SALIDA"
        assert row["cantidad"] == 100
        assert row["add_at"] == "2026-05-22T12:00:00"
        assert row["user_id"] == 123
        assert row["username"] == "test"
        assert row["notas"] == "notas_test"
        # SALIDA entry should have consumed_at set (consistent with migration that sets it on all SALIDAs)
        assert row["consumed_at"] is not None

    def test_consume_fifo_empty_stock_raises(self, db: MilkDatabase) -> None:
        """Consuming from empty stock raises ValueError."""
        with pytest.raises(ValueError, match="Insufficient stock"):
            db.consume_fifo(100, '2026-05-22T12:00:00', 123, 'test')

    def test_consume_fifo_only_counts_unconsumed_entradas(self, db: MilkDatabase) -> None:
        """Once an ENTRADA is marked consumed by FIFO, it cannot be consumed again."""
        id1 = db.add_entry('ENTRADA', 100, '2026-05-22T10:00:00', 123)
        db.consume_fifo(50, '2026-05-22T11:00:00', 123, 'test')  # marks id1 consumed (over-marked)

        # id1 is now marked consumed, so no unconsumed ENTRADAs available for FIFO
        # Even though stock shows 50 remaining (100 ENTRADA - 50 SALIDA),
        # the ENTRADA is marked and can't be consumed again via FIFO
        with pytest.raises(ValueError, match="Insufficient stock"):
            db.consume_fifo(1, '2026-05-22T12:00:00', 123, 'test')

    def test_consume_fifo_with_tie_breaker_id(self, db: MilkDatabase) -> None:
        """When add_at is equal, use id ASC as tie-breaker."""
        id1 = db.add_entry('ENTRADA', 100, '2026-05-22T10:00:00', 123)
        id2 = db.add_entry('ENTRADA', 100, '2026-05-22T10:00:00', 123)  # same timestamp
        
        db.consume_fifo(100, '2026-05-22T11:00:00', 123, 'test')
        
        # id1 should be consumed (lower id), id2 should remain
        cur = db.conn.execute("SELECT id, consumed_at FROM transactions WHERE tipo='ENTRADA'")
        rows = {row[0]: row[1] for row in cur.fetchall()}
        assert rows[id1] is not None
        assert rows[id2] is None


class TestGetAllEntriesIncludeConsumed:
    """Test suite for get_all_entries include_consumed parameter."""

    def test_get_all_entries_default_excludes_consumed(self, db: MilkDatabase) -> None:
        """Default behavior excludes consumed entries."""
        id1 = db.add_entry('ENTRADA', 100, '2026-05-22T10:00:00', 123)
        id2 = db.add_entry('ENTRADA', 200, '2026-05-22T11:00:00', 123)
        db.delete_entry(id1)
        
        entries = db.get_all_entries()
        assert len(entries) == 1
        assert entries[0]["id"] == id2

    def test_get_all_entries_include_consumed_true(self, db: MilkDatabase) -> None:
        """include_consumed=True shows all entries including consumed."""
        id1 = db.add_entry('ENTRADA', 100, '2026-05-22T10:00:00', 123)
        id2 = db.add_entry('ENTRADA', 200, '2026-05-22T11:00:00', 123)
        db.delete_entry(id1)
        
        entries = db.get_all_entries(include_consumed=True)
        assert len(entries) == 2
        ids = {e["id"] for e in entries}
        assert ids == {id1, id2}

    def test_get_all_entries_include_consumed_false(self, db: MilkDatabase) -> None:
        """include_consumed=False is same as default (excludes consumed)."""
        id1 = db.add_entry('ENTRADA', 100, '2026-05-22T10:00:00', 123)
        db.add_entry('ENTRADA', 200, '2026-05-22T11:00:00', 123)
        db.delete_entry(id1)
        
        entries = db.get_all_entries(include_consumed=False)
        assert len(entries) == 1


class TestStockFormula:
    """Test suite for the stock formula: sum of unconsumed ENTRADAs."""

    def test_get_total_stock_formula(self, db: MilkDatabase) -> None:
        """Stock = SUM(ENTRADA WHERE consumed_at IS NULL)."""
        db.add_entry('ENTRADA', 300, '2026-05-19T10:00:00', 123)
        db.add_entry('SALIDA', 100, '2026-05-19T11:00:00', 123)
        assert db.get_total_stock() == 300

    def test_get_total_stock_never_negative(self, db: MilkDatabase) -> None:
        """Stock never goes below 0."""
        db.add_entry('SALIDA', 50, '2026-05-19T10:00:00', 123)
        assert db.get_total_stock() == 0

    def test_get_total_stock_after_consumption(self, db: MilkDatabase) -> None:
        """Stock decreases when ENTRADAs are consumed via FIFO."""
        db.add_entry('ENTRADA', 200, '2026-05-19T10:00:00', 123)
        assert db.get_total_stock() == 200

        db.consume_fifo(100, '2026-05-19T12:00:00', 123, 'test')
        # ENTRADA marked consumed (excluded) + SALIDA 100 with consumed_at (excluded)
        # Stock = 0 (matched ENTRADA and SALIDA cancel out)
        assert db.get_total_stock() == 0


class TestDualDateSummary:
    """RED tests: demonstrate that get_entries_by_date() and get_daily_summary()
    fail to include SALIDA entries whose add_at differs from consumed_at.

    These tests MUST FAIL on the current code because both methods use:
        WHERE add_at >= ? AND add_at < ? AND consumed_at IS NULL

    The entry is added as ENTRADA yesterday (2026-05-21), then tipo is
    changed to SALIDA and consumed_at is set to today (2026-05-22).
    The queries for today should find this SALIDA entry, but the
    add_at-based filter (plus consumed_at IS NULL) excludes it.
    """

    def test_daily_summary_includes_consumed_entries(
        self, db: MilkDatabase
    ) -> None:
        """SALIDA entries consumed today appear in today's summary despite add_at being yesterday.

        Must FAIL (RED) because get_daily_summary filters by add_at
        and requires consumed_at IS NULL.
        """
        entry_id = db.add_entry(
            "ENTRADA", 150, "2026-05-21T10:00:00", 123, "test_user"
        )
        db.update_entry(entry_id, tipo="SALIDA")
        db.conn.execute(
            "UPDATE transactions SET consumed_at = ? WHERE id = ?",
            ("2026-05-22T12:00:00", entry_id),
        )
        db.conn.commit()

        summary = db.get_daily_summary("2026-05-22")
        assert summary["total_salidas"] == 150

    def test_get_entries_by_date_includes_consumed(
        self, db: MilkDatabase
    ) -> None:
        """SALIDA entries consumed today appear in get_entries_by_date despite add_at being yesterday.

        Must FAIL (RED) because get_entries_by_date filters by add_at
        and requires consumed_at IS NULL.
        """
        entry_id = db.add_entry(
            "ENTRADA", 150, "2026-05-21T10:00:00", 123, "test_user"
        )
        db.update_entry(entry_id, tipo="SALIDA")
        db.conn.execute(
            "UPDATE transactions SET consumed_at = ? WHERE id = ?",
            ("2026-05-22T12:00:00", entry_id),
        )
        db.conn.commit()

        entries = db.get_entries_by_date("2026-05-22")
        assert len(entries) == 1
        assert entries[0]["tipo"] == "SALIDA"
        assert entries[0]["cantidad"] == 150


class TestUpdateEntryGuard:
    """Tests for update_entry guard on consumed entries.

    Tests 1-2: DESIRED behavior — notas/add_at edits SHOULD be allowed on
    consumed entries. These FAIL (RED) because update_entry() currently
    blocks ALL edits with ``WHERE consumed_at IS NULL``.

    Tests 3-5: Blocked fields — cantidad/tipo/user_id must remain blocked
    on consumed entries. These PASS (GREEN) already.
    """

    def test_update_entry_notas_on_consumed(self) -> None:
        """notas can be updated on a consumed entry. (SHOULD PASS after fix, FAILS now.)"""
        db = MilkDatabase(":memory:")
        try:
            entry_id = db.add_entry(
                "ENTRADA", 100, "2026-05-19T10:00:00", 123
            )
            db.conn.execute(
                "UPDATE transactions SET consumed_at = ? WHERE id = ?",
                (now_madrid(), entry_id),
            )
            db.conn.commit()
            result = db.update_entry(entry_id, notas="nueva nota")
            assert result is True
        finally:
            db.close()

    def test_update_entry_add_at_on_consumed(self) -> None:
        """add_at can be updated on a consumed entry. (SHOULD PASS after fix, FAILS now.)"""
        db = MilkDatabase(":memory:")
        try:
            entry_id = db.add_entry(
                "ENTRADA", 100, "2026-05-19T10:00:00", 123
            )
            db.conn.execute(
                "UPDATE transactions SET consumed_at = ? WHERE id = ?",
                (now_madrid(), entry_id),
            )
            db.conn.commit()
            result = db.update_entry(entry_id, add_at="2026-06-01T10:00:00")
            assert result is True
        finally:
            db.close()

    def test_update_entry_cantidad_on_consumed_blocked(self) -> None:
        """cantidad cannot be updated on a consumed entry. (PASSES now.)"""
        db = MilkDatabase(":memory:")
        try:
            entry_id = db.add_entry(
                "ENTRADA", 100, "2026-05-19T10:00:00", 123
            )
            db.conn.execute(
                "UPDATE transactions SET consumed_at = ? WHERE id = ?",
                (now_madrid(), entry_id),
            )
            db.conn.commit()
            result = db.update_entry(entry_id, cantidad=999)
            assert result is False
        finally:
            db.close()

    def test_update_entry_tipo_on_consumed_blocked(self) -> None:
        """tipo cannot be updated on a consumed entry. (PASSES now.)"""
        db = MilkDatabase(":memory:")
        try:
            entry_id = db.add_entry(
                "ENTRADA", 100, "2026-05-19T10:00:00", 123
            )
            db.conn.execute(
                "UPDATE transactions SET consumed_at = ? WHERE id = ?",
                (now_madrid(), entry_id),
            )
            db.conn.commit()
            result = db.update_entry(entry_id, tipo="SALIDA")
            assert result is False
        finally:
            db.close()

    def test_update_entry_user_id_on_consumed_blocked(self) -> None:
        """user_id cannot be updated on a consumed entry. (PASSES now.)"""
        db = MilkDatabase(":memory:")
        try:
            entry_id = db.add_entry(
                "ENTRADA", 100, "2026-05-19T10:00:00", 123
            )
            db.conn.execute(
                "UPDATE transactions SET consumed_at = ? WHERE id = ?",
                (now_madrid(), entry_id),
            )
            db.conn.commit()
            result = db.update_entry(entry_id, user_id=999)
            assert result is False
        finally:
            db.close()
