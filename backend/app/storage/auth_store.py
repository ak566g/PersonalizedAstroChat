import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from app.brain.models import utc_now

_SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    user_id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    password_salt TEXT NOT NULL,
    password_iterations INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES accounts (user_id) ON DELETE CASCADE,
    created_at TEXT NOT NULL
);
"""


class EmailAlreadyRegistered(Exception):
    pass


@dataclass
class Account:
    user_id: str
    email: str
    password_hash: str
    password_salt: str
    password_iterations: int


class AuthStore:
    """Accounts and sessions. Deliberately separate from the graph so login keeps working
    while Neo4j is down."""

    def __init__(self, db_path: Path) -> None:
        self._path = db_path
        with closing(self._connect()) as conn:
            conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, timeout=10)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def create_account(self, account: Account) -> None:
        try:
            with closing(self._connect()) as conn, conn:
                conn.execute(
                    "INSERT INTO accounts (user_id, email, password_hash, password_salt, "
                    "password_iterations, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        account.user_id,
                        account.email,
                        account.password_hash,
                        account.password_salt,
                        account.password_iterations,
                        utc_now(),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            # The UNIQUE constraint is the source of truth, so concurrent signups can't both win.
            raise EmailAlreadyRegistered(account.email) from exc

    def delete_account(self, user_id: str) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute("DELETE FROM accounts WHERE user_id = ?", (user_id,))

    def get_account_by_email(self, email: str) -> Account | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT user_id, email, password_hash, password_salt, password_iterations "
                "FROM accounts WHERE email = ?",
                (email,),
            ).fetchone()
            return Account(*row) if row else None

    def create_session(self, token_hash: str, user_id: str) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO sessions (token_hash, user_id, created_at) VALUES (?, ?, ?)",
                (token_hash, user_id, utc_now()),
            )

    def user_for_session(self, token_hash: str) -> str | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT user_id FROM sessions WHERE token_hash = ?",
                (token_hash,),
            ).fetchone()
            return row[0] if row else None

    def delete_session(self, token_hash: str) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))