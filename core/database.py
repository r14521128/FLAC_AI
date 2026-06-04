"""SQLite database for storing calibration runs."""

import sqlite3
import os
from datetime import datetime


DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "calibration.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id     INTEGER PRIMARY KEY AUTOINCREMENT,
                k_E        REAL NOT NULL,
                k_E_fault  REAL NOT NULL,
                loss       REAL,
                rmse       REAL,
                pearson_r  REAL,
                csv_path   TEXT,
                timestamp  TEXT,
                status     TEXT DEFAULT 'pending'
            )
        """)
        conn.commit()
    print("[DB] Initialized at", DB_PATH)


def insert_run(k_E, k_E_fault, status="pending"):
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO runs (k_E, k_E_fault, timestamp, status)
               VALUES (?, ?, ?, ?)""",
            (k_E, k_E_fault, datetime.now().isoformat(), status)
        )
        conn.commit()
        return cur.lastrowid


def update_run(run_id, loss, rmse, pearson_r, csv_path, status="completed"):
    with get_connection() as conn:
        conn.execute(
            """UPDATE runs SET loss=?, rmse=?, pearson_r=?, csv_path=?, status=?
               WHERE run_id=?""",
            (loss, rmse, pearson_r, csv_path, status, run_id)
        )
        conn.commit()


def get_all_runs():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM runs WHERE status='completed' ORDER BY run_id"
        ).fetchall()
    return [dict(r) for r in rows]


def get_best_runs(threshold_multiplier=1.5):
    """Return all runs with loss < threshold_multiplier * best_loss (GLUE)."""
    runs = get_all_runs()
    if not runs:
        return []
    best_loss = min(r["loss"] for r in runs)
    threshold = threshold_multiplier * best_loss
    return [r for r in runs if r["loss"] <= threshold]


def get_best_run():
    runs = get_all_runs()
    if not runs:
        return None
    return min(runs, key=lambda r: r["loss"])


def count_completed():
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as n FROM runs WHERE status='completed'"
        ).fetchone()
    return row["n"]
