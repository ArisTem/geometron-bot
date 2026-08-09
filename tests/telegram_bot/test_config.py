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
