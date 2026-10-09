from telegram import BotCommand, BotCommandScopeDefault, Update
from telegram.ext import Application, CommandHandler, TypeHandler

from geometron_bot.generation.service import (
    FractalTreeGenerationService,
    LissajousGenerationService,
    SpirographGenerationService,
)
from geometron_bot.telegram_bot.config import Config, ConfigurationError
from geometron_bot.telegram_bot.generation_jobs import (
    GENERATION_JOBS_KEY,
    GenerationJobs,
)
from geometron_bot.telegram_bot.handlers import (
    COMMANDS,
    FRACTAL_TREE_SERVICE_KEY,
    LISSAJOUS_SERVICE_KEY,
    PUBLIC_COMMANDS,
    SPIROGRAPH_SERVICE_KEY,
    handle_error,
)
from geometron_bot.telegram_bot.languages import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES
from geometron_bot.telegram_bot.localization import initialize_localization, tr
from geometron_bot.telegram_bot.preferences import UserPreferences
from geometron_bot.telegram_bot.statistics import (
    STATISTICS_KEY,
    UsageStatistics,
    track_usage,
)


async def set_bot_commands(application: Application) -> None:
    for language_code in ("", *SUPPORTED_LANGUAGES):
        language = language_code or DEFAULT_LANGUAGE
        await application.bot.set_my_commands(
            [
                BotCommand(command.name, tr(language, command.description_key))
                for command in PUBLIC_COMMANDS
            ],
            scope=BotCommandScopeDefault(),
            language_code=language_code,
        )


def _check_database_paths(config: Config) -> None:
    """Reject shared database files before initializing either store."""
    if config.stats_db_path is None:
        return
    try:
        prefs_path = config.preferences.db_path.resolve()
        stats_path = config.stats_db_path.resolve()
        if prefs_path == stats_path or (
            prefs_path.exists() and stats_path.exists() and prefs_path.samefile(stats_path)
        ):
            raise ConfigurationError(
                "PREFS_DB_PATH must be separate from STATS_DB_PATH."
            )
    except (OSError, ValueError) as error:
        raise ConfigurationError("Database paths cannot be resolved or compared.") from error


def create_application(
    config: Config,
    lissajous_service: LissajousGenerationService | None = None,
    spirograph_service: SpirographGenerationService | None = None,
    fractal_tree_service: FractalTreeGenerationService | None = None,
) -> Application:
    initialize_localization()
    _check_database_paths(config)
    preferences = UserPreferences(config.preferences)
    preferences.initialize()
    statistics = None
    if config.stats_db_path is not None:
        if not config.stats_hmac_key:
            raise ConfigurationError(
                "STATS_HMAC_KEY is required when STATS_DB_PATH is set."
            )
        statistics = UsageStatistics(config.stats_db_path, config.stats_hmac_key)
        statistics.initialize()

    application = (
        Application.builder()
        .token(config.telegram_bot_token)
        .post_init(set_bot_commands)
        .build()
    )
    application.bot_data[GENERATION_JOBS_KEY] = GenerationJobs(
        config.max_concurrent_generations
    )
    application.bot_data[LISSAJOUS_SERVICE_KEY] = (
        lissajous_service
        if lissajous_service is not None
        else LissajousGenerationService()
    )
    application.bot_data[SPIROGRAPH_SERVICE_KEY] = (
        spirograph_service
        if spirograph_service is not None
        else SpirographGenerationService()
    )
    application.bot_data[FRACTAL_TREE_SERVICE_KEY] = (
        fractal_tree_service
        if fractal_tree_service is not None
        else FractalTreeGenerationService()
    )
    if statistics is not None:
        application.bot_data[STATISTICS_KEY] = statistics
        application.add_handler(TypeHandler(Update, track_usage), group=-1)
    for command in COMMANDS:
        application.add_handler(CommandHandler(command.name, command.callback))
    application.add_error_handler(handle_error)
    return application
