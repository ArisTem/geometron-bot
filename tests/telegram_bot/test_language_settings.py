import asyncio
import sqlite3
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from telegram import BotCommand, BotCommandScopeChat, Chat, Message, Update, User
from telegram.error import TelegramError

from geometron_bot.telegram_bot.language_settings import (
    LANGUAGE_SETTINGS_KEY,
    LanguageSettings,
    ResolvedLanguage,
    get_resolved_language,
    sync_private_menu,
)
from geometron_bot.telegram_bot.preferences import UserPreferences


@pytest.fixture
def environment():
    store = Mock(spec=UserPreferences)
    store.get_language.return_value = None
    commands = [BotCommand("help", "Test command")]
    build_commands = Mock(return_value=commands)
    bot = SimpleNamespace(set_my_commands=AsyncMock(), delete_my_commands=AsyncMock())
    settings = LanguageSettings(store, build_commands)
    return SimpleNamespace(
        store=store,
        commands=commands,
        build_commands=build_commands,
        bot=bot,
        settings=settings,
    )


def new_context(env):
    return SimpleNamespace(bot_data={LANGUAGE_SETTINGS_KEY: env.settings}, bot=env.bot)


def message_update(language="en", *, user_id=1, chat_type=Chat.PRIVATE, chat_id=None):
    message = Message(
        1,
        datetime.now(UTC),
        Chat(user_id if chat_id is None else chat_id, chat_type),
        from_user=User(user_id, "User", is_bot=False, language_code=language),
    )
    return Update(1, message=message)


@pytest.mark.parametrize("manual", [None, "ru"])
def test_resolve_uses_manual_choice_or_telegram_language(environment, manual):
    env = environment
    env.store.get_language.return_value = manual
    assert asyncio.run(env.settings.resolve(message_update("en"))) == ResolvedLanguage(
        manual or "en", manual
    )
    env.store.get_language.assert_called_once_with(1)


def test_resolve_without_user_does_not_read_preferences(environment):
    env = environment
    assert asyncio.run(env.settings.resolve(Update(1))) == ResolvedLanguage(
        "en", preference_available=False
    )
    env.store.get_language.assert_not_called()


def test_read_failure_falls_back_without_writing_or_changing_menu(environment, caplog):
    env = environment
    env.store.get_language.return_value = "ru"
    env.store.get_language.side_effect = sqlite3.OperationalError("private-data")

    async def run():
        update = message_update("en")
        context = new_context(env)
        assert await get_resolved_language(update, context) == ResolvedLanguage(
            "en", preference_available=False
        )
        await sync_private_menu(update, context)
        env.bot.set_my_commands.assert_not_awaited()
        env.bot.delete_my_commands.assert_not_awaited()
        env.store.set_language.assert_not_called()
        env.store.reset_language.assert_not_called()
        env.store.get_language.side_effect = None
        await sync_private_menu(message_update("en"), new_context(env))

    asyncio.run(run())
    assert "OperationalError" in caplog.text
    assert "private-data" not in caplog.text
    env.bot.set_my_commands.assert_awaited_once_with(
        env.commands, scope=BotCommandScopeChat(1), language_code=""
    )


@pytest.mark.parametrize("manual", [None, "ru"])
def test_save_commits_manual_choice_or_resets_to_auto(environment, manual):
    env = environment
    assert asyncio.run(env.settings.save(1, manual)) is True
    if manual is None:
        env.store.reset_language.assert_called_once_with(1)
        env.store.set_language.assert_not_called()
    else:
        env.store.set_language.assert_called_once_with(1, manual)
        env.store.reset_language.assert_not_called()


@pytest.mark.parametrize("manual", [None, "ru"])
def test_save_reports_write_failure(environment, caplog, manual):
    env = environment
    write = env.store.reset_language if manual is None else env.store.set_language
    write.side_effect = sqlite3.OperationalError("private-data")
    assert asyncio.run(env.settings.save(1, manual)) is False
    assert "OperationalError" in caplog.text
    assert "private-data" not in caplog.text


