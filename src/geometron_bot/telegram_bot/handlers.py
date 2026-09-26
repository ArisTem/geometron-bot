import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from io import BytesIO
from time import perf_counter
from typing import Protocol

from telegram import InputFile, Message, Update
from telegram.ext import ContextTypes

from geometron_bot.generation.service import (
    FractalTreeGenerationService,
    LissajousGenerationService,
    SpirographGenerationService,
)

logger = logging.getLogger(__name__)

LISSAJOUS_SERVICE_KEY = "lissajous_generation_service"
SPIROGRAPH_SERVICE_KEY = "spirograph_generation_service"
FRACTAL_TREE_SERVICE_KEY = "fractal_tree_generation_service"
GENERATION_STATUS_TEXT = "Создаю изображение. Это может занять несколько секунд…"
GENERATION_ERROR_TEXT = "Не удалось создать изображение. Попробуйте ещё раз."


class ImageGenerationResult(Protocol):
    @property
    def image(self) -> BytesIO: ...

    @property
    def seed(self) -> int: ...


@dataclass(frozen=True, slots=True)
class CommandSpec:
    name: str
    description: str
    callback: Callable[..., Awaitable[None]]
    is_public: bool = True


def build_help_text() -> str:
    command_lines = [
        f"/{command.name} — {command.description}"
        for command in PUBLIC_COMMANDS
    ]
    return "Доступные команды:\n\n" + "\n".join(command_lines)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    if update.message is not None:
        await update.message.reply_text(
            "Привет! Я Geometron — бот для создания изображений "
            "с помощью математических алгоритмов.\n\n"
            f"{build_help_text()}"
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    if update.message is not None:
        await update.message.reply_text(build_help_text())


async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    if update.message is not None:
        await update.message.reply_text("Бот работает 🟢")


async def _generate_and_send_image[T: ImageGenerationResult](
    message: Message,
    generate: Callable[[], T],
    *,
    image_name: str,
    filename_prefix: str,
    caption: Callable[[T], str],
) -> None:
    status_message = await message.reply_text(GENERATION_STATUS_TEXT)
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
        await status_message.edit_text(GENERATION_ERROR_TEXT)
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
        await status_message.edit_text(GENERATION_ERROR_TEXT)
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
    await _generate_and_send_image(
        update.message,
        service.generate,
        image_name="Lissajous",
        filename_prefix="lissajous",
        caption=lambda result: f"Кривая Лиссажу\nSeed: {result.seed}",
    )


async def spirograph(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate and send one spirograph image with its reproducible seed."""
    if update.message is None:
        return

    service: SpirographGenerationService = context.bot_data[SPIROGRAPH_SERVICE_KEY]
    await _generate_and_send_image(
        update.message,
        service.generate,
        image_name="Spirograph",
        filename_prefix="spirograph",
        caption=lambda result: (
            "Спирограф: "
            f"{'внутри' if result.parameters.pattern_type == 'inside' else 'снаружи'}"
            f"\nSeed: {result.seed}"
        ),
    )


async def fractal_tree(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate and send a fractal tree with its reproducible seed."""
    if update.message is None:
        return

    service: FractalTreeGenerationService = context.bot_data[FRACTAL_TREE_SERVICE_KEY]
    await _generate_and_send_image(
        update.message,
        service.generate,
        image_name="Fractal tree",
        filename_prefix="fractal-tree",
        caption=lambda result: f"Фрактальное дерево\nSeed: {result.seed}",
    )


async def handle_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    del update
    logger.error("Unhandled error while processing an update", exc_info=context.error)


COMMANDS = (
    CommandSpec("start", "Познакомиться с ботом", start),
    CommandSpec("lissajous", "Создать кривую Лиссажу", lissajous),
    CommandSpec("spirograph", "Создать узор спирографа", spirograph),
    CommandSpec("fractal_tree", "Создать фрактальное дерево", fractal_tree),
    CommandSpec("help", "Показать доступные команды", help_command),
    CommandSpec("ping", "Проверить работу бота", ping, is_public=False),
)

PUBLIC_COMMANDS = tuple(command for command in COMMANDS if command.is_public)
