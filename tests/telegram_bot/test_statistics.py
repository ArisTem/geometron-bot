import asyncio
import hashlib
import hmac
import logging
import sqlite3
from datetime import UTC, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from telegram import Chat

from geometron_bot.telegram_bot.config import ConfigurationError
from geometron_bot.telegram_bot.statistics import (
    STATISTICS_KEY,
    UsageStatistics,
    track_usage,
)


def test_daily_monthly_and_total_counts_survive_restart(tmp_path) -> None:
    db_path = tmp_path / "stats.sqlite3"
    statistics = UsageStatistics(db_path, "test-secret")
    statistics.initialize()
    with sqlite3.connect(db_path) as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM daily_activity").fetchone()[0] == 0
        )
        assert [
            column[1] for column in connection.execute("PRAGMA table_info(daily_activity)")
        ] == ["day_utc", "user_digest"]

    # The first local timestamp maps to the same UTC day as 23:59 UTC.
    statistics.record(
        123456789,
        datetime(2026, 1, 31, 19, 59, tzinfo=timezone(timedelta(hours=-4))),
    )
    statistics.record(123456789, datetime(2026, 1, 31, 23, 59, tzinfo=UTC))
    statistics.record(987654321, datetime(2026, 1, 31, 23, 59, tzinfo=UTC))

    restarted = UsageStatistics(db_path, "test-secret")
    restarted.initialize()
    restarted.record(
        123456789,
        datetime(2026, 1, 31, 20, 0, tzinfo=timezone(timedelta(hours=-4))),
    )
    restarted.record(123456789, datetime(2026, 2, 2, 0, 0, tzinfo=UTC))
    restarted.record(123456789, datetime(2026, 2, 2, 0, 0, tzinfo=UTC))

    with sqlite3.connect(db_path) as connection:
        daily = connection.execute(
            "SELECT day_utc, COUNT(*) FROM daily_activity GROUP BY day_utc ORDER BY day_utc"
        ).fetchall()
        monthly = connection.execute(
            "SELECT substr(day_utc, 1, 7), COUNT(DISTINCT user_digest) "
            "FROM daily_activity GROUP BY substr(day_utc, 1, 7) "
            "ORDER BY substr(day_utc, 1, 7)"
        ).fetchall()
        total = connection.execute(
            "SELECT COUNT(DISTINCT user_digest) FROM daily_activity"
        ).fetchone()[0]
        rows = connection.execute(
            "SELECT day_utc, user_digest FROM daily_activity ORDER BY day_utc"
        ).fetchall()

    assert daily == [("2026-01-31", 2), ("2026-02-01", 1), ("2026-02-02", 1)]
    assert monthly == [("2026-01", 2), ("2026-02", 1)]
    assert total == 2
    expected_digest = hmac.new(
        b"test-secret", b"telegram-user-id:v1:123456789", hashlib.sha256
    ).hexdigest()
    assert sum(digest == expected_digest for _, digest in rows) == 3
    assert all(len(digest) == 64 for _, digest in rows)


def test_initialize_rejects_invalid_or_unavailable_database(tmp_path) -> None:
    with pytest.raises(ConfigurationError, match="parent directory"):
        UsageStatistics(tmp_path / "missing" / "stats.sqlite3", "secret").initialize()

    invalid_database = tmp_path / "invalid.sqlite3"
    invalid_database.write_text("not a database")
    with pytest.raises(ConfigurationError, match="cannot be opened"):
        UsageStatistics(invalid_database, "secret").initialize()

    invalid_schema = tmp_path / "invalid-schema.sqlite3"
    with sqlite3.connect(invalid_schema) as connection:
        connection.execute("CREATE TABLE daily_activity (day_utc TEXT, user_digest TEXT)")
    with pytest.raises(ConfigurationError, match="cannot be opened"):
        UsageStatistics(invalid_schema, "secret").initialize()


def test_tracking_accepts_any_new_private_message_and_ignores_other_updates() -> None:
    statistics = SimpleNamespace(record=Mock())
    context = SimpleNamespace(bot_data={STATISTICS_KEY: statistics})
    user = SimpleNamespace(id=123456789)

    for payload in (
        {"text": "/ping"},
        {"text": "/unknown"},
        {"text": "hello"},
        {"photo": [object()]},
        {"voice": object()},
    ):
        message = SimpleNamespace(
            chat=SimpleNamespace(type=Chat.PRIVATE), from_user=user, **payload
        )
        asyncio.run(track_usage(SimpleNamespace(message=message), context))

    assert statistics.record.call_count == 5
    assert all(call.args[0] == user.id for call in statistics.record.call_args_list)
    assert all(call.args[1].tzinfo == UTC for call in statistics.record.call_args_list)

    for update in (
        SimpleNamespace(message=None, edited_message=SimpleNamespace(from_user=user)),
        SimpleNamespace(message=None, callback_query=object()),
        SimpleNamespace(
            message=SimpleNamespace(
                chat=SimpleNamespace(type=Chat.GROUP), from_user=user
            )
        ),
        SimpleNamespace(
            message=SimpleNamespace(
                chat=SimpleNamespace(type=Chat.CHANNEL), from_user=user
            )
        ),
        SimpleNamespace(
            message=SimpleNamespace(
                chat=SimpleNamespace(type=Chat.PRIVATE), from_user=None
            )
        ),
    ):
        asyncio.run(track_usage(update, context))

    assert statistics.record.call_count == 5


def test_record_failure_is_logged_without_identifiers_or_secret(caplog) -> None:
    statistics = SimpleNamespace(
        record=Mock(side_effect=RuntimeError("123456789 private-key"))
    )
    context = SimpleNamespace(bot_data={STATISTICS_KEY: statistics})
    message = SimpleNamespace(
        chat=SimpleNamespace(type=Chat.PRIVATE), from_user=SimpleNamespace(id=123456789)
    )

    with caplog.at_level(logging.ERROR):
        asyncio.run(track_usage(SimpleNamespace(message=message), context))

    assert "Failed to record usage statistics" in caplog.text
    assert "error_type=RuntimeError" in caplog.text
    assert "123456789" not in caplog.text
    assert "private-key" not in caplog.text
