from telegram.ext import CommandHandler

from geometron_bot.generation.service import LissajousGenerationService
from geometron_bot.telegram_bot.app import create_application
from geometron_bot.telegram_bot.config import Config
from geometron_bot.telegram_bot.handlers import LISSAJOUS_SERVICE_KEY, lissajous


def test_application_registers_lissajous_command() -> None:
    service = LissajousGenerationService()

    application = create_application(
        Config(telegram_bot_token="123:test-token"),
        lissajous_service=service,
    )

    command_handlers = [
        handler
        for handlers in application.handlers.values()
        for handler in handlers
        if isinstance(handler, CommandHandler)
    ]
    matching_handlers = [
        handler for handler in command_handlers if "lissajous" in handler.commands
    ]

    assert len(matching_handlers) == 1
    assert matching_handlers[0].callback is lissajous
    assert application.bot_data[LISSAJOUS_SERVICE_KEY] is service
