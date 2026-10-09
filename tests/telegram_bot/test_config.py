from pathlib import Path

import pytest

from geometron_bot.telegram_bot.config import (
    Config,
    ConfigurationError,
    PreferencesConfig,
    load_config,
)


@pytest.fixture(autouse=True)
def config_environment(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("PREFS_DB_PATH", "data/preferences.sqlite3")
    monkeypatch.setenv("PREFS_HMAC_KEY", "preferences-secret")
    monkeypatch.delenv("STATS_DB_PATH", raising=False)
    monkeypatch.delenv("STATS_HMAC_KEY", raising=False)
    monkeypatch.delenv("MAX_CONCURRENT_GENERATIONS", raising=False)


def test_load_config_reads_token_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "custom-token")

    config = load_config(env_file=None)

    assert config.telegram_bot_token == "custom-token"


def test_load_config_rejects_missing_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

    with pytest.raises(ConfigurationError, match="TELEGRAM_BOT_TOKEN is not set"):
        load_config(env_file=None)


def test_statistics_are_disabled_for_blank_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STATS_DB_PATH", "   ")

    config = load_config(env_file=None)

    assert config.stats_db_path is None
    assert config.stats_hmac_key is None


def test_statistics_configuration_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STATS_DB_PATH", "data/stats.sqlite3")
    monkeypatch.setenv("STATS_HMAC_KEY", "  ")

    with pytest.raises(ConfigurationError, match="STATS_HMAC_KEY is required"):
        load_config(env_file=None)


def test_statistics_configuration_reads_path_and_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STATS_DB_PATH", " data/stats.sqlite3 ")
    monkeypatch.setenv("STATS_HMAC_KEY", "secret")

    config = load_config(env_file=None)

    assert config.stats_db_path == Path("data/stats.sqlite3")
    assert config.stats_hmac_key == "secret"
    assert "secret" not in repr(config)


def test_generation_limit_defaults_to_two() -> None:
    loaded = load_config(env_file=None)
    direct = Config("test-token", preferences=loaded.preferences)

    assert loaded.max_concurrent_generations == direct.max_concurrent_generations == 2


def test_generation_limit_reads_environment(monkeypatch) -> None:
    monkeypatch.setenv("MAX_CONCURRENT_GENERATIONS", " 3 ")

    assert load_config(env_file=None).max_concurrent_generations == 3


@pytest.mark.parametrize("value", ["0", "-1", "", "many", "1.5"])
def test_generation_limit_rejects_invalid_values(monkeypatch, value) -> None:
    monkeypatch.setenv("MAX_CONCURRENT_GENERATIONS", value)

    with pytest.raises(ConfigurationError, match="MAX_CONCURRENT_GENERATIONS"):
        load_config(env_file=None)


def test_config_rejects_nonpositive_generation_limit() -> None:
    with pytest.raises(ConfigurationError, match="MAX_CONCURRENT_GENERATIONS"):
        Config(
            "test-token",
            preferences=PreferencesConfig(Path("data/preferences.sqlite3"), "key"),
            max_concurrent_generations=0,
        )


@pytest.mark.parametrize("value", [None, "", "   "])
def test_preferences_configuration_requires_path(monkeypatch, value) -> None:
    if value is None:
        monkeypatch.delenv("PREFS_DB_PATH", raising=False)
    else:
        monkeypatch.setenv("PREFS_DB_PATH", value)
    with pytest.raises(ConfigurationError, match="PREFS_DB_PATH is required"):
        load_config(env_file=None)


@pytest.mark.parametrize("value", [None, "", "   "])
def test_preferences_configuration_requires_key(monkeypatch, value) -> None:
    if value is None:
        monkeypatch.delenv("PREFS_HMAC_KEY", raising=False)
    else:
        monkeypatch.setenv("PREFS_HMAC_KEY", value)
    with pytest.raises(ConfigurationError, match="PREFS_HMAC_KEY is required"):
        load_config(env_file=None)


def test_preferences_configuration_keeps_literal_secret_private(monkeypatch) -> None:
    secret = " 0123456789abcdef "
    monkeypatch.setenv("PREFS_DB_PATH", " data/preferences.sqlite3 ")
    monkeypatch.setenv("PREFS_HMAC_KEY", secret)

    config = load_config(env_file=None)

    assert config.preferences.db_path == Path("data/preferences.sqlite3")
    assert config.preferences.hmac_key == secret
    assert "0123456789abcdef" not in repr(config)


def test_preferences_configuration_can_load_an_environment_file(tmp_path, monkeypatch):
    monkeypatch.delenv("PREFS_DB_PATH", raising=False)
    monkeypatch.delenv("PREFS_HMAC_KEY", raising=False)
    env_file = tmp_path / "preferences.env"
    env_file.write_text(
        "PREFS_DB_PATH=data/preferences.sqlite3\nPREFS_HMAC_KEY=file-secret\n",
        encoding="utf-8",
    )
    config = load_config(env_file=env_file)
    assert config.preferences.db_path == Path("data/preferences.sqlite3")
    assert config.preferences.hmac_key == "file-secret"


def test_preferences_configuration_rejects_blank_direct_key(tmp_path) -> None:
    with pytest.raises(ConfigurationError, match="PREFS_HMAC_KEY"):
        PreferencesConfig(tmp_path / "preferences.sqlite3", "   ")
