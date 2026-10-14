import asyncio
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from telegram import (
    BotCommandScopeDefault,
    CallbackQuery,
    Chat,
    Message,
    MessageEntity,
    Update,
    User,
)
from telegram.ext import CommandHandler, ExtBot, TypeHandler

from geometron_bot.generation.service import (
    FractalTreeGenerationService,
    LissajousGenerationService,
    SpirographGenerationService,
)
from geometron_bot.telegram_bot import handlers
from geometron_bot.telegram_bot.app import create_application, set_bot_commands
from geometron_bot.telegram_bot.config import (
    Config,
    ConfigurationError,
    PreferencesConfig,
)
from geometron_bot.telegram_bot.handlers import (
    COMMANDS,
    FRACTAL_TREE_SERVICE_KEY,
    LISSAJOUS_SERVICE_KEY,
    PUBLIC_COMMANDS,
    SPIROGRAPH_SERVICE_KEY,
)
from geometron_bot.telegram_bot.language_settings import (
    LANGUAGE_SETTINGS_KEY,
    sync_private_menu,
)
from geometron_bot.telegram_bot.languages import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES
from geometron_bot.telegram_bot.localization import tr
from geometron_bot.telegram_bot.preferences import UserPreferences
from geometron_bot.telegram_bot.statistics import (
    STATISTICS_KEY,
    UsageStatistics,
    track_usage,
)

REAL_TO_THREAD = asyncio.to_thread


@pytest.fixture
def preferences_config(tmp_path):
    return PreferencesConfig(tmp_path / "preferences.sqlite3", "preferences-secret")


@pytest.fixture
def telegram_reply(monkeypatch):
    """Initialize the test bot and stub Telegram calls; return the reply mock."""

    async def initialize_bot(bot):
        bot._bot_user = User(999, "Geometron", is_bot=True, username="geometron_bot")

    reply = AsyncMock()
    monkeypatch.setattr(ExtBot, "initialize", initialize_bot)
    monkeypatch.setattr(Message, "reply_text", reply)
    monkeypatch.setattr(Message, "edit_text", AsyncMock())
    monkeypatch.setattr(CallbackQuery, "answer", AsyncMock())
    monkeypatch.setattr(ExtBot, "set_my_commands", AsyncMock())
    monkeypatch.setattr(ExtBot, "delete_my_commands", AsyncMock())
    return reply


