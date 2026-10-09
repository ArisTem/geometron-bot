import asyncio
import sqlite3
from contextlib import closing
from datetime import UTC, datetime

import pytest

from geometron_bot.telegram_bot import preferences
from geometron_bot.telegram_bot.config import ConfigurationError, PreferencesConfig
from geometron_bot.telegram_bot.preferences import UserPreferences
from geometron_bot.telegram_bot.statistics import UsageStatistics


def store_at(path, key="preferences-secret"):
    return UserPreferences(PreferencesConfig(path, key))


def preference_rows(path):
    with closing(sqlite3.connect(path)) as connection:
        return connection.execute(
            "SELECT user_digest, language FROM user_preferences ORDER BY user_digest"
        ).fetchall()


def test_initialize_and_auto_reads_leave_database_empty(tmp_path):
    path = tmp_path / "preferences.sqlite3"
    store = store_at(path)
    store.initialize()
    store.initialize()

    assert store.get_language(123456789) is None
    assert store.get_language(987654321) is None
    assert preference_rows(path) == []
    with closing(sqlite3.connect(path)) as connection:
        assert connection.execute(
            "SELECT name FROM sqlite_schema WHERE type = 'table'"
        ).fetchall() == [("user_preferences",)]
        assert [
            column[1]
            for column in connection.execute("PRAGMA table_info(user_preferences)")
        ] == ["user_digest", "language"]


def test_set_reset_and_restart_preserve_only_manual_choices(tmp_path):
    path = tmp_path / "preferences.sqlite3"
    store = store_at(path)
    store.initialize()
    store.set_language(123456789, "ru")
    store.set_language(123456789, "ru")
    store.set_language(987654321, "en")
    assert store.get_language(123456789) == "ru"
    assert store.get_language(987654321) == "en"
    assert len(preference_rows(path)) == 2

    restarted = store_at(path)
    restarted.initialize()
    assert restarted.get_language(123456789) == "ru"
    restarted.set_language(123456789, "en")
    assert store.get_language(123456789) == "en"
    assert len(preference_rows(path)) == 2

    restarted.reset_language(123456789)
    restarted.reset_language(123456789)
    restarted.reset_language(999)
    assert store.get_language(123456789) is None
    assert restarted.get_language(987654321) == "en"
    assert len(preference_rows(path)) == 1
    restarted.reset_language(987654321)
    assert preference_rows(path) == []


def test_hmac_uses_literal_utf8_key_and_preferences_domain(tmp_path):
    path = tmp_path / "preferences.sqlite3"
    store = store_at(path, " 0123456789abcdef ")
    store.initialize()
    store.set_language(123456789, "ru")
    assert preference_rows(path) == [
        ("75240d608ba682714649fee13349fa33cdbd6b2be5b59e09c511f9405396012b", "ru")
    ]


def test_digests_differ_for_users_keys_and_statistics(tmp_path):
    path = tmp_path / "preferences.sqlite3"
    stats_path = tmp_path / "stats.sqlite3"
    store = store_at(path, "shared-test-key")
    store.initialize()
    store.set_language(123456789, "ru")
    store.set_language(987654321, "en")
    digests = {digest for digest, _ in preference_rows(path)}
    assert len(digests) == 2
    assert all(
        len(digest) == 64 and set(digest) <= set("0123456789abcdef")
        for digest in digests
    )

    # Even the same key cannot directly join the two purposes by digest equality.
    statistics = UsageStatistics(stats_path, "shared-test-key")
    statistics.initialize()
    statistics.record(123456789, datetime(2026, 1, 1, tzinfo=UTC))
    with closing(sqlite3.connect(stats_path)) as connection:
        stats_digest = connection.execute(
            "SELECT user_digest FROM daily_activity"
        ).fetchone()[0]
    assert stats_digest not in digests

    changed_key = store_at(path, "another-key")
    changed_key.initialize()
    assert changed_key.get_language(123456789) is None
    changed_key.set_language(123456789, "ru")
    assert len(preference_rows(path)) == 3
    assert len({digest for digest, _ in preference_rows(path)}) == 3
    assert store.get_language(123456789) == "ru"


