import asyncio
from datetime import UTC, datetime
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from telegram import Chat, Message, MessageEntity, Update, User
from telegram.ext import CommandHandler, ExtBot, TypeHandler

from geometron_bot.generation.service import (
    FractalTreeGenerationService,
    LissajousGenerationService,
    SpirographGenerationService,
)
from geometron_bot.telegram_bot import handlers
from geometron_bot.telegram_bot.app import create_application, set_bot_commands
from geometron_bot.telegram_bot.config import Config
from geometron_bot.telegram_bot.handlers import (
    COMMANDS,
    FRACTAL_TREE_SERVICE_KEY,
    LISSAJOUS_SERVICE_KEY,
    SPIROGRAPH_SERVICE_KEY,
)
from geometron_bot.telegram_bot.localization import tr
from geometron_bot.telegram_bot.statistics import STATISTICS_KEY, track_usage


def test_application_registers_all_commands() -> None:
    lissajous_service = LissajousGenerationService()
    spirograph_service = SpirographGenerationService()
    fractal_tree_service = FractalTreeGenerationService()

    application = create_application(
        Config(telegram_bot_token="123:test-token"),
        lissajous_service=lissajous_service,
        spirograph_service=spirograph_service,
        fractal_tree_service=fractal_tree_service,
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
    assert application.bot_data[LISSAJOUS_SERVICE_KEY] is lissajous_service
    assert application.bot_data[SPIROGRAPH_SERVICE_KEY] is spirograph_service
    assert application.bot_data[FRACTAL_TREE_SERVICE_KEY] is fractal_tree_service
    assert "lissajous" in registered_commands
    assert "spirograph" in registered_commands
    assert "fractal_tree" in registered_commands
    assert "random" in registered_commands
    assert application.post_init is set_bot_commands
    assert -1 not in application.handlers


def test_application_initializes_statistics_before_command_handlers(tmp_path) -> None:
    db_path = tmp_path / "stats.sqlite3"

    application = create_application(Config("123:test-token", db_path, "secret"))

    assert db_path.is_file()
    assert STATISTICS_KEY in application.bot_data
    assert len(application.handlers[-1]) == 1
    handler = application.handlers[-1][0]
    assert isinstance(handler, TypeHandler)
    assert handler.callback is track_usage
    assert all(
        isinstance(command_handler, CommandHandler)
        for command_handler in application.handlers[0]
    )


@pytest.mark.parametrize(
    ("language", "chat_type"),
    [("ru", Chat.PRIVATE), ("en", Chat.GROUP)],
)
def test_background_jobs_keep_updates_responsive_and_shutdown_waits(
    monkeypatch, language, chat_type,
) -> None:
    async def run() -> None:
        async def initialize_bot(bot):
            bot._bot_user = User(
                999, "Geometron", is_bot=True, username="geometron_bot"
            )

        monkeypatch.setattr(ExtBot, "initialize", initialize_bot)
        started = asyncio.Event()
        finish = asyncio.Event()
        help_sent = asyncio.Event()
        replies = []
        status = SimpleNamespace(edit_text=AsyncMock(), delete=AsyncMock())

        async def reply_text(message, text, **kwargs):
            replies.append((message.message_id, text))
            if message.text == "/help":
                help_sent.set()
            return status

        async def to_thread(generate):
            started.set()
            await finish.wait()
            return generate()

        monkeypatch.setattr(Message, "reply_text", reply_text)
        send_photo = AsyncMock()
        monkeypatch.setattr(Message, "reply_photo", send_photo)
        monkeypatch.setattr(handlers.asyncio, "to_thread", to_thread)
        service = SimpleNamespace(
            generate=Mock(
                return_value=SimpleNamespace(image=BytesIO(b"PNG"), seed=12345)
            )
        )
        application = create_application(
            Config("123:test-token", max_concurrent_generations=1),
            lissajous_service=service,
        )

        def command_update(message_id, user_id, command, chat_id):
            message = Message(
                message_id=message_id,
                date=datetime.now(UTC),
                chat=Chat(chat_id if chat_type == Chat.PRIVATE else -chat_id, chat_type),
                from_user=User(user_id, "User", is_bot=False, language_code=language),
                text=command,
                entities=[MessageEntity(MessageEntity.BOT_COMMAND, 0, len(command))],
            )
            message.set_bot(application.bot)
            return Update(message_id, message=message)

        await application.initialize()
        await application.start()
        stopping = None
        try:
            assert application.concurrent_updates == 1
            await application.update_queue.put(command_update(1, 1, "/lissajous", 1))
            await asyncio.wait_for(started.wait(), timeout=2)
            # Repeating from another chat still uses the same user's active job.
            await application.update_queue.put(command_update(2, 1, "/random", 10))
            await application.update_queue.put(command_update(3, 2, "/fractal_tree", 2))
            await application.update_queue.put(command_update(4, 1, "/help", 1))
            await asyncio.wait_for(help_sent.wait(), timeout=2)

            assert (1, tr(language, "generation.started")) in replies
            assert (2, tr(language, "generation.busy")) in replies
            assert (3, tr(language, "generation.capacity")) in replies
            assert (4, handlers.build_help_text(language)) in replies
            service.generate.assert_not_called()
            send_photo.assert_not_awaited()

            await asyncio.wait_for(application.update_queue.join(), timeout=2)
            stopping = asyncio.create_task(application.stop())
            # Let stop() enqueue its stop signal, then wait for it to be consumed.
            await asyncio.sleep(0)
            await asyncio.wait_for(application.update_queue.join(), timeout=2)
            await asyncio.sleep(0)
            # Only the unfinished generation should now be holding up shutdown.
            assert not stopping.done()
            finish.set()
            await asyncio.wait_for(stopping, timeout=2)
            service.generate.assert_called_once_with()
            send_photo.assert_awaited_once()
            status.delete.assert_awaited_once()
        finally:
            finish.set()
            if stopping is not None:
                await stopping
            elif application.running:
                await application.stop()
            await application.shutdown()

    asyncio.run(run())
