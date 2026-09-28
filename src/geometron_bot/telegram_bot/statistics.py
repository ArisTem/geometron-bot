"""Privacy-preserving daily activity records for private Telegram messages."""

import asyncio
import hashlib
import hmac
import logging
import secrets
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from telegram import Chat, Update
from telegram.ext import ContextTypes

from geometron_bot.telegram_bot.config import ConfigurationError

logger = logging.getLogger(__name__)
STATISTICS_KEY = "usage_statistics"


class UsageStatistics:
    def __init__(self, db_path: Path, hmac_key: str) -> None:
        self._db_path = db_path
        self._key = hmac_key.encode("utf-8")

    def initialize(self) -> None:
        """Create and verify the database before polling starts."""
        try:
            if not self._db_path.parent.is_dir():
                raise ConfigurationError(
                    "STATS_DB_PATH parent directory does not exist or is not a directory."
                )
            with closing(sqlite3.connect(self._db_path)) as connection, connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS daily_activity (
                        day_utc TEXT NOT NULL,
                        user_digest TEXT NOT NULL,
                        PRIMARY KEY (day_utc, user_digest)
                    )
                    """
                )
                connection.execute(
                    "SELECT day_utc, user_digest FROM daily_activity LIMIT 0"
                )
                # Verify write access without leaving a synthetic activity record.
                connection.execute("SAVEPOINT stats_write_check")
                connection.execute(
                    "INSERT INTO daily_activity (day_utc, user_digest) "
                    "VALUES ('0000-00-00', ?) "
                    "ON CONFLICT(day_utc, user_digest) DO NOTHING",
                    (secrets.token_hex(32),),
                )
                connection.execute("ROLLBACK TO stats_write_check")
                connection.execute("RELEASE stats_write_check")
        except (OSError, ValueError, sqlite3.Error) as error:
            raise ConfigurationError(
                "STATS_DB_PATH database cannot be opened or initialized."
            ) from error

    def record(self, user_id: int, received_at: datetime) -> None:
        """Insert at most one activity row per user and UTC day."""
        if received_at.tzinfo is None:
            raise ValueError("received_at must be timezone-aware")
        day_utc = received_at.astimezone(UTC).date().isoformat()
        digest = hmac.new(
            self._key,
            f"telegram-user-id:v1:{user_id}".encode("ascii"),
            hashlib.sha256,
        ).hexdigest()
        with closing(sqlite3.connect(self._db_path)) as connection, connection:
            connection.execute(
                "INSERT INTO daily_activity (day_utc, user_digest) "
                "VALUES (?, ?) "
                "ON CONFLICT(day_utc, user_digest) DO NOTHING",
                (day_utc, digest),
            )


async def track_usage(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Record new private messages independently of command processing."""
    message = update.message
    if (
        message is None
        or message.chat.type != Chat.PRIVATE
        or message.from_user is None
    ):
        return

    statistics: UsageStatistics = context.bot_data[STATISTICS_KEY]
    try:
        await asyncio.to_thread(
            statistics.record, message.from_user.id, datetime.now(UTC)
        )
    except Exception as error:  # noqa: BLE001 - statistics must not block messages
        logger.error(
            "Failed to record usage statistics | error_type=%s",
            type(error).__name__,
        )
