"""
Postgres persistence for EduGenie accounts and history.

Works against Neon / Vercel Postgres (or any standard Postgres instance).
Uses plain psycopg2 -- no ORM -- to keep the deployment footprint small.
A fresh connection is opened per request/operation, which is the right
pattern for serverless: connections can't be safely kept alive across
invocations anyway.
"""
import psycopg2
import psycopg2.extras
from contextlib import contextmanager

from app.config import settings


class DatabaseNotConfigured(RuntimeError):
    pass


@contextmanager
def get_conn():
    if not settings.DATABASE_URL:
        raise DatabaseNotConfigured(
            "DATABASE_URL (or POSTGRES_URL) is not set. Add your Neon / Vercel "
            "Postgres connection string as an environment variable."
        )
    conn = psycopg2.connect(settings.DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS history (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                tool TEXT NOT NULL,
                input_summary TEXT NOT NULL,
                result TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )


# ---------- users ----------

def create_user(name: str, email: str, password_hash: str):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO users (name, email, password_hash)
            VALUES (%s, %s, %s)
            RETURNING *
            """,
            (name, email.lower().strip(), password_hash),
        )
        return cur.fetchone()


def get_user_by_email(email: str):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE email = %s", (email.lower().strip(),))
        return cur.fetchone()


def get_user_by_id(user_id: int):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        return cur.fetchone()


# ---------- history ----------

def add_history(user_id: int, tool: str, input_summary: str, result: str):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO history (user_id, tool, input_summary, result)
            VALUES (%s, %s, %s, %s)
            """,
            (user_id, tool, input_summary[:300], result),
        )


def list_history(user_id: int, limit: int = 50):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM history WHERE user_id = %s ORDER BY id DESC LIMIT %s",
            (user_id, limit),
        )
        return cur.fetchall()


def delete_history_item(user_id: int, item_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM history WHERE id = %s AND user_id = %s",
            (item_id, user_id),
        )
        return cur.rowcount > 0
