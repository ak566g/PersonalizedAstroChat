import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from app.brain.models import utc_now
from app.llm.base import Turn

_SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_user_session ON messages (user_id, session_id, id);
"""


@dataclass
class SessionSummary:
    session_id: str
    title: str
    message_count: int
    last_message_at: str


@dataclass
class StoredMessage:
    role: str
    content: str
    created_at: str


class ShortTermStore:
    """Recent conversation turns. Always keyed by (user_id, session_id): session_id comes
    from the client, so scoping by it alone would let one user read another's turns."""

    def __init__(self, db_path: Path) -> None:
        self._path = db_path
        with closing(self._connect()) as conn:
            conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path, timeout=10)

    def append(self, user_id: str, session_id: str, role: str, content: str) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO messages (user_id, session_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, session_id, role, content, utc_now()),
            )

    def recent(self, user_id: str, session_id: str, k: int) -> list[Turn]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT role, content FROM messages WHERE user_id = ? AND session_id = ? "
                "ORDER BY id DESC LIMIT ?",
                (user_id, session_id, k),
            ).fetchall()
        return [Turn(role, content) for role, content in reversed(rows)]

    def sessions(self, user_id: str, limit: int = 50) -> list[SessionSummary]:
        """The user's sessions, most recently active first, titled by their first message."""
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT m.session_id, COUNT(*), MAX(m.created_at),
                       (SELECT content FROM messages f
                        WHERE f.user_id = m.user_id AND f.session_id = m.session_id AND f.role = 'user'
                        ORDER BY f.id LIMIT 1)
                FROM messages m
                WHERE m.user_id = ?
                GROUP BY m.session_id
                ORDER BY MAX(m.id) DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        return [
            SessionSummary(sid, (title or "")[:80], count, last)
            for sid, count, last, title in rows
        ]

    def history(
        self, user_id: str, session_id: str, limit: int = 200
    ) -> list[StoredMessage]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT role, content, created_at FROM messages WHERE user_id = ? AND session_id = ? "
                "ORDER BY id DESC LIMIT ?",
                (user_id, session_id, limit),
            ).fetchall()
        return [StoredMessage(*row) for row in reversed(rows)]