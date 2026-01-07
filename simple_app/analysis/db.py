import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path("data/app.db")


def get_connection():
    DB_PATH.parent.mkdir(exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db():
    with get_connection() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            raw_data TEXT,
            mean REAL,
            min REAL,
            max REAL,
            slope REAL,
            created_at TEXT
        )
        """)
        conn.commit()


def insert_result(raw_data, mean, min_val, max_val, slope):
    with get_connection() as conn:
        conn.execute("""
        INSERT INTO results (raw_data, mean, min, max, slope, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            raw_data,
            mean,
            min_val,
            max_val,
            slope,
            datetime.now().isoformat()
        ))
        conn.commit()


def fetch_results():
    with get_connection() as conn:
        cursor = conn.execute("""
        SELECT id, raw_data, mean, min, max, slope, created_at
        FROM results
        ORDER BY created_at DESC
        """)
        return cursor.fetchall()
