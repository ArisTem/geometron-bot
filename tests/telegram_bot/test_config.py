from pathlib import Path

import pytest

from geometron_bot.telegram_bot.config import Config, ConfigurationError, load_config


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


def test_generation_limit_defaults_to_two(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.delenv("MAX_CONCURRENT_GENERATIONS", raising=False)

    loaded = load_config(env_file=None)
    direct = Config("test-token")

    assert loaded.max_concurrent_generations == direct.max_concurrent_generations == 2


def test_generation_limit_reads_environment(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("MAX_CONCURRENT_GENERATIONS", " 3 ")

    assert load_config(env_file=None).max_concurrent_generations == 3


@pytest.mark.parametrize("value", ["0", "-1", "", "many", "1.5"])
def test_generation_limit_rejects_invalid_values(monkeypatch, value) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("MAX_CONCURRENT_GENERATIONS", value)

    with pytest.raises(ConfigurationError, match="MAX_CONCURRENT_GENERATIONS"):
        load_config(env_file=None)


def test_config_rejects_nonpositive_generation_limit() -> None:
    with pytest.raises(ConfigurationError, match="MAX_CONCURRENT_GENERATIONS"):
        Config("test-token", max_concurrent_generations=0)