@pytest.mark.parametrize("language", ["auto", "de", ""])
def test_unsupported_manual_choices_do_not_change_data(tmp_path, language):
    path = tmp_path / "preferences.sqlite3"
    store = store_at(path)
    store.initialize()
    store.set_language(1, "ru")
    with pytest.raises(ValueError, match="Only ru and en"):
        store.set_language(1, language)
    assert store.get_language(1) == "ru"
    assert len(preference_rows(path)) == 1


def test_initialization_fails_for_missing_parent_and_invalid_files(tmp_path):
    missing = tmp_path / "missing" / "preferences.sqlite3"
    with pytest.raises(ConfigurationError, match="parent directory"):
        store_at(missing).initialize()
    assert not missing.parent.exists()

    invalid = tmp_path / "invalid.sqlite3"
    invalid.write_bytes(b"not a SQLite database")
    with pytest.raises(ConfigurationError, match="cannot be opened"):
        store_at(invalid).initialize()
    assert invalid.read_bytes() == b"not a SQLite database"

    with pytest.raises(ConfigurationError, match="cannot be opened"):
        store_at(tmp_path).initialize()


@pytest.mark.parametrize(
    "schema",
    [
        "user_digest TEXT NOT NULL, language TEXT NOT NULL CHECK (language IN ('ru', 'en'))",
        "user_digest TEXT PRIMARY KEY NOT NULL, language TEXT CHECK (language IN ('ru', 'en'))",
        "user_digest TEXT PRIMARY KEY NOT NULL, language TEXT NOT NULL CHECK (language IN ('ru', 'en')), user_id INTEGER",
        "user_digest TEXT PRIMARY KEY NOT NULL, language TEXT NOT NULL UNIQUE CHECK (language IN ('ru', 'en'))",
    ],
    ids=["missing_primary_key", "nullable_language", "extra_column", "unique_language"],
)
def test_initialization_rejects_incompatible_schema_without_leaving_probe_rows(
    tmp_path, schema
):
    path = tmp_path / "preferences.sqlite3"
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute(f"CREATE TABLE user_preferences ({schema})")
    with pytest.raises(ConfigurationError, match="PREFS_DB_PATH"):
        store_at(path).initialize()
    assert preference_rows(path) == []


@pytest.mark.parametrize("constraint", ["", "CHECK (language IN ('ru', 'en', 'es'))"])
def test_existing_permissive_schema_rejects_unsupported_stored_language(
    tmp_path, constraint
):
    path = tmp_path / "preferences.sqlite3"
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute(
            "CREATE TABLE user_preferences (user_digest TEXT PRIMARY KEY NOT NULL, "
            f"language TEXT NOT NULL {constraint})"
        )
    store = store_at(path)
    store.initialize()
    assert preference_rows(path) == []
    store.set_language(1, "ru")
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute("UPDATE user_preferences SET language = 'es'")
    before = preference_rows(path)
    with pytest.raises(sqlite3.DatabaseError, match="Unsupported language"):
        store.get_language(1)
    with pytest.raises(ConfigurationError, match="unsupported language"):
        store.initialize()
    assert preference_rows(path) == before


def test_database_constraints_reject_invalid_direct_writes(tmp_path):
    path = tmp_path / "preferences.sqlite3"
    store_at(path).initialize()
    with closing(sqlite3.connect(path)) as connection, connection:
        for digest, language in [(None, "ru"), ("digest", None), ("digest", "auto")]:
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO user_preferences (user_digest, language) VALUES (?, ?)",
                    (digest, language),
                )
        connection.execute(
            "INSERT INTO user_preferences (user_digest, language) VALUES (?, ?)",
            ("digest", "ru"),
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO user_preferences (user_digest, language) VALUES (?, ?)",
                ("digest", "en"),
            )
    assert preference_rows(path) == [("digest", "ru")]


def test_statistics_database_is_rejected_by_its_schema(tmp_path):
    stats_path = tmp_path / "stats.sqlite3"
    statistics = UsageStatistics(stats_path, "stats-secret")
    statistics.initialize()
    statistics.record(1, datetime(2026, 1, 1, tzinfo=UTC))
    before = stats_path.read_bytes()
    with pytest.raises(ConfigurationError, match="unexpected database schema"):
        store_at(stats_path).initialize()
    assert stats_path.read_bytes() == before


