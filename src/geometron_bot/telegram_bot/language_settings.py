"""Resolve preferences per update and synchronize private command menus."""

import asyncio
import logging
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass

from telegram import Bot, BotCommand, BotCommandScopeChat, Chat, Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from geometron_bot.telegram_bot.localization import get_telegram_language
from geometron_bot.telegram_bot.preferences import UserPreferences

logger = logging.getLogger(__name__)
LANGUAGE_SETTINGS_KEY = "language_settings"


@dataclass(frozen=True, slots=True)
class ResolvedLanguage:
    """Reply language and manual preference resolved for one update."""

    effective_language: str
    manual_language: str | None = None
    preference_available: bool = True


class LanguageSettings:
    def __init__(
        self,
        preferences: UserPreferences,
        build_commands: Callable[[str], list[BotCommand]],
    ) -> None:
        self._preferences = preferences
        self._build_commands = build_commands
        # Successful menu synchronization only; never used to resolve replies.
        self._synced_menus: dict[int, str | None] = {}

    async def resolve(self, update: Update) -> ResolvedLanguage:
        fallback = get_telegram_language(update)
        user = update.effective_user
        if user is None:
            return ResolvedLanguage(fallback, preference_available=False)
        try:
            manual = await asyncio.to_thread(self._preferences.get_language, user.id)
        except (OSError, ValueError, sqlite3.Error) as error:
            logger.error(
                "Could not read language preference | error_type=%s",
                type(error).__name__,
            )
            return ResolvedLanguage(fallback, preference_available=False)
        return ResolvedLanguage(manual or fallback, manual)

    async def save(self, user_id: int, manual_language: str | None) -> bool:
        """Save a manual language or reset to Auto; report whether it was committed."""
        try:
            if manual_language is None:
                await asyncio.to_thread(self._preferences.reset_language, user_id)
            else:
                await asyncio.to_thread(
                    self._preferences.set_language, user_id, manual_language
                )
        except (OSError, ValueError, sqlite3.Error) as error:
            logger.error(
                "Could not save language preference | error_type=%s",
                type(error).__name__,
            )
            return False
        return True

    async def sync_menu(
        self,
        bot: Bot,
        chat_id: int,
        manual_language: str | None,
    ) -> bool:
        if (
            chat_id in self._synced_menus
            and self._synced_menus[chat_id] == manual_language
        ):
            return True
        self._synced_menus.pop(chat_id, None)
        scope = BotCommandScopeChat(chat_id)
        try:
            if manual_language is None:
                await bot.delete_my_commands(scope=scope, language_code="")
            else:
                await bot.set_my_commands(
                    self._build_commands(manual_language), scope=scope, language_code=""
                )
        except TelegramError as error:
            logger.error(
                "Could not synchronize language menu | error_type=%s",
                type(error).__name__,
            )
            return False
        self._synced_menus[chat_id] = manual_language
        return True


async def get_resolved_language(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> ResolvedLanguage:
    """Resolve once in the context shared by this update's handlers."""
    resolved = getattr(context, "resolved_language", None)
    if resolved is not None:
        return resolved
    settings: LanguageSettings = context.bot_data[LANGUAGE_SETTINGS_KEY]
    resolved = await settings.resolve(update)
    context.resolved_language = resolved
    return resolved


async def sync_private_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Synchronize the private menu after command handlers, also for ordinary messages."""
    message = update.message
    user = update.effective_user
    if (
        message is None
        or user is None
        or message.chat.type != Chat.PRIVATE
        or message.chat.id != user.id
    ):
        return
    resolved = await get_resolved_language(update, context)
    if not resolved.preference_available:
        return
    settings: LanguageSettings = context.bot_data[LANGUAGE_SETTINGS_KEY]
    await settings.sync_menu(context.bot, message.chat.id, resolved.manual_language)
