"""Persistent manual language choices, keyed by pseudonymized Telegram user IDs."""

import hashlib
import hmac
import secrets
import sqlite3
from contextlib import closing

from geometron_bot.telegram_bot.config import ConfigurationError, PreferencesConfig
from geometron_bot.telegram_bot.languages import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES

SQLITE_TIMEOUT = 5.0


class UserPreferences:
    """Synchronous storage; async handlers must call operations via asyncio.to_thread.

    Each operation owns its connection. Runtime SQLite errors propagate to the
    caller so an unavailable database cannot be mistaken for Auto.
    """

    def __init__(self, config: PreferencesConfig) -> None:
        self._db_path = config.db_path
        self._key = config.hmac_key.encode("utf-8")

    def _connect(self, *, create: bool = False) -> sqlite3.Connection:
        if create:
            return sqlite3.connect(self._db_path, timeout=SQLITE_TIMEOUT)
        # A removed or unavailable file is an error, not a new empty Auto database.
        return sqlite3.connect(
            self._db_path.resolve().as_uri() + "?mode=rw",
            uri=True,
            timeout=SQLITE_TIMEOUT,
        )

    def initialize(self) -> None:
        """Create and verify the database before it is used by handlers."""
        try:
            self._db_path = self._db_path.resolve()
            if not self._db_path.parent.is_dir():
                raise ConfigurationError(
                    "PREFS_DB_PATH parent directory does not exist or is not a directory."
                )
            with closing(self._connect(create=True)) as connection, connection:
                objects = connection.execute(
                    "SELECT type, name FROM sqlite_schema "
                    "WHERE type IN ('table', 'view', 'trigger') "
                    "AND name NOT GLOB 'sqlite_*'"
                ).fetchall()
                if set(objects) - {("table", "user_preferences")}:
                    raise ConfigurationError(
                        "PREFS_DB_PATH contains an unexpected database schema."
                    )
                connection.execute("BEGIN")
                # Schema v1: adding languages requires updating existing databases too.
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_preferences (
                        user_digest TEXT PRIMARY KEY NOT NULL,
                        language TEXT NOT NULL CHECK (language IN ('ru', 'en'))
                    )
                    """
                )
                self._check_schema(connection)
                self._check_write_access(connection)
        except (OSError, ValueError, sqlite3.Error) as error:
            raise ConfigurationError(
                "PREFS_DB_PATH database cannot be opened or initialized."
            ) from error

    @staticmethod
    def _check_schema(connection: sqlite3.Connection) -> None:
        columns = [
            (name, kind.upper(), not_null, default, primary_key, hidden)
            for _, name, kind, not_null, default, primary_key, hidden in connection.execute(
                "PRAGMA table_xinfo(user_preferences)"
            )
        ]
        if columns != [
            ("user_digest", "TEXT", 1, None, 1, 0),
            ("language", "TEXT", 1, None, 0, 0),
        ]:
            raise ConfigurationError("PREFS_DB_PATH has an invalid preferences schema.")
        if connection.execute(
            "PRAGMA foreign_key_list(user_preferences)"
        ).fetchone() or any(
            unique and origin != "pk"
            for _, _, unique, origin, _ in connection.execute(
                "PRAGMA index_list(user_preferences)"
            )
        ):
            raise ConfigurationError("PREFS_DB_PATH has an invalid preferences schema.")
        language_parameters = ", ".join("?" for _ in SUPPORTED_LANGUAGES)
        if connection.execute(
            "SELECT 1 FROM user_preferences "
            f"WHERE language NOT IN ({language_parameters}) LIMIT 1",
            SUPPORTED_LANGUAGES,
        ).fetchone():
            raise ConfigurationError("PREFS_DB_PATH contains an unsupported language.")

    @staticmethod
    def _check_write_access(connection: sqlite3.Connection) -> None:
        # Verify write access without leaving a synthetic preference.
        connection.execute("SAVEPOINT prefs_write_check")
        try:
            connection.execute(
                "INSERT INTO user_preferences (user_digest, language) VALUES (?, ?)",
                (secrets.token_hex(32), DEFAULT_LANGUAGE),
            )
        finally:
            connection.execute("ROLLBACK TO prefs_write_check")
            connection.execute("RELEASE prefs_write_check")

    def _user_digest(self, user_id: int) -> str:
        return hmac.new(
            self._key,
            f"telegram-user-preferences:v1:{user_id}".encode("ascii"),
            hashlib.sha256,
        ).hexdigest()

    def get_language(self, user_id: int) -> str | None:
        """Read a manual choice; no row means Auto and does not create a record."""
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT language FROM user_preferences WHERE user_digest = ?",
                (self._user_digest(user_id),),
            ).fetchone()
        if row is None:
            return None
        if row[0] not in SUPPORTED_LANGUAGES:
            raise sqlite3.DatabaseError("Unsupported language in preferences database.")
        return row[0]

    def set_language(self, user_id: int, language: str) -> None:
        """Commit a supported manual choice, replacing any previous choice."""
        if language not in SUPPORTED_LANGUAGES:
            raise ValueError(
                f"Only {' and '.join(SUPPORTED_LANGUAGES)} can be stored as a manual language."
            )
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "INSERT INTO user_preferences (user_digest, language) VALUES (?, ?) "
                "ON CONFLICT(user_digest) DO UPDATE SET language = excluded.language",
                (self._user_digest(user_id), language),
            )

    def reset_language(self, user_id: int) -> None:
        """Commit Auto by deleting the user's row; repeated resets are harmless."""
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "DELETE FROM user_preferences WHERE user_digest = ?",
                (self._user_digest(user_id),),
            )