@pytest.mark.parametrize("operation", ["initialize", "get", "set", "reset"])
def test_locked_database_fails_and_retains_state_after_recovery(
    tmp_path, monkeypatch, operation
):
    monkeypatch.setattr(preferences, "SQLITE_TIMEOUT", 0.02)
    path = tmp_path / "preferences.sqlite3"
    store = store_at(path)
    store.initialize()
    store.set_language(1, "ru")
    callbacks = {
        "initialize": store.initialize,
        "get": lambda: store.get_language(1),
        "set": lambda: store.set_language(1, "en"),
        "reset": lambda: store.reset_language(1),
    }
    expected = (
        ConfigurationError if operation == "initialize" else sqlite3.OperationalError
    )
    with closing(sqlite3.connect(path)) as locked:
        locked.execute("BEGIN EXCLUSIVE")
        with pytest.raises(expected):
            callbacks[operation]()
        locked.rollback()
    assert store.get_language(1) == "ru"


def test_read_only_database_fails_initialization_and_writes(tmp_path, monkeypatch):
    path = tmp_path / "preferences.sqlite3"
    store = store_at(path)
    store.initialize()
    store.set_language(1, "ru")
    monkeypatch.setattr(
        store,
        "_connect",
        lambda **kwargs: sqlite3.connect(path.as_uri() + "?mode=ro", uri=True),
    )
    assert store.get_language(1) == "ru"
    with pytest.raises(ConfigurationError, match="cannot be opened"):
        store.initialize()
    for callback in [
        lambda: store.set_language(1, "en"),
        lambda: store.reset_language(1),
    ]:
        with pytest.raises(sqlite3.OperationalError):
            callback()
    assert preference_rows(path)[0][1] == "ru"


@pytest.mark.parametrize("operation", ["set", "reset"])
def test_failed_statement_rolls_back_partial_changes(tmp_path, operation):
    path = tmp_path / "preferences.sqlite3"
    store = store_at(path)
    store.initialize()
    if operation == "reset":
        store.set_language(1, "ru")
    before = preference_rows(path)
    event = "INSERT" if operation == "set" else "DELETE"
    with closing(sqlite3.connect(path)) as connection, connection:
        # FAIL leaves the statement's earlier changes pending in the transaction.
        connection.execute(
            f"CREATE TRIGGER fail_write AFTER {event} ON user_preferences "
            "BEGIN SELECT RAISE(FAIL, 'temporary write failure'); END"
        )
    with pytest.raises(sqlite3.IntegrityError, match="temporary write failure"):
        if operation == "set":
            store.set_language(1, "en")
        else:
            store.reset_language(1)
    assert preference_rows(path) == before


@pytest.mark.parametrize("operation", ["get", "set", "reset"])
def test_removed_database_is_not_recreated_by_runtime_operations(tmp_path, operation):
    path = tmp_path / "preferences.sqlite3"
    store = store_at(path)
    store.initialize()
    path.unlink()
    callbacks = {
        "get": lambda: store.get_language(1),
        "set": lambda: store.set_language(1, "ru"),
        "reset": lambda: store.reset_language(1),
    }
    with pytest.raises(sqlite3.OperationalError):
        callbacks[operation]()
    assert not path.exists()


def test_relative_path_remains_stable_after_initialization(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "preferences.sqlite3"
    store = store_at(path.relative_to(tmp_path))
    store.initialize()
    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.chdir(other)
    store.set_language(1, "ru")
    assert store.get_language(1) == "ru"
    assert not (other / "preferences.sqlite3").exists()


def test_operations_work_in_separate_worker_threads(tmp_path):
    path = tmp_path / "preferences.sqlite3"
    store = store_at(path)

    async def run():
        await asyncio.to_thread(store.initialize)
        await asyncio.gather(
            asyncio.to_thread(store.set_language, 1, "ru"),
            asyncio.to_thread(store.set_language, 2, "en"),
        )
        assert await asyncio.gather(
            asyncio.to_thread(store.get_language, 1),
            asyncio.to_thread(store.get_language, 2),
        ) == ["ru", "en"]
        await asyncio.gather(
            asyncio.to_thread(store.reset_language, 1),
            asyncio.to_thread(store.reset_language, 2),
        )

    asyncio.run(run())
    assert preference_rows(path) == []
