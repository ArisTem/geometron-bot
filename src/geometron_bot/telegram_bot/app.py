from telegram import BotCommand
from telegram.ext import Application, CommandHandler

from geometron_bot.generation.service import (
    FractalTreeGenerationService,
    LissajousGenerationService,
    SpirographGenerationService,
)
from geometron_bot.telegram_bot.config import Config
from geometron_bot.telegram_bot.handlers import (
    COMMANDS,
    FRACTAL_TREE_SERVICE_KEY,
    LISSAJOUS_SERVICE_KEY,
    PUBLIC_COMMANDS,
    SPIROGRAPH_SERVICE_KEY,
    handle_error,
)


async def set_bot_commands(application: Application) -> None:
    await application.bot.set_my_commands(
        [
            BotCommand(command.name, command.description)
            for command in PUBLIC_COMMANDS
        ]
    )


def create_application(
    config: Config,
    lissajous_service: LissajousGenerationService | None = None,
    spirograph_service: SpirographGenerationService | None = None,
    fractal_tree_service: FractalTreeGenerationService | None = None,
) -> Application:
    application = (
        Application.builder()
        .token(config.telegram_bot_token)
        .post_init(set_bot_commands)
        .build()
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
    for command in COMMANDS:
        application.add_handler(CommandHandler(command.name, command.callback))
    application.add_error_handler(handle_error)
    return application
