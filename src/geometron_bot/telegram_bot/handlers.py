import asyncio
import logging
import secrets
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from io import BytesIO
from time import perf_counter
from typing import Protocol

from telegram import (
    BotCommand,
    CallbackQuery,
    Chat,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputFile,
    Message,
    Update,
)
from telegram.error import BadRequest, TelegramError
from telegram.ext import ContextTypes

from geometron_bot.generation.service import (
    FractalTreeGenerationService,
    LissajousGenerationService,
    SpirographGenerationService,
)
from geometron_bot.telegram_bot.generation_jobs import (
    GENERATION_JOBS_KEY,
    GenerationJobs,
    GenerationRejection,
)
from geometron_bot.telegram_bot.language_settings import (
    LANGUAGE_SETTINGS_KEY,
    LanguageSettings,
    ResolvedLanguage,
    get_resolved_language,
)
from geometron_bot.telegram_bot.localization import get_telegram_language, tr

logger = logging.getLogger(__name__)

LISSAJOUS_SERVICE_KEY = "lissajous_generation_service"
SPIROGRAPH_SERVICE_KEY = "spirograph_generation_service"
FRACTAL_TREE_SERVICE_KEY = "fractal_tree_generation_service"


class ImageGenerationResult(Protocol):
    @property
    def image(self) -> BytesIO: ...

    @property
    def seed(self) -> int: ...


@dataclass(frozen=True, slots=True)
class CommandSpec:
    name: str
    description_key: str
    callback: Callable[..., Awaitable[None]]
    is_public: bool = True


def build_help_text(language: str) -> str:
    command_lines = [
        tr(
            language,
            "help.command",
            command=command.name,
            description=tr(language, command.description_key),
        )
        for command in PUBLIC_COMMANDS
    ]
    return tr(language, "help.text", commands="\n".join(command_lines))


def build_bot_commands(language: str) -> list[BotCommand]:
    return [
        BotCommand(command.name, tr(language, command.description_key))
        for command in PUBLIC_COMMANDS
    ]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is not None:
        language = (await get_resolved_language(update, context)).effective_language
        await update.message.reply_text(
            tr(language, "start.text", help_text=build_help_text(language))
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is not None:
        language = (await get_resolved_language(update, context)).effective_language
        await update.message.reply_text(build_help_text(language))


async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is not None:
        language = (await get_resolved_language(update, context)).effective_language
        await update.message.reply_text(tr(language, "ping.text"))


def build_language_keyboard(language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Русский", callback_data="language:ru"),
                InlineKeyboardButton("English", callback_data="language:en"),
            ],
            [
                InlineKeyboardButton(
                    tr(language, "language.button.auto"), callback_data="language:auto"
                )
            ],
        ]
    )


def language_choice_text(resolved: ResolvedLanguage) -> str:
    if not resolved.preference_available:
        mode = "unavailable"
    elif resolved.manual_language is not None:
        mode = "manual"
    else:
        mode = "auto"
    return tr(
        resolved.effective_language,
        "language.choice",
        language_name=tr(
            resolved.effective_language,
            f"language.name.{resolved.effective_language}",
        ),
        mode=tr(resolved.effective_language, f"language.mode.{mode}"),
    )


async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if message is None or message.chat.type != Chat.PRIVATE:
        return
    resolved = await get_resolved_language(update, context)
    try:
        await message.reply_text(
            language_choice_text(resolved),
            reply_markup=build_language_keyboard(resolved.effective_language),
        )
    except TelegramError as error:
        logger.warning(
            "Could not send language selection | error_type=%s", type(error).__name__
        )


async def _answer_language_callback(
    query: CallbackQuery, text: str | None = None
) -> None:
    try:
        await query.answer(text=text, show_alert=text is not None)
    except TelegramError as error:
        logger.warning(
            "Could not answer language callback | error_type=%s", type(error).__name__
        )


async def _show_language_result(message: Message, text: str, *, language: str) -> None:
    keyboard = build_language_keyboard(language)
    try:
        await message.edit_text(text, reply_markup=keyboard)
        return
    except BadRequest as error:
        if error.message.startswith("Message is not modified"):
            return
        logger.warning(
            "Could not edit language message | error_type=%s", type(error).__name__
        )
    except TelegramError as error:
        logger.warning(
            "Could not edit language message | error_type=%s", type(error).__name__
        )
    try:
        await message.reply_text(text, reply_markup=keyboard)
    except TelegramError as error:
        logger.warning(
            "Could not send language result | error_type=%s", type(error).__name__
        )


async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return
    message = query.message
    choices = {"language:ru": "ru", "language:en": "en", "language:auto": None}
    if (
        not isinstance(query.data, str)
        or query.data not in choices
        or not isinstance(message, Message)
        or message.chat.type != Chat.PRIVATE
        or message.chat.id != query.from_user.id
        or message.from_user is None
        or message.from_user.id != context.bot.id
    ):
        await _answer_language_callback(
            query, tr(get_telegram_language(update), "language.invalid")
        )
        return
    # Acknowledge before any potentially blocking database operation.
    await _answer_language_callback(query)
    settings: LanguageSettings = context.bot_data[LANGUAGE_SETTINGS_KEY]
    previous = await get_resolved_language(update, context)
    manual = choices[query.data]
    if not await settings.save(query.from_user.id, manual):
        await _show_language_result(
            message,
            tr(previous.effective_language, "language.save_error"),
            language=previous.effective_language,
        )
        return
    resolved = ResolvedLanguage(manual or get_telegram_language(update), manual)
    context.resolved_language = resolved
    menu_ok = await settings.sync_menu(context.bot, message.chat.id, manual)
    text = tr(
        resolved.effective_language,
        "language.saved",
        selection=language_choice_text(resolved),
    )
    if not menu_ok:
        text += "\n\n" + tr(resolved.effective_language, "language.menu_error")
    await _show_language_result(message, text, language=resolved.effective_language)


