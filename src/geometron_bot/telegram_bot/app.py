from telegram.ext import Application, CommandHandler

from geometron_bot.generation.service import LissajousGenerationService
from geometron_bot.telegram_bot.config import Config
from geometron_bot.telegram_bot.handlers import (
    LISSAJOUS_SERVICE_KEY,
    handle_error,
    lissajous,
    ping,
)


def create_application(
    config: Config,
    lissajous_service: LissajousGenerationService | None = None,
) -> Application:
    application = Application.builder().token(config.telegram_bot_token).build()
    application.bot_data[LISSAJOUS_SERVICE_KEY] = (
        lissajous_service
        if lissajous_service is not None
        else LissajousGenerationService()
    )
    application.add_handler(CommandHandler("ping", ping))
    application.add_handler(CommandHandler("lissajous", lissajous))
    application.add_error_handler(handle_error)
    return application
