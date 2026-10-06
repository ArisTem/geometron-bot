import asyncio
import logging
import secrets
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
from geometron_bot.telegram_bot.generation_jobs import (
    GENERATION_JOBS_KEY,
    GenerationJobs,
    GenerationRejection,
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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    if update.message is not None:
        language = get_telegram_language(update)
        await update.message.reply_text(
            tr(language, "start.text", help_text=build_help_text(language))
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    if update.message is not None:
        await update.message.reply_text(build_help_text(get_telegram_language(update)))


async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    if update.message is not None:
        await update.message.reply_text(tr(get_telegram_language(update), "ping.text"))


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
    language = get_telegram_language(update)
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
    language = get_telegram_language(update)
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
    language = get_telegram_language(update)
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
    CommandSpec("ping", "command.ping", ping, is_public=False),
)

PUBLIC_COMMANDS = tuple(command for command in COMMANDS if command.is_public)
