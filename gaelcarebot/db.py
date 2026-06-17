"""Database layer for GaelCareBot - SQLite backend for milk stock management."""

import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

# Europe/Madrid timezone
MADRID_TZ = timezone(timedelta(hours=2))  # CEST (UTC+2, May 2026)
# For non-DST periods this would be UTC+1; for simplicity we use a fixed +2 offset
# during the May–October window. Production should use zoneinfo or pytz.


def now_madrid() -> str:
    """Return the current datetime in Europe/Madrid as ISO-8601 without timezone."""
    return datetime.now(MADRID_TZ).strftime("%Y-%m-%dT%H:%M:%S")

_VALID_COLUMNS = frozenset(
    {"entry_type", "amount", "event_date", "user_id", "username", "notes"}
)

_VALID_ENTRY_TYPES = frozenset({"ENTRADA", "SALIDA"})

_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS milk_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_type TEXT NOT NULL CHECK(entry_type IN ('ENTRADA', 'SALIDA')),
    amount INTEGER NOT NULL CHECK(amount > 0),
    event_date TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    username TEXT,
    notes TEXT,
            created_at TEXT NOT NULL,
    consumed_at TEXT DEFAULT NULL
)
"""


def dict_from_row(row: sqlite3.Row) -> dict[str, Any]:
    """Convert a sqlite3.Row to a plain dict."""
    if row is None:
        return None
    return dict(row)


class MilkDatabase:
    """SQLite-backed database for milk stock tracking.

    Supports context manager usage:

        with MilkDatabase('data.db') as db:
            db.add_entry(...)
    """

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self._connect()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect(self) -> None:
        """Open connection, configure pragmas, set row factory, create tables."""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._create_tables()
        self._migrate_schema()

    def _create_tables(self) -> None:
        """Create the milk_entries table if it does not exist."""
        self.conn.execute(_TABLE_SQL)
        self.conn.commit()

    def _migrate_schema(self) -> None:
        """Migrate schema: rename deleted_at→consumed_at, add consumed_at if missing, migrate SALIDAs."""
        try:
            self.conn.execute(
                "ALTER TABLE transactions RENAME COLUMN deleted_at TO consumed_at"
            )
            self.conn.commit()
        except sqlite3.OperationalError:
            pass
        try:
            self.conn.execute(
                "ALTER TABLE transactions ADD COLUMN consumed_at TEXT DEFAULT NULL"
            )
            self.conn.commit()
        except sqlite3.OperationalError:
            pass
        self.conn.execute(
            "UPDATE milk_entries SET consumed_at = COALESCE(consumed_at, created_at) WHERE entry_type = 'SALIDA'"
        )
        self.conn.commit()
        try:
            self.conn.execute(
                "ALTER TABLE transactions RENAME COLUMN fecha_hora TO add_at"
            )
            self.conn.commit()
        except sqlite3.OperationalError:
            pass

    @staticmethod
    def _validate_entry_type(entry_type: str) -> None:
        if entry_type not in _VALID_ENTRY_TYPES:
            raise ValueError(
                f"entry_type must be one of {_VALID_ENTRY_TYPES}, got {entry_type!r}"
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_entry(
        self,
        entry_type: str,
        amount: int,
        event_date: str,
        user_id: int,
        username: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> int:
        """Insert a new transaction and return its id."""
        self._validate_entry_type(entry_type)
        if notes is not None and len(notes) > 200:
            raise ValueError("notes cannot exceed 200 characters")

        cur = self.conn.execute(
            """INSERT INTO milk_entries (entry_type, amount, event_date, user_id, username, notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (entry_type, amount, event_date, user_id, username, notes, now_madrid()),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_entry(self, entry_id: int, include_consumed: bool = False) -> Optional[dict[str, Any]]:
        """Return a single entry by id, or None if not found.

        Args:
            entry_id: The entry ID to look up.
            include_consumed: If True, return the entry even if consumed_at is set.
        """
        sql = "SELECT * FROM milk_entries WHERE id = ?"
        if not include_consumed:
            sql += " AND consumed_at IS NULL"
        cur = self.conn.execute(sql, (entry_id,))
        row = cur.fetchone()
        return dict_from_row(row)

    def get_all_entries(
        self, order_by: str = "event_date DESC", include_consumed: bool = False
    ) -> list[dict[str, Any]]:
        """Return all entries ordered by *order_by* (sanitised).

        Args:
            order_by: Column and direction to sort by
            include_consumed: If True, include consumed entries. Default False.
        """
        parts = order_by.strip().split()
        if len(parts) not in (1, 2):
            raise ValueError(f"Invalid order_by: {order_by!r}")
        col = parts[0]
        allowed_cols = {"id", "entry_type", "amount", "event_date", "created_at"}
        if col not in allowed_cols:
            raise ValueError(f"Invalid sort column: {col!r}")
        direction = parts[1].upper() if len(parts) == 2 else "DESC"
        if direction not in ("ASC", "DESC"):
            raise ValueError(f"Invalid sort direction: {direction!r}")

        safe_order = f"{col} {direction}"
        if include_consumed:
            cur = self.conn.execute(
                f"SELECT * FROM milk_entries ORDER BY {safe_order}"
            )
        else:
            cur = self.conn.execute(
                f"SELECT * FROM milk_entries WHERE consumed_at IS NULL ORDER BY {safe_order}"
            )
        return [dict_from_row(row) for row in cur.fetchall()]

    def get_entries_by_date(self, date: str) -> list[dict[str, Any]]:
        """Return all entries matching an ISO date prefix (YYYY-MM-DD).

        Uses a half-open interval: [date 00:00:00, next_date 00:00:00).
        ENTRADA entries are filtered by add_at (extraction date).
        SALIDA entries are filtered by consumed_at (consumption date).
        """
        start = f"{date}T00:00:00"
        # Compute next day
        dt = datetime.strptime(date, "%Y-%m-%d")
        next_dt = dt + timedelta(days=1)
        end = next_dt.strftime("%Y-%m-%dT00:00:00")

        cur = self.conn.execute(
            """SELECT * FROM milk_entries
               WHERE (entry_type = 'ENTRADA' AND event_date >= ? AND event_date < ?)
                  OR (entry_type = 'SALIDA' AND consumed_at >= ? AND consumed_at < ?)
                  OR (entry_type = 'SALIDA' AND consumed_at IS NULL AND event_date >= ? AND event_date < ?)
               ORDER BY event_date DESC""",
            (start, end, start, end, start, end),
        )
        entries = [dict_from_row(row) for row in cur.fetchall()]

        # Reversal SALIDAs on the same day represent both an extraction
        # and a consumption. Add synthetic ENTRADA entries so the daily
        # summary shows both sides.
        synthetic = []
        for entry in entries:
            if entry["entry_type"] == "SALIDA" and entry.get("consumed_at"):
                salida_add_date = entry["event_date"][:10] if entry["event_date"] else ""
                if salida_add_date == date:
                    synthetic.append({**entry, "entry_type": "ENTRADA"})
        entries.extend(synthetic)
        entries.sort(key=lambda e: e["event_date"], reverse=True)
        return entries

    def update_entry(self, entry_id: int, **kwargs: Any) -> bool:
        """Update provided fields on an entry. Returns True if a row was updated."""
        # Filter to valid column names only
        updates = {k: v for k, v in kwargs.items() if k in _VALID_COLUMNS}
        if not updates:
            return False

        # Validate tipo if present
        if "entry_type" in updates:
            self._validate_entry_type(updates["entry_type"])
        # Validate notas length if present
        if "notes" in updates and updates["notes"] is not None and len(updates["notes"]) > 200:
            raise ValueError("notes cannot exceed 200 characters")

        set_clause = ", ".join(f"{col} = ?" for col in updates)
        values = list(updates.values()) + [entry_id]

        # Selective guard: restricted fields (affect stock/identity) require
        # consumed_at IS NULL; safe fields (metadata only) are always allowed.
        restricted_fields = {"entry_type", "amount", "user_id", "username"}
        has_restricted = any(field in updates for field in restricted_fields)

        if has_restricted:
            cur = self.conn.execute(
                f"UPDATE milk_entries SET {set_clause} WHERE id = ? AND consumed_at IS NULL",
                values,
            )
        else:
            cur = self.conn.execute(
                f"UPDATE milk_entries SET {set_clause} WHERE id = ?",
                values,
            )
        self.conn.commit()
        return cur.rowcount > 0

    def delete_entry(self, entry_id: int) -> bool:
        """Soft delete an entry by id. Returns True if a row was soft-deleted."""
        cur = self.conn.execute(
            "UPDATE milk_entries SET consumed_at = ? WHERE id = ? AND consumed_at IS NULL",
            (now_madrid(), entry_id)
        )
        self.conn.commit()
        return cur.rowcount > 0

    def consume_fifo(
        self,
        amount: int,
        event_date: str,
        user_id: int,
        username: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> int:
        """Consume stock using FIFO strategy.

        1. Fetch ENTRADA entries WHERE consumed_at IS NULL ORDER BY event_date ASC, id ASC
        2. Verify sum of available ENTRADAs >= amount (raise ValueError if insufficient)
        3. Mark ENTRADA entries with consumed_at = now_madrid() in FIFO order until cumulative >= amount
        4. Create a new SALIDA entry recording the consumption
        5. Return the new SALIDA entry_id

        Args:
            amount: Amount to consume (must be > 0)
            add_at: ISO format datetime for the SALIDA entry
            user_id: User consuming the stock
            username: Optional username
            notas: Optional notes

        Returns:
            The ID of the newly created SALIDA entry

        Raises:
            ValueError: If stock is insufficient
        """
        if amount <= 0:
            raise ValueError("amount must be positive")

        cur = self.conn.execute(
            "SELECT id, amount FROM milk_entries WHERE entry_type = 'ENTRADA' AND consumed_at IS NULL ORDER BY event_date ASC, id ASC"
        )
        entradas = cur.fetchall()

        available = sum(row[1] for row in entradas)
        if available < amount:
            raise ValueError(f"Insufficient stock: need {amount}, available {available}")

        cumulative = 0
        for row in entradas:
            entry_id = row[0]
            entry_cantidad = row[1]
            self.conn.execute(
                "UPDATE milk_entries SET consumed_at = ? WHERE id = ?",
                (now_madrid(), entry_id)
            )
            cumulative += entry_cantidad
            if cumulative >= amount:
                break

        now_str = now_madrid()
        cur = self.conn.execute(
            """INSERT INTO milk_entries (entry_type, amount, event_date, user_id, username, notes, consumed_at, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("SALIDA", amount, event_date, user_id, username, notes, now_str, now_str),
        )
        self.conn.commit()
        return cur.lastrowid

    def reset_database(self, confirm: bool = False) -> int:
        """Hard-delete all rows and reset the autoincrement sequence.

        This is a destructive operation that permanently removes all data.
        Pass ``confirm=True`` to proceed.
        Returns the number of rows deleted.
        """
        if not confirm:
            raise ValueError("Must pass confirm=True to reset database")

        cur = self.conn.execute("DELETE FROM milk_entries")
        self.conn.execute("DELETE FROM sqlite_sequence WHERE name = 'milk_entries'")
        self.conn.commit()
        return cur.rowcount

    def get_total_stock(self) -> int:
        """Return total unconsumed ENTRADAs (matches entries shown in /stock).

        ``consume_fifo()`` marks consumed ENTRADAs with ``consumed_at`` so
        they are excluded.  Only ENTRADA entries with ``consumed_at IS NULL``
        are counted — this matches the entries displayed by /stock.
        """
        cur = self.conn.execute(
            """SELECT COALESCE(SUM(amount), 0)
               FROM milk_entries
               WHERE entry_type = 'ENTRADA' AND consumed_at IS NULL"""
        )
        row = cur.fetchone()
        return max(row[0], 0) if row else 0

    def get_daily_summary(self, date: str) -> dict[str, int]:
        """Return aggregate for a single day.

        ENTRADA entries are filtered by add_at (extraction date).
        SALIDA entries are filtered by consumed_at (consumption date).

        Returns *{"total_entradas": int, "total_salidas": int, "balance": int}*.
        """
        start = f"{date}T00:00:00"
        dt = datetime.strptime(date, "%Y-%m-%d")
        next_dt = dt + timedelta(days=1)
        end = next_dt.strftime("%Y-%m-%dT00:00:00")

        cur = self.conn.execute(
            """SELECT
                   COALESCE(SUM(CASE WHEN entry_type = 'ENTRADA' THEN amount ELSE 0 END), 0) AS total_entradas,
                   COALESCE(SUM(CASE WHEN entry_type = 'SALIDA'   THEN amount ELSE 0 END), 0) AS total_salidas
               FROM milk_entries
               WHERE (entry_type = 'ENTRADA' AND event_date >= ? AND event_date < ?)
                  OR (entry_type = 'SALIDA' AND consumed_at >= ? AND consumed_at < ?)
                  OR (entry_type = 'SALIDA' AND consumed_at IS NULL AND event_date >= ? AND event_date < ?)""",
            (start, end, start, end, start, end),
        )
        row = cur.fetchone()
        total_entradas = row["total_entradas"]
        total_salidas = row["total_salidas"]

        # Reversal SALIDAs (ENTRADA→SALIDA on same day) represent both
        # an extraction and a consumption. Add their amount as phantom ENTRADA.
        cur = self.conn.execute(
            """SELECT COALESCE(SUM(amount), 0)
               FROM milk_entries
               WHERE entry_type = 'SALIDA'
                 AND consumed_at >= ? AND consumed_at < ?
                 AND event_date >= ? AND event_date < ?""",
            (start, end, start, end),
        )
        phantom = cur.fetchone()[0]
        total_entradas += phantom

        return {
            "total_entradas": total_entradas,
            "total_salidas": total_salidas,
            "balance": total_entradas - total_salidas,
        }

    def close(self) -> None:
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "MilkDatabase":
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[object],
    ) -> None:
        self.close()
