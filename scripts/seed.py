"""Seed script — resets the database and populates with 17 ENTRADA records (870 ml total)."""

import os
import sys
from datetime import datetime

# Ensure the project root is on sys.path so `from src.db import MilkDatabase` works
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.db import MilkDatabase


def parse_date(dd_mm_yyyy: str) -> str:
    """Convert DD/MM/YYYY to ISO 8601 with noon Europe/Madrid CEST offset."""
    dt = datetime.strptime(dd_mm_yyyy, "%d/%m/%Y")
    return dt.strftime("%Y-%m-%dT12:00:00+02:00")


SEED_DATA = [
    ("09/04/2026", 45),
    ("26/03/2026", 150),
    ("05/03/2026", 90),
    ("04/05/2026", 45),
    ("05/05/2026", 20),
    ("06/05/2026", 25),
    ("07/05/2026", 50),
    ("07/05/2026", 25),
    ("28/05/2026", 50),
    ("08/05/2026", 35),
    ("12/05/2026", 45),
    ("12/05/2026", 25),
    ("13/05/2026", 50),
    ("14/05/2026", 40),
    ("20/05/2026", 70),
    ("21/05/2026", 50),
    ("14/05/2026", 55),
]


def main() -> None:
    db_path = os.environ.get("DB_PATH", "data/milk.db")
    db = MilkDatabase(db_path)

    db.reset_database(confirm=True)

    for date_str, cantidad in SEED_DATA:
        fecha_hora = parse_date(date_str)
        db.add_entry(
            tipo="ENTRADA",
            cantidad=cantidad,
            fecha_hora=fecha_hora,
            user_id=0,
            username="seed",
        )

    records = db.get_all_entries(order_by="fecha_hora ASC")
    total_stock = db.get_total_stock()
    print(f"Inserted {len(records)} ENTRADA records. Total stock: {total_stock} ml.")

    db.close()


if __name__ == "__main__":
    main()
