from pathlib import Path

import pytest

from geometron_bot.telegram_bot.config import ConfigurationError, load_config


def test_load_config_reads_token_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")

    config = load_config(env_file=None)

    assert config.telegram_bot_token == "test-token"


def test_load_config_rejects_missing_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

    with pytest.raises(ConfigurationError, match="TELEGRAM_BOT_TOKEN is not set"):
        load_config(env_file=None)


def test_statistics_are_disabled_for_blank_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("STATS_DB_PATH", "   ")
    monkeypatch.delenv("STATS_HMAC_KEY", raising=False)

    config = load_config(env_file=None)

    assert config.stats_db_path is None
    assert config.stats_hmac_key is None


def test_statistics_configuration_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("STATS_DB_PATH", "data/stats.sqlite3")
    monkeypatch.setenv("STATS_HMAC_KEY", "  ")

    with pytest.raises(ConfigurationError, match="STATS_HMAC_KEY is required"):
        load_config(env_file=None)


def test_statistics_configuration_reads_path_and_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("STATS_DB_PATH", " data/stats.sqlite3 ")
    monkeypatch.setenv("STATS_HMAC_KEY", "secret")

    config = load_config(env_file=None)

    assert config.stats_db_path == Path("data/stats.sqlite3")
    assert config.stats_hmac_key == "secret"
    assert "secret" not in repr(config)
