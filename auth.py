"""Login setup: demo users, password hashing, Flask-Login integration."""

import sqlite3
from pathlib import Path

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

DATA_DIR = Path(__file__).parent / "data"
USERS_DB_PATH = DATA_DIR / "flask_credentials.sqlite"

# Demo accounts only. Replace before using this with anything real.
DEMO_USERS = [
    ("alice", "alice123", 5000),
    ("bob", "bob123", 3000),
    ("carla", "carla123", 8000),
]


class User(UserMixin):
    def __init__(self, username, budget):
        self.id = username
        self.budget = budget


def get_users_conn():
    conn = sqlite3.connect(USERS_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_users_db():
    DATA_DIR.mkdir(exist_ok=True)
    conn = get_users_conn()
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                budget REAL NOT NULL
            )
        """)

        already_seeded = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if already_seeded == 0:
            conn.executemany(
                "INSERT INTO users (username, password_hash, budget) VALUES (?, ?, ?)",
                [
                    (username, generate_password_hash(password), budget)
                    for username, password, budget in DEMO_USERS
                ],
            )
    conn.close()


def load_user(username):
    """Look up a user by username. Used by Flask-Login on every request."""
    conn = get_users_conn()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return None if row is None else User(row["username"], row["budget"])


def verify_user(username, password):
    """Check a login attempt. Returns the User on success, None otherwise."""
    conn = get_users_conn()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    if row is None or not check_password_hash(row["password_hash"], password):
        return None
    return User(row["username"], row["budget"])