def test_language_is_cached_only_for_the_current_update(environment):
    env = environment
    env.store.get_language.return_value = "ru"

    async def run():
        update = message_update("en")
        context = new_context(env)
        resolved = await get_resolved_language(update, context)
        assert resolved == ResolvedLanguage("ru", "ru")
        assert await get_resolved_language(update, context) is resolved
        env.store.get_language.assert_called_once_with(1)
        env.store.get_language.return_value = "en"
        assert await get_resolved_language(message_update("ru"), new_context(env)) == (
            ResolvedLanguage("en", "en")
        )

    asyncio.run(run())
    assert env.store.get_language.call_count == 2


def test_users_keep_their_distinct_preferences(environment):
    env = environment
    preferences = {1: "ru", 2: "en"}
    env.store.get_language.side_effect = preferences.__getitem__

    async def run():
        for user_id, expected in [(1, "ru"), (2, "en"), (1, "ru")]:
            resolved = await get_resolved_language(
                message_update("de", user_id=user_id), new_context(env)
            )
            assert resolved == ResolvedLanguage(expected, expected)

    asyncio.run(run())


@pytest.mark.parametrize("manual", [None, "ru"])
def test_private_menu_sync_is_cached_until_service_restart(environment, manual):
    env = environment
    env.store.get_language.return_value = manual

    async def run():
        await sync_private_menu(message_update(), new_context(env))
        await sync_private_menu(message_update(), new_context(env))

    asyncio.run(run())
    api_method = (
        env.bot.delete_my_commands if manual is None else env.bot.set_my_commands
    )
    if manual is None:
        api_method.assert_awaited_once_with(
            scope=BotCommandScopeChat(1), language_code=""
        )
        env.bot.set_my_commands.assert_not_awaited()
        env.build_commands.assert_not_called()
    else:
        api_method.assert_awaited_once_with(
            env.commands, scope=BotCommandScopeChat(1), language_code=""
        )
        env.bot.delete_my_commands.assert_not_awaited()
        env.build_commands.assert_called_once_with(manual)
    env.settings = LanguageSettings(env.store, env.build_commands)
    asyncio.run(sync_private_menu(message_update(), new_context(env)))
    assert api_method.await_count == 2


@pytest.mark.parametrize("manual", [None, "ru"])
def test_menu_failure_is_retried_and_only_success_is_cached(
    environment, caplog, manual
):
    env = environment
    api_method = (
        env.bot.delete_my_commands if manual is None else env.bot.set_my_commands
    )
    api_method.side_effect = [TelegramError("private-data"), True]

    async def run():
        assert await env.settings.sync_menu(env.bot, 1, manual) is False
        assert await env.settings.sync_menu(env.bot, 1, manual) is True
        assert await env.settings.sync_menu(env.bot, 1, manual) is True

    asyncio.run(run())
    assert api_method.await_count == 2
    assert "private-data" not in caplog.text


def test_private_menu_follows_changed_preferences(environment):
    env = environment

    async def run():
        await sync_private_menu(message_update(), new_context(env))
        env.store.get_language.return_value = "ru"
        await sync_private_menu(message_update(), new_context(env))

    asyncio.run(run())
    env.bot.delete_my_commands.assert_awaited_once_with(
        scope=BotCommandScopeChat(1), language_code=""
    )
    env.bot.set_my_commands.assert_awaited_once_with(
        env.commands, scope=BotCommandScopeChat(1), language_code=""
    )
    env.build_commands.assert_called_once_with("ru")


@pytest.mark.parametrize(
    "update",
    [
        Update(1),
        message_update(chat_type=Chat.GROUP, chat_id=-100),
        message_update(chat_id=2),
    ],
)
def test_private_menu_ignores_unsupported_updates(environment, update):
    env = environment
    asyncio.run(sync_private_menu(update, new_context(env)))
    env.store.get_language.assert_not_called()
    env.bot.set_my_commands.assert_not_awaited()
    env.bot.delete_my_commands.assert_not_awaited()
