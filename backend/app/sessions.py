"""Server-issued upload sessions. Only token hashes are retained in SQLite."""

import hashlib
import re
import secrets
import time
from dataclasses import dataclass, field

from app.database import Database

SESSION_COOKIE = "adi_session"
SESSION_TTL_SECONDS = 24 * 60 * 60


@dataclass(frozen=True)
class SessionGrant:
    owner_id: str
    token: str = field(repr=False)
    created_at: int
    expires_at: int
    is_new: bool


class SessionStore:
    def __init__(self, database: Database) -> None:
        self.database = database

    def resolve(self, token: str | None) -> SessionGrant | None:
        if token is None or re.fullmatch(r"[A-Za-z0-9_-]{43}", token) is None:
            return None
        owner_id = hashlib.sha256(token.encode("ascii")).hexdigest()
        with self.database.connection() as connection:
            row = connection.execute(
                "SELECT created_at, expires_at FROM upload_sessions "
                "WHERE id = ? AND expires_at > ?",
                (owner_id, int(time.time())),
            ).fetchone()
        if row is None:
            return None
        return SessionGrant(owner_id, token, row[0], row[1], False)

    @staticmethod
    def candidate() -> SessionGrant:
        token = secrets.token_urlsafe(32)
        now = int(time.time())
        return SessionGrant(
            hashlib.sha256(token.encode("ascii")).hexdigest(),
            token,
            now,
            now + SESSION_TTL_SECONDS,
            True,
        )
