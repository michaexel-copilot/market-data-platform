"""
lists_db: SQLite persistence for favourites and ignored symbol lists.

DB location: data/lists.db
Schema:      lists(symbol TEXT, list_name TEXT, PRIMARY KEY (symbol, list_name))
list_name values: "fav" | "ignored"
"""
import sqlite3
from pathlib import Path

ROOT     = Path(__file__).parent
DATA_DIR = ROOT / "data"
DB_PATH  = DATA_DIR / "lists.db"


def _connect() -> sqlite3.Connection:
    """Open (or create) the DB and ensure the schema exists."""
    DATA_DIR.mkdir(exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS lists (
            symbol    TEXT NOT NULL,
            list_name TEXT NOT NULL,
            PRIMARY KEY (symbol, list_name)
        )
    """)
    con.commit()
    return con


def get_lists() -> dict[str, list[str]]:
    """Return {"favs": [...], "ignored": [...]}."""
    con = _connect()
    rows = con.execute("SELECT symbol, list_name FROM lists ORDER BY rowid").fetchall()
    con.close()
    return {
        "favs":    [r[0] for r in rows if r[1] == "fav"],
        "ignored": [r[0] for r in rows if r[1] == "ignored"],
    }


def add_item(symbol: str, list_name: str) -> None:
    """Insert (symbol, list_name); silently ignores duplicates."""
    con = _connect()
    con.execute(
        "INSERT OR IGNORE INTO lists(symbol, list_name) VALUES (?, ?)",
        (symbol.upper(), list_name),
    )
    con.commit()
    con.close()


def remove_item(symbol: str, list_name: str) -> None:
    """Delete the (symbol, list_name) row if it exists."""
    con = _connect()
    con.execute(
        "DELETE FROM lists WHERE symbol = ? AND list_name = ?",
        (symbol.upper(), list_name),
    )
    con.commit()
    con.close()
