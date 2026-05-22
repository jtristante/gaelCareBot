"""Database layer for GaelCareBot - SQLite backend for milk stock management."""

import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

# Europe/Madrid timezone
MADRID_TZ = timezone(timedelta(hours=2))  # CEST (UTC+2, May 2026)
# For non-DST periods this would be UTC+1; for simplicity we use a fixed +2 offset
# during the May–October window. Production should use zoneinfo or pytz.

_VALID_COLUMNS = frozenset(
    {"tipo", "cantidad", "fecha_hora", "user_id", "username", "notas"}
)

_VALID_TIPOS = frozenset({"ENTRADA", "SALIDA"})

_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo TEXT NOT NULL CHECK(tipo IN ('ENTRADA', 'SALIDA')),
    cantidad INTEGER NOT NULL CHECK(cantidad > 0),
    fecha_hora TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    username TEXT,
    notas TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    deleted_at TEXT DEFAULT NULL
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
        """Create the transactions table if it does not exist."""
        self.conn.execute(_TABLE_SQL)
        self.conn.commit()

    def _migrate_schema(self) -> None:
        """Add the deleted_at column if it does not already exist (idempotent)."""
        try:
            self.conn.execute(
                "ALTER TABLE transactions ADD COLUMN deleted_at TEXT DEFAULT NULL"
            )
            self.conn.commit()
        except sqlite3.OperationalError:
            pass  # Column already exists — migration is idempotent

    @staticmethod
    def _validate_tipo(tipo: str) -> None:
        if tipo not in _VALID_TIPOS:
            raise ValueError(
                f"tipo must be one of {_VALID_TIPOS}, got {tipo!r}"
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_entry(
        self,
        tipo: str,
        cantidad: int,
        fecha_hora: str,
        user_id: int,
        username: Optional[str] = None,
        notas: Optional[str] = None,
    ) -> int:
        """Insert a new transaction and return its id."""
        self._validate_tipo(tipo)
        if notas is not None and len(notas) > 200:
            raise ValueError("notas cannot exceed 200 characters")

        cur = self.conn.execute(
            """INSERT INTO transactions (tipo, cantidad, fecha_hora, user_id, username, notas)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (tipo, cantidad, fecha_hora, user_id, username, notas),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_entry(self, entry_id: int) -> Optional[dict[str, Any]]:
        """Return a single entry by id, or None if not found or soft-deleted."""
        cur = self.conn.execute(
            "SELECT * FROM transactions WHERE id = ? AND deleted_at IS NULL", (entry_id,)
        )
        row = cur.fetchone()
        return dict_from_row(row)

    def get_all_entries(
        self, order_by: str = "fecha_hora DESC"
    ) -> list[dict[str, Any]]:
        """Return all entries ordered by *order_by* (sanitised)."""
        # order_by is split on whitespace and only the first two tokens are used
        # to prevent injection. Acceptable: "fecha_hora DESC" or "fecha_hora ASC".
        parts = order_by.strip().split()
        if len(parts) not in (1, 2):
            raise ValueError(f"Invalid order_by: {order_by!r}")
        col = parts[0]
        # Whitelist allowed column names
        allowed_cols = {"id", "tipo", "cantidad", "fecha_hora", "created_at"}
        if col not in allowed_cols:
            raise ValueError(f"Invalid sort column: {col!r}")
        direction = parts[1].upper() if len(parts) == 2 else "DESC"
        if direction not in ("ASC", "DESC"):
            raise ValueError(f"Invalid sort direction: {direction!r}")

        safe_order = f"{col} {direction}"
        cur = self.conn.execute(
            f"SELECT * FROM transactions WHERE deleted_at IS NULL ORDER BY {safe_order}"
        )
        return [dict_from_row(row) for row in cur.fetchall()]

    def get_entries_by_date(self, date: str) -> list[dict[str, Any]]:
        """Return all entries matching an ISO date prefix (YYYY-MM-DD).

        Uses a half-open interval: [date 00:00:00, next_date 00:00:00).
        """
        start = f"{date}T00:00:00"
        # Compute next day
        dt = datetime.strptime(date, "%Y-%m-%d")
        next_dt = dt + timedelta(days=1)
        end = next_dt.strftime("%Y-%m-%dT00:00:00")

        cur = self.conn.execute(
            "SELECT * FROM transactions WHERE fecha_hora >= ? AND fecha_hora < ? AND deleted_at IS NULL ORDER BY fecha_hora DESC",
            (start, end),
        )
        return [dict_from_row(row) for row in cur.fetchall()]

    def update_entry(self, entry_id: int, **kwargs: Any) -> bool:
        """Update provided fields on an entry. Returns True if a row was updated."""
        # Filter to valid column names only
        updates = {k: v for k, v in kwargs.items() if k in _VALID_COLUMNS}
        if not updates:
            return False

        # Validate tipo if present
        if "tipo" in updates:
            self._validate_tipo(updates["tipo"])
        # Validate notas length if present
        if "notas" in updates and updates["notas"] is not None and len(updates["notas"]) > 200:
            raise ValueError("notas cannot exceed 200 characters")

        set_clause = ", ".join(f"{col} = ?" for col in updates)
        values = list(updates.values()) + [entry_id]

        cur = self.conn.execute(
            f"UPDATE transactions SET {set_clause} WHERE id = ? AND deleted_at IS NULL",
            values,
        )
        self.conn.commit()
        return cur.rowcount > 0

    def delete_entry(self, entry_id: int) -> bool:
        """Soft delete an entry by id. Returns True if a row was soft-deleted."""
        cur = self.conn.execute(
            "UPDATE transactions SET deleted_at = datetime('now') WHERE id = ? AND deleted_at IS NULL",
            (entry_id,)
        )
        self.conn.commit()
        return cur.rowcount > 0

    def get_total_stock(self) -> int:
        """Return current stock: SUM(ENTRADA) - SUM(SALIDA). 0 if empty."""
        cur = self.conn.execute(
            """SELECT
                   COALESCE(SUM(CASE WHEN tipo = 'ENTRADA' THEN cantidad ELSE 0 END), 0) -
                   COALESCE(SUM(CASE WHEN tipo = 'SALIDA'   THEN cantidad ELSE 0 END), 0)
               FROM transactions WHERE deleted_at IS NULL"""
        )
        row = cur.fetchone()
        return row[0] if row else 0

    def get_daily_summary(self, date: str) -> dict[str, int]:
        """Return aggregate for a single day.

        Returns *{"total_entradas": int, "total_salidas": int, "balance": int}*.
        """
        start = f"{date}T00:00:00"
        dt = datetime.strptime(date, "%Y-%m-%d")
        next_dt = dt + timedelta(days=1)
        end = next_dt.strftime("%Y-%m-%dT00:00:00")

        cur = self.conn.execute(
            """SELECT
                   COALESCE(SUM(CASE WHEN tipo = 'ENTRADA' THEN cantidad ELSE 0 END), 0) AS total_entradas,
                   COALESCE(SUM(CASE WHEN tipo = 'SALIDA'   THEN cantidad ELSE 0 END), 0) AS total_salidas
               FROM transactions
               WHERE fecha_hora >= ? AND fecha_hora < ? AND deleted_at IS NULL""",
            (start, end),
        )
        row = cur.fetchone()
        total_entradas = row["total_entradas"]
        total_salidas = row["total_salidas"]
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
