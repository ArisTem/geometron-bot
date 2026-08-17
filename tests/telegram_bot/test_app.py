import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from telegram.ext import CommandHandler

from geometron_bot.generation.service import LissajousGenerationService
from geometron_bot.telegram_bot.app import create_application, set_bot_commands
from geometron_bot.telegram_bot.config import Config
from geometron_bot.telegram_bot.handlers import (
    COMMANDS,
    LISSAJOUS_SERVICE_KEY,
    PUBLIC_COMMANDS,
)


def test_application_registers_all_commands() -> None:
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
    registered_commands = {
        command_name: handler.callback
        for handler in command_handlers
        for command_name in handler.commands
    }

    assert registered_commands == {
        command.name: command.callback for command in COMMANDS
    }
    assert application.bot_data[LISSAJOUS_SERVICE_KEY] is service
    assert application.post_init is set_bot_commands


def test_set_bot_commands_publishes_only_public_commands() -> None:
    bot = SimpleNamespace(set_my_commands=AsyncMock())

    asyncio.run(set_bot_commands(SimpleNamespace(bot=bot)))

    bot.set_my_commands.assert_awaited_once()
    published_commands = bot.set_my_commands.await_args.args[0]
    assert [
        (command.command, command.description) for command in published_commands
    ] == [
        (command.name, command.description) for command in PUBLIC_COMMANDS
    ]
