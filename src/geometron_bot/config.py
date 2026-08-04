import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class ConfigurationError(RuntimeError):
    """Raised when the application configuration is invalid."""


@dataclass(frozen=True, slots=True)
class Config:
    telegram_bot_token: str


def load_config(env_file: str | Path | None = ".env") -> Config:
    if env_file is not None:
        load_dotenv(dotenv_path=env_file)

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise ConfigurationError(
            "TELEGRAM_BOT_TOKEN is not set. Copy .env.example to .env and "
            "provide a bot token."
        )

    return Config(telegram_bot_token=token)
