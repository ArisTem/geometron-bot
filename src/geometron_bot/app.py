from telegram.ext import Application, CommandHandler

from geometron_bot.config import Config
from geometron_bot.handlers import handle_error, ping


def create_application(config: Config) -> Application:
    application = Application.builder().token(config.telegram_bot_token).build()
    application.add_handler(CommandHandler("ping", ping))
    application.add_error_handler(handle_error)
    return application
