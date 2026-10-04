import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_MAX_CONCURRENT_GENERATIONS = 2


class ConfigurationError(RuntimeError):
    """Raised when the application configuration is invalid."""


@dataclass(frozen=True, slots=True)
class Config:
    telegram_bot_token: str
    stats_db_path: Path | None = None
    stats_hmac_key: str | None = field(default=None, repr=False)
    max_concurrent_generations: int = DEFAULT_MAX_CONCURRENT_GENERATIONS

    def __post_init__(self) -> None:
        if self.max_concurrent_generations < 1:
            raise ConfigurationError("MAX_CONCURRENT_GENERATIONS must be positive.")


def load_config(env_file: str | Path | None = ".env") -> Config:
    if env_file is not None:
        load_dotenv(dotenv_path=env_file)

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise ConfigurationError(
            "TELEGRAM_BOT_TOKEN is not set. Copy .env.example to .env and "
            "provide a bot token."
        )

    stats_db_path_value = os.getenv("STATS_DB_PATH", "").strip()
    stats_db_path = Path(stats_db_path_value) if stats_db_path_value else None
    stats_hmac_key = None
    if stats_db_path is not None:
        stats_hmac_key = os.getenv("STATS_HMAC_KEY", "").strip()
        if not stats_hmac_key:
            raise ConfigurationError(
                "STATS_HMAC_KEY is required when STATS_DB_PATH is set."
            )

    try:
        max_concurrent_generations = int(
            os.getenv(
                "MAX_CONCURRENT_GENERATIONS", str(DEFAULT_MAX_CONCURRENT_GENERATIONS)
            ).strip()
        )
    except ValueError as error:
        raise ConfigurationError(
            "MAX_CONCURRENT_GENERATIONS must be a positive integer."
        ) from error

    return Config(
        telegram_bot_token=token,
        stats_db_path=stats_db_path,
        stats_hmac_key=stats_hmac_key,
        max_concurrent_generations=max_concurrent_generations,
    )
