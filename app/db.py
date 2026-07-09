"""
Lightweight SQLite persistence for EduGenie accounts and history.

No ORM — just stdlib sqlite3 — to keep the deployment footprint small.
"""
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from app.config import settings

os.makedirs(os.path.dirname(settings.DB_PATH), exist_ok=True)


@contextmanager
def get_conn():
    conn = sqlite3.connect(settings.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                tool TEXT NOT NULL,
                input_summary TEXT NOT NULL,
                result TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------- users ----------

def create_user(name: str, email: str, password_hash: str) -> sqlite3.Row:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (name, email.lower().strip(), password_hash, now_iso()),
        )
        user_id = cur.lastrowid
        return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def get_user_by_email(email: str):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE email = ?", (email.lower().strip(),)
        ).fetchone()


def get_user_by_id(user_id: int):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


# ---------- history ----------

def add_history(user_id: int, tool: str, input_summary: str, result: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO history (user_id, tool, input_summary, result, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, tool, input_summary[:300], result, now_iso()),
        )


def list_history(user_id: int, limit: int = 50):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM history WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()


def delete_history_item(user_id: int, item_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM history WHERE id = ? AND user_id = ?", (item_id, user_id)
        )
        return cur.rowcount > 0