async def _start_image_generation[T: ImageGenerationResult](
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    generate: Callable[[], T],
    *,
    language: str,
    image_name: str,
    filename_prefix: str,
    caption: Callable[[T], str],
) -> None:
    message = update.message
    user = update.effective_user
    if message is None or user is None:
        return

    jobs: GenerationJobs = context.bot_data[GENERATION_JOBS_KEY]
    rejection = jobs.submit(
        user.id,
        context.application,
        update,
        lambda: _generate_and_send_image(
            message,
            generate,
            language=language,
            image_name=image_name,
            filename_prefix=filename_prefix,
            caption=caption,
        ),
    )
    if rejection is not None:
        key = (
            "generation.busy"
            if rejection is GenerationRejection.USER_BUSY
            else "generation.capacity"
        )
        await message.reply_text(tr(language, key))


async def _generate_and_send_image[T: ImageGenerationResult](
    message: Message,
    generate: Callable[[], T],
    *,
    language: str,
    image_name: str,
    filename_prefix: str,
    caption: Callable[[T], str],
) -> None:
    status_message = await message.reply_text(tr(language, "generation.started"))
    started_at = perf_counter()
    try:
        result = await asyncio.to_thread(generate)
    except Exception as error:
        duration_ms = round((perf_counter() - started_at) * 1000)
        logger.exception(
            "%s generation failed | duration_ms=%d | error_type=%s",
            image_name,
            duration_ms,
            type(error).__name__,
        )
        await status_message.edit_text(tr(language, "generation.error"))
        return

    duration_ms = round((perf_counter() - started_at) * 1000)
    logger.info(
        "%s image generated | seed=%d | duration_ms=%d",
        image_name,
        result.seed,
        duration_ms,
    )
    photo = InputFile(result.image, filename=f"{filename_prefix}-{result.seed}.png")
    try:
        await message.reply_photo(photo=photo, caption=caption(result))
    except Exception:
        logger.exception("%s image delivery failed", image_name)
        await status_message.edit_text(tr(language, "generation.error"))
        return

    try:
        await status_message.delete()
    except Exception:
        logger.warning("Could not delete generation status message", exc_info=True)


async def lissajous(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate and send a Lissajous image with its reproducible seed."""
    if update.message is None:
        return

    service: LissajousGenerationService = context.bot_data[LISSAJOUS_SERVICE_KEY]
    language = (await get_resolved_language(update, context)).effective_language
    await _start_image_generation(
        update,
        context,
        service.generate,
        language=language,
        image_name="Lissajous",
        filename_prefix="lissajous",
        caption=lambda result: tr(language, "caption.lissajous", seed=result.seed),
    )


async def spirograph(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate and send one spirograph image with its reproducible seed."""
    if update.message is None:
        return

    service: SpirographGenerationService = context.bot_data[SPIROGRAPH_SERVICE_KEY]
    language = (await get_resolved_language(update, context)).effective_language
    await _start_image_generation(
        update,
        context,
        service.generate,
        language=language,
        image_name="Spirograph",
        filename_prefix="spirograph",
        caption=lambda result: tr(
            language,
            "caption.spirograph.inside"
            if result.parameters.pattern_type == "inside"
            else "caption.spirograph.outside",
            seed=result.seed,
        ),
    )


async def fractal_tree(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate and send a fractal tree with its reproducible seed."""
    if update.message is None:
        return

    service: FractalTreeGenerationService = context.bot_data[FRACTAL_TREE_SERVICE_KEY]
    language = (await get_resolved_language(update, context)).effective_language
    await _start_image_generation(
        update,
        context,
        service.generate,
        language=language,
        image_name="Fractal tree",
        filename_prefix="fractal-tree",
        caption=lambda result: tr(language, "caption.fractal_tree", seed=result.seed),
    )


async def random_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate one image chosen from the registered image commands."""
    if update.message is None:
        return

    command = secrets.choice(IMAGE_COMMANDS)
    await command.callback(update, context)


async def handle_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    del update
    logger.error("Unhandled error while processing an update", exc_info=context.error)


IMAGE_COMMANDS = (
    CommandSpec("lissajous", "command.lissajous", lissajous),
    CommandSpec("spirograph", "command.spirograph", spirograph),
    CommandSpec("fractal_tree", "command.fractal_tree", fractal_tree),
)

COMMANDS = (
    CommandSpec("start", "command.start", start),
    *IMAGE_COMMANDS,
    CommandSpec("random", "command.random", random_image),
    CommandSpec("help", "command.help", help_command),
    CommandSpec("language", "command.language", language_command),
    CommandSpec("ping", "command.ping", ping, is_public=False),
)

PUBLIC_COMMANDS = tuple(command for command in COMMANDS if command.is_public)