def test_application_registers_all_commands(preferences_config) -> None:
    lissajous_service = LissajousGenerationService()
    spirograph_service = SpirographGenerationService()
    fractal_tree_service = FractalTreeGenerationService()

    application = create_application(
        Config(telegram_bot_token="123:test-token", preferences=preferences_config),
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
    assert application.handlers[1][0].callback is sync_private_menu
    assert LANGUAGE_SETTINGS_KEY in application.bot_data
    assert not any(
        handler.callback is track_usage
        for group in application.handlers.values()
        for handler in group
    )


def test_application_initializes_statistics_before_command_handlers(
    tmp_path, preferences_config
) -> None:
    db_path = tmp_path / "stats.sqlite3"

    application = create_application(
        Config("123:test-token", db_path, "secret", preferences=preferences_config)
    )

    assert db_path.is_file()
    assert STATISTICS_KEY in application.bot_data
    assert len(application.handlers[-1]) == 1
    handler = application.handlers[-1][0]
    assert isinstance(handler, TypeHandler)
    assert handler.callback is track_usage


def test_application_initializes_preferences(preferences_config):
    create_application(Config("123:test-token", preferences=preferences_config))
    with closing(sqlite3.connect(preferences_config.db_path)) as connection:
        assert connection.execute("SELECT * FROM user_preferences").fetchall() == []


def test_global_menus_share_public_command_registry_and_include_language():
    bot = SimpleNamespace(set_my_commands=AsyncMock())
    asyncio.run(set_bot_commands(SimpleNamespace(bot=bot)))
    calls = {
        call.kwargs["language_code"]: call
        for call in bot.set_my_commands.await_args_list
    }
    assert calls.keys() == {"", *SUPPORTED_LANGUAGES}
    for language_code, call in calls.items():
        language = language_code or DEFAULT_LANGUAGE
        assert call.kwargs["scope"] == BotCommandScopeDefault()
        assert [(command.command, command.description) for command in call.args[0]] == [
            (command.name, tr(language, command.description_key))
            for command in PUBLIC_COMMANDS
        ]
        names = {command.command for command in call.args[0]}
        assert "language" in names
        assert "ping" not in names


def test_language_flow_routes_callbacks_and_survives_application_restart(
    telegram_reply, preferences_config
):
    reply = telegram_reply
    config = Config("123:test-token", preferences=preferences_config)

    def command(application, name):
        message = Message(
            1,
            datetime.now(UTC),
            Chat(1, Chat.PRIVATE),
            from_user=User(1, "User", is_bot=False, language_code="en-US"),
            text=name,
            entities=[MessageEntity(MessageEntity.BOT_COMMAND, 0, len(name))],
        )
        message.set_bot(application.bot)
        return Update(1, message=message)

    def callback(application, choice):
        message = Message(
            2, datetime.now(UTC), Chat(1, Chat.PRIVATE), from_user=application.bot.bot
        )
        # Bot.bot is its initialized User instance in PTB.
        message.set_bot(application.bot)
        query = CallbackQuery(
            "query",
            User(1, "User", is_bot=False, language_code="en-US"),
            "instance",
            message=message,
            data=f"language:{choice}",
        )
        query.set_bot(application.bot)
        return Update(2, callback_query=query)

    async def run():
        first = create_application(config)
        await first.initialize()
        try:
            await first.process_update(command(first, "/language"))
            assert reply.await_args.kwargs[
                "reply_markup"
            ] == handlers.build_language_keyboard("en")
            await first.process_update(callback(first, "ru"))
            await first.process_update(command(first, "/help"))
            assert reply.await_args.args[0] == handlers.build_help_text("ru")
        finally:
            await first.shutdown()

        restarted = create_application(config)
        await restarted.initialize()
        try:
            reply.reset_mock()
            await restarted.process_update(command(restarted, "/help"))
            reply.assert_awaited_once_with(handlers.build_help_text("ru"))
            await restarted.process_update(callback(restarted, "auto"))
            await restarted.process_update(command(restarted, "/help"))
            assert reply.await_args.args[0] == handlers.build_help_text("en")
        finally:
            await restarted.shutdown()

    asyncio.run(run())


def test_command_reply_is_sent_while_private_menu_update_is_pending(
    monkeypatch, telegram_reply, preferences_config
):
    async def run():
        monkeypatch.setattr(UserPreferences, "get_language", Mock(return_value="ru"))
        menu_started = asyncio.Event()
        finish_menu = asyncio.Event()

        async def update_menu(bot, *args, **kwargs):
            menu_started.set()
            await finish_menu.wait()

        monkeypatch.setattr(ExtBot, "set_my_commands", update_menu)
        application = create_application(
            Config("123:test-token", preferences=preferences_config)
        )
        message = Message(
            1,
            datetime.now(UTC),
            Chat(1, Chat.PRIVATE),
            from_user=User(1, "User", is_bot=False, language_code="en"),
            text="/help",
            entities=[MessageEntity(MessageEntity.BOT_COMMAND, 0, 5)],
        )
        message.set_bot(application.bot)
        await application.initialize()
        processing = asyncio.create_task(
            application.process_update(Update(1, message=message))
        )
        try:
            await asyncio.wait_for(menu_started.wait(), timeout=2)
            telegram_reply.assert_awaited_once_with(handlers.build_help_text("ru"))
            assert not processing.done()
        finally:
            finish_menu.set()
            await asyncio.wait_for(processing, timeout=2)
            await application.shutdown()

    asyncio.run(run())


@pytest.mark.parametrize("invalid_database", ["missing_parent", "invalid_schema"])
def test_preferences_error_stops_before_statistics_and_telegram(
    tmp_path, monkeypatch, invalid_database
):
    prefs_path = tmp_path / "preferences.sqlite3"
    if invalid_database == "missing_parent":
        prefs_path = tmp_path / "missing" / "preferences.sqlite3"
    else:
        with closing(sqlite3.connect(prefs_path)) as connection, connection:
            connection.execute("CREATE TABLE unrelated (value TEXT)")
    stats_path = tmp_path / "stats.sqlite3"
    application = Mock()
    monkeypatch.setattr("geometron_bot.telegram_bot.app.Application", application)
    with pytest.raises(ConfigurationError, match="PREFS_DB_PATH"):
        create_application(
            Config(
                "123:test-token",
                stats_path,
                "stats-secret",
                preferences=PreferencesConfig(prefs_path, "preferences-secret"),
            )
        )
    application.builder.assert_not_called()
    assert not stats_path.exists()


@pytest.mark.parametrize("existing_store", [None, "statistics", "preferences"])
def test_coincident_paths_fail_before_modifying_databases(tmp_path, existing_store):
    path = tmp_path / "shared.sqlite3"
    if existing_store == "statistics":
        statistics = UsageStatistics(path, "stats-secret")
        statistics.initialize()
        statistics.record(1, datetime(2026, 1, 1, tzinfo=UTC))
    elif existing_store == "preferences":
        preferences = UserPreferences(PreferencesConfig(path, "preferences-secret"))
        preferences.initialize()
        preferences.set_language(1, "ru")
    before = path.read_bytes() if path.exists() else None
    with pytest.raises(ConfigurationError, match="separate from STATS_DB_PATH"):
        create_application(
            Config(
                "123:test-token",
                path,
                "stats-secret",
                preferences=PreferencesConfig(path, "preferences-secret"),
            )
        )
    assert (path.read_bytes() if path.exists() else None) == before


@pytest.mark.parametrize("alias_kind", ["relative", "hardlink"])
def test_database_aliases_fail_before_modifying_statistics(
    tmp_path, monkeypatch, alias_kind
):
    stats_path = tmp_path / "stats.sqlite3"
    statistics = UsageStatistics(stats_path, "stats-secret")
    statistics.initialize()
    statistics.record(1, datetime(2026, 1, 1, tzinfo=UTC))
    before = stats_path.read_bytes()
    if alias_kind == "relative":
        monkeypatch.chdir(tmp_path)
        alias = stats_path.relative_to(tmp_path)
    else:
        alias = tmp_path / "hardlink.sqlite3"
        alias.hardlink_to(stats_path)
    with pytest.raises(ConfigurationError, match="separate from STATS_DB_PATH"):
        create_application(
            Config(
                "123:test-token",
                stats_path,
                "stats-secret",
                preferences=PreferencesConfig(alias, "preferences-secret"),
            )
        )
    assert stats_path.read_bytes() == before


def test_background_jobs_keep_updates_responsive_and_shutdown_waits(
    monkeypatch,
    telegram_reply,
    preferences_config,
) -> None:
    language = "ru"

    async def run() -> None:
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

        async def to_thread(generate, *args):
            if args:
                return await REAL_TO_THREAD(generate, *args)
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
            Config(
                "123:test-token",
                preferences=preferences_config,
                max_concurrent_generations=1,
            ),
            lissajous_service=service,
        )

        def command_update(message_id, user_id, command):
            message = Message(
                message_id=message_id,
                date=datetime.now(UTC),
                chat=Chat(user_id, Chat.PRIVATE),
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
            await application.update_queue.put(command_update(1, 1, "/lissajous"))
            await asyncio.wait_for(started.wait(), timeout=2)
            await application.update_queue.put(command_update(2, 1, "/random"))
            await application.update_queue.put(command_update(3, 2, "/fractal_tree"))
            await application.update_queue.put(command_update(4, 1, "/help"))
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
