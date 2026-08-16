import asyncio
import logging
from time import perf_counter

from telegram import InputFile, Update
from telegram.ext import ContextTypes

from geometron_bot.generation.service import LissajousGenerationService

logger = logging.getLogger(__name__)

LISSAJOUS_SERVICE_KEY = "lissajous_generation_service"


async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    if update.message is not None:
        await update.message.reply_text("Бот работает 🟢")


async def lissajous(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate and send a Lissajous image with its reproducible seed."""
    if update.message is None:
        return

    started_at = perf_counter()
    try:
        service: LissajousGenerationService = context.bot_data[
            LISSAJOUS_SERVICE_KEY
        ]
        result = await asyncio.to_thread(service.generate)
    except Exception as error:
        duration_ms = round((perf_counter() - started_at) * 1000)
        logger.exception(
            "Lissajous generation failed | duration_ms=%d | error_type=%s",
            duration_ms,
            type(error).__name__,
        )
        await update.message.reply_text(
            "Не удалось создать изображение. Попробуйте ещё раз."
        )
        return

    duration_ms = round((perf_counter() - started_at) * 1000)
    logger.info(
        "Lissajous image generated | seed=%d | duration_ms=%d",
        result.seed,
        duration_ms,
    )

    photo = InputFile(
        result.image,
        filename=f"lissajous-{result.seed}.png",
    )
    await update.message.reply_photo(
        photo=photo,
        caption=f"Кривая Лиссажу\nSeed: {result.seed}",
    )


async def handle_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    del update
    logger.error("Unhandled error while processing an update", exc_info=context.error)
